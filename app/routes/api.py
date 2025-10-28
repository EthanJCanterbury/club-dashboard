"""
API routes blueprint for the Hack Club Dashboard.
Handles public API endpoints, admin API, and mobile app endpoints.
"""

import html
from flask import Blueprint, jsonify, request, current_app
from extensions import db, limiter
from app.decorators.auth import api_key_required, oauth_required, admin_required, login_required
from app.utils.auth_helpers import get_current_user, is_authenticated
from app.utils.club_helpers import is_user_co_leader
from app.utils.sanitization import sanitize_string
from app.utils.formatting import markdown_to_html
from app.utils.security import validate_input_with_security
from app.utils.economy_helpers import create_club_transaction, update_quest_progress
from app.models.user import User, create_audit_log
from app.models.club import Club, ClubMembership
from app.models.club_content import ClubPost, ClubAssignment, ClubMeeting, ClubProject
from app.models.gallery import GalleryPost
from app.models.economy import ClubTransaction, ClubQuestProgress
from app.models.system import SystemSettings
from app.services.airtable import airtable_service

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
            'is_leader': user.id == club.leader_id,
            'is_co_leader': user.id == club.co_leader_id,
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
        # Count clubs led
        from app.models.club import Club
        clubs_led = Club.query.filter(
            (Club.leader_id == user.id) | (Club.co_leader_id == user.id)
        ).count()

        # Count clubs joined
        from app.models.club import ClubMembership
        clubs_joined = ClubMembership.query.filter_by(user_id=user.id).count()

        users_data.append({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_admin': user.is_admin,
            'is_suspended': user.is_suspended,
            'clubs_led': clubs_led,
            'clubs_joined': clubs_joined,
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
        # Get leader info
        leader_username = club.leader.username if club.leader else 'Unknown'
        leader_email = club.leader.email if club.leader else 'Unknown'

        # Count members
        from app.models.club import ClubMembership
        member_count = ClubMembership.query.filter_by(club_id=club.id).count()

        clubs_data.append({
            'id': club.id,
            'name': club.name,
            'description': club.description,
            'leader': leader_username,
            'leader_email': leader_email,
            'member_count': member_count,
            'location': club.location,
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
    if request.method == 'GET':
        return jsonify({
            'maintenance_mode': SystemSettings.is_maintenance_mode(),
            'economy_enabled': SystemSettings.is_economy_enabled(),
            'registration_enabled': SystemSettings.is_user_registration_enabled(),
            'mobile_enabled': SystemSettings.is_mobile_enabled(),
            'heidi_enabled': SystemSettings.is_heidi_enabled(),
            'club_creation_enabled': SystemSettings.is_club_creation_enabled(),
            'announcement': SystemSettings.get_setting('announcement', '')
        })

    elif request.method == 'POST':
        data = request.get_json()
        current_user = get_current_user()

        if 'maintenance_mode' in data:
            SystemSettings.set_setting('maintenance_mode', str(data['maintenance_mode']).lower(), current_user.id)
        if 'economy_enabled' in data:
            SystemSettings.set_setting('economy_enabled', str(data['economy_enabled']).lower(), current_user.id)
        if 'registration_enabled' in data:
            SystemSettings.set_setting('user_registration_enabled', str(data['registration_enabled']).lower(), current_user.id)
        if 'mobile_enabled' in data:
            SystemSettings.set_setting('mobile_enabled', str(data['mobile_enabled']).lower(), current_user.id)
        if 'heidi_enabled' in data:
            SystemSettings.set_setting('heidi_enabled', str(data['heidi_enabled']).lower(), current_user.id)
        if 'club_creation_enabled' in data:
            SystemSettings.set_setting('club_creation_enabled', str(data['club_creation_enabled']).lower(), current_user.id)
        if 'announcement' in data:
            SystemSettings.set_setting('announcement', data['announcement'], current_user.id)

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
            'category': log.action_category,
            'timestamp': log.timestamp.isoformat() if log.timestamp else None
        })

    return jsonify({
        'logs': logs_data,
        'total': logs_pagination.total,
        'page': page,
        'per_page': per_page,
        'pages': logs_pagination.pages
    })


@api_bp.route('/admin/rbac/roles', methods=['GET'])
@login_required
@admin_required
def admin_get_roles():
    """Get all roles (admin only)"""
    from app.models.user import Role
    roles = Role.query.all()
    roles_data = []
    for role in roles:
        roles_data.append({
            'id': role.id,
            'name': role.name,
            'display_name': role.display_name,
            'description': role.description,
            'is_system_role': role.is_system_role,
            'permissions': [p.name for p in role.permissions.all()],
            'user_count': len(role.users)
        })
    return jsonify({'roles': roles_data})


@api_bp.route('/admin/rbac/permissions', methods=['GET'])
@login_required
@admin_required
def admin_get_permissions():
    """Get all permissions (admin only)"""
    from app.models.user import Permission
    permissions = Permission.query.all()

    # Group by category
    permissions_by_category = {}
    for perm in permissions:
        if perm.category not in permissions_by_category:
            permissions_by_category[perm.category] = []
        permissions_by_category[perm.category].append({
            'id': perm.id,
            'name': perm.name,
            'display_name': perm.display_name,
            'description': perm.description,
            'category': perm.category
        })

    return jsonify({'permissions': permissions_by_category})


@api_bp.route('/admin/rbac/users/<int:user_id>/roles', methods=['GET'])
@login_required
@admin_required
def admin_get_user_roles(user_id):
    """Get a specific user's roles and permissions (admin only)"""
    from app.models.user import User, UserRole

    user = User.query.get_or_404(user_id)

    # Get user's roles
    user_roles = UserRole.query.filter_by(user_id=user_id).all()
    roles_data = []
    permissions_data = []

    for user_role in user_roles:
        role = user_role.role
        roles_data.append({
            'id': role.id,
            'name': role.name,
            'display_name': role.display_name,
            'description': role.description
        })

        # Collect all permissions from this role
        for perm in role.permissions.all():
            if perm.name not in [p['name'] for p in permissions_data]:
                permissions_data.append({
                    'id': perm.id,
                    'name': perm.name,
                    'display_name': perm.display_name,
                    'category': perm.category
                })

    return jsonify({
        'roles': roles_data,
        'permissions': permissions_data,
        'is_root': user.is_root if hasattr(user, 'is_root') else False
    })


@api_bp.route('/admin/apikeys', methods=['GET'])
@login_required
@admin_required
def admin_get_api_keys():
    """Get all API keys (admin only)"""
    from app.models.auth import APIKey

    keys = APIKey.query.order_by(APIKey.created_at.desc()).all()
    keys_data = []
    for key in keys:
        keys_data.append({
            'id': key.id,
            'name': key.name,
            'key_preview': key.key[:8] + '...' if key.key else '',
            'user_id': key.user_id,
            'username': key.user.username if key.user else None,
            'scopes': key.get_scopes(),
            'is_active': key.is_active,
            'created_at': key.created_at.isoformat() if key.created_at else None,
            'last_used_at': key.last_used_at.isoformat() if key.last_used_at else None
        })

    return jsonify({'api_keys': keys_data})


@api_bp.route('/admin/oauthapps', methods=['GET'])
@login_required
@admin_required
def admin_get_oauth_apps():
    """Get all OAuth applications (admin only)"""
    from app.models.auth import OAuthApplication

    apps = OAuthApplication.query.order_by(OAuthApplication.created_at.desc()).all()
    apps_data = []
    for app in apps:
        apps_data.append({
            'id': app.id,
            'name': app.name,
            'client_id': app.client_id,
            'owner_id': app.user_id,
            'owner_username': app.user.username if app.user else None,
            'redirect_uris': app.get_redirect_uris(),
            'scopes': app.get_scopes(),
            'is_active': app.is_active,
            'created_at': app.created_at.isoformat() if app.created_at else None
        })

    return jsonify({'oauth_apps': apps_data})


@api_bp.route('/admin/audit-logs', methods=['GET'])
@login_required
@admin_required
def admin_get_audit_logs():
    """Get audit logs (admin only)"""
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
            'username': log.user.username if log.user else 'System',
            'action_type': log.action_type,
            'description': log.description,
            'target_type': log.target_type,
            'target_id': log.target_id,
            'severity': log.severity,
            'action_category': log.action_category,
            'ip_address': log.ip_address,
            'timestamp': log.timestamp.isoformat() if log.timestamp else None
        })

    return jsonify({
        'logs': logs_data,
        'total': logs_pagination.total,
        'page': page,
        'per_page': per_page,
        'pages': logs_pagination.pages
    })


