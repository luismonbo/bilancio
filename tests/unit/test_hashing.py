"""Unit tests for token hashing utilities."""

from bilancio.auth.hashing import generate_token, hash_token, verify_token


def test_generate_token_is_urlsafe_string() -> None:
    token = generate_token()
    assert isinstance(token, str)
    assert len(token) > 30  # 32 bytes base64-encoded → ~43 chars


def test_generate_token_is_unique() -> None:
    assert generate_token() != generate_token()


def test_hash_token_returns_argon2_hash() -> None:
    token = generate_token()
    hashed = hash_token(token)
    assert hashed.startswith("$argon2")


def test_verify_token_correct() -> None:
    token = generate_token()
    hashed = hash_token(token)
    assert verify_token(token, hashed) is True


def test_verify_token_wrong_token() -> None:
    token = generate_token()
    hashed = hash_token(token)
    assert verify_token("wrong-token", hashed) is False


def test_verify_token_tampered_hash() -> None:
    token = generate_token()
    assert verify_token(token, "not-a-valid-hash") is False
