# Application Modularization Guide

## Overview

The Hack Club Dashboard application has been partially modularized to improve code organization, maintainability, and testability. This document describes the new structure and provides guidance for completing the modularization.

## Current Structure

```
├── app/
│   ├── __init__.py          # Application factory (ready for blueprints)
│   ├── decorators/          # Authentication and authorization decorators
│   │   ├── __init__.py
│   │   ├── auth.py          # login_required, admin_required, etc.
│   │   ├── economy.py       # economy_required decorator
│   │   └── rate_limit.py    # Rate limiting decorators
│   ├── models/              # Database models
│   │   ├── __init__.py
│   │   ├── user.py          # User, Role, Permission, AuditLog
│   │   ├── auth.py          # APIKey, OAuth models
│   │   ├── club.py          # Club, ClubMembership, Cosmetics
│   │   ├── club_content.py  # Posts, Assignments, Meetings, Resources
│   │   ├── slack.py         # Slack integration models
│   │   ├── chat.py          # Chat messages
│   │   ├── attendance.py    # Attendance tracking
│   │   ├── economy.py       # Transactions, Quests, Projects
│   │   ├── gallery.py       # Gallery posts
│   │   ├── blog.py          # Blog posts and categories
│   │   └── system.py        # System settings and status
│   ├── routes/              # Route blueprints (TODO: to be created)
│   │   └── __init__.py
│   ├── services/            # External service integrations
│   │   ├── __init__.py
│   │   ├── airtable.py      # Airtable/Pizza grants
│   │   ├── hackatime.py     # Hackatime integration
│   │   ├── identity.py      # Hack Club Identity OAuth
│   │   └── slack_oauth.py   # Slack OAuth
│   └── utils/               # Utility functions
│       ├── __init__.py
│       ├── formatting.py    # Markdown conversion, formatting
│       ├── sanitization.py  # Input sanitization
│       ├── security.py      # Security validation, headers
│       ├── club_helpers.py  # Club membership/leadership checks
│       ├── auth_helpers.py  # Authentication helpers
│       └── economy_helpers.py # Transaction and quest helpers
├── config.py                # Application configuration
├── extensions.py            # Flask extensions (db, limiter)
├── main.py                  # Original monolithic application (16,220 lines)
├── main_refactored.py       # Partially refactored version using modules
└── main_new.py              # Application factory approach (experimental)
```

## What Has Been Modularized

### ✅ Completed

1. **Configuration** (`config.py`)
   - Database URL configuration
   - Secret key generation
   - Configuration class

2. **Extensions** (`extensions.py`)
   - SQLAlchemy database instance
   - Flask-Limiter rate limiting

3. **Models** (`app/models/`)
   - All database models extracted and organized by domain
   - Models are properly imported and registered with SQLAlchemy

4. **Utilities** (`app/utils/`)
   - Formatting utilities (markdown conversion)
   - Sanitization functions (XSS prevention, CSS/URL sanitization)
   - Security utilities (profanity check, exploit detection, security headers)
   - Club helpers (leadership verification)
   - Auth helpers (session management)
   - Economy helpers (transactions, quests)

5. **Decorators** (`app/decorators/`)
   - Authentication decorators
   - Permission and role-based access control
   - Economy system protection

6. **Services** (`app/services/`)
   - External service integrations extracted
   - Airtable, Hackatime, Identity, Slack OAuth

7. **Application Factory** (`app/__init__.py`)
   - Factory function ready for blueprint registration
   - Error handlers configured
   - Template helpers registered
   - Middleware configured

### 🚧 In Progress / TODO

1. **Routes** (`app/routes/` - NOT YET CREATED)
   - 86 routes still in `main.py` need to be migrated to blueprints
   - Suggested blueprint organization:
     - `main.py` - Home, dashboard, general pages
     - `auth.py` - Login, signup, password reset, Slack/Identity OAuth
     - `clubs.py` - Club management, shop, poster editor
     - `chat.py` - Club chat API
     - `attendance.py` - Attendance tracking API
     - `blog.py` - Blog posts and categories
     - `admin.py` - Admin panel, user management, pizza grants
     - `api.py` - Public API endpoints
     - `status.py` - Status page
     - `oauth.py` - OAuth authorization endpoints

2. **Main Entry Point**
   - `main.py` - Original file (keep as backup)
   - `main_refactored.py` - Uses modular components but keeps routes inline
   - `main_new.py` - Application factory approach (experimental)

## Migration Strategy

### Phase 1: Immediate Use ✅ COMPLETE

Use `main_refactored.py` which:
- Imports all modularized components
- Keeps routes inline for backward compatibility
- Provides immediate benefits of organized code
- No breaking changes

**To use:** Copy all routes from `main.py` (lines 4292-end) into `main_refactored.py`

### Phase 2: Gradual Blueprint Migration (Recommended Next Step)

1. Choose a route group (e.g., auth routes)
2. Create blueprint file (e.g., `app/routes/auth.py`)
3. Move routes to blueprint
4. Register blueprint in `app/__init__.py`
5. Test thoroughly
6. Repeat for other route groups

Example blueprint structure:

```python
# app/routes/auth.py
from flask import Blueprint, render_template, request, redirect, flash
from app.decorators.auth import login_required
from app.utils.auth_helpers import login_user, logout_user

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # ... login logic ...
    pass

@auth_bp.route('/logout')
@login_required
def logout():
    # ... logout logic ...
    pass
```

Register in `app/__init__.py`:

```python
def register_blueprints(app):
    from app.routes.auth import auth_bp
    app.register_blueprint(auth_bp)
```

### Phase 3: Full Application Factory

Once all routes are in blueprints:
1. Use `app/__init__.py` as the sole application creation point
2. Create simple `main.py` that just does:
   ```python
   from app import create_app
   app = create_app()
   ```
3. Archive old `main.py`

## Benefits of Modularization

1. **Better Organization** - Related code grouped together
2. **Easier Testing** - Individual components can be tested in isolation
3. **Improved Maintainability** - Smaller files are easier to understand
4. **Reduced Code Duplication** - Shared utilities in one place
5. **Clearer Dependencies** - Import statements show relationships
6. **Scalability** - Easy to add new features without growing main.py

## Important Notes

1. **Backward Compatibility** - The current structure maintains full backward compatibility
2. **No Breaking Changes** - Existing functionality remains unchanged
3. **Gradual Migration** - Routes can be migrated incrementally
4. **Database** - All models work identically to before
5. **Services** - External service integrations preserved

## Testing Checklist

When migrating routes to blueprints, verify:

- [ ] Route URLs match original
- [ ] Decorators work correctly
- [ ] Database queries function properly
- [ ] Template rendering works
- [ ] Flash messages appear
- [ ] Redirects go to correct locations
- [ ] API responses match expected format
- [ ] Error handlers trigger appropriately
- [ ] Rate limiting applies correctly
- [ ] Session management works

## Next Steps

1. Review and test `main_refactored.py`
2. Choose first route group to migrate (recommend: auth routes)
3. Create blueprint and test thoroughly
4. Continue with other route groups
5. Update deployment configuration if needed

## Questions?

Refer to Flask documentation on blueprints:
https://flask.palletsprojects.com/en/2.3.x/blueprints/