# ============================================================================
# Club Content API Endpoints
# ============================================================================

@api_bp.route('/clubs/<int:club_id>/posts', methods=['GET', 'POST'])
@login_required
@limiter.limit("500 per hour")
def club_posts(club_id):
    """Get or create club posts"""
    current_user = get_current_user()
    club = Club.query.get_or_404(club_id)

    is_leader = club.leader_id == current_user.id
    is_co_leader = is_user_co_leader(club, current_user)
    is_member = ClubMembership.query.filter_by(club_id=club_id, user_id=current_user.id).first()
    is_admin_access = request.args.get('admin') == 'true' and current_user.is_admin

    if not is_leader and not is_co_leader and not is_member and not is_admin_access:
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Give admins leader privileges
    if is_admin_access:
        is_leader = True

    if request.method == 'POST':
        # Only leaders and co-leaders can create posts
        if not is_leader and not is_co_leader:
            return jsonify({'error': 'Only club leaders and co-leaders can create posts'}), 403
            
        data = request.get_json()
        content = data.get('content')

        if not content:
            return jsonify({'error': 'Content is required'}), 400

        # Security validation with auto-suspend
        valid, result = validate_input_with_security(content, "club_post", current_user, max_length=5000,
                                                     app=current_app)
        if not valid:
            return jsonify({'error': result}), 403

        # For leaders, content is treated as markdown and converted to HTML
        if is_leader or is_co_leader:
            # Store raw markdown content (basic sanitization only)
            markdown_content = sanitize_string(result, max_length=5000, allow_html=False)
            # Convert markdown to safe HTML
            html_content = markdown_to_html(markdown_content)
        else:
            # For regular members, treat as plain text
            markdown_content = sanitize_string(result, max_length=5000, allow_html=False)
            html_content = html.escape(markdown_content).replace('\n', '<br>')

        if not markdown_content.strip():
            return jsonify({'error': 'Content cannot be empty after sanitization'}), 400

        post = ClubPost(
            club_id=club_id,
            user_id=current_user.id,
            content=markdown_content,
            content_html=html_content
        )
        db.session.add(post)
        db.session.commit()

        # Create audit log for post creation
        create_audit_log(
            action_type='create_post',
            description=f"User {current_user.username} created a post in {club.name}",
            user=current_user,
            target_type='club',
            target_id=club_id,
            details={
                'club_name': club.name,
                'post_id': post.id,
                'content_length': len(markdown_content)
            },
            category='club'
        )

        return jsonify({'message': 'Post created successfully'})

    # GET request
    posts = ClubPost.query.filter_by(club_id=club_id).order_by(ClubPost.created_at.desc()).all()
    posts_data = []
    
    for post in posts:
        try:
            # Handle content_html field safely (might be NULL for some posts)
            content_html = post.content_html
            if not content_html:
                # For posts without HTML content, escape and convert newlines
                content_html = html.escape(post.content).replace('\n', '<br>')
            
            post_data = {
                'id': post.id,
                'content': post.content,  # Raw markdown content
                'content_html': content_html,  # HTML content for display
                'created_at': post.created_at.isoformat(),
                'user': {
                    'id': post.user.id,
                    'username': post.user.username
                }
            }
            posts_data.append(post_data)
        except Exception as e:
            current_app.logger.error(f"Error processing post {post.id}: {e}")
            continue
    
    return jsonify({'posts': posts_data})


