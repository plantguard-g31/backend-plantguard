"""
Unit Tests -- Group A: Authentication & Cryptography (core/security.py)
Maps to STP Section 3.3.1, Test Cases UT-01 through UT-05.
"""
import time
import pytest
import jwt as pyjwt
from app.core.security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, decode_token
)
from app.core.config import get_settings
from fastapi import HTTPException


def test_UT01_password_hash_roundtrip_succeeds():
    """UT-01: hash then verify with the correct password succeeds, and the
    stored hash is never equal to the plaintext."""
    plain = "FarmerPass123"
    hashed = hash_password(plain)
    assert hashed != plain
    assert verify_password(plain, hashed) is True


def test_UT02_password_verification_fails_with_wrong_password():
    """UT-02: verifying a different password against the hash fails."""
    hashed = hash_password("FarmerPass123")
    assert verify_password("WrongPass456", hashed) is False


def test_UT03_access_token_contains_correct_claims():
    """UT-03: access token payload contains sub, role, and an exp ~30 min out."""
    result = create_access_token(user_id="abc-123", role="farmer")
    token = result["access_token"]
    settings = get_settings()
    payload = pyjwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    assert payload["sub"] == "abc-123"
    assert payload["role"] == "farmer"
    expected_lifetime_seconds = settings.JWT_EXPIRE_MINUTES * 60
    actual_lifetime_seconds = payload["exp"] - payload["iat"]
    assert abs(actual_lifetime_seconds - expected_lifetime_seconds) < 5


def test_UT04_expired_token_is_rejected():
    """UT-04: a token with exp in the past is rejected by decode_token()."""
    settings = get_settings()
    expired_payload = {
        "sub": "abc-123",
        "role": "farmer",
        "exp": int(time.time()) - 1,   # 1 second in the past
        "iat": int(time.time()) - 3600,
    }
    expired_token = pyjwt.encode(expired_payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    with pytest.raises(HTTPException) as exc_info:
        decode_token(expired_token)
    assert exc_info.value.status_code == 401


def test_UT05_tampered_token_is_rejected():
    """UT-05: altering a character in the middle of a valid token's signature
    causes rejection.

    Note: the *very last* character of a base64url string can, in some
    cases, encode only unused padding bits -- flipping it may decode to the
    same underlying bytes and NOT actually change the signature. That edge
    case was hit during initial test authoring (see Execution Report finding
    log). Tampering with a character from the middle of the signature avoids
    that ambiguity and unambiguously changes the decoded signature bytes.
    """
    result = create_access_token(user_id="abc-123", role="farmer")
    token = result["access_token"]
    header, payload, signature = token.split(".")
    mid = len(signature) // 2
    corrupted_char = "A" if signature[mid] != "A" else "B"
    tampered_signature = signature[:mid] + corrupted_char + signature[mid + 1:]
    tampered = f"{header}.{payload}.{tampered_signature}"
    assert tampered != token
    with pytest.raises(HTTPException) as exc_info:
        decode_token(tampered)
    assert exc_info.value.status_code == 401
