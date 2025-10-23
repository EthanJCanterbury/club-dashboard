"""
API routes blueprint for the Hack Club Dashboard.
Handles public API endpoints, admin API, and mobile app endpoints.
"""

from flask import Blueprint, jsonify, request
from extensions import db, limiter
from app.decorators.auth import api_key_required, oauth_required, admin_required, login_required
from app.utils.auth_helpers import get_current_user
from app.models.user import User
from app.models.club import Club, ClubMembership
from app.models.club_content import ClubPost, ClubAssignment, ClubMeeting, ClubProject
from app.models.system import SystemSettings

api_bp = Blueprint('api', __name__, url_prefix='/api')


@api_bp.route('/docs')
def api_documentation():
    """API documentation page"""
    from flask import render_template
    return render_template('api_docs.html')


# ============================================================================
# Public API Endpoints (require API key or OAuth)
# ============================================================================

@api_bp.route('/user', methods=['GET'])
@oauth_required(scopes=['user:read'])
def get_user():
    """Get current user information (OAuth)"""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Not authenticated'}), 401

    return jsonify({
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'created_at': user.created_at.isoformat() if user.created_at else None
    })


@api_bp.route('/user/clubs', methods=['GET'])
@oauth_required(scopes=['clubs:read'])
def get_user_clubs():
    """Get user's clubs (OAuth)"""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Not authenticated'}), 401

    memberships = ClubMembership.query.filter_by(user_id=user.id).all()

    clubs_data = []
    for membership in memberships:
        club = membership.club
        clubs_data.append({
            'id': club.id,
            'name': club.name,
            'description': club.description,
            'tokens': club.tokens,
            'is_leader': membership.is_leader,
            'is_co_leader': membership.is_co_leader,
            'joined_at': membership.joined_at.isoformat() if membership.joined_at else None
        })

    return jsonify({
        'clubs': clubs_data,
        'total': len(clubs_data)
    })


@api_bp.route('/user/assignments', methods=['GET'])
@oauth_required(scopes=['assignments:read'])
def get_user_assignments():
    """Get user's club assignments (OAuth)"""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Not authenticated'}), 401

    # Get all clubs user is a member of
    memberships = ClubMembership.query.filter_by(user_id=user.id).all()
    club_ids = [m.club_id for m in memberships]

    # Get assignments from those clubs
    assignments = ClubAssignment.query.filter(
        ClubAssignment.club_id.in_(club_ids)
    ).order_by(ClubAssignment.due_date.desc()).all()

    assignments_data = []
    for assignment in assignments:
        assignments_data.append({
            'id': assignment.id,
            'club_id': assignment.club_id,
            'club_name': assignment.club.name,
            'title': assignment.title,
            'description': assignment.description,
            'due_date': assignment.due_date.isoformat() if assignment.due_date else None,
            'created_at': assignment.created_at.isoformat() if assignment.created_at else None
        })

    return jsonify({
        'assignments': assignments_data,
        'total': len(assignments_data)
    })


@api_bp.route('/user/meetings', methods=['GET'])
@oauth_required(scopes=['meetings:read'])
def get_user_meetings():
    """Get user's club meetings (OAuth)"""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Not authenticated'}), 401

    # Get all clubs user is a member of
    memberships = ClubMembership.query.filter_by(user_id=user.id).all()
    club_ids = [m.club_id for m in memberships]

    # Get meetings from those clubs
    meetings = ClubMeeting.query.filter(
        ClubMeeting.club_id.in_(club_ids)
    ).order_by(ClubMeeting.meeting_date.desc()).all()

    meetings_data = []
    for meeting in meetings:
        meetings_data.append({
            'id': meeting.id,
            'club_id': meeting.club_id,
            'club_name': meeting.club.name,
            'title': meeting.title,
            'description': meeting.description,
            'meeting_date': meeting.meeting_date.isoformat() if meeting.meeting_date else None,
            'location': meeting.location,
            'created_at': meeting.created_at.isoformat() if meeting.created_at else None
        })

    return jsonify({
        'meetings': meetings_data,
        'total': len(meetings_data)
    })


@api_bp.route('/user/projects', methods=['GET'])
@oauth_required(scopes=['projects:read'])
def get_user_projects():
    """Get user's club projects (OAuth)"""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Not authenticated'}), 401

    # Get all clubs user is a member of
    memberships = ClubMembership.query.filter_by(user_id=user.id).all()
    club_ids = [m.club_id for m in memberships]

    # Get projects from those clubs
    projects = ClubProject.query.filter(
        ClubProject.club_id.in_(club_ids)
    ).order_by(ClubProject.created_at.desc()).all()

    projects_data = []
    for project in projects:
        projects_data.append({
            'id': project.id,
            'club_id': project.club_id,
            'club_name': project.club.name,
            'name': project.name,
            'description': project.description,
            'url': project.url,
            'created_at': project.created_at.isoformat() if project.created_at else None
        })

    return jsonify({
        'projects': projects_data,
        'total': len(projects_data)
    })


