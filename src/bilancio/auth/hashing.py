"""Token generation and Argon2 hashing utilities.

Design note: token validation is O(n) in the number of active tokens. For
3–5 users with a handful of tokens each, this is acceptable. If the user
base grows, add a lookup_prefix column (first 8 chars of token) to reduce
Argon2 verifications to O(1).
"""

import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError

_ph = PasswordHasher()


def generate_token() -> str:
    """Return a cryptographically random URL-safe token (32 bytes → ~43 chars)."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Hash a raw token with Argon2id."""
    return _ph.hash(token)


def verify_token(token: str, token_hash: str) -> bool:
    """Return True if token matches token_hash, False otherwise."""
    try:
        return _ph.verify(token_hash, token)
    except (VerifyMismatchError, VerificationError, Exception):
        return False
