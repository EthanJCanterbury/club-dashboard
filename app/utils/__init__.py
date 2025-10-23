"""
Utility functions for the Hack Club Dashboard.
"""

from app.utils.formatting import *
from app.utils.sanitization import *
from app.utils.security import *
from app.utils.auth_helpers import *
from app.utils.club_helpers import *
from app.utils.economy_helpers import *

__all__ = [
    # Formatting
    'format_date', 'format_datetime', 'format_currency',
    # Sanitization
    'sanitize_string', 'sanitize_css_value', 'sanitize_css_color',
    'sanitize_html_attribute', 'sanitize_url', 'markdown_to_html',
    # Security
    'get_real_ip', 'log_security_event', 'add_security_headers',
    'validate_security_input', 'check_profanity', 'check_content_safety',
    # Auth helpers
    'get_current_user', 'is_authenticated', 'login_user', 'logout_user',
    # Club helpers
    'get_user_club', 'check_club_permission',
    # Economy helpers
    'process_transaction', 'check_quest_completion', 'award_quest_tokens',
]