@api_bp.route('/clubs/<int:club_id>/posts/<int:post_id>', methods=['DELETE'])
@login_required
@limiter.limit("100 per hour")
def delete_club_post(club_id, post_id):
    """Delete a club post"""
    current_user = get_current_user()
    club = Club.query.get_or_404(club_id)
    post = ClubPost.query.get_or_404(post_id)

    # Verify post belongs to this club
    if post.club_id != club_id:
        return jsonify({'error': 'Post not found in this club'}), 404

    is_leader = club.leader_id == current_user.id
    is_co_leader = is_user_co_leader(club, current_user)
    is_post_author = post.user_id == current_user.id

    # Only leaders, co-leaders, or post authors can delete
    if not is_leader and not is_co_leader and not is_post_author and not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403

    db.session.delete(post)
    db.session.commit()

    create_audit_log(
        action_type='delete_post',
        description=f"User {current_user.username} deleted a post in {club.name}",
        user=current_user,
        target_type='club',
        target_id=club_id,
        category='club'
    )

    return jsonify({'message': 'Post deleted successfully'})


@api_bp.route('/clubs/<int:club_id>/assignments', methods=['GET', 'POST'])
@login_required
@limiter.limit("500 per hour")
def club_assignments(club_id):
    """Get or create club assignments"""
    current_user = get_current_user()
    club = Club.query.get_or_404(club_id)

    is_leader = club.leader_id == current_user.id
    is_co_leader = is_user_co_leader(club, current_user)
    is_member = ClubMembership.query.filter_by(club_id=club_id, user_id=current_user.id).first()

    if not is_leader and not is_co_leader and not is_member:
        return jsonify({'error': 'Unauthorized'}), 403

    if request.method == 'POST':
        # Only leaders and co-leaders can create assignments
        if not is_leader and not is_co_leader:
            return jsonify({'error': 'Only club leaders can create assignments'}), 403

        data = request.get_json()
        title = data.get('title')
        description = data.get('description')
        due_date = data.get('due_date')

        if not title or not description:
            return jsonify({'error': 'Title and description are required'}), 400

        # Validate inputs
        valid, result = validate_input_with_security(title, "assignment_title", current_user, max_length=200, app=current_app)
        if not valid:
            return jsonify({'error': result}), 403
        title = result

        valid, result = validate_input_with_security(description, "assignment_description", current_user, max_length=2000, app=current_app)
        if not valid:
            return jsonify({'error': result}), 403
        description = result

        assignment = ClubAssignment(
            club_id=club_id,
            title=title,
            description=description,
            due_date=due_date
        )
        db.session.add(assignment)
        db.session.commit()

        create_audit_log(
            action_type='create_assignment',
            description=f"User {current_user.username} created assignment '{title}' in {club.name}",
            user=current_user,
            target_type='club',
            target_id=club_id,
            category='club'
        )

        return jsonify({'message': 'Assignment created successfully', 'assignment_id': assignment.id})

    # GET request
    assignments = ClubAssignment.query.filter_by(club_id=club_id).order_by(ClubAssignment.due_date.desc()).all()
    assignments_data = [{
        'id': a.id,
        'title': a.title,
        'description': a.description,
        'due_date': a.due_date.isoformat() if a.due_date else None,
        'created_at': a.created_at.isoformat() if a.created_at else None
    } for a in assignments]

    return jsonify({'assignments': assignments_data})


