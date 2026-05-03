"""Shared yt-dlp auth/format error helpers used by both scrapers."""
from __future__ import annotations

AUTH_ERROR_PATTERNS = [
    'login required',
    'authentication',
    'api is not granting access',
    'http error 400',
    'http error 401',
    'http error 403',
    'rate-limit',
    'requested content is not available',
    'members only',
    'locked behind the login page',
]


def is_auth_error(error_msg: str) -> bool:
    error_lower = error_msg.lower()
    return any(p in error_lower for p in AUTH_ERROR_PATTERNS)
