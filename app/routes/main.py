"""
Main routes blueprint for the Hack Club Dashboard.
Handles home page, dashboard, gallery, leaderboard, and general pages.
"""

from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from app.decorators.auth import login_required
from app.utils.auth_helpers import get_current_user
from app.models.user import User
from app.models.club import Club
from app.models.gallery import GalleryPost
from app.models.economy import LeaderboardExclusion
from app.models.system import SystemSettings
from extensions import db

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    """Home page"""
    user = get_current_user()
    if user:
        return redirect(url_for('main.dashboard'))
    return render_template('index.html')


@main_bp.route('/dashboard')
@login_required
def dashboard():
    """User dashboard"""
    user = get_current_user()

    # Get user's club memberships and led clubs
    from app.models.club import ClubMembership
    memberships = ClubMembership.query.filter_by(user_id=user.id).all()
    led_clubs = Club.query.filter_by(leader_id=user.id).all()

    # If user only has one club, redirect directly to it
    all_club_ids = set([club.id for club in led_clubs] + [m.club.id for m in memberships])
    if len(all_club_ids) == 1:
        club_id = list(all_club_ids)[0]
        return redirect(url_for('main.club_dashboard', club_id=club_id))

    return render_template('dashboard.html', memberships=memberships, led_clubs=led_clubs)


@main_bp.route('/club-dashboard')
@main_bp.route('/club-dashboard/<int:club_id>')
@login_required
def club_dashboard(club_id=None):
    """Club dashboard"""
    user = get_current_user()

    if club_id:
        club = Club.query.get_or_404(club_id)
    else:
        # Get user's first club
        club = Club.query.filter_by(leader_id=user.id).first()
        if not club:
            from app.models.club import ClubMembership
            membership = ClubMembership.query.filter_by(user_id=user.id).first()
            if membership:
                club = membership.club

        if not club:
            flash('You are not a member of any club', 'error')
            return redirect(url_for('main.dashboard'))

    # Verify user has access to this club
    from app.models.club import ClubMembership
    is_leader = club.leader_id == user.id
    is_co_leader = club.co_leader_id == user.id
    membership = ClubMembership.query.filter_by(club_id=club.id, user_id=user.id).first()
    is_member = membership is not None
    is_admin_access = request.args.get('admin') == 'true' and user.is_admin

    if not is_leader and not is_co_leader and not is_member and not is_admin_access:
        flash('You are not a member of this club', 'error')
        return redirect(url_for('main.dashboard'))

    # Check if club is suspended
    if club.is_suspended and not user.is_admin:
        flash('This club has been suspended', 'error')
        return redirect(url_for('main.dashboard'))

    # Check if club has orders
    from app.services.airtable import AirtableService
    try:
        airtable_service = AirtableService()
        orders = airtable_service.get_orders_for_club(club.name)
        has_orders = len(orders) > 0
    except:
        has_orders = False

    # Check if club has gallery post
    has_gallery_post = GalleryPost.query.filter_by(club_id=club.id).first() is not None

    # Check if connected to directory
    airtable_data = club.get_airtable_data()
    is_connected_to_directory = airtable_data and airtable_data.get('airtable_id')

    # Get banner settings
    banner_settings = {
        'enabled': SystemSettings.get_setting('banner_enabled', 'false') == 'true',
        'title': SystemSettings.get_setting('banner_title', 'Design Contest'),
        'subtitle': SystemSettings.get_setting('banner_subtitle', 'Submit your creative projects!'),
        'icon': SystemSettings.get_setting('banner_icon', 'fas fa-palette'),
        'primary_color': SystemSettings.get_setting('banner_primary_color', '#ec3750'),
        'secondary_color': SystemSettings.get_setting('banner_secondary_color', '#d63146'),
        'background_color': SystemSettings.get_setting('banner_background_color', '#ffffff'),
        'text_color': SystemSettings.get_setting('banner_text_color', '#1a202c'),
        'link_url': SystemSettings.get_setting('banner_link_url', '/gallery'),
        'link_text': SystemSettings.get_setting('banner_link_text', 'Submit Entry')
    }

    # Get membership date
    membership_date = membership.joined_at if membership else None

    # Role variables for template
    effective_is_leader = is_leader or is_admin_access
    effective_is_co_leader = is_co_leader or is_admin_access
    effective_can_manage = is_leader or is_co_leader or is_admin_access

    # Check for mobile
    user_agent = request.headers.get('User-Agent', '').lower()
    is_mobile = any(mobile in user_agent for mobile in ['mobile', 'android', 'iphone', 'ipad'])
    force_mobile = request.args.get('mobile', '').lower() == 'true'
    force_desktop = request.args.get('desktop', '').lower() == 'true'

    if (is_mobile or force_mobile) and not force_desktop:
        return render_template('club_dashboard_mobile.html',
                             club=club,
                             membership_date=membership_date,
                             has_orders=has_orders,
                             has_gallery_post=has_gallery_post,
                             is_leader=is_leader,
                             is_co_leader=is_co_leader,
                             is_admin_access=is_admin_access,
                             effective_is_leader=effective_is_leader,
                             effective_is_co_leader=effective_is_co_leader,
                             effective_can_manage=effective_can_manage,
                             banner_settings=banner_settings,
                             is_connected_to_directory=is_connected_to_directory)

    return render_template('club_dashboard.html',
                         club=club,
                         membership_date=membership_date,
                         has_orders=has_orders,
                         has_gallery_post=has_gallery_post,
                         is_leader=is_leader,
                         is_co_leader=is_co_leader,
                         is_admin_access=is_admin_access,
                         effective_is_leader=effective_is_leader,
                         effective_is_co_leader=effective_is_co_leader,
                         effective_can_manage=effective_can_manage,
                         banner_settings=banner_settings,
                         is_connected_to_directory=is_connected_to_directory)


