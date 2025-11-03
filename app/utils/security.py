"""
Security utilities for the Hack Club Dashboard.
Contains functions for security validation, profanity checking, and exploit detection.
"""

import re
import logging
from flask import request
from better_profanity import profanity

# Try to import profanity_check if available
try:
    import profanity_check
    PROFANITY_CHECK_AVAILABLE = True
except ImportError:
    PROFANITY_CHECK_AVAILABLE = False

# Initialize profanity filters
profanity.load_censor_words()


def get_real_ip():
    """Get the real client IP address, accounting for proxies and load balancers"""
    # Check common proxy headers in order of preference
    if request.headers.get('CF-Connecting-IP'):
        return request.headers.get('CF-Connecting-IP')
    elif request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP')
    elif request.headers.get('X-Forwarded-For'):
        # X-Forwarded-For can contain multiple IPs, get the first one (original client)
        forwarded_ips = request.headers.get('X-Forwarded-For').split(',')
        return forwarded_ips[0].strip()
    elif request.headers.get('X-Forwarded-Proto'):
        return request.headers.get('X-Client-IP', request.remote_addr)
    else:
        return request.remote_addr


def log_security_event(event_type, message, user_id=None, ip_address=None, app=None):
    """Log security-related events for monitoring"""
    if not ip_address:
        ip_address = get_real_ip() if request else 'unknown'

    security_message = f"SECURITY EVENT - {event_type}: {message} | User ID: {user_id} | IP: {ip_address}"

    if app:
        app.logger.warning(security_message)
    else:
        logging.warning(security_message)


def check_profanity_comprehensive(text):
    """
    Less strict profanity detection to avoid false positives with names.
    Returns True if clear profanity is detected, False otherwise.
    """
    if not text or not isinstance(text, str):
        return False

    # Normalize text for better detection
    normalized_text = text.lower().strip()

    # Common false positive patterns (names, etc.) to exclude
    false_positive_patterns = [
        r'\b(shi|wang|dong|hung|peng|ling|chen|chan|chang|cheng|jung|sung|young|long|wong|tong|kong|song|pong|ding|ming|jing|king|ping|zing|ring|wing|yang|gang|bang|fang|dang|sang|tang|hang|lang|mang|nang|pang|rang|vang|zang)\b',
        r'\b(kumar|singh|shah|khan|ali|hassan|hussain|ahmad|ahmed)\b',
        r'\b(analytic|analytics|arsenal|assassin|bass|class|glass|mass|pass|brass)\b',
        r'\b(scunthorpe|shitake|shiitake|shitzu|shihtzu)\b'  # Common false positives
    ]

    # Check if text matches common false positive patterns
    for pattern in false_positive_patterns:
        if re.search(pattern, normalized_text, re.IGNORECASE):
            return False

    # Only use the basic profanity filter, skip aggressive detection methods
    if profanity.contains_profanity(normalized_text):
        # Allow mild words like 'screw', 'crap', 'damn', 'hell' in appropriate contexts
        mild_words = ['screw', 'crap', 'damn', 'hell', 'suck', 'sucks']
        if normalized_text.strip() in mild_words:
            return False
        return True

    # Only check spaced out words if they're clearly intentional profanity
    # (require at least 3 spaces to avoid false positives)
    spaced_pattern = re.findall(r'\b\w(?:\s+\w){3,}\b', normalized_text)
    for spaced_word in spaced_pattern:
        no_spaces = re.sub(r'\s+', '', spaced_word)
        if profanity.contains_profanity(no_spaces):
            return True

    return False


def filter_profanity_comprehensive(text, replacement="***"):
    """
    Filter profanity with comprehensive evasion detection and replacement.
    Returns the filtered text or raises ValueError if profanity is detected.
    """
    if not text or not isinstance(text, str):
        return text

    if check_profanity_comprehensive(text):
        raise ValueError("Content contains inappropriate language")

    return text


