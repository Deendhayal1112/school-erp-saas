import bcrypt

from app.core import constants


def hash_password(password: str) -> str:
    """
    Hashes a plaintext password using the blowfish-based bcrypt algorithm.
    Automatically generates a salt.
    """
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    """
    Safely verifies a plaintext password against a stored bcrypt hash.
    Catches encoding or parsing exceptions, returning False in case of errors.
    """
    try:
        password_bytes = password.encode("utf-8")
        hashed_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except Exception:
        return False


def validate_password_strength(password: str) -> None:
    """
    Validates a plaintext password against standard password policies.
    Raises ValueError with a specific, readable message if any validation checks fail.
    """
    if len(password) < constants.PASSWORD_MIN_LENGTH:
        raise ValueError(
            f"Password must be at least {constants.PASSWORD_MIN_LENGTH} characters long."
        )

    if len(password) > constants.PASSWORD_MAX_LENGTH:
        raise ValueError(
            f"Password cannot be longer than {constants.PASSWORD_MAX_LENGTH} characters."
        )

    if constants.PASSWORD_REQUIRE_UPPERCASE and not any(c.isupper() for c in password):
        raise ValueError("Password must contain at least one uppercase character.")

    if constants.PASSWORD_REQUIRE_LOWERCASE and not any(c.islower() for c in password):
        raise ValueError("Password must contain at least one lowercase character.")

    if constants.PASSWORD_REQUIRE_NUMBER and not any(c.isdigit() for c in password):
        raise ValueError("Password must contain at least one numeric digit.")

    if constants.PASSWORD_REQUIRE_SPECIAL_CHARACTER:
        if not any(c in constants.SPECIAL_CHARACTERS for c in password):
            raise ValueError(
                f"Password must contain at least one special character (e.g. {constants.SPECIAL_CHARACTERS[0:10]})."
            )
