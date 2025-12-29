"""Utility to detect authentication and authorization errors in error messages."""

from typing import List

# Common authentication error patterns across different STT providers
AUTH_ERROR_PATTERNS: List[str] = [
    "401",  # Unauthorized HTTP status
    "403",  # Forbidden HTTP status
    "invalid_api_key",
    "invalid api key",
    "invalid key",
    "api key",
    "authentication failed",
    "authentication error",
    "authorization failed",
    "expired",
    "token expired",
    "key expired",
    "invalid credentials",
    "invalid token",
    "unauthorized",
    "forbidden",
    "quota exceeded",  # Often indicates key/account issue
    "rate limit exceeded",  # May indicate key issue
]


def is_auth_error(error_message: str) -> bool:
    """Check if an error message indicates an authentication/authorization failure.

    Args:
        error_message: The error message to check.

    Returns:
        True if the error appears to be authentication-related, False otherwise.

    Examples:
        >>> is_auth_error("401 Unauthorized")
        True
        >>> is_auth_error("Invalid API key provided")
        True
        >>> is_auth_error("Network connection timeout")
        False
    """
    if not error_message:
        return False

    error_lower = error_message.lower()
    return any(pattern in error_lower for pattern in AUTH_ERROR_PATTERNS)


def get_auth_error_type(error_message: str) -> str:
    """Get a human-readable authentication error type.

    Args:
        error_message: The error message to analyze.

    Returns:
        A string describing the error type, or "unknown" if not an auth error.

    Examples:
        >>> get_auth_error_type("401 Unauthorized")
        'unauthorized'
        >>> get_auth_error_type("API key expired")
        'expired'
    """
    if not is_auth_error(error_message):
        return "unknown"

    error_lower = error_message.lower()

    if "401" in error_lower or "unauthorized" in error_lower:
        return "unauthorized"
    elif "403" in error_lower or "forbidden" in error_lower:
        return "forbidden"
    elif "expired" in error_lower:
        return "expired"
    elif "invalid" in error_lower:
        return "invalid_key"
    elif "quota" in error_lower or "rate limit" in error_lower:
        return "quota_exceeded"
    else:
        return "auth_error"