def validate_username(username):
    """Validate username format"""
    if not username:
        return False, "Username is required"

    username = username.strip()
    if len(username) < 3:
        return False, "Username must be at least 3 characters long"
    if len(username) > 30:
        return False, "Username must be less than 30 characters"

    # Only allow alphanumeric characters, underscores, and hyphens
    if not re.match(r'^[a-zA-Z0-9_-]+$', username):
        return False, "Username can only contain letters, numbers, underscores, and hyphens"

    return True, username


def validate_email(email):
    """Validate email format"""
    if not email:
        return False, "Email is required"

    email = email.strip().lower()
    if len(email) > 120:
        return False, "Email is too long"

    # Basic email validation
    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_regex, email):
        return False, "Invalid email format"

    return True, email


def validate_name(name, field_name="Name"):
    """Validate first/last name"""
    if not name:
        return True, ""  # Names are optional

    name = name.strip()
    if len(name) > 50:
        return False, f"{field_name} must be less than 50 characters"

    # Only allow letters, spaces, hyphens, and apostrophes
    if not re.match(r"^[a-zA-Z\s'-]+$", name):
        return False, f"{field_name} can only contain letters, spaces, hyphens, and apostrophes"

    return True, name


def validate_password(password):
    """Validate password strength"""
    if not password:
        return False, "Password is required"

    if len(password) < 8:
        return False, "Password must be at least 8 characters long"

    if len(password) > 128:
        return False, "Password must be less than 128 characters"

    # Check against common weak passwords
    common_passwords = {
        'password', 'password123', '12345678', 'qwertyui', 'qwerty123',
        'admin123', 'welcome123', 'hackclub123', 'password1', '123456789',
        'letmein123', 'password!', 'Welcome123', 'Password123'
    }

    if password.lower() in common_passwords:
        return False, "Password is too common. Please choose a more secure password."

    # Check for at least one uppercase, lowercase, digit, and special character
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password)

    if not (has_upper and has_lower and has_digit and has_special):
        return False, "Password must contain at least one uppercase letter, lowercase letter, digit, and special character"

    return True, password


def suspend_user_for_security_violation(user, violation_type, details="", db=None, app=None, create_audit_log=None):
    """Suspend a user for security violations with logging"""
    if not user or user.is_admin:
        return False  # Don't suspend admins

    try:
        user.is_suspended = True
        if db:
            db.session.commit()

        # Log the security violation in audit log
        if create_audit_log:
            create_audit_log(
                action_type='security_violation',
                description=f"User suspended for {violation_type}",
                user=user,
                target_type='user',
                target_id=user.id,
                details={
                    'violation_type': violation_type,
                    'details': details,
                    'action_taken': 'account_suspended'
                },
                severity='critical',
                category='security'
            )

        # Also log the security event (existing system)
        log_security_event(
            violation_type,
            f"User suspended: {details}",
            user_id=user.id,
            ip_address=get_real_ip(),
            app=app
        )

        if app:
            app.logger.warning(f"SECURITY SUSPENSION - User {user.username} (ID: {user.id}) suspended for {violation_type}: {details}")
        return True
    except Exception as e:
        if app:
            app.logger.error(f"Error suspending user {user.id}: {str(e)}")
        return False


