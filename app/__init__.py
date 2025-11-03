"""
Hack Club Dashboard Application Factory

This module provides the application factory pattern for creating and configuring
the Flask application with all necessary extensions, blueprints, and configurations.
"""

import logging
from flask import Flask
from config import Config
from extensions import db, limiter
from better_profanity import profanity


def create_app(config_class=Config):
    """
    Application factory function.

    Args:
        config_class: Configuration class to use (defaults to Config from config.py)

    Returns:
        Configured Flask application instance
    """
    # Create Flask app
    app = Flask(__name__,
                template_folder='../templates',
                static_folder='../static')

    # Load configuration
    app.config.from_object(config_class)

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Initialize profanity filter
    profanity.load_censor_words()

    # Initialize extensions
    db.init_app(app)
    limiter.init_app(app)

    # Import models (ensures they're registered with SQLAlchemy)
    with app.app_context():
        from app import models

    # Register blueprints
    register_blueprints(app)

    # Register error handlers
    register_error_handlers(app)

    # Register template filters and context processors
    register_template_helpers(app)

    # Register middleware
    register_middleware(app)

    # Initialize services
    initialize_services(app)

    return app


def register_blueprints(app):
    """Register all Flask blueprints for routes"""
    # Import all blueprints
    from app.routes.main import main_bp
    from app.routes.auth import auth_bp
    from app.routes.clubs import clubs_bp
    from app.routes.admin import admin_bp
    from app.routes.api import api_bp
    from app.routes.chat import chat_bp
    from app.routes.attendance import attendance_bp
    from app.routes.status import status_bp
    from app.routes.oauth import oauth_bp

    # Register all blueprints
    # Note: URL prefixes are defined in the blueprint constructors where applicable
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(clubs_bp)
    app.register_blueprint(admin_bp)  # Prefix: /admin
    app.register_blueprint(api_bp)  # Prefix: /api
    app.register_blueprint(chat_bp)  # Routes: /api/club/<id>/chat/*
    app.register_blueprint(
        attendance_bp)  # Routes: /api/clubs/<id>/attendance/*
    app.register_blueprint(status_bp)  # Routes: /status, /admin/status/*
    app.register_blueprint(oauth_bp)  # Prefix: /oauth


def register_error_handlers(app):
    """Register error handlers for common HTTP errors"""
    from flask import render_template, jsonify, request

    @app.errorhandler(400)
    def bad_request(e):
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Bad request', 'message': str(e)}), 400
        try:
            return render_template(
                'errors/400.html',
                error_code=400,
                error_title='Bad Request',
                error_message=
                'The request could not be understood by the server.'), 400
        except:
            return '<h1>400 Bad Request</h1>', 400

    @app.errorhandler(403)
    def forbidden(e):
        if request.path.startswith('/api/'):
            return jsonify({
                'error':
                'Forbidden',
                'message':
                'You do not have permission to access this resource'
            }), 403
        try:
            return render_template(
                'errors/403.html',
                error_code=403,
                error_title='Forbidden',
                error_message=
                'You do not have permission to access this resource.'), 403
        except:
            return '<h1>403 Forbidden</h1>', 403

    @app.errorhandler(404)
    def not_found(e):
        if request.path.startswith('/api/'):
            return jsonify({
                'error': 'Not found',
                'message': 'The requested resource was not found'
            }), 404
        try:
            return render_template(
                'errors/404.html',
                error_code=404,
                error_title='Page Not Found',
                error_message='The page you are looking for does not exist.'
            ), 404
        except:
            return '<h1>404 Page Not Found</h1>', 404

    @app.errorhandler(429)
    def ratelimit_handler(e):
        if request.path.startswith('/api/'):
            return jsonify({
                'error': 'Too many requests',
                'message': 'Rate limit exceeded'
            }), 429
        try:
            return render_template(
                'errors/429.html',
                error_code=429,
                error_title='Too Many Requests',
                error_message=
                'You have made too many requests. Please try again later.'
            ), 429
        except:
            return '<h1>429 Too Many Requests</h1>', 429

    @app.errorhandler(401)
    def unauthorized(e):
        if request.path.startswith('/api/'):
            return jsonify({
                'error': 'Unauthorized',
                'message': 'Authentication is required'
            }), 401
        try:
            return render_template(
                'errors/401.html',
                error_code=401,
                error_title='Unauthorized',
                error_message='You need to be logged in to access this page.'
            ), 401
        except:
            return '<h1>401 Unauthorized</h1>', 401

    @app.errorhandler(405)
    def method_not_allowed(e):
        if request.path.startswith('/api/'):
            return jsonify({
                'error':
                'Method not allowed',
                'message':
                'The request method is not supported for this resource'
            }), 405
        try:
            return render_template(
                'errors/405.html',
                error_code=405,
                error_title='Method Not Allowed',
                error_message=
                'The request method is not supported for this resource.'), 405
        except:
            return '<h1>405 Method Not Allowed</h1>', 405

    @app.errorhandler(500)
    def internal_error(e):
        app.logger.error(f'Internal server error: {str(e)}')
        if request.path.startswith('/api/'):
            return jsonify({
                'error': 'Internal server error',
                'message': 'An unexpected error occurred'
            }), 500
        try:
            return render_template(
                'errors/500.html',
                error_code=500,
                error_title='Internal Server Error',
                error_message=
                'An unexpected error occurred. We have been notified and are working to fix it.'
            ), 500
        except:
            return '<h1>500 Internal Server Error</h1>', 500

    @app.errorhandler(503)
    def service_unavailable(e):
        if request.path.startswith('/api/'):
            return jsonify({
                'error': 'Service unavailable',
                'message': 'The service is temporarily unavailable'
            }), 503
        try:
            return render_template(
                'errors/503.html',
                error_code=503,
                error_title='Service Unavailable',
                error_message=
                'The service is temporarily unavailable. Please try again later.'
            ), 503
        except:
            return '<h1>503 Service Unavailable</h1>', 503


