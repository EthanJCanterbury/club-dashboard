"""
OAuth routes blueprint for the Hack Club Dashboard.
Implements OAuth 2.0 authorization server for third-party applications.
"""

from flask import Blueprint, render_template, redirect, url_for, request, jsonify, session
from datetime import datetime, timedelta, timezone
import secrets
from extensions import db, limiter
from app.decorators.auth import login_required
from app.utils.auth_helpers import get_current_user
from app.utils.sanitization import sanitize_string, sanitize_url
from app.models.auth import OAuthApplication, OAuthToken, OAuthAuthorizationCode
from app.models.user import User

oauth_bp = Blueprint('oauth', __name__, url_prefix='/oauth')


@oauth_bp.route('/authorize')
@limiter.limit("30 per minute")
def authorize():
    """OAuth authorization endpoint"""
    # Get OAuth parameters
    client_id = request.args.get('client_id')
    redirect_uri = request.args.get('redirect_uri')
    response_type = request.args.get('response_type', 'code')
    scope = request.args.get('scope', '')
    state = request.args.get('state', '')

    if not client_id or not redirect_uri:
        return jsonify({'error': 'invalid_request', 'error_description': 'Missing required parameters'}), 400

    app = OAuthApplication.query.filter_by(client_id=client_id).first()
    if not app:
        return jsonify({'error': 'invalid_client', 'error_description': 'Unknown client'}), 401

    # Validate redirect URI
    if redirect_uri not in app.redirect_uris:
        return jsonify({'error': 'invalid_request', 'error_description': 'Invalid redirect_uri'}), 400

    # Check if user is logged in
    user = get_current_user()
    if not user:
        # Store OAuth params and redirect to login
        session['oauth_params'] = {
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'response_type': response_type,
            'scope': scope,
            'state': state
        }
        return redirect(url_for('auth.login'))

    # Only support authorization code flow
    if response_type != 'code':
        return jsonify({'error': 'unsupported_response_type'}), 400

    # Show authorization page
    scopes = scope.split() if scope else []
    return render_template('oauth/authorize.html',
                         app=app,
                         scopes=scopes,
                         redirect_uri=redirect_uri,
                         state=state)


@oauth_bp.route('/authorize/approve', methods=['POST'])
@login_required
@limiter.limit("30 per minute")
def approve_authorization():
    """User approves OAuth authorization"""
    user = get_current_user()

    client_id = request.form.get('client_id')
    redirect_uri = request.form.get('redirect_uri')
    scope = request.form.get('scope', '')
    state = request.form.get('state', '')

    app = OAuthApplication.query.filter_by(client_id=client_id).first()
    if not app:
        return jsonify({'error': 'invalid_client'}), 401

    # Check if identity verification is required
    if app.requires_identity_verification and not user.identity_verified:
        # Store OAuth params and redirect to identity verification
        session['pending_oauth'] = {
            'application_id': app.id,
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'scope': scope,
            'state': state
        }

        # Redirect to identity setup
        from flask import flash
        flash('This application requires identity verification', 'info')
        return redirect(url_for('main.account'))

    # Generate authorization code
    code = secrets.token_urlsafe(32)

    # Store authorization code
    auth_code = OAuthAuthorizationCode(
        code=code,
        application_id=app.id,
        user_id=user.id,
        redirect_uri=redirect_uri,
        scope=scope,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10)
    )

    db.session.add(auth_code)
    db.session.commit()

    # Redirect back to client with code
    separator = '&' if '?' in redirect_uri else '?'
    callback_url = f"{redirect_uri}{separator}code={code}"
    if state:
        callback_url += f"&state={state}"

    return redirect(callback_url)


