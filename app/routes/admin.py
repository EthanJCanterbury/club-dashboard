"""
Admin routes blueprint for the Hack Club Dashboard.
Handles admin panel, user management, club management, order reviews, and system settings.
"""

from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from datetime import datetime, timezone
from extensions import db
from app.decorators.auth import login_required, admin_required, reviewer_required
from app.utils.auth_helpers import get_current_user
from app.utils.sanitization import sanitize_string
from app.models.user import User, Role, AuditLog
from app.models.club import Club, ClubMembership
from app.models.economy import ProjectSubmission, ClubTransaction
from app.models.system import SystemSettings
from app.services.airtable import AirtableService

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.route('/')
@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    """Admin dashboard"""
    from app.models.club_content import ClubPost, ClubAssignment

    current_user = get_current_user()

    # Get statistics
    total_users = User.query.count()
    total_clubs = Club.query.count()
    total_posts = ClubPost.query.count()
    total_assignments = ClubAssignment.query.count()
    pending_projects = ProjectSubmission.query.filter_by(approved_at=None).count()

    # Get total club balance
    total_club_balance = db.session.query(db.func.sum(Club.balance)).scalar() or 0

    # Get recent activity
    recent_users = User.query.order_by(User.created_at.desc()).limit(10).all()
    recent_clubs = Club.query.order_by(Club.created_at.desc()).limit(10).all()

    # Check permissions for each tab
    can_view_users = current_user.has_permission('users.view') or current_user.is_admin
    can_view_clubs = current_user.has_permission('clubs.view') or current_user.is_admin
    can_view_content = current_user.has_permission('content.view') or current_user.is_admin
    can_manage_roles = current_user.has_permission('system.manage_roles') or current_user.has_role('super-admin')
    can_manage_users = current_user.has_permission('users.edit') or current_user.is_admin
    can_access_api = current_user.has_permission('admin.manage_api_keys') or current_user.is_admin
    can_manage_settings = current_user.has_permission('system.manage_settings') or current_user.is_admin

    return render_template('admin_dashboard.html',
                         total_users=total_users,
                         total_clubs=total_clubs,
                         total_posts=total_posts,
                         total_assignments=total_assignments,
                         pending_projects=pending_projects,
                         total_club_balance=total_club_balance,
                         recent_users=recent_users,
                         recent_clubs=recent_clubs,
                         can_view_users=can_view_users,
                         can_view_clubs=can_view_clubs,
                         can_view_content=can_view_content,
                         can_manage_roles=can_manage_roles,
                         can_manage_users=can_manage_users,
                         can_access_api=can_access_api,
                         can_manage_settings=can_manage_settings)


@admin_bp.route('/users')
@login_required
@admin_required
def users():
    """User management - returns JSON for now"""
    page = request.args.get('page', 1, type=int)
    per_page = 50

    search = request.args.get('search', '')
    if search:
        search_term = f"%{search}%"
        users_query = User.query.filter(
            db.or_(
                User.username.ilike(search_term),
                User.email.ilike(search_term),
                User.first_name.ilike(search_term),
                User.last_name.ilike(search_term)
            )
        )
    else:
        users_query = User.query

    users_pagination = users_query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    # Return JSON for now since template doesn't exist
    return jsonify({
        'users': [{
            'id': u.id,
            'username': u.username,
            'email': u.email,
            'created_at': u.created_at.isoformat() if u.created_at else None
        } for u in users_pagination.items],
        'total': users_pagination.total,
        'page': page
    })


@admin_bp.route('/users/<int:user_id>')
@login_required
@admin_required
def user_detail(user_id):
    """View user details"""
    user = User.query.get_or_404(user_id)

    # Get user's clubs
    memberships = ClubMembership.query.filter_by(user_id=user_id).all()
    clubs = [m.club for m in memberships]

    # Get user's audit logs
    audit_logs = AuditLog.query.filter_by(user_id=user_id).order_by(
        AuditLog.timestamp.desc()
    ).limit(50).all()

    return render_template('admin_user_detail.html',
                         user=user,
                         clubs=clubs,
                         audit_logs=audit_logs)


@admin_bp.route('/users/<int:user_id>/suspend', methods=['POST'])
@login_required
@admin_required
def suspend_user(user_id):
    """Suspend a user"""
    user = User.query.get_or_404(user_id)

    if user.is_admin:
        flash('Cannot suspend admin users.', 'error')
        return redirect(url_for('admin.user_detail', user_id=user_id))

    reason = sanitize_string(request.form.get('reason', ''), max_length=500)

    user.is_suspended = True
    db.session.commit()

    # Create audit log
    from app.models.user import AuditLog
    audit_log = AuditLog(
        user_id=get_current_user().id,
        action_type='user_suspended',
        description=f'Suspended user: {user.username}',
        target_type='user',
        target_id=user_id,
        details={'reason': reason},
        severity='warning',
        category='admin'
    )
    db.session.add(audit_log)
    db.session.commit()

    flash(f'User {user.username} has been suspended.', 'success')
    return redirect(url_for('admin.user_detail', user_id=user_id))