# ============================================================================
# Admin API Endpoints
# ============================================================================

@api_bp.route('/admin/users', methods=['GET'])
@login_required
@admin_required
@limiter.limit("100 per minute")
def admin_get_users():
    """Get all users (admin only)"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    per_page = min(per_page, 100)  # Max 100 per page

    users_pagination = User.query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    users_data = []
    for user in users_pagination.items:
        users_data.append({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_admin': user.is_admin,
            'is_suspended': user.is_suspended,
            'created_at': user.created_at.isoformat() if user.created_at else None
        })

    return jsonify({
        'users': users_data,
        'total': users_pagination.total,
        'page': page,
        'per_page': per_page,
        'pages': users_pagination.pages
    })


@api_bp.route('/admin/clubs', methods=['GET'])
@login_required
@admin_required
@limiter.limit("100 per minute")
def admin_get_clubs():
    """Get all clubs (admin only)"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    per_page = min(per_page, 100)

    clubs_pagination = Club.query.order_by(Club.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    clubs_data = []
    for club in clubs_pagination.items:
        clubs_data.append({
            'id': club.id,
            'name': club.name,
            'description': club.description,
            'tokens': club.tokens,
            'balance': club.balance,
            'created_at': club.created_at.isoformat() if club.created_at else None
        })

    return jsonify({
        'clubs': clubs_data,
        'total': clubs_pagination.total,
        'page': page,
        'per_page': per_page,
        'pages': clubs_pagination.pages
    })


@api_bp.route('/admin/stats', methods=['GET'])
@login_required
@admin_required
def admin_get_stats():
    """Get system statistics (admin only)"""
    from app.models.economy import ClubTransaction, ProjectSubmission

    stats = {
        'users': {
            'total': User.query.count(),
            'active': User.query.filter_by(is_suspended=False).count(),
            'suspended': User.query.filter_by(is_suspended=True).count(),
            'admins': User.query.filter_by(is_admin=True).count()
        },
        'clubs': {
            'total': Club.query.count(),
            'total_tokens': db.session.query(db.func.sum(Club.tokens)).scalar() or 0
        },
        'projects': {
            'pending': ProjectSubmission.query.filter_by(approved_at=None).count(),
            'approved': ProjectSubmission.query.filter(
                ProjectSubmission.approved_at.isnot(None)
            ).count()
        },
        'transactions': {
            'total': ClubTransaction.query.count(),
            'total_credits': db.session.query(
                db.func.sum(ClubTransaction.amount)
            ).filter(ClubTransaction.amount > 0).scalar() or 0
        }
    }

    return jsonify(stats)


@api_bp.route('/admin/settings', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_settings():
    """Get/update system settings (admin only)"""
    settings = SystemSettings.query.first()
    if not settings:
        settings = SystemSettings()
        db.session.add(settings)
        db.session.commit()

    if request.method == 'GET':
        return jsonify({
            'maintenance_mode': settings.maintenance_mode,
            'economy_enabled': settings.economy_enabled,
            'registration_enabled': settings.registration_enabled,
            'announcement': settings.announcement
        })

    elif request.method == 'POST':
        data = request.get_json()

        if 'maintenance_mode' in data:
            settings.maintenance_mode = bool(data['maintenance_mode'])
        if 'economy_enabled' in data:
            settings.economy_enabled = bool(data['economy_enabled'])
        if 'registration_enabled' in data:
            settings.registration_enabled = bool(data['registration_enabled'])
        if 'announcement' in data:
            settings.announcement = data['announcement']

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Settings updated'
        })


@api_bp.route('/admin/activity', methods=['GET'])
@login_required
@admin_required
@limiter.limit("100 per minute")
def admin_get_activity():
    """Get recent activity (admin only)"""
    from app.models.user import AuditLog

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    per_page = min(per_page, 100)

    logs_pagination = AuditLog.query.order_by(
        AuditLog.timestamp.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)

    logs_data = []
    for log in logs_pagination.items:
        logs_data.append({
            'id': log.id,
            'user_id': log.user_id,
            'action_type': log.action_type,
            'description': log.description,
            'target_type': log.target_type,
            'target_id': log.target_id,
            'severity': log.severity,
            'category': log.category,
            'timestamp': log.timestamp.isoformat() if log.timestamp else None
        })

    return jsonify({
        'logs': logs_data,
        'total': logs_pagination.total,
        'page': page,
        'per_page': per_page,
        'pages': logs_pagination.pages
    })
