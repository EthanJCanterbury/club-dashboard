"""
Authentication routes blueprint for the Hack Club Dashboard.
Handles login, signup, password reset, Slack OAuth, and Hack Club Identity OAuth.
"""

from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, session
from werkzeug.security import generate_password_hash
from extensions import db, limiter
from app.decorators.auth import login_required
from app.utils.auth_helpers import get_current_user, login_user as do_login_user, logout_user as do_logout_user, is_authenticated
from app.utils.sanitization import sanitize_string
from app.utils.security import (
    get_real_ip, log_security_event, validate_username, validate_email,
    validate_name, validate_password, validate_input_with_security
)
from app.models.user import User
from app.models.club import Club, ClubMembership
import re
import os

auth_bp = Blueprint('auth', __name__)

# Constants from environment
SLACK_CLIENT_ID = os.getenv('SLACK_CLIENT_ID')
SLACK_CLIENT_SECRET = os.getenv('SLACK_CLIENT_SECRET')
HACKCLUB_IDENTITY_URL = os.getenv('HACKCLUB_IDENTITY_URL', 'https://identity.hackclub.com')
HACKCLUB_IDENTITY_CLIENT_ID = os.getenv('HACKCLUB_IDENTITY_CLIENT_ID')
HACKCLUB_IDENTITY_CLIENT_SECRET = os.getenv('HACKCLUB_IDENTITY_CLIENT_SECRET')


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def login():
    """User login"""
    if is_authenticated():
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        email = sanitize_string(request.form.get('email', ''), max_length=120).strip().lower()
        password = request.form.get('password', '')
        remember_me = request.form.get('remember_me') == 'on'

        if not email or not password:
            flash('Email and password are required', 'error')
            return render_template('login.html')

        try:
            user = User.query.filter_by(email=email).first()
        except Exception as e:
            db.session.rollback()
            flash('Database connection error. Please try again.', 'error')
            return render_template('login.html')

        if user and user.check_password(password):
            # Check if account is suspended
            if user.is_suspended:
                flash('Your account has been suspended. Please contact support.', 'error')
                return redirect(url_for('main.suspended'))

            do_login_user(user, remember=remember_me)
            flash(f'Welcome back, {user.username}!', 'success')

            # Check for pending OAuth flow
            oauth_params = session.get('oauth_params')
            if oauth_params:
                session.pop('oauth_params', None)
                query_string = '&'.join([f"{k}={v}" for k, v in oauth_params.items()])
                return redirect(url_for('oauth.authorize') + f'?{query_string}')

            return redirect(url_for('main.dashboard'))
        else:
            log_security_event("FAILED_LOGIN", f"Failed login attempt for email: {email}", ip_address=get_real_ip())
            flash('Invalid email or password', 'error')

    # Check if mobile device
    user_agent = request.headers.get('User-Agent', '').lower()
    is_mobile = any(mobile in user_agent for mobile in ['mobile', 'android', 'iphone', 'ipad'])
    force_mobile = request.args.get('mobile', '').lower() == 'true'
    force_desktop = request.args.get('desktop', '').lower() == 'true'

    if (is_mobile or force_mobile) and not force_desktop:
        return render_template('login_mobile.html')
    else:
        return render_template('login.html')


@auth_bp.route('/logout')
def logout():
    """User logout"""
    do_logout_user()
    flash('You have been logged out successfully.', 'success')
    return redirect(url_for('main.index'))


@auth_bp.route('/signup', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def signup():
    """User signup"""
    if is_authenticated():
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        # Get form data
        username = sanitize_string(request.form.get('username', ''), max_length=30).strip()
        email = sanitize_string(request.form.get('email', ''), max_length=120).strip().lower()
        password = request.form.get('password', '')
        first_name = sanitize_string(request.form.get('first_name', ''), max_length=50).strip()
        last_name = sanitize_string(request.form.get('last_name', ''), max_length=50).strip()

        # Validate inputs
        valid_username, username_or_error = validate_username(username)
        if not valid_username:
            flash(username_or_error, 'error')
            return render_template('signup.html')

        valid_email, email_or_error = validate_email(email)
        if not valid_email:
            flash(email_or_error, 'error')
            return render_template('signup.html')

        valid_password, password_or_error = validate_password(password)
        if not valid_password:
            flash(password_or_error, 'error')
            return render_template('signup.html')

        # Check if username or email already exists
        if User.query.filter_by(username=username).first():
            flash('Username already taken', 'error')
            return render_template('signup.html')

        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'error')
            return render_template('signup.html')

        # Create new user
        user = User(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name
        )
        user.set_password(password)

        db.session.add(user)
        db.session.commit()

        # Log in the new user
        do_login_user(user)
        flash(f'Welcome to Hack Club, {user.username}!', 'success')

        return redirect(url_for('main.dashboard'))

    return render_template('signup.html')


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def forgot_password():
    """Request password reset"""
    if is_authenticated():
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        email = sanitize_string(request.form.get('email', ''), max_length=120).strip().lower()

        if not email:
            return jsonify({'success': False, 'message': 'Email is required'}), 400

        # Validate email format
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            return jsonify({'success': False, 'message': 'Invalid email format'}), 400

        # TODO: Implement email sending for password reset
        # For now, just return success
        return jsonify({'success': True, 'message': 'If an account exists with this email, you will receive reset instructions.'})

    return render_template('forgot_password.html')


