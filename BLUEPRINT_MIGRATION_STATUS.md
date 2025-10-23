# Blueprint Migration Status

## Overview

The modularization of the Hack Club Dashboard has progressed to Phase 2: Route Blueprint Migration. Core routes have been extracted from the monolithic `main.py` into organized blueprints.

## Progress Summary

### ✅ Completed Blueprints (4 of ~10)

1. **Main Routes** (`app/routes/main.py`) - 11 routes
   - `/` - Home page
   - `/dashboard` - User dashboard
   - `/club-dashboard` - Club dashboard
   - `/club-dashboard/<int:club_id>` - Specific club dashboard
   - `/gallery` - Public gallery
   - `/leaderboard` - Leaderboard
   - `/leaderboard/<leaderboard_type>` - Specific leaderboard
   - `/join-club` - Join club redirect
   - `/maintenance` - Maintenance page
   - `/suspended` - Suspended account page
   - `/account` - Account settings

2. **Auth Routes** (`app/routes/auth.py`) - 13 routes
   - `/login` - User login
   - `/logout` - User logout
   - `/signup` - User registration
   - `/forgot-password` - Password reset request
   - `/reset-password` - Password reset form
   - `/verify-reset-code` - Verify reset code
   - `/auth/slack` - Slack OAuth initiation
   - `/auth/slack/callback` - Slack OAuth callback
   - `/complete-slack-signup` - Complete Slack signup
   - `/identity/callback` - Hack Club Identity callback
   - `/verify-leader` - Leader verification
   - `/complete-leader-signup` - Complete leader signup
   - `/setup-hackatime` - Hackatime setup

3. **Clubs Routes** (`app/routes/clubs.py`) - 6 routes
   - `/club-connection-required/<int:club_id>` - Connection required page
   - `/club/<int:club_id>/shop` - Club shop
   - `/club/<int:club_id>/orders` - Club orders
   - `/club/<int:club_id>/poster-editor` - Poster editor
   - `/club/<int:club_id>/project-submission` - Project submission
   - `/api/clubs/<int:club_id>/members` - Get members API

4. **Blog Routes** (`app/routes/blog.py`) - 4 routes
   - `/blog` - Blog index
   - `/blog/<slug>` - View blog post
   - `/blog/create` - Create blog post
   - `/blog/<slug>/edit` - Edit blog post
   - `/blog/<slug>/delete` - Delete blog post

### 📊 Statistics

- **Routes Migrated**: ~34 of 86 total routes
- **Progress**: ~40% complete
- **Blueprints Created**: 4
- **Lines of Code**: ~600 lines in blueprints

### 🚧 Remaining Blueprints (TODO)

1. **Admin Routes** (`app/routes/admin.py`) - Estimated 15-20 routes
   - Admin dashboard
   - User management
   - Club management
   - Pizza grant management
   - Order review
   - Project review
   - RBAC management
   - System settings
   - Statistics

2. **API Routes** (`app/routes/api.py`) - Estimated 10-15 routes
   - `/api/docs` - API documentation
   - `/api/admin/*` - Admin API endpoints
   - Public API endpoints
   - Mobile app endpoints

3. **Chat Routes** (`app/routes/chat.py`) - Estimated 5 routes
   - `/api/club/<int:club_id>/chat/messages` - Get/post messages
   - `/api/club/<int:club_id>/chat/messages/<int:message_id>` - Message operations
   - `/api/club/<int:club_id>/chat/upload-image` - Upload images

4. **Attendance Routes** (`app/routes/attendance.py`) - Estimated 10 routes
   - `/api/clubs/<int:club_id>/attendance/sessions` - Manage sessions
   - `/api/clubs/<int:club_id>/attendance/records` - Attendance records
   - `/api/clubs/<int:club_id>/attendance/guests` - Guest management
   - `/api/clubs/<int:club_id>/attendance/reports` - Reports
   - `/api/clubs/<int:club_id>/attendance/export` - Export data

5. **Status Routes** (`app/routes/status.py`) - Estimated 5 routes
   - `/status` - Public status page
   - Status API endpoints
   - Admin status management

6. **OAuth Routes** (`app/routes/oauth.py`) - Estimated 8 routes
   - `/oauth/authorize` - OAuth authorization
   - `/oauth/token` - Token endpoint
   - `/oauth/user` - User info endpoint
   - `/oauth/user/*` - User resource endpoints
   - OAuth debug endpoints

## File Structure

```
app/
└── routes/
    ├── __init__.py          # Exports all blueprints
    ├── main.py              # ✅ Main routes (11 routes)
    ├── auth.py              # ✅ Auth routes (13 routes)
    ├── clubs.py             # ✅ Club routes (6 routes)
    ├── blog.py              # ✅ Blog routes (4 routes)
    ├── admin.py             # 🚧 TODO: Admin routes
    ├── api.py               # 🚧 TODO: API routes
    ├── chat.py              # 🚧 TODO: Chat routes
    ├── attendance.py        # 🚧 TODO: Attendance routes
    ├── status.py            # 🚧 TODO: Status routes
    └── oauth.py             # 🚧 TODO: OAuth routes
```