def detect_exploit_attempts(text, field_context=""):
    """Detect common exploit and penetration testing attempts with context awareness"""
    if not text or not isinstance(text, str):
        return False, ""

    text_lower = text.lower().strip()

    # More lenient patterns for assignment, meeting, and resource content
    is_content_field = any(keyword in field_context.lower() for keyword in ["assignment", "meeting", "resource", "club_post"])

    # SQL Injection patterns
    sql_patterns = [
        r"union\s+select", r"drop\s+table", r"delete\s+from", r"insert\s+into",
        r"alter\s+table", r"create\s+table", r"exec\s*\(",
        r"'.*or.*'", r"'.*and.*'", r"--", r"/\*.*\*/", r"xp_cmdshell",
        r"sp_executesql", r"information_schema", r"sysobjects", r"syscolumns"
    ]

    # Only flag "update.*set" if it's not content field
    if not is_content_field:
        sql_patterns.append(r"update\s+.*set")

    # XSS patterns
    xss_patterns = [
        r"<script", r"javascript:", r"vbscript:", r"onload=", r"onerror=",
        r"onclick=", r"onmouseover=", r"alert\s*\(", r"document\.cookie",
        r"eval\s*\(", r"fromcharcode", r"<iframe", r"<object", r"<embed"
    ]

    # Command injection patterns - more restrictive for content fields
    if is_content_field:
        cmd_patterns = [
            r";\s*rm\s+[^\s]", r";\s*ls\s+[^\s]", r";\s*pwd\s", r";\s*id\s",
            r"&&\s*rm\s+", r"\|\s*rm\s+", r">\s*/dev/null", r"2>&1", r"/etc/passwd",
            r"/bin/sh", r"/bin/bash", r"curl\s+http", r"wget\s+http", r"nc\s+-"
        ]
    else:
        cmd_patterns = [
            r";\s*rm\s+", r";\s*cat\s+", r";\s*ls\s+", r";\s*pwd", r";\s*id",
            r"&&\s*rm\s+", r"\|\s*rm\s+", r">\s*/dev/null", r"2>&1", r"/etc/passwd",
            r"/bin/sh", r"/bin/bash", r"curl\s+", r"wget\s+", r"nc\s+-"
        ]

    # Path traversal patterns
    path_patterns = [
        r"\.\.\/", r"\.\.\\", r"..%2f", r"..%5c", r"~root", r"~admin",
        r"/etc/", r"/proc/", r"/sys/", r"c:\\windows", r"c:\\users"
    ]

    # LDAP injection patterns
    ldap_patterns = [
        r"\(\|", r"\(&", r"\(!", r"\*\)", r"admin\)", r"user\)", r"password\)"
    ]

    # File inclusion patterns - http/https are legitimate protocols, not file inclusion attacks
    file_patterns = [
        r"php://", r"file://", r"ftp://",
        r"include\s*\(", r"require\s*\(", r"include_once", r"require_once"
    ]

    all_patterns = {
        "SQL Injection": sql_patterns,
        "XSS": xss_patterns,
        "Command Injection": cmd_patterns,
        "Path Traversal": path_patterns,
        "LDAP Injection": ldap_patterns,
        "File Inclusion": file_patterns
    }

    for exploit_type, patterns in all_patterns.items():
        for pattern in patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return True, exploit_type

    return False, ""


def detect_enumeration_attempts(text, field_context=""):
    """Detect reconnaissance and enumeration attempts with context awareness"""
    if not text or not isinstance(text, str):
        return False, ""

    text_lower = text.lower().strip()

    # Be much more lenient for content fields
    is_content_field = any(keyword in field_context.lower() for keyword in ["assignment", "meeting", "resource", "club_post"])

    if is_content_field:
        # Only flag obvious enumeration patterns in content fields
        enum_patterns = [
            r"information_schema", r"sysobjects", r"syscolumns",
            r"web\.config", r"\.htaccess", r"wp-config"
        ]

        suspicious_files = [
            r"passwords?\.txt", r"secrets\.txt", r"\.env"
        ]

        # Much higher threshold for content fields
        enum_count = sum(1 for pattern in enum_patterns if re.search(pattern, text_lower))
        file_count = sum(1 for pattern in suspicious_files if re.search(pattern, text_lower))

        if enum_count >= 2 or file_count >= 2:
            return True, "Enumeration"
    else:
        # Original strict patterns for other content
        enum_patterns = [
            r"admin", r"administrator", r"root", r"test", r"guest", r"user",
            r"backup", r"temp", r"demo", r"default", r"service", r"oracle",
            r"mysql", r"postgres", r"database", r"db", r"config", r"conf"
        ]

        suspicious_files = [
            r"web\.config", r"\.htaccess", r"config\.php", r"wp-config",
            r"database\.yml", r"settings\.py", r"\.env", r"secrets",
            r"passwords?\.txt", r"users?\.txt", r"backup", r"dump"
        ]

        enum_count = sum(1 for pattern in enum_patterns if re.search(pattern, text_lower))
        file_count = sum(1 for pattern in suspicious_files if re.search(pattern, text_lower))

        if enum_count >= 3 or file_count >= 2:
            return True, "Enumeration"

    return False, ""