def register_template_helpers(app):
    """Register Jinja2 template filters and context processors"""
    from app.utils.sanitization import (markdown_to_html, sanitize_css_color,
                                        sanitize_css_value,
                                        sanitize_html_attribute, sanitize_url)
    from app.utils.auth_helpers import get_current_user
    from app.models.system import SystemSettings

    # Register custom Jinja2 filters
    app.jinja_env.filters['safe_css_color'] = sanitize_css_color
    app.jinja_env.filters['safe_css_value'] = sanitize_css_value
    app.jinja_env.filters['safe_html_attr'] = sanitize_html_attribute
    app.jinja_env.filters['safe_url'] = sanitize_url
    app.jinja_env.filters['markdown'] = markdown_to_html

    # Context processor for current user
    @app.context_processor
    def inject_user():
        return dict(current_user=get_current_user())

    # Context processor for system settings
    @app.context_processor
    def inject_system_settings():
        """Inject system settings helpers into templates"""
        return dict(
            is_maintenance_mode=SystemSettings.is_maintenance_mode(),
            is_economy_enabled=SystemSettings.is_economy_enabled(),
            is_mobile_enabled=SystemSettings.is_mobile_enabled(),
            economy_enabled=SystemSettings.is_economy_enabled(
            )  # Legacy compatibility
        )

    # Context processor for cosmetics functions
    @app.context_processor
    def inject_cosmetics_functions():
        """Inject cosmetics helper functions for templates"""
        import html
        from app.utils.sanitization import sanitize_html_attribute
        from app.models.club import MemberCosmetic
        from app.models.user import User

        def get_member_cosmetics(club_id, user_id):
            """Get cosmetic effects for a club member"""
            cosmetic = MemberCosmetic.query.filter_by(club_id=club_id,
                                                      user_id=user_id).first()
            return cosmetic.cosmetic_type if cosmetic else None

        def get_cosmetic_css_class(effects):
            """Convert cosmetic effects to CSS class"""
            if not effects:
                return ''
            # Map effects to CSS classes
            effect_classes = {
                'rainbow': 'rainbow-text',
                'glow': 'glow-text',
                'sparkle': 'sparkle-text',
                'fire': 'fire-text'
            }
            return effect_classes.get(effects, '')

        def apply_member_cosmetics(club_id, user_id, username):
            """Apply cosmetic effects to a member's username"""
            user = User.query.get(user_id)
            escaped_username = html.escape(username) if username else ''
            result = escaped_username

            # Check if user is admin and add lightning bolt
            if user and user.is_admin:
                result = f'{escaped_username} <i class="fas fa-bolt" style="color: #fbbf24; margin-left: 4px;" title="Admin"></i>'

            # Apply cosmetic effects
            effects = get_member_cosmetics(club_id, user_id)
            if effects:
                css_class = get_cosmetic_css_class(effects)
                if css_class:
                    safe_css_class = sanitize_html_attribute(css_class)
                    result = f'<span class="{safe_css_class}">{result}</span>'

            return result

        return dict(get_member_cosmetics=get_member_cosmetics,
                    get_cosmetic_css_class=get_cosmetic_css_class,
                    apply_member_cosmetics=apply_member_cosmetics)

    # Override url_for to provide backward compatibility for templates
    from flask import url_for as flask_url_for

    @app.context_processor
    def override_url_for():
        """Provide backward compatibility for old endpoint names"""

        def url_for_compat(endpoint, **values):
            # Map old endpoint names to new blueprint names
            endpoint_map = {
                # Static files
                'static': 'static',
                # Main routes
                'index': 'main.index',
                'dashboard': 'main.dashboard',
                'gallery': 'main.gallery',
                'leaderboard': 'main.leaderboard',
                'maintenance': 'main.maintenance',
                'account': 'main.account',
                'contact': 'main.contact',
                # Auth routes
                'login': 'auth.login',
                'logout': 'auth.logout',
                'signup': 'auth.signup',
                'forgot_password': 'auth.forgot_password',
                'reset_password': 'auth.reset_password',
                'verify_email': 'auth.verify_email',
                'verify_reset_code': 'auth.verify_reset_code',
                'verify_leader': 'auth.verify_leader',
                'setup_hackatime': 'auth.setup_hackatime',
                # Club routes
                'club_dashboard': 'main.club_dashboard',
                'club_shop': 'clubs.club_shop',
                'club_orders': 'clubs.club_orders',
                'poster_editor': 'clubs.poster_editor',
                'project_submission': 'clubs.project_submission',
                # Blog routes
                'blog': 'blog.blog_index',
                'blog_list': 'blog.blog_index',
                'blog_post': 'blog.blog_post',
                'blog_detail': 'blog.blog_post',
                'blog_create': 'blog.blog_create',
                'blog_edit': 'blog.blog_edit',
                'blog_delete': 'blog.blog_delete',
                # Admin routes
                'admin': 'admin.dashboard',
                'admin_dashboard': 'admin.dashboard',
                'admin_users': 'admin.admin_users',
                'admin_clubs': 'admin.admin_clubs',
                'admin_settings': 'admin.admin_settings',
            }

            # If endpoint is in map, use the new name, otherwise keep as-is
            endpoint = endpoint_map.get(endpoint, endpoint)

            return flask_url_for(endpoint, **values)

        return dict(url_for=url_for_compat)