## Blueprint Registration

Blueprints are registered in `app/__init__.py`:

```python
def register_blueprints(app):
    """Register all Flask blueprints for routes"""
    from app.routes.main import main_bp
    from app.routes.auth import auth_bp
    from app.routes.clubs import clubs_bp
    from app.routes.blog import blog_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(clubs_bp)
    app.register_blueprint(blog_bp)
```

## Testing Checklist

For each migrated blueprint, verify:

- [x] Routes are accessible at correct URLs
- [x] Decorators (@login_required, @admin_required) work
- [x] Database queries execute correctly
- [x] Templates render properly
- [ ] Flash messages display
- [ ] Redirects work correctly
- [ ] Error handlers trigger
- [ ] Rate limiting applies
- [ ] Session management works
- [ ] API responses match expected format

## Next Steps

### Immediate (Continue Migration)

1. **Create Admin Blueprint**
   - Extract admin routes from main.py
   - Organize by function (users, clubs, orders, settings)
   - Test admin panel access

2. **Create API Blueprint**
   - Extract public API routes
   - Extract admin API routes
   - Ensure API documentation works

3. **Create Chat Blueprint**
   - Extract chat message routes
   - Test real-time messaging
   - Verify image uploads

4. **Create Attendance Blueprint**
   - Extract attendance tracking routes
   - Test session management
   - Verify export functionality

5. **Create Status & OAuth Blueprints**
   - Extract status page routes
   - Extract OAuth server routes
   - Test OAuth flows

### Final Steps

1. **Remove Routes from main.py**
   - Once all routes migrated
   - Keep helper functions
   - Archive old main.py

2. **Update Documentation**
   - Update MODULARIZATION.md
   - Create migration guide
   - Document route organization

3. **Write Tests**
   - Unit tests for route handlers
   - Integration tests for workflows
   - API endpoint tests

## Benefits Realized

### Already Achieved ✅

1. **Better Organization**
   - Routes grouped by functionality
   - Easier to find specific endpoints
   - Clear separation of concerns

2. **Improved Maintainability**
   - Smaller, focused files
   - Easier to understand each blueprint
   - Simpler to modify specific features

3. **Team Collaboration**
   - Less merge conflicts
   - Clear ownership of features
   - Easier code reviews

### To Come 🎯

1. **Complete Testing**
   - Test each blueprint independently
   - Mock dependencies
   - Comprehensive coverage

2. **Performance Optimization**
   - Lazy loading of blueprints
   - Route-specific caching
   - Optimized imports

3. **Documentation**
   - API documentation per blueprint
   - Route documentation
   - Developer guides

## Migration Pattern

Each blueprint follows this pattern:

```python
"""
[Blueprint Name] routes blueprint for the Hack Club Dashboard.
[Description of what this blueprint handles]
"""

from flask import Blueprint, ...
from app.decorators.auth import login_required, ...
from app.utils... import ...
from app.models... import ...

[name]_bp = Blueprint('[name]', __name__)

@[name]_bp.route('/route')
@decorators
def route_handler():
    # Handler logic
    pass
```

## Common Imports

All blueprints commonly use:

```python
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from extensions import db, limiter
from app.decorators.auth import login_required, admin_required
from app.utils.auth_helpers import get_current_user
from app.utils.sanitization import sanitize_string, sanitize_url
from app.models.[domain] import Model1, Model2
```

## URL Structure

Blueprints maintain the original URL structure:

- Main routes: `/`, `/dashboard`, etc. (no prefix)
- Auth routes: `/login`, `/signup`, `/auth/*` (no prefix)
- Club routes: `/club/*` (no prefix, for compatibility)
- Blog routes: `/blog`, `/blog/*` (no prefix)
- Admin routes: `/admin/*` (TODO)
- API routes: `/api/*` (TODO)
- Chat routes: `/api/club/*/chat/*` (TODO)

## Notes

1. **Backward Compatibility**: All URLs remain unchanged
2. **No Breaking Changes**: Existing functionality preserved
3. **Gradual Migration**: Can deploy incrementally
4. **Original main.py**: Kept as reference and backup

## Questions & Issues

### How to test blueprints?

```bash
# Test import
python -c "from app.routes.main import main_bp; print('OK')"

# Test app creation
python -c "from app import create_app; app = create_app(); print('OK')"

# Run app
python -c "from app import create_app; app = create_app(); app.run(debug=True)"
```

### How to add a new route?

1. Determine which blueprint it belongs to
2. Add route handler to that blueprint file
3. No need to register - blueprint already registered
4. Test the new route

### How to modify an existing route?

1. Find the route in appropriate blueprint
2. Make changes
3. Test thoroughly
4. Deploy

---

**Status**: 🚧 Phase 2 - Blueprint Migration In Progress (40% complete)
**Next Milestone**: Complete Admin & API blueprints (60% total)
**End Goal**: All 86 routes in organized blueprints (100%)