@admin_bp.route('/users/<int:user_id>/unsuspend', methods=['POST'])
@login_required
@admin_required
def unsuspend_user(user_id):
    """Unsuspend a user"""
    user = User.query.get_or_404(user_id)

    user.is_suspended = False
    db.session.commit()

    # Create audit log
    audit_log = AuditLog(
        user_id=get_current_user().id,
        action_type='user_unsuspended',
        description=f'Unsuspended user: {user.username}',
        target_type='user',
        target_id=user_id,
        severity='info',
        category='admin'
    )
    db.session.add(audit_log)
    db.session.commit()

    flash(f'User {user.username} has been unsuspended.', 'success')
    return redirect(url_for('admin.user_detail', user_id=user_id))


@admin_bp.route('/clubs')
@login_required
@admin_required
def clubs():
    """Club management - returns JSON for now"""
    page = request.args.get('page', 1, type=int)
    per_page = 50

    search = request.args.get('search', '')
    if search:
        search_term = f"%{search}%"
        clubs_query = Club.query.filter(Club.name.ilike(search_term))
    else:
        clubs_query = Club.query

    clubs_pagination = clubs_query.order_by(Club.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    # Return JSON for now since template doesn't exist
    return jsonify({
        'clubs': [{
            'id': c.id,
            'name': c.name,
            'location': c.location,
            'tokens': c.tokens,
            'created_at': c.created_at.isoformat() if c.created_at else None
        } for c in clubs_pagination.items],
        'total': clubs_pagination.total,
        'page': page
    })


@admin_bp.route('/clubs/<int:club_id>')
@login_required
@admin_required
def club_detail(club_id):
    """View club details"""
    club = Club.query.get_or_404(club_id)

    # Get club members
    memberships = ClubMembership.query.filter_by(club_id=club_id).all()

    # Get club transactions
    transactions = ClubTransaction.query.filter_by(club_id=club_id).order_by(
        ClubTransaction.created_at.desc()
    ).limit(50).all()

    return render_template('admin_club_detail.html',
                         club=club,
                         memberships=memberships,
                         transactions=transactions)


@admin_bp.route('/projects/review')
@login_required
@reviewer_required
def review_projects():
    """Review pending project submissions"""
    pending_projects = ProjectSubmission.query.filter_by(
        approved_at=None
    ).order_by(ProjectSubmission.submitted_at.desc()).all()

    return render_template('admin_review_projects.html', projects=pending_projects)


@admin_bp.route('/projects/<int:project_id>/approve', methods=['POST'])
@login_required
@reviewer_required
def approve_project(project_id):
    """Approve a project submission"""
    project = ProjectSubmission.query.get_or_404(project_id)

    if project.approved_at:
        flash('Project already approved.', 'warning')
        return redirect(url_for('admin.review_projects'))

    project.approved_at = datetime.now(timezone.utc)
    project.approved_by = get_current_user().id

    # TODO: Award tokens to club for approved project

    db.session.commit()

    flash(f'Project "{project.project_name}" approved!', 'success')
    return redirect(url_for('admin.review_projects'))


@admin_bp.route('/orders/review')
@login_required
@admin_required
def review_orders():
    """Review pending shop orders"""
    # TODO: Implement order review system
    return render_template('admin_order_review.html', orders=[])


@admin_bp.route('/settings', methods=['GET', 'POST'])
@login_required
@admin_required
def settings():
    """System settings"""
    system_settings = SystemSettings.query.first()
    if not system_settings:
        system_settings = SystemSettings()
        db.session.add(system_settings)
        db.session.commit()

    if request.method == 'POST':
        # Update settings
        system_settings.maintenance_mode = request.form.get('maintenance_mode') == 'on'
        system_settings.economy_enabled = request.form.get('economy_enabled') == 'on'
        system_settings.registration_enabled = request.form.get('registration_enabled') == 'on'

        announcement = sanitize_string(request.form.get('announcement', ''), max_length=500)
        system_settings.announcement = announcement if announcement else None

        db.session.commit()

        flash('Settings updated successfully.', 'success')
        return redirect(url_for('admin.settings'))

    return render_template('admin_settings.html', settings=system_settings)


@admin_bp.route('/stats')
@login_required
@admin_required
def stats():
    """System statistics"""
    # Get various statistics
    stats_data = {
        'total_users': User.query.count(),
        'active_users': User.query.filter_by(is_suspended=False).count(),
        'suspended_users': User.query.filter_by(is_suspended=True).count(),
        'total_clubs': Club.query.count(),
        'total_tokens_distributed': db.session.query(
            db.func.sum(ClubTransaction.amount)
        ).filter(ClubTransaction.amount > 0).scalar() or 0,
        'pending_projects': ProjectSubmission.query.filter_by(approved_at=None).count(),
        'approved_projects': ProjectSubmission.query.filter(
            ProjectSubmission.approved_at.isnot(None)
        ).count(),
    }

    return render_template('admin_stats.html', stats=stats_data)


@admin_bp.route('/pizza-grants')
@login_required
@admin_required
def pizza_grants():
    """Pizza grant management"""
    # Get grants from Airtable
    try:
        grants = AirtableService.get_pizza_grants()
    except Exception as e:
        flash(f'Error loading grants: {str(e)}', 'error')
        grants = []

    return render_template('admin_pizza_grants.html', grants=grants)


@admin_bp.route('/activity')
@login_required
@admin_required
def activity():
    """Recent activity log"""
    page = request.args.get('page', 1, type=int)
    per_page = 100

    # Get recent audit logs
    logs_pagination = AuditLog.query.order_by(
        AuditLog.timestamp.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)

    return render_template('admin_activity.html',
                         logs=logs_pagination.items,
                         pagination=logs_pagination)
