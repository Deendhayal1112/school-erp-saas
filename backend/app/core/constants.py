# ==========================================
# Password Validation Constants
# ==========================================
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128
PASSWORD_REQUIRE_UPPERCASE = True
PASSWORD_REQUIRE_LOWERCASE = True
PASSWORD_REQUIRE_NUMBER = True
PASSWORD_REQUIRE_SPECIAL_CHARACTER = True

# Characters considered special for password strength checks
SPECIAL_CHARACTERS = "!@#$%^&*()_+-=[]{}|;:',.<>?/~`"

# ==========================================
# Cryptography Defaults
# ==========================================
DEFAULT_HASH_ALGORITHM = "bcrypt"
