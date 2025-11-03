"""
Authentication routes blueprint for the Hack Club Dashboard.
Handles login, signup, password reset, and Hack Club Identity OAuth.
"""

from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, session, current_app
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
from app.models.system import SystemSettings
import re
import os

auth_bp = Blueprint('auth', __name__)

# Constants from environment
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
            return render_template('login.html', user_registration_enabled=SystemSettings.is_user_registration_enabled())

        try:
            user = User.query.filter_by(email=email).first()
        except Exception as e:
            db.session.rollback()
            flash('Database connection error. Please try again.', 'error')
            return render_template('login.html', user_registration_enabled=SystemSettings.is_user_registration_enabled())

        if user and user.check_password(password):
            # Check if account is suspended
            if user.is_suspended:
                flash('Your account has been suspended. Please contact support.', 'error')
                return redirect(url_for('main.suspended'))

            # Check if 2FA is enabled
            if user.totp_enabled:
                # Store user ID in session for 2FA verification
                session['2fa_user_id'] = user.id
                session['2fa_remember_me'] = remember_me
                return redirect(url_for('auth.verify_2fa'))

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

    return render_template('login.html', user_registration_enabled=SystemSettings.is_user_registration_enabled())


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

        # For now, just return success
        return jsonify({'success': True, 'message': 'If an account exists with this email, you will receive reset instructions.'})

    return render_template('forgot_password.html')


