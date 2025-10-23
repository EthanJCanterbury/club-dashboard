"""
Club routes blueprint for the Hack Club Dashboard.
Handles club management, shop, poster editor, and club-specific features.
"""

from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, send_file
from extensions import db
from app.decorators.auth import login_required
from app.decorators.economy import economy_required
from app.utils.auth_helpers import get_current_user
from app.utils.club_helpers import verify_club_leadership, is_user_co_leader
from app.utils.economy_helpers import create_club_transaction
from app.models.club import Club, ClubMembership
from app.models.economy import ClubTransaction
from app.models.club_content import ClubPost, ClubProject

clubs_bp = Blueprint('clubs', __name__)


@clubs_bp.route('/club-connection-required/<int:club_id>')
@login_required
def club_connection_required(club_id):
    """Page shown when club connection is required"""
    club = Club.query.get_or_404(club_id)
    user = get_current_user()

    # Check if user is a member
    membership = ClubMembership.query.filter_by(
        club_id=club_id,
        user_id=user.id
    ).first()

    if not membership:
        flash('You must be a member of this club to access this page.', 'danger')
        return redirect(url_for('main.dashboard'))

    return render_template('club_connection_required.html', club=club)


@clubs_bp.route('/club/<int:club_id>/shop')
@login_required
@economy_required
def club_shop(club_id):
    """Club token shop"""
    club = Club.query.get_or_404(club_id)
    user = get_current_user()

    # Verify user is a member or leader
    membership = ClubMembership.query.filter_by(
        club_id=club_id,
        user_id=user.id
    ).first()

    if not membership:
        flash('You must be a member of this club to access the shop.', 'danger')
        return redirect(url_for('main.dashboard'))

    # Get club transactions for balance history
    transactions = ClubTransaction.query.filter_by(
        club_id=club_id
    ).order_by(ClubTransaction.created_at.desc()).limit(20).all()

    return render_template('club_shop.html', club=club, transactions=transactions)


@clubs_bp.route('/club/<int:club_id>/orders')
@login_required
def club_orders(club_id):
    """View club orders"""
    club = Club.query.get_or_404(club_id)
    user = get_current_user()

    # Verify user is a leader
    if not verify_club_leadership(club, user):
        flash('Only club leaders can view orders.', 'danger')
        return redirect(url_for('main.club_dashboard', club_id=club_id))

    # TODO: Implement order viewing
    return render_template('club_orders.html', club=club)


@clubs_bp.route('/club/<int:club_id>/poster-editor')
@login_required
def poster_editor(club_id):
    """Club poster editor"""
    club = Club.query.get_or_404(club_id)
    user = get_current_user()

    # Verify user is a member
    membership = ClubMembership.query.filter_by(
        club_id=club_id,
        user_id=user.id
    ).first()

    if not membership:
        flash('You must be a member of this club to use the poster editor.', 'danger')
        return redirect(url_for('main.dashboard'))

    return render_template('poster_editor.html', club=club)


@clubs_bp.route('/club/<int:club_id>/project-submission', methods=['GET', 'POST'])
@login_required
def project_submission(club_id):
    """Submit a project for club"""
    club = Club.query.get_or_404(club_id)
    user = get_current_user()

    # Verify user is a member
    membership = ClubMembership.query.filter_by(
        club_id=club_id,
        user_id=user.id
    ).first()

    if not membership:
        flash('You must be a member of this club to submit projects.', 'danger')
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        from app.utils.sanitization import sanitize_string, sanitize_url
        from app.models.economy import ProjectSubmission

        project_name = sanitize_string(request.form.get('project_name', ''), max_length=200)
        project_url = sanitize_url(request.form.get('project_url', ''), max_length=500)

        if not project_name:
            flash('Project name is required.', 'error')
            return render_template('project_submission.html', club=club)

        # Create project submission
        submission = ProjectSubmission(
            user_id=user.id,
            club_id=club_id,
            project_name=project_name,
            project_url=project_url
        )

        db.session.add(submission)
        db.session.commit()

        flash('Project submitted successfully! Waiting for approval.', 'success')
        return redirect(url_for('main.club_dashboard', club_id=club_id))

    return render_template('project_submission.html', club=club)


@clubs_bp.route('/api/clubs/<int:club_id>/members')
@login_required
def get_club_members(club_id):
    """Get club members API endpoint"""
    club = Club.query.get_or_404(club_id)
    user = get_current_user()

    # Verify user is a member
    membership = ClubMembership.query.filter_by(
        club_id=club_id,
        user_id=user.id
    ).first()

    if not membership:
        return jsonify({'error': 'Not authorized'}), 403

    # Get all members
    memberships = ClubMembership.query.filter_by(club_id=club_id).all()

    members_data = []
    for m in memberships:
        member_data = {
            'id': m.user.id,
            'username': m.user.username,
            'first_name': m.user.first_name,
            'last_name': m.user.last_name,
            'email': m.user.email,
            'is_leader': m.is_leader,
            'is_co_leader': m.is_co_leader,
            'joined_at': m.joined_at.isoformat() if m.joined_at else None
        }
        members_data.append(member_data)

    return jsonify({
        'success': True,
        'club_id': club_id,
        'club_name': club.name,
        'members': members_data,
        'total_members': len(members_data)
    })