@auth_bp.route('/reset-password', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def reset_password():
    """Reset password with code"""
    # TODO: Implement password reset functionality
    return render_template('reset_password.html')


@auth_bp.route('/verify-reset-code', methods=['POST'])
@limiter.limit("10 per minute")
def verify_reset_code():
    """Verify password reset code"""
    # TODO: Implement reset code verification
    return jsonify({'success': False, 'message': 'Not implemented'}), 501


@auth_bp.route('/auth/slack')
def slack_login():
    """Initiate Slack OAuth flow"""
    if not SLACK_CLIENT_ID:
        flash('Slack authentication is not configured', 'error')
        return redirect(url_for('auth.login'))

    from app.services.slack_oauth import SlackOAuthService
    redirect_uri = url_for('auth.slack_callback', _external=True)

    # Generate state for CSRF protection
    import secrets
    state = secrets.token_urlsafe(32)
    session['slack_oauth_state'] = state

    auth_url = SlackOAuthService.get_authorization_url(redirect_uri, state)
    return redirect(auth_url)


@auth_bp.route('/auth/slack/callback')
@limiter.limit("10 per minute")
def slack_callback():
    """Handle Slack OAuth callback"""
    # Verify state for CSRF protection
    state = request.args.get('state')
    if state != session.get('slack_oauth_state'):
        flash('Invalid authentication state', 'error')
        return redirect(url_for('auth.login'))

    session.pop('slack_oauth_state', None)

    code = request.args.get('code')
    error = request.args.get('error')

    if error:
        flash(f'Slack authentication failed: {error}', 'error')
        return redirect(url_for('auth.login'))

    if not code:
        flash('No authorization code received', 'error')
        return redirect(url_for('auth.login'))

    # Exchange code for token
    from app.services.slack_oauth import SlackOAuthService
    redirect_uri = url_for('auth.slack_callback', _external=True)
    token_data = SlackOAuthService.exchange_code(code, redirect_uri)

    if not token_data:
        flash('Failed to authenticate with Slack', 'error')
        return redirect(url_for('auth.login'))

    # Get user info from Slack
    user_info = SlackOAuthService.get_user_info(token_data.get('access_token'))

    if not user_info:
        flash('Failed to get user information from Slack', 'error')
        return redirect(url_for('auth.login'))

    # Find or create user
    slack_id = user_info.get('user', {}).get('id')
    email = user_info.get('user', {}).get('email')

    if not slack_id or not email:
        flash('Incomplete user information from Slack', 'error')
        return redirect(url_for('auth.login'))

    # Check if user exists
    user = User.query.filter_by(email=email).first()

    if user:
        # User exists, log them in
        user.slack_id = slack_id
        db.session.commit()
        do_login_user(user)
        flash(f'Welcome back, {user.username}!', 'success')
        return redirect(url_for('main.dashboard'))
    else:
        # New user, redirect to complete signup
        session['slack_user_info'] = user_info
        return redirect(url_for('auth.complete_slack_signup'))


@auth_bp.route('/complete-slack-signup', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def complete_slack_signup():
    """Complete signup after Slack OAuth"""
    slack_user_info = session.get('slack_user_info')
    if not slack_user_info:
        flash('No Slack authentication found. Please try again.', 'error')
        return redirect(url_for('auth.signup'))

    if request.method == 'POST':
        username = sanitize_string(request.form.get('username', ''), max_length=30).strip()

        # Validate username
        valid_username, username_or_error = validate_username(username)
        if not valid_username:
            flash(username_or_error, 'error')
            return render_template('complete_slack_signup.html', user_info=slack_user_info)

        # Check if username exists
        if User.query.filter_by(username=username).first():
            flash('Username already taken', 'error')
            return render_template('complete_slack_signup.html', user_info=slack_user_info)

        # Create new user
        email = slack_user_info.get('user', {}).get('email')
        slack_id = slack_user_info.get('user', {}).get('id')
        first_name = slack_user_info.get('user', {}).get('profile', {}).get('first_name', '')
        last_name = slack_user_info.get('user', {}).get('profile', {}).get('last_name', '')

        user = User(
            username=username,
            email=email,
            slack_id=slack_id,
            first_name=first_name,
            last_name=last_name
        )

        # Generate a random password (user won't need it since they use Slack OAuth)
        import secrets
        random_password = secrets.token_urlsafe(32)
        user.set_password(random_password)

        db.session.add(user)
        db.session.commit()

        session.pop('slack_user_info', None)

        # Log in the new user
        do_login_user(user)
        flash(f'Welcome to Hack Club, {user.username}!', 'success')

        return redirect(url_for('main.dashboard'))

    return render_template('complete_slack_signup.html', user_info=slack_user_info)


@auth_bp.route('/identity/callback')
@limiter.limit("10 per minute")
def hackclub_identity_callback():
    """Handle Hack Club Identity OAuth callback"""
    # TODO: Implement Hack Club Identity OAuth
    flash('Hack Club Identity authentication is not yet implemented', 'warning')
    return redirect(url_for('auth.login'))


@auth_bp.route('/verify-leader', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def verify_leader():
    """Verify club leader with Airtable"""
    # TODO: Implement leader verification
    return render_template('verify_leader.html')


@auth_bp.route('/complete-leader-signup')
@login_required
def complete_leader_signup():
    """Complete signup for verified leaders"""
    # TODO: Implement leader signup completion
    flash('Leader signup completion is not yet implemented', 'warning')
    return redirect(url_for('main.dashboard'))


@auth_bp.route('/setup-hackatime', methods=['GET', 'POST'])
@login_required
def setup_hackatime():
    """Setup Hackatime integration"""
    # TODO: Implement Hackatime setup
    return render_template('setup_hackatime.html')
