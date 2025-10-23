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
    app = Flask(__name__, template_folder='../templates', static_folder='../static')

    # Load configuration
    app.config.from_object(config_class)

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

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
    # Import blueprints
    from app.routes.main import main_bp
    from app.routes.auth import auth_bp
    from app.routes.clubs import clubs_bp
    from app.routes.blog import blog_bp

    # Register blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(clubs_bp)
    app.register_blueprint(blog_bp)

    # TODO: Create and register additional blueprints
    # from app.routes.chat import chat_bp
    # from app.routes.attendance import attendance_bp
    # from app.routes.admin import admin_bp
    # from app.routes.api import api_bp
    # from app.routes.status import status_bp
    # from app.routes.oauth import oauth_bp

    # app.register_blueprint(chat_bp, url_prefix='/api/club')
    # app.register_blueprint(attendance_bp, url_prefix='/api/clubs')
    # app.register_blueprint(admin_bp, url_prefix='/admin')
    # app.register_blueprint(api_bp, url_prefix='/api')
    # app.register_blueprint(status_bp)
    # app.register_blueprint(oauth_bp, url_prefix='/oauth')


def register_error_handlers(app):
    """Register error handlers for common HTTP errors"""
    from flask import render_template, jsonify, request

    @app.errorhandler(400)
    def bad_request(e):
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Bad request', 'message': str(e)}), 400
        return render_template('error.html', error_code=400, error_message='Bad Request'), 400

    @app.errorhandler(403)
    def forbidden(e):
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Forbidden', 'message': 'You do not have permission to access this resource'}), 403
        return render_template('error.html', error_code=403, error_message='Forbidden'), 403

    @app.errorhandler(404)
    def not_found(e):
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Not found', 'message': 'The requested resource was not found'}), 404
        return render_template('error.html', error_code=404, error_message='Page Not Found'), 404

    @app.errorhandler(429)
    def ratelimit_handler(e):
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Too many requests', 'message': 'Rate limit exceeded'}), 429
        return render_template('error.html', error_code=429, error_message='Too Many Requests'), 429

    @app.errorhandler(500)
    def internal_error(e):
        app.logger.error(f'Internal server error: {str(e)}')
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Internal server error', 'message': 'An unexpected error occurred'}), 500
        return render_template('error.html', error_code=500, error_message='Internal Server Error'), 500


def register_template_helpers(app):
    """Register Jinja2 template filters and context processors"""
    from app.utils.formatting import markdown_to_html
    from app.utils.sanitization import (
        sanitize_css_color,
        sanitize_css_value,
        sanitize_html_attribute,
        sanitize_url
    )
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
        settings = SystemSettings.query.first()
        if not settings:
            settings = SystemSettings()
            db.session.add(settings)
            db.session.commit()
        return dict(system_settings=settings)


def register_middleware(app):
    """Register middleware and before/after request handlers"""
    from flask import request, session
    from app.models.system import SystemSettings
    from app.utils.security import add_security_headers, get_real_ip

    @app.before_request
    def check_maintenance_mode():
        """Check if maintenance mode is enabled and redirect if necessary"""
        # Skip for maintenance page itself and static files
        if request.endpoint in ['maintenance', 'static']:
            return None

        settings = SystemSettings.query.first()
        if settings and settings.maintenance_mode:
            # Allow admins to bypass maintenance mode
            from app.utils.auth_helpers import get_current_user
            user = get_current_user()
            if not user or not user.is_admin:
                from flask import render_template
                return render_template('maintenance.html'), 503

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
    from app.services.slack_oauth import SlackOAuthService

    # Initialize services with app context
    # Services will be accessible via their respective modules
    with app.app_context():
        # Services are initialized when imported
        # Additional initialization can be done here if needed
        pass
