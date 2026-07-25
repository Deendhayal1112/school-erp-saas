import time
from datetime import timedelta
import pytest
from app.core import jwt, tokens


def test_create_access_token():
    """Verify that access token creation succeeds and returns a string."""
    subject = "test-user-uuid"
    token = tokens.create_access_token(subject)
    assert token is not None
    assert isinstance(token, str)


def test_create_refresh_token():
    """Verify that refresh token creation succeeds and returns a string."""
    subject = "test-user-uuid"
    token = tokens.create_refresh_token(subject)
    assert token is not None
    assert isinstance(token, str)


def test_decode_access_token():
    """Verify that a valid access token can be decoded, containing standard claims."""
    subject = "test-user-uuid"
    token = tokens.create_access_token(subject)
    payload = jwt.decode_token(token)
    assert payload["sub"] == subject
    assert payload["type"] == "access"
    assert "exp" in payload
    assert "iat" in payload


def test_decode_refresh_token():
    """Verify that a valid refresh token can be decoded, containing standard claims."""
    subject = "test-user-uuid"
    token = tokens.create_refresh_token(subject)
    payload = jwt.decode_token(token)
    assert payload["sub"] == subject
    assert payload["type"] == "refresh"
    assert "exp" in payload
    assert "iat" in payload


def test_expired_token():
    """Verify that decoding an expired token raises a TokenExpiredError."""
    subject = "test-user-uuid"
    expired_delta = timedelta(seconds=-5)  # Expired 5 seconds ago
    token = tokens.create_access_token(subject, expires_delta=expired_delta)
    with pytest.raises(jwt.TokenExpiredError):
        jwt.decode_token(token)


def test_invalid_signature():
    """Verify that decoding a token with a different secret key raises an InvalidSignatureError."""
    subject = "test-user-uuid"
    token = tokens.create_access_token(subject)
    with pytest.raises(jwt.InvalidSignatureError):
        jwt.decode_token(token, secret_key="wrong-secret-key-signature-failure")


def test_corrupted_token():
    """Verify that decoding a completely malformed token string raises a MalformedTokenError."""
    with pytest.raises(jwt.MalformedTokenError):
        jwt.decode_token("invalid-malformed-segmented-token-string")


def test_wrong_secret_key():
    """Verify that encoding with a wrong key raises a signature failure during default key checks."""
    subject = "test-user-uuid"
    payload = {
        "sub": subject,
        "exp": int(time.time() + 60),
        "type": "access"
    }
    # Encode with a custom key
    token = jwt.encode_token(payload, secret_key="custom-unrecognized-secret-key-longer-than-32-chars")
    # Decode with defaults (uses settings.SECRET_KEY)
    with pytest.raises(jwt.InvalidSignatureError):
        jwt.decode_token(token)


def test_missing_payload_claims():
    """Verify that decoding raises MissingClaimsError if standard claims are missing."""
    payload = {
        "exp": int(time.time() + 60),
        "type": "access"
        # 'sub' is missing
    }
    token = jwt.encode_token(payload)
    with pytest.raises(jwt.MissingClaimsError, match="sub"):
        jwt.decode_token(token)


def test_invalid_algorithm():
    """Verify that decoding raises an exception if the signing algorithm does not match."""
    subject = "test-user-uuid"
    payload = {
        "sub": subject,
        "exp": int(time.time() + 60),
        "type": "access"
    }
    token = jwt.encode_token(payload)
    # Attempt to decode expecting HS512 (default is HS256)
    with pytest.raises(jwt.InvalidTokenError):
        jwt.decode_token(token, algorithm="HS512")