@api_bp.route('/clubs/<int:club_id>/assignments/<int:assignment_id>', methods=['DELETE'])
@login_required
@limiter.limit("100 per hour")
def delete_club_assignment(club_id, assignment_id):
    """Delete a club assignment"""
    current_user = get_current_user()
    club = Club.query.get_or_404(club_id)
    assignment = ClubAssignment.query.get_or_404(assignment_id)

    if assignment.club_id != club_id:
        return jsonify({'error': 'Assignment not found in this club'}), 404

    is_leader = club.leader_id == current_user.id
    is_co_leader = is_user_co_leader(club, current_user)

    if not is_leader and not is_co_leader and not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403

    db.session.delete(assignment)
    db.session.commit()

    return jsonify({'message': 'Assignment deleted successfully'})


@api_bp.route('/clubs/<int:club_id>/meetings', methods=['GET', 'POST'])
@login_required
@limiter.limit("500 per hour")
def club_meetings(club_id):
    """Get or create club meetings"""
    current_user = get_current_user()
    club = Club.query.get_or_404(club_id)

    is_leader = club.leader_id == current_user.id
    is_co_leader = is_user_co_leader(club, current_user)
    is_member = ClubMembership.query.filter_by(club_id=club_id, user_id=current_user.id).first()

    if not is_leader and not is_co_leader and not is_member:
        return jsonify({'error': 'Unauthorized'}), 403

    if request.method == 'POST':
        # Only leaders and co-leaders can create meetings
        if not is_leader and not is_co_leader:
            return jsonify({'error': 'Only club leaders can create meetings'}), 403

        data = request.get_json()
        title = data.get('title')
        description = data.get('description')
        meeting_date = data.get('meeting_date')
        location = data.get('location')

        if not title:
            return jsonify({'error': 'Title is required'}), 400

        # Validate inputs
        valid, result = validate_input_with_security(title, "meeting_title", current_user, max_length=200, app=current_app)
        if not valid:
            return jsonify({'error': result}), 403
        title = result

        if description:
            valid, result = validate_input_with_security(description, "meeting_description", current_user, max_length=2000, app=current_app)
            if not valid:
                return jsonify({'error': result}), 403
            description = result

        meeting = ClubMeeting(
            club_id=club_id,
            title=title,
            description=description,
            meeting_date=meeting_date,
            location=location
        )
        db.session.add(meeting)
        db.session.commit()

        create_audit_log(
            action_type='create_meeting',
            description=f"User {current_user.username} created meeting '{title}' in {club.name}",
            user=current_user,
            target_type='club',
            target_id=club_id,
            category='club'
        )

        return jsonify({'message': 'Meeting created successfully', 'meeting_id': meeting.id})

    # GET request
    meetings = ClubMeeting.query.filter_by(club_id=club_id).order_by(ClubMeeting.meeting_date.desc()).all()
    meetings_data = [{
        'id': m.id,
        'title': m.title,
        'description': m.description,
        'meeting_date': m.meeting_date.isoformat() if m.meeting_date else None,
        'location': m.location,
        'created_at': m.created_at.isoformat() if m.created_at else None
    } for m in meetings]

    return jsonify({'meetings': meetings_data})


