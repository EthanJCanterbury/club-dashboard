"""
Route blueprints for the Hack Club Dashboard.

This package contains all Flask blueprints organized by functionality:
- main: Home, dashboard, gallery, leaderboard
- auth: Login, signup, OAuth flows
- clubs: Club management, shop, projects
- blog: Blog posts and categories
- admin: Admin panel (TODO)
- api: Public API endpoints (TODO)
- chat: Club chat functionality (TODO)
- attendance: Attendance tracking (TODO)
- status: Status page (TODO)
- oauth: OAuth authorization server (TODO)
"""

from app.routes.main import main_bp
from app.routes.auth import auth_bp
from app.routes.clubs import clubs_bp
from app.routes.blog import blog_bp

__all__ = [
    'main_bp',
    'auth_bp',
    'clubs_bp',
    'blog_bp',
]