@main_bp.route('/gallery')
def gallery():
    """Public gallery of club posts"""
    # Get all gallery posts ordered by date (featured first, then by date)
    posts = GalleryPost.query.order_by(
        GalleryPost.featured.desc(),
        GalleryPost.created_at.desc()
    ).limit(50).all()

    return render_template('gallery.html', posts=posts)


@main_bp.route('/leaderboard')
@main_bp.route('/leaderboard/<leaderboard_type>')
def leaderboard(leaderboard_type='total_tokens'):
    """Club leaderboard"""
    # Get excluded clubs for this leaderboard type
    excluded_club_ids = [
        exc.club_id for exc in LeaderboardExclusion.query.filter_by(
            leaderboard_type=leaderboard_type
        ).all()
    ]

    # Query clubs based on leaderboard type
    if leaderboard_type == 'total_tokens':
        clubs = Club.query.filter(
            ~Club.id.in_(excluded_club_ids)
        ).order_by(Club.tokens.desc()).limit(100).all()
        title = "Top Clubs by Total Tokens"
    elif leaderboard_type == 'monthly_tokens':
        # For now, use total tokens (TODO: track monthly separately)
        clubs = Club.query.filter(
            ~Club.id.in_(excluded_club_ids)
        ).order_by(Club.tokens.desc()).limit(100).all()
        title = "Top Clubs by Monthly Tokens"
    else:
        clubs = []
        title = "Leaderboard"

    # Add rank to each club
    for i, club in enumerate(clubs, 1):
        club.rank = i

    return render_template('leaderboard.html',
                         clubs=clubs,
                         title=title,
                         leaderboard_type=leaderboard_type)


@main_bp.route('/join-club')
def join_club_redirect():
    """Redirect to club joining flow"""
    return redirect('https://clubs.hackclub.com')


@main_bp.route('/maintenance')
def maintenance():
    """Maintenance mode page"""
    return render_template('maintenance.html'), 503


@main_bp.route('/suspended')
def suspended():
    """Account suspended page"""
    return render_template('suspended.html'), 403


@main_bp.route('/account')
@login_required
def account():
    """User account settings"""
    user = get_current_user()
    return render_template('account.html', user=user)


@main_bp.route('/contact')
def contact():
    """Contact page"""
    return render_template('contact.html')


@main_bp.route('/help')
def help():
    """Help and FAQ page"""
    return render_template('help.html')


@main_bp.route('/privacy')
def privacy():
    """Privacy policy page"""
    return render_template('privacy.html')


@main_bp.route('/terms')
def terms():
    """Terms of service page"""
    return render_template('terms.html')


@main_bp.route('/mobile-unavailable')
def mobile_unavailable():
    """Mobile unavailable notice page"""
    return render_template('mobile_unavailable.html')


@main_bp.route('/raccoon-mascot')
def raccoon_mascot():
    """Easter egg raccoon mascot page"""
    return render_template('raccoon_mascot.html')


@main_bp.route('/pizza-order')
@login_required
def pizza_order():
    """Pizza ordering page"""
    user = get_current_user()
    # Get user's clubs
    from app.models.club import ClubMembership
    memberships = ClubMembership.query.filter_by(user_id=user.id).all()
    led_clubs = Club.query.filter_by(leader_id=user.id).all()

    return render_template('pizza_order.html',
                         memberships=memberships,
                         led_clubs=led_clubs)


@main_bp.route('/project-review')
@login_required
def project_review():
    """Project review page (non-admin)"""
    user = get_current_user()

    # Get user's submitted projects
    from app.models.economy import ProjectSubmission
    projects = ProjectSubmission.query.filter_by(user_id=user.id).order_by(
        ProjectSubmission.submitted_at.desc()
    ).all()

    return render_template('project_review.html', projects=projects)
