"""
Password Policy and Entropy Validators.
"""

import math
from collections import Counter
from app.core import constants
from app.modules.auth.password.exceptions import PasswordValidationError

# Configurable list of basic dictionary words to reject
DEFAULT_DICTIONARY_WORDS = {
    "password", "admin", "administrator", "school", "saas", "qwerty", "welcome", "pass123"
}

def calculate_shannon_entropy(password: str) -> float:
    """
    Calculates Shannon Entropy of a password string.
    This measures the randomness/unpredictability of the character distribution.
    """
    if not password:
        return 0.0
    length = len(password)
    counts = Counter(password)
    entropy = 0.0
    for count in counts.values():
        p = count / length
        entropy -= p * math.log2(p)
    return entropy

def validate_password_policy(
    password: str, 
    min_length: int = constants.PASSWORD_MIN_LENGTH,
    max_length: int = constants.PASSWORD_MAX_LENGTH,
    require_uppercase: bool = constants.PASSWORD_REQUIRE_UPPERCASE,
    require_lowercase: bool = constants.PASSWORD_REQUIRE_LOWERCASE,
    require_number: bool = constants.PASSWORD_REQUIRE_NUMBER,
    require_special: bool = constants.PASSWORD_REQUIRE_SPECIAL_CHARACTER,
    reject_dictionary_words: bool = True,
    dictionary_words: set[str] = DEFAULT_DICTIONARY_WORDS,
    min_entropy: float = 2.5
) -> None:
    """
    Validates a plaintext password against standard policies and entropy checks.
    Raises PasswordValidationError if validation fails.
    """
    if len(password) < min_length:
        raise PasswordValidationError(f"Password must be at least {min_length} characters long.")
    if len(password) > max_length:
        raise PasswordValidationError(f"Password cannot exceed {max_length} characters.")

    if require_uppercase and not any(c.isupper() for c in password):
        raise PasswordValidationError("Password must contain at least one uppercase letter.")
    if require_lowercase and not any(c.islower() for c in password):
        raise PasswordValidationError("Password must contain at least one lowercase letter.")
    if require_number and not any(c.isdigit() for c in password):
        raise PasswordValidationError("Password must contain at least one numeric digit.")
    if require_special and not any(c in constants.SPECIAL_CHARACTERS for c in password):
        raise PasswordValidationError("Password must contain at least one special character.")

    # Dictionary word rejection (case-insensitive substring and exact matches)
    if reject_dictionary_words:
        normalized_pwd = password.lower()
        for word in dictionary_words:
            if word.lower() in normalized_pwd:
                raise PasswordValidationError(f"Password is too common and contains the rejected word: '{word}'.")

    # Entropy check
    entropy = calculate_shannon_entropy(password)
    if entropy < min_entropy:
        raise PasswordValidationError(
            f"Password character distribution is too simple (entropy: {entropy:.2f} < {min_entropy:.2f})."
        )
