import uuid
from datetime import datetime, timezone
import pytest
from pydantic import ValidationError
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    TokenRefreshResponse,
    CurrentUserResponse,
)


def test_valid_login_request():
    """Verify that LoginRequest accepts policy-compliant emails and passwords."""
    req = LoginRequest(email=" admin@demoschool.edu  ", password="Password123!")
    # Email should be trimmed/whitespace-stripped
    assert req.email == "admin@demoschool.edu"
    assert req.password == "Password123!"


def test_invalid_email_login_request():
    """Verify that LoginRequest rejects malformed email strings."""
    with pytest.raises(ValidationError):
        LoginRequest(email="not-an-email-pattern", password="Password123!")


def test_empty_password_login_request():
    """Verify that LoginRequest rejects empty or too-short passwords."""
    with pytest.raises(ValidationError):
        LoginRequest(email="admin@demoschool.edu", password="")


def test_password_confirmation_success():
    """Verify that ChangePasswordRequest accepts matching new password entries."""
    req = ChangePasswordRequest(
        current_password="OldPassword123!",
        new_password="NewSecurePassword123!",
        confirm_password="NewSecurePassword123!",
    )
    assert req.new_password == req.confirm_password


def test_password_confirmation_failure():
    """Verify ChangePasswordRequest validation fails when passwords mismatch."""
    with pytest.raises(ValidationError, match="do not match"):
        ChangePasswordRequest(
            current_password="OldPassword123!",
            new_password="NewSecurePassword123!",
            confirm_password="MismatchedPassword123!",
        )


def test_forgot_password_schema():
    """Verify ForgotPasswordRequest handles email strings and validation correctly."""
    req = ForgotPasswordRequest(email=" recovery@demoschool.edu ")
    assert req.email == "recovery@demoschool.edu"

    with pytest.raises(ValidationError):
        ForgotPasswordRequest(email="invalid-email")


def test_reset_password_schema():
    """Verify ResetPasswordRequest processes resets and requires matching entries."""
    req = ResetPasswordRequest(
        reset_token="crypto-reset-token-value",
        new_password="NewSecurePassword123!",
        confirm_password="NewSecurePassword123!",
    )
    assert req.reset_token == "crypto-reset-token-value"

    with pytest.raises(ValidationError, match="do not match"):
        ResetPasswordRequest(
            reset_token="crypto-reset-token-value",
            new_password="NewSecurePassword123!",
            confirm_password="MismatchedPassword123!",
        )


def test_token_response_schema():
    """Verify that TokenRefreshResponse validates access and refresh properties."""
    res = TokenRefreshResponse(
        access_token="access-token-value-jwt",
        refresh_token="refresh-token-value-jwt",
        token_type="bearer",
        expires_in=1800,
    )
    assert res.access_token == "access-token-value-jwt"
    assert res.expires_in == 1800


def test_current_user_response():
    """Verify CurrentUserResponse maps user metadata and strictly excludes secure password fields."""
    user_id = uuid.uuid4()
    school_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    
    res = CurrentUserResponse(
        id=user_id,
        school_id=school_id,
        email="user@demoschool.edu",
        full_name="Jane Doe",
        role="PRINCIPAL",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    assert res.id == user_id
    assert res.full_name == "Jane Doe"
    # Security constraint check: Verify password hash is never exposed in schema attributes
    assert "password_hash" not in CurrentUserResponse.model_fields
    assert "password" not in CurrentUserResponse.model_fields
