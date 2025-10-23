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

    # Get user's clubs
    from app.models.club import ClubMembership
    memberships = ClubMembership.query.filter_by(user_id=user.id).all()
    clubs = [membership.club for membership in memberships]

    return render_template('dashboard.html', clubs=clubs)


@main_bp.route('/club-dashboard')
@main_bp.route('/club-dashboard/<int:club_id>')
@login_required
def club_dashboard(club_id=None):
    """Club dashboard"""
    user = get_current_user()

    if club_id:
        club = Club.query.get_or_404(club_id)
        # Verify user is a member
        from app.models.club import ClubMembership
        membership = ClubMembership.query.filter_by(
            club_id=club_id,
            user_id=user.id
        ).first()
        if not membership:
            flash('You are not a member of this club.', 'danger')
            return redirect(url_for('main.dashboard'))
    else:
        # Get user's first club
        from app.models.club import ClubMembership
        membership = ClubMembership.query.filter_by(user_id=user.id).first()
        if not membership:
            flash('You are not a member of any club.', 'warning')
            return redirect(url_for('main.dashboard'))
        club = membership.club
        return redirect(url_for('main.club_dashboard', club_id=club.id))

    return render_template('club_dashboard.html', club=club)


@main_bp.route('/gallery')
def gallery():
    """Public gallery of club posts"""
    # Get all gallery posts ordered by date
    posts = GalleryPost.query.filter_by(is_public=True).order_by(
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
        # TODO: Implement monthly tokens tracking
        clubs = []
        title = "Top Clubs by Monthly Tokens"
    else:
        clubs = []
        title = "Leaderboard"

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