def validate_input_with_security(text, field_name="input", user=None, max_length=None,
                                 app=None, create_audit_log=None, sanitize_string=None,
                                 suspend_user_func=None):
    """Comprehensive input validation with auto-suspension for security violations"""
    if not text:
        return True, text

    try:
        # Check length before processing to avoid false positives from truncation
        if max_length and len(text) > max_length:
            # For content fields, be more lenient and just return an error instead of suspending
            is_content_field = any(keyword in field_name.lower() for keyword in ["assignment", "meeting", "resource", "club_post"])
            if is_content_field:
                return False, f"Content too long (max {max_length} characters)"
            # For other fields, also just return error to be consistent
            return False, f"Content too long (max {max_length} characters)"

        # Basic sanitization without truncation since we've already checked length
        if sanitize_string:
            sanitized = sanitize_string(text, max_length=None)
        else:
            from .sanitization import sanitize_string as _sanitize_string
            sanitized = _sanitize_string(text, max_length=None)

        # Check for profanity
        if check_profanity_comprehensive(sanitized):
            # Log the profanity attempt for monitoring but don't suspend
            if user and not user.is_admin:
                if app:
                    app.logger.warning(f"PROFANITY DETECTED - User {user.username} (ID: {user.id}) used inappropriate language in {field_name}: {text[:100]}...")
                if create_audit_log:
                    create_audit_log(
                        action_type='profanity_violation',
                        description=f"Inappropriate language detected in {field_name}",
                        user=user,
                        target_type='user',
                        target_id=user.id,
                        details={
                            'field_name': field_name,
                            'content_preview': text[:100] + "..." if len(text) > 100 else text
                        },
                        severity='warning',
                        category='security'
                    )
            return False, "Please remove inappropriate language from your content and try again."

        # Check for exploit attempts with field context
        is_exploit, exploit_type = detect_exploit_attempts(sanitized, field_name)
        if is_exploit and user and not user.is_admin:
            if suspend_user_func:
                suspend_user_func(
                    user,
                    f"Security Exploit - {exploit_type}",
                    f"Detected {exploit_type} attempt in {field_name}: {text[:100]}..."
                )
            return False, "Account suspended for security violation"

        # Check for enumeration attempts with field context
        is_enum, enum_type = detect_enumeration_attempts(sanitized, field_name)
        if is_enum and user and not user.is_admin:
            if suspend_user_func:
                suspend_user_func(
                    user,
                    f"Enumeration Attempt - {enum_type}",
                    f"Detected enumeration in {field_name}: {text[:100]}..."
                )
            return False, "Account suspended for suspicious activity"

        return True, sanitized

    except Exception as e:
        if app:
            app.logger.error(f"Error in security validation: {str(e)}")
        return False, "Validation error"


def add_security_headers(response):
    """Add security headers to HTTP responses"""
    # Prevent clickjacking
    response.headers['X-Frame-Options'] = 'DENY'
    # Prevent MIME type sniffing
    response.headers['X-Content-Type-Options'] = 'nosniff'
    # XSS protection
    response.headers['X-XSS-Protection'] = '1; mode=block'
    # Referrer policy
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    # Strict Transport Security (HTTPS only)
    if request.is_secure:
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    # Content Security Policy - more restrictive
    if not response.headers.get('Content-Security-Policy'):
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://server.fillout.com; "
            "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://fonts.googleapis.com; "
            "font-src 'self' https://cdnjs.cloudflare.com https://fonts.gstatic.com https://r2cdn.perplexity.ai; "
            "img-src 'self' data: https:; "
            "connect-src 'self' https://api.hackclub.com https://ai.hackclub.com https://cdnjs.cloudflare.com https://cdn.jsdelivr.net https://server.fillout.com; "
            "frame-src 'self' https://forms.hackclub.com https://server.fillout.com; "
            "object-src 'none'; "
            "base-uri 'self'"
        )
    # Permissions Policy (formerly Feature Policy)
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    return response