@api_bp.route('/clubs/<int:club_id>/meetings/<int:meeting_id>', methods=['DELETE'])
@login_required
@limiter.limit("100 per hour")
def delete_club_meeting(club_id, meeting_id):
    """Delete a club meeting"""
    current_user = get_current_user()
    club = Club.query.get_or_404(club_id)
    meeting = ClubMeeting.query.get_or_404(meeting_id)

    if meeting.club_id != club_id:
        return jsonify({'error': 'Meeting not found in this club'}), 404

    is_leader = club.leader_id == current_user.id
    is_co_leader = is_user_co_leader(club, current_user)

    if not is_leader and not is_co_leader and not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403

    db.session.delete(meeting)
    db.session.commit()

    return jsonify({'message': 'Meeting deleted successfully'})


@api_bp.route('/clubs/<int:club_id>/transactions', methods=['GET'])
@login_required
@limiter.limit("500 per hour")
def club_transactions(club_id):
    """Get club transaction history"""
    current_user = get_current_user()
    club = Club.query.get_or_404(club_id)

    is_leader = club.leader_id == current_user.id
    is_co_leader = is_user_co_leader(club, current_user)
    is_member = ClubMembership.query.filter_by(club_id=club_id, user_id=current_user.id).first()

    if not is_leader and not is_co_leader and not is_member and not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    per_page = min(per_page, 100)

    transactions_pagination = ClubTransaction.query.filter_by(club_id=club_id).order_by(
        ClubTransaction.created_at.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)

    transactions_data = []
    for t in transactions_pagination.items:
        transactions_data.append({
            'id': t.id,
            'transaction_type': t.transaction_type,
            'amount': t.amount,
            'description': t.description,
            'created_at': t.created_at.isoformat() if t.created_at else None,
            'reference_type': t.reference_type,
            'reference_id': t.reference_id
        })

    return jsonify({
        'transactions': transactions_data,
        'total': transactions_pagination.total,
        'page': page,
        'per_page': per_page,
        'pages': transactions_pagination.pages
    })


