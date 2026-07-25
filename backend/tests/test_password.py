import pytest

from app.core.password import hash_password, validate_password_strength, verify_password


def test_hash_password():
    """Verify that password hashing changes the password format."""
    password = "SecurePassword123!"
    hashed = hash_password(password)
    assert hashed != password
    assert len(hashed) > 10


def test_verify_correct_password():
    """Verify that hashing and verification succeeds with the correct password."""
    password = "SecurePassword123!"
    hashed = hash_password(password)
    assert verify_password(password, hashed) is True


def test_verify_incorrect_password():
    """Verify that verification fails when the incorrect password is submitted."""
    password = "SecurePassword123!"
    hashed = hash_password(password)
    assert verify_password("WrongPassword123!", hashed) is False


def test_hashes_are_different_for_same_password():
    """Verify that two hashes of the same password produce different salt values."""
    password = "SecurePassword123!"
    hashed1 = hash_password(password)
    hashed2 = hash_password(password)
    assert hashed1 != hashed2


def test_validate_password_strength_success():
    """Verify that a policy-compliant password passes validation without exceptions."""
    # Should not raise any error
    validate_password_strength("SecurePassword123!")


def test_validate_password_strength_missing_uppercase():
    """Verify password strength policy rejects missing uppercase characters."""
    with pytest.raises(ValueError, match="uppercase"):
        validate_password_strength("securepassword123!")


def test_validate_password_strength_missing_lowercase():
    """Verify password strength policy rejects missing lowercase characters."""
    with pytest.raises(ValueError, match="lowercase"):
        validate_password_strength("SECUREPASSWORD123!")


def test_validate_password_strength_missing_number():
    """Verify password strength policy rejects missing numeric characters."""
    with pytest.raises(ValueError, match="numeric"):
        validate_password_strength("SecurePassword!")


def test_validate_password_strength_missing_special_character():
    """Verify password strength policy rejects missing special characters."""
    with pytest.raises(ValueError, match="special character"):
        validate_password_strength("SecurePassword123")


def test_validate_password_strength_min_length():
    """Verify password strength policy enforces minimum length requirements."""
    with pytest.raises(ValueError, match="at least"):
        validate_password_strength("Sec1!")
