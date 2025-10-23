"""
Hack Club Dashboard - Main Application Entry Point

This is the entry point for the Flask application. It creates the app using
the application factory pattern and registers all routes, blueprints, and services.
"""

import os
from app import create_app
from extensions import db

# Create the Flask application
app = create_app()

# Import all routes - these will be migrated to blueprints gradually
# For now, we need to keep the old routes functional while we migrate
with app.app_context():
    # Import models to ensure they're registered
    from app import models

    # Import services and initialize with app
    from app.services.airtable import AirtableService
    from app.services.hackatime import HackatimeService
    from app.services.identity import HackClubIdentityService
    from app.services.slack_oauth import SlackOAuthService

    # Set app references for services that need them
    import app.services.hackatime as hackatime_module
    import app.services.identity as identity_module
    import app.services.slack_oauth as slack_module

    hackatime_module.app = app
    identity_module.app = app
    identity_module.HACKCLUB_IDENTITY_URL = os.getenv('HACKCLUB_IDENTITY_URL', 'https://identity.hackclub.com')
    slack_module.app = app

    # Import and register all route functions from old main.py
    # TODO: These will be moved to blueprints in app/routes/
    # For now, we import them to maintain backward compatibility
    try:
        # This will import all the route definitions from the old main
        # We'll need to refactor these into blueprints gradually
        pass
    except Exception as e:
        app.logger.error(f"Error importing routes: {e}")

if __name__ == '__main__':
    # Run the application
    # In production, this should be run with a WSGI server like gunicorn
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('FLASK_DEBUG', 'False') == 'True')
