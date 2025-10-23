"""
Decorators for the Hack Club Dashboard.

This package contains various decorators for authentication, authorization,
rate limiting, and feature toggling.
"""

from app.decorators.auth import (
    login_required,
    permission_required,
    role_required,
    admin_required,
    reviewer_required,
    api_key_required,
    oauth_required
)
from app.decorators.economy import economy_required

__all__ = [
    # Authentication decorators
    'login_required',
    'permission_required',
    'role_required',
    'admin_required',
    'reviewer_required',
    'api_key_required',
    'oauth_required',
    # Economy decorators
    'economy_required',
]