@auth_bp.route('/reset-password', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def reset_password():
    """Reset password with code"""
    return render_template('reset_password.html')


@auth_bp.route('/verify-reset-code', methods=['POST'])
@limiter.limit("10 per minute")
def verify_reset_code():
    """Verify password reset code"""
    return jsonify({'success': False, 'message': 'Not implemented'}), 501


@auth_bp.route('/identity/callback')
@limiter.limit("10 per minute")
def hackclub_identity_callback():
    """Handle Hack Club Identity OAuth callback"""
    import os
    from app.services.identity import HackClubIdentityService, init_service
    from app.utils.auth_helpers import get_current_user

    # Verify state for CSRF protection
    stored_state = session.get('hackclub_identity_state')
    received_state = request.args.get('state')

    if not stored_state or received_state != stored_state:
        flash('Invalid state parameter - possible CSRF attack', 'error')
        return redirect(url_for('main.account'))

    session.pop('hackclub_identity_state', None)

    # Check for errors
    error = request.args.get('error')
    if error:
        flash(f'Identity verification failed: {error}', 'error')
        return redirect(url_for('main.account'))

    # Get authorization code
    code = request.args.get('code')
    if not code:
        flash('No authorization code received', 'error')
        return redirect(url_for('main.account'))

    # Verify user is logged in
    user = get_current_user()
    if not user:
        flash('Please log in to complete identity verification', 'error')
        return redirect(url_for('auth.login'))

    # Initialize identity service
    client_id = HACKCLUB_IDENTITY_CLIENT_ID
    client_secret = HACKCLUB_IDENTITY_CLIENT_SECRET
    identity_url = os.getenv('HACKCLUB_IDENTITY_URL', 'https://identity.hackclub.com')

    init_service(current_app._get_current_object(), identity_url, client_id, client_secret)
    identity_service = HackClubIdentityService()

    # Get redirect URI
    redirect_uri = request.url_root.rstrip('/') + '/auth/identity/callback'
    if request.url_root.startswith('http://'):
        redirect_uri = redirect_uri.replace('http://', 'https://', 1)

    # Exchange code for access token
    token_data = identity_service.exchange_code(code, redirect_uri)

    if 'error' in token_data:
        flash(f'Token exchange failed: {token_data.get("error", "Unknown error")}', 'error')
        return redirect(url_for('main.account'))

    # Store access token
    access_token = token_data.get('access_token')
    if not access_token:
        flash('No access token received', 'error')
        return redirect(url_for('main.account'))

    user.identity_token = access_token

    # Get user identity information
    identity_info = identity_service.get_user_identity(access_token)

    if identity_info and 'identity' in identity_info:
        verification_status = identity_info['identity'].get('verification_status', 'unverified')
        user.identity_verified = (verification_status == 'verified')

        # Get Slack ID if available
        if 'slack_id' in identity_info['identity']:
            user.slack_user_id = identity_info['identity']['slack_id']

        db.session.commit()

        # Check for pending OAuth flow
        pending_oauth = session.get('pending_oauth')
        if pending_oauth and user.identity_verified:
            # OAuth flow was waiting for identity verification
            session.pop('pending_oauth', None)

            # Generate authorization code
            from app.models.auth import OAuthAuthorizationCode
            auth_code = OAuthAuthorizationCode(
                application_id=pending_oauth['application_id'],
                user_id=user.id,
                redirect_uri=pending_oauth['redirect_uri'],
                scope=pending_oauth['scope']
            )
            auth_code.generate_code()

            db.session.add(auth_code)
            db.session.commit()

            # Redirect back to client with code
            separator = '&' if '?' in pending_oauth['redirect_uri'] else '?'
            callback_url = f"{pending_oauth['redirect_uri']}{separator}code={auth_code.code}"
            if pending_oauth.get('state'):
                callback_url += f"&state={pending_oauth['state']}"

            return redirect(callback_url)

        # Create audit log
        from app.models.user import create_audit_log
        create_audit_log(
            action_type='identity_verified',
            description=f'User {user.username} verified Hack Club identity',
            user=user,
            category='auth',
            severity='info',
            details={
                'verification_status': verification_status,
                'has_slack': bool(user.slack_user_id)
            }
        )

        if verification_status == 'verified':
            flash('🎉 Successfully verified your Hack Club identity!', 'success')
        elif verification_status == 'pending':
            flash('Your identity verification is pending review.', 'info')
        else:
            flash('Identity linked, but not yet verified.', 'info')
    else:
        flash('Failed to retrieve identity information', 'error')

    return redirect(url_for('main.account'))


@auth_bp.route('/identity/disconnect', methods=['POST'])
@login_required
def disconnect_identity():
    """Disconnect Hack Club identity from account"""
    from app.utils.auth_helpers import get_current_user

    user = get_current_user()
    if not user:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401

    if not user.identity_verified:
        return jsonify({'success': False, 'message': 'No identity connected'}), 400

    # Clear identity information
    user.identity_token = None
    user.identity_verified = False
    user.slack_user_id = None

    db.session.commit()

    # Create audit log
    from app.models.user import create_audit_log
    create_audit_log(
        action_type='identity_disconnected',
        description=f'User {user.username} disconnected Hack Club identity',
        user=user,
        category='auth',
        severity='info'
    )

    return jsonify({'success': True, 'message': 'Identity disconnected successfully'})


@auth_bp.route('/verify-leader', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def verify_leader():
    """Verify club leader with Airtable"""
    return render_template('verify_leader.html')


@auth_bp.route('/complete-leader-signup')
@login_required
def complete_leader_signup():
    """Complete signup for verified leaders"""
    flash('Leader signup completion is not yet implemented', 'warning')
    return redirect(url_for('main.dashboard'))


@auth_bp.route('/setup-hackatime', methods=['GET', 'POST'])
@login_required
def setup_hackatime():
    """Setup Hackatime integration"""
    return render_template('setup_hackatime.html')


@auth_bp.route('/2fa/setup', methods=['GET', 'POST'])
@login_required
def setup_2fa():
    """Setup 2FA/TOTP"""
    from app.utils.auth_helpers import get_current_user
    from datetime import datetime, timezone
    import pyotp
    import qrcode
    import io
    import base64

    user = get_current_user()

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'generate':
            # Generate new secret
            secret = user.generate_totp_secret()
            session['totp_setup_secret'] = secret
            return jsonify({'success': True})

        elif action == 'verify':
            # Verify the token and enable 2FA
            token = request.form.get('token', '').strip()
            secret = session.get('totp_setup_secret')

            if not secret:
                return jsonify({'success': False, 'message': 'No setup in progress'}), 400

            # Verify token
            totp = pyotp.TOTP(secret)
            if totp.verify(token, valid_window=1):
                # Generate backup codes
                backup_codes = user.generate_backup_codes(10)

                # Enable 2FA
                user.totp_secret = secret
                user.totp_enabled = True
                user.totp_enabled_at = datetime.now(timezone.utc)
                user.set_backup_codes(backup_codes)

                db.session.commit()

                # Clear session
                session.pop('totp_setup_secret', None)

                # Create audit log
                from app.models.user import create_audit_log
                create_audit_log(
                    action_type='2fa_enabled',
                    description=f'User {user.username} enabled 2FA',
                    user=user,
                    category='auth',
                    severity='info'
                )

                return jsonify({
                    'success': True,
                    'backup_codes': backup_codes
                })
            else:
                return jsonify({'success': False, 'message': 'Invalid token'}), 400

    # GET request - show setup page
    if user.totp_enabled:
        # Already enabled, redirect to settings
        flash('2FA is already enabled', 'info')
        return redirect(url_for('main.account'))

    # Generate QR code if secret exists in session
    qr_code_data = None
    if 'totp_setup_secret' in session:
        secret = session['totp_setup_secret']
        uri = pyotp.totp.TOTP(secret).provisioning_uri(
            name=user.email,
            issuer_name='Hack Club Dashboard'
        )

        # Generate QR code
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(uri)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        # Convert to base64
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        qr_code_data = base64.b64encode(buffer.getvalue()).decode()

    return render_template('2fa_setup.html', qr_code_data=qr_code_data, secret=session.get('totp_setup_secret'))


@auth_bp.route('/2fa/disable', methods=['POST'])
@login_required
def disable_2fa():
    """Disable 2FA/TOTP"""
    from app.utils.auth_helpers import get_current_user

    user = get_current_user()

    if not user.totp_enabled:
        return jsonify({'success': False, 'message': '2FA is not enabled'}), 400

    # Verify password
    password = request.form.get('password', '')
    if not user.check_password(password):
        return jsonify({'success': False, 'message': 'Invalid password'}), 400

    # Disable 2FA
    user.totp_secret = None
    user.totp_enabled = False
    user.totp_backup_codes = None
    user.totp_enabled_at = None

    db.session.commit()

    # Create audit log
    from app.models.user import create_audit_log
    create_audit_log(
        action_type='2fa_disabled',
        description=f'User {user.username} disabled 2FA',
        user=user,
        category='auth',
        severity='warning'
    )

    flash('2FA has been disabled', 'success')
    return jsonify({'success': True})


@auth_bp.route('/2fa/regenerate-backup-codes', methods=['POST'])
@login_required
def regenerate_backup_codes():
    """Regenerate backup codes"""
    from app.utils.auth_helpers import get_current_user

    user = get_current_user()

    if not user.totp_enabled:
        return jsonify({'success': False, 'message': '2FA is not enabled'}), 400

    # Verify password
    password = request.form.get('password', '')
    if not user.check_password(password):
        return jsonify({'success': False, 'message': 'Invalid password'}), 400

    # Generate new backup codes
    backup_codes = user.generate_backup_codes(10)
    user.set_backup_codes(backup_codes)

    db.session.commit()

    # Create audit log
    from app.models.user import create_audit_log
    create_audit_log(
        action_type='2fa_backup_codes_regenerated',
        description=f'User {user.username} regenerated 2FA backup codes',
        user=user,
        category='auth',
        severity='info'
    )

    return jsonify({
        'success': True,
        'backup_codes': backup_codes
    })


@auth_bp.route('/2fa/verify', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def verify_2fa():
    """Verify 2FA token during login"""
    # Check if user is in 2FA verification state
    user_id = session.get('2fa_user_id')
    if not user_id:
        flash('No 2FA verification in progress', 'error')
        return redirect(url_for('auth.login'))

    user = User.query.get(user_id)
    if not user or not user.totp_enabled:
        session.pop('2fa_user_id', None)
        flash('Invalid 2FA state', 'error')
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        token = request.form.get('token', '').strip().replace('-', '').replace(' ', '')
        use_backup = request.form.get('use_backup') == 'true'

        verified = False
        if use_backup:
            # Verify backup code
            verified = user.verify_backup_code(token)
            if verified:
                db.session.commit()
                flash(f'Backup code accepted. You have {user.get_backup_codes_count()} backup codes remaining.', 'warning')
        else:
            # Verify TOTP token
            verified = user.verify_totp(token)

        if verified:
            # Complete login
            from app.utils.auth_helpers import login_user as do_login_user
            session.pop('2fa_user_id', None)
            remember_me = session.pop('2fa_remember_me', False)
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
            flash('Invalid token or backup code', 'error')

    return render_template('2fa_verify.html', user=user)