@api_bp.route('/club/<int:club_id>/quests', methods=['GET'])
@login_required
@limiter.limit("500 per hour")
def club_quests(club_id):
    """Get club quests and progress"""
    current_user = get_current_user()
    club = Club.query.get_or_404(club_id)

    is_member = ClubMembership.query.filter_by(club_id=club_id, user_id=current_user.id).first()
    if not is_member and not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403

    quests = ClubQuestProgress.query.filter_by(club_id=club_id).all()
    quests_data = [{
        'id': q.id,
        'quest_type': q.quest.quest_type if q.quest else 'unknown',
        'quest_name': q.quest.name if q.quest else 'Unknown Quest',
        'quest_description': q.quest.description if q.quest else '',
        'progress': q.progress,
        'goal': q.target,
        'reward': q.quest.reward_tokens if q.quest else 0,
        'completed': q.completed,
        'reward_claimed': q.reward_claimed,
        'completed_at': q.completed_at.isoformat() if q.completed_at else None
    } for q in quests]

    return jsonify({'quests': quests_data})


# ============================================================================
# Gallery API Endpoints
# ============================================================================

@api_bp.route('/gallery/posts', methods=['GET', 'POST'])
@limiter.limit("100 per hour")
def gallery_posts():
    """Get or create gallery posts"""
    if request.method == 'POST':
        if not is_authenticated():
            return jsonify({'error': 'Authentication required'}), 401
        
        current_user = get_current_user()
        data = request.get_json()
        
        club_id = data.get('club_id')
        title = data.get('title')
        description = data.get('description')
        images = data.get('images', [])
        custom_club_name = data.get('custom_club_name')  # Admin override for club name
        
        if not club_id or not title or not description:
            return jsonify({'error': 'Club ID, title, and description are required'}), 400
        
        # Limit to 50 images max
        if len(images) > 50:
            images = images[:50]
        
        # Verify user is leader or co-leader of the club
        club = Club.query.get_or_404(club_id)
        is_leader = club.leader_id == current_user.id
        is_co_leader = is_user_co_leader(club, current_user)
        
        if not is_leader and not is_co_leader:
            return jsonify({'error': 'Only club leaders can create gallery posts'}), 403
        
        # Security validation
        valid, result = validate_input_with_security(title, "gallery_title", current_user, max_length=200, app=current_app)
        if not valid:
            return jsonify({'error': result}), 403
        title = result
        
        valid, result = validate_input_with_security(description, "gallery_description", current_user, max_length=2000, app=current_app)
        if not valid:
            return jsonify({'error': result}), 403
        description = result
        
        # Create gallery post
        post = GalleryPost(
            club_id=club_id,
            user_id=current_user.id,
            title=title,
            description=description
        )
        post.set_images(images)
        
        # Update quest progress for gallery post
        update_quest_progress(club_id, 'gallery_post', 1)
        
        # Admin can override club name display
        if current_user.is_admin and custom_club_name:
            valid, result = validate_input_with_security(custom_club_name, "custom_club_name", current_user, max_length=100, app=current_app)
            if not valid:
                return jsonify({'error': result}), 403
            # Store custom club name in a new field or use description field with a prefix
            post.description = f"[CUSTOM_CLUB:{result}] {description}"
        
        db.session.add(post)
        db.session.commit()
        
        current_app.logger.info(f"Gallery post created: ID={post.id}, title='{title}', club_id={club_id}, images={len(images)}")
        
        # Log gallery post to Airtable
        try:
            airtable_success = airtable_service.log_gallery_post(
                post_title=title,
                description=description,
                photos=images,
                club_name=club.name,
                author_username=current_user.username
            )
            if airtable_success:
                current_app.logger.info(f"Gallery post {post.id} successfully logged to Airtable")
            else:
                current_app.logger.warning(f"Failed to log gallery post {post.id} to Airtable")
        except Exception as e:
            current_app.logger.error(f"Exception logging gallery post {post.id} to Airtable: {str(e)}")
        
        # Create audit log for gallery post creation
        create_audit_log(
            action_type='gallery_post_create',
            description=f"User {current_user.username} created gallery post '{title}' for club '{club.name}'",
            user=current_user,
            target_type='club',
            target_id=str(club_id),
            details={
                'post_title': title,
                'club_name': club.name,
                'image_count': len(images),
                'custom_club_name': custom_club_name if current_user.is_admin and custom_club_name else None
            },
            severity='info',
            admin_action=current_user.is_admin and custom_club_name,
            category='gallery'
        )
        
        return jsonify({'message': 'Gallery post created successfully', 'post_id': post.id})
    
    # GET request - return all gallery posts
    try:
        posts = GalleryPost.query.order_by(GalleryPost.created_at.desc()).all()
        posts_data = []
        
        current_app.logger.info(f"Retrieved {len(posts)} gallery posts from database")
        
        for post in posts:
            try:
                # Get club and user info safely
                club = Club.query.get(post.club_id)
                user = User.query.get(post.user_id)
                
                if not club or not user:
                    current_app.logger.warning(f"Skipping post {post.id}: missing club ({club}) or user ({user})")
                    continue
                
                # Check for admin custom club name override
                display_club_name = club.name
                display_description = post.description
                
                if post.description.startswith('[CUSTOM_CLUB:'):
                    # Extract custom club name and actual description
                    try:
                        end_idx = post.description.find('] ')
                        if end_idx != -1:
                            custom_club_name = post.description[13:end_idx]  # Skip '[CUSTOM_CLUB:'
                            display_club_name = custom_club_name
                            display_description = post.description[end_idx + 2:]  # Skip '] '
                    except:
                        pass  # Fall back to original if parsing fails
                
                post_data = {
                    'id': post.id,
                    'title': post.title,
                    'description': display_description,
                    'images': post.get_images(),
                    'club_name': display_club_name,
                    'club': {
                        'id': club.id,
                        'name': display_club_name,
                        'location': club.location or ''
                    },
                    'author': {
                        'id': user.id,
                        'username': user.username
                    },
                    'created_at': post.created_at.isoformat() if post.created_at else '',
                    'featured': bool(post.featured)
                }
                posts_data.append(post_data)
                current_app.logger.debug(f"Gallery post {post.id}: '{post.title}' by {user.username} from {club.name}, {len(post.get_images())} images")
                
            except Exception as e:
                current_app.logger.error(f"Error processing gallery post {post.id}: {str(e)}")
                continue
        
        current_app.logger.info(f"Returning {len(posts_data)} gallery posts to frontend")
        return jsonify({'posts': posts_data})
        
    except Exception as e:
        current_app.logger.error(f"Error fetching gallery posts: {str(e)}")
        db.session.rollback()
        return jsonify({'posts': []})


