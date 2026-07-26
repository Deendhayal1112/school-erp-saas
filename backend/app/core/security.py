import base64
import hashlib

from cryptography.fernet import Fernet

from app.core.config import Settings

# Derive a 32-byte url-safe base64 key for Fernet from the app's SECRET_KEY
settings = Settings()
key_material = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
fernet_key = base64.urlsafe_b64encode(key_material)
fernet = Fernet(fernet_key)


def encrypt_field(val: str | None) -> str | None:
    """Encrypts plaintext string to base64 cipher text."""
    if val is None:
        return None
    return fernet.encrypt(val.encode("utf-8")).decode("utf-8")


def decrypt_field(val: str | None) -> str | None:
    """Decrypts base64 cipher text to plaintext string."""
    if val is None:
        return None
    return fernet.decrypt(val.encode("utf-8")).decode("utf-8")


def mask_sensitive_value(val: str | None, visible_suffix_len: int = 4) -> str | None:
    """Masks all characters of a string with '*' except the last few visible characters."""
    if not val:
        return val
    # Strip any formatting spaces/hyphens for length check
    clean_val = val.strip()
    if len(clean_val) <= visible_suffix_len:
        return "*" * len(clean_val)
    return "*" * (len(clean_val) - visible_suffix_len) + clean_val[-visible_suffix_len:]