@oauth_bp.route('/token', methods=['POST'])
@limiter.limit("30 per minute")
def token():
    """OAuth token endpoint"""
    grant_type = request.form.get('grant_type')
    code = request.form.get('code')
    redirect_uri = request.form.get('redirect_uri')
    client_id = request.form.get('client_id')
    client_secret = request.form.get('client_secret')

    if grant_type != 'authorization_code':
        return jsonify({'error': 'unsupported_grant_type'}), 400

    app = OAuthApplication.query.filter_by(
        client_id=client_id,
        client_secret=client_secret
    ).first()

    if not app:
        return jsonify({'error': 'invalid_client'}), 401

    # Validate authorization code
    auth_code = OAuthAuthorizationCode.query.filter_by(
        code=code,
        application_id=app.id
    ).first()

    if not auth_code:
        return jsonify({'error': 'invalid_grant'}), 400

    # Check if code expired
    if auth_code.expires_at < datetime.now(timezone.utc):
        return jsonify({'error': 'invalid_grant', 'error_description': 'Code expired'}), 400

    # Check if code was used
    if auth_code.used_at:
        return jsonify({'error': 'invalid_grant', 'error_description': 'Code already used'}), 400

    # Validate redirect URI
    if auth_code.redirect_uri != redirect_uri:
        return jsonify({'error': 'invalid_grant', 'error_description': 'Redirect URI mismatch'}), 400

    # Mark code as used
    auth_code.used_at = datetime.now(timezone.utc)

    # Generate access token
    access_token = secrets.token_urlsafe(32)
    refresh_token = secrets.token_urlsafe(32)

    # Create token
    oauth_token = OAuthToken(
        access_token=access_token,
        refresh_token=refresh_token,
        application_id=app.id,
        user_id=auth_code.user_id,
        scope=auth_code.scope,
        expires_at=datetime.now(timezone.utc) + timedelta(days=30)
    )

    db.session.add(oauth_token)
    db.session.commit()

    return jsonify({
        'access_token': access_token,
        'token_type': 'Bearer',
        'expires_in': 30 * 24 * 60 * 60,  # 30 days in seconds
        'refresh_token': refresh_token,
        'scope': auth_code.scope
    })


@oauth_bp.route('/user')
@limiter.limit("60 per minute")
def user_info():
    """Get user info with OAuth token"""
    # Get token from Authorization header
    auth_header = request.headers.get('Authorization', '')

    if not auth_header.startswith('Bearer '):
        return jsonify({'error': 'invalid_request'}), 401

    access_token = auth_header[7:]  # Remove "Bearer " prefix

    token = OAuthToken.query.filter_by(access_token=access_token).first()

    if not token:
        return jsonify({'error': 'invalid_token'}), 401

    # Check if token expired
    if token.expires_at < datetime.now(timezone.utc):
        return jsonify({'error': 'invalid_token', 'error_description': 'Token expired'}), 401

    # Check if token was revoked
    if token.revoked_at:
        return jsonify({'error': 'invalid_token', 'error_description': 'Token revoked'}), 401

    user = User.query.get(token.user_id)
    if not user:
        return jsonify({'error': 'invalid_token'}), 401

    # Return user info (scope-limited)
    scopes = token.scope.split() if token.scope else []

    user_info = {
        'id': user.id,
        'username': user.username
    }

    if 'user:read' in scopes or 'user:email' in scopes:
        user_info['email'] = user.email

    if 'user:read' in scopes:
        user_info['first_name'] = user.first_name
        user_info['last_name'] = user.last_name
        user_info['created_at'] = user.created_at.isoformat() if user.created_at else None

    return jsonify(user_info)


@oauth_bp.route('/debug')
@login_required
def oauth_debug():
    """OAuth debug page (for testing)"""
    user = get_current_user()

    # Get user's tokens
    tokens = OAuthToken.query.filter_by(user_id=user.id).all()

    return render_template('oauth/debug.html', tokens=tokens)


@oauth_bp.route('/debug/callback')
def oauth_debug_callback():
    """OAuth debug callback (for testing)"""
    code = request.args.get('code')
    state = request.args.get('state')
    error = request.args.get('error')

    return render_template('oauth/debug_callback.html',
                         code=code,
                         state=state,
                         error=error)


@oauth_bp.route('/consent')
@login_required
def oauth_consent():
    """OAuth consent page"""
    user = get_current_user()

    # Get OAuth parameters from session or query string
    oauth_params = session.get('oauth_params', {})
    client_id = oauth_params.get('client_id') or request.args.get('client_id')

    if not client_id:
        return jsonify({'error': 'Missing client_id'}), 400

    # Get OAuth application
    app = OAuthApplication.query.filter_by(client_id=client_id).first()
    if not app:
        return jsonify({'error': 'Unknown client'}), 404

    return render_template('oauth_consent.html',
                         app=app,
                         oauth_params=oauth_params)
