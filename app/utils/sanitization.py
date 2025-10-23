"""
Sanitization utilities for the Hack Club Dashboard.
Contains functions for sanitizing various types of user input to prevent XSS and injection attacks.
"""

import html
import re
import urllib.parse
import markdown
from markdown.extensions import codehilite
import bleach


def sanitize_string(value, max_length=None, allow_html=False):
    """Sanitize string input to prevent XSS and injection attacks"""
    if not value:
        return value

    # Convert to string if not already
    value = str(value).strip()

    # Limit length if specified
    if max_length and len(value) > max_length:
        value = value[:max_length]

    # Remove or escape HTML/script tags
    if not allow_html:
        # Remove script tags completely
        value = re.sub(r'<script[^>]*>.*?</script>', '', value, flags=re.IGNORECASE | re.DOTALL)
        # Remove other potentially dangerous tags
        value = re.sub(r'<(script|iframe|object|embed|form|input|button|link|style)[^>]*>', '', value, flags=re.IGNORECASE)
        # Escape remaining HTML
        value = html.escape(value)

    # Remove null bytes and other control characters
    value = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', value)

    return value


def sanitize_css_value(value, max_length=None):
    """Sanitize CSS values to prevent CSS injection attacks"""
    if not value:
        return value

    value = str(value).strip()

    # Limit length if specified
    if max_length and len(value) > max_length:
        value = value[:max_length]

    # Remove dangerous CSS patterns that could lead to XSS
    # Remove javascript: URLs
    value = re.sub(r'javascript:', '', value, flags=re.IGNORECASE)
    # Remove data: URLs (except safe image types)
    value = re.sub(r'data:(?!image/(png|jpeg|jpg|gif|webp|svg\+xml))', '', value, flags=re.IGNORECASE)
    # Remove expression() which can execute JavaScript in IE
    value = re.sub(r'expression\s*\(', '', value, flags=re.IGNORECASE)
    # Remove @import which could load external CSS
    value = re.sub(r'@import', '', value, flags=re.IGNORECASE)
    # Remove url() with non-safe protocols
    value = re.sub(r'url\s*\(\s*["\']?(?!https?:)[^)]*["\']?\s*\)', '', value, flags=re.IGNORECASE)
    # Remove semicolons and other characters that could break out of CSS context
    value = re.sub(r'[;"{}]', '', value)
    # Remove control characters
    value = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', value)

    return value


def sanitize_css_color(value):
    """Sanitize CSS color values specifically"""
    if not value:
        return value

    value = str(value).strip()

    # Only allow safe color formats
    # Hex colors (#rgb, #rrggbb, #rrggbbaa)
    hex_pattern = r'^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$'
    # RGB/RGBA colors
    rgb_pattern = r'^rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*(?:,\s*[01]?\.?\d*)?\s*\)$'
    # HSL/HSLA colors
    hsl_pattern = r'^hsla?\(\s*(\d{1,3})\s*,\s*(\d{1,3})%\s*,\s*(\d{1,3})%\s*(?:,\s*[01]?\.?\d*)?\s*\)$'
    # Named colors (basic set)
    named_colors = ['transparent', 'black', 'white', 'red', 'green', 'blue', 'yellow', 'orange', 'purple', 'pink', 'gray', 'grey', 'brown']

    if re.match(hex_pattern, value):
        return value
    elif re.match(rgb_pattern, value):
        return value
    elif re.match(hsl_pattern, value):
        return value
    elif value.lower() in named_colors:
        return value
    else:
        # Return a safe default if the color format is invalid
        return '#000000'


def sanitize_html_attribute(value, max_length=None):
    """Sanitize values for HTML attributes to prevent attribute injection"""
    if not value:
        return value

    value = str(value).strip()

    # Limit length if specified
    if max_length and len(value) > max_length:
        value = value[:max_length]

    # Remove quotes and other characters that could break out of attribute context
    value = re.sub(r'["\'><=&]', '', value)
    # Remove control characters
    value = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', value)
    # Remove potential JavaScript event attributes
    value = re.sub(r'\bon[a-z]+\s*=', '', value, flags=re.IGNORECASE)

    return value


def sanitize_url(value, max_length=None):
    """Sanitize URLs to prevent JavaScript injection and other attacks"""
    if not value:
        return value

    value = str(value).strip()

    # Limit length if specified
    if max_length and len(value) > max_length:
        value = value[:max_length]

    # Only allow safe URL schemes
    allowed_schemes = ['http', 'https', 'mailto', 'tel']

    # Parse URL to check scheme
    try:
        parsed = urllib.parse.urlparse(value)
        if parsed.scheme and parsed.scheme.lower() not in allowed_schemes:
            return '#'  # Return safe default

        # Ensure the URL doesn't contain dangerous patterns
        if 'javascript:' in value.lower() or 'data:' in value.lower() or 'vbscript:' in value.lower():
            return '#'

        return value
    except:
        return '#'  # Return safe default if URL parsing fails


def markdown_to_html(markdown_content):
    """Convert markdown to safe HTML for club posts"""
    if not markdown_content:
        return ""
    
    # Configure markdown with safe extensions
    md = markdown.Markdown(extensions=['extra', 'codehilite', 'nl2br'], 
                          extension_configs={
                              'codehilite': {
                                  'css_class': 'highlight',
                                  'use_pygments': False
                              }
                          })
    
    # Convert markdown to HTML
    html_content = md.convert(markdown_content)
    
    # Define allowed HTML tags and attributes for club posts
    allowed_tags = [
        'p', 'br', 'strong', 'b', 'em', 'i', 'u', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'ul', 'ol', 'li', 'blockquote', 'code', 'pre', 'a', 'img',
        'table', 'thead', 'tbody', 'tr', 'th', 'td', 'hr', 'del', 'ins'
    ]
    
    allowed_attributes = {
        'a': ['href', 'title'],
        'img': ['src', 'alt', 'title', 'width', 'height'],
        'code': ['class'],
        'pre': ['class'],
        'th': ['align'],
        'td': ['align']
    }
    
    # Clean HTML with bleach to prevent XSS
    clean_html = bleach.clean(html_content, 
                             tags=allowed_tags, 
                             attributes=allowed_attributes,
                             protocols=['http', 'https', 'mailto'])
    
    return clean_html
