"""Email validation and filtering patterns."""
import re

# Bad email patterns to filter out (Wix tracking pixels, placeholders, etc.)
BAD_EMAIL_PATTERNS = [
    r'@sentry\.wixpress\.com$',
    r'@sentry-next\.wixpress\.com$',
    r'@2x\.png$',
    r'^youremail@',
    r'^email@example\.com$',
    r'^test@test\.com$',
    r'^noreply@',
    r'^no-reply@',
    r'^donotreply@',
    r'\.png$',
    r'\.jpg$',
    r'\.gif$',
]


def is_bad_email(email: str) -> bool:
    """Check if email matches any bad pattern (tracking pixels, placeholders, etc.)."""
    if not email:
        return False
    email_lower = email.lower().strip()
    for pattern in BAD_EMAIL_PATTERNS:
        if re.search(pattern, email_lower):
            return True
    return False