@api_bp.route('/gallery/posts/<int:post_id>', methods=['DELETE'])
@login_required
@limiter.limit("50 per hour")
def delete_gallery_post(post_id):
    """Delete a gallery post"""
    current_user = get_current_user()
    
    # Only admins can delete gallery posts
    if not current_user.is_admin:
        return jsonify({'error': 'Admin access required'}), 403
    
    post = GalleryPost.query.get_or_404(post_id)
    
    try:
        # Get images and related data before deletion
        images = post.get_images()
        post_title = post.title
        post_author_name = post.user.username if post.user else 'Unknown'
        club_name = post.club.name if post.club else 'Unknown'
        club = post.club
        
        # Deduct 100 tokens from the club if it has enough tokens
        if club and club.tokens >= 100:
            success, error_msg = create_club_transaction(
                club_id=club.id,
                transaction_type='debit',
                amount=-100,  # Negative amount for deduction
                description=f'Gallery post deletion penalty: "{post_title}"',
                user_id=current_user.id,
                reference_type='gallery_post_deletion',
                reference_id=post_id,
                created_by=current_user.id
            )
            
            if not success:
                current_app.logger.warning(f"Failed to deduct tokens for gallery post deletion: {error_msg}")
        
        # Delete the post
        db.session.delete(post)
        db.session.commit()
        
        create_audit_log(
            action_type='gallery_post_delete',
            description=f"Admin {current_user.username} deleted gallery post '{post_title}' by {post_author_name}",
            user=current_user,
            target_type='gallery_post',
            target_id=str(post_id),
            details={
                'post_title': post_title,
                'club_name': club_name,
                'author': post_author_name,
                'image_count': len(images),
                'token_penalty': 100 if club and club.tokens >= 100 else 0
            },
            severity='warning',
            admin_action=True,
            category='gallery'
        )
        
        current_app.logger.info(f"Gallery post {post_id} deleted by admin {current_user.username}")
        return jsonify({'message': 'Gallery post deleted successfully'})
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting gallery post {post_id}: {str(e)}")
        return jsonify({'error': 'Failed to delete gallery post'}), 500