def register_middleware(app):
    """Register middleware and before/after request handlers"""
    from flask import request, session
    from app.models.system import SystemSettings
    from app.utils.security import add_security_headers, get_real_ip

    @app.before_request
    def check_maintenance_mode():
        """Check if maintenance mode is enabled and redirect if necessary"""
        # Skip for maintenance page itself and static files
        if request.endpoint in ['main.maintenance', 'static']:
            return None

        if SystemSettings.is_maintenance_mode():
            # Allow admins to bypass maintenance mode
            from app.utils.auth_helpers import get_current_user
            user = get_current_user()
            if not user or not user.is_admin:
                from flask import render_template
                try:
                    return render_template('maintenance.html'), 503
                except:
                    # Fallback if template doesn't exist
                    return '<h1>System Maintenance</h1><p>We are currently performing maintenance. Please check back soon.</p>', 503

        return None

    @app.after_request
    def after_request(response):
        """Add security headers to all responses"""
        return add_security_headers(response)


def initialize_services(app):
    """Initialize external service integrations"""
    from app.services.airtable import AirtableService
    from app.services.hackatime import HackatimeService
    from app.services.identity import HackClubIdentityService
    # Initialize services with app context
    # Services will be accessible via their respective modules
    with app.app_context():
        # Services are initialized when imported
        # Additional initialization can be done here if needed
        pass
