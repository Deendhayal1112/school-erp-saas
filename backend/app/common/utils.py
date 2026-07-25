"""
Core utility helpers.
"""

import secrets
import string

from fastapi import Request


def generate_secure_token(length: int = 32) -> str:
    """Generates a secure random URL-safe string token."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def get_client_ip(request: Request) -> str:
    """Extracts client IP address considering proxy headers like X-Forwarded-For."""
    x_forwarded_for = request.headers.get("x-forwarded-for")
    if x_forwarded_for:
        # Get primary client IP (first element in comma separated list)
        return x_forwarded_for.split(",")[0].strip()

    # Fallback to direct client host address info
    if request.client:
        return request.client.host

    return "127.0.0.1"
