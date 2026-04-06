import hashlib
import os

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import String
from sqlalchemy.types import TypeDecorator


def get_encryption_key() -> bytes:
    """Read ENCRYPTION_KEY from environment and return as bytes."""
    key = os.getenv("ENCRYPTION_KEY")
    if not key:
        raise RuntimeError("ENCRYPTION_KEY environment variable is not set")
    key_bytes = key.encode() if isinstance(key, str) else key
    Fernet(key_bytes)
    return key_bytes


def encrypt_value(value: str) -> str:
    """Encrypt a plaintext string and return base64-encoded ciphertext."""
    f = Fernet(get_encryption_key())
    return f.encrypt(value.encode()).decode()


def decrypt_value(value: str) -> str:
    """Decrypt a base64-encoded ciphertext back to plaintext."""
    f = Fernet(get_encryption_key())
    return f.decrypt(value.encode()).decode()


def hash_value(value: str) -> str:
    """Return a deterministic SHA-256 hex digest for lookup columns."""
    return hashlib.sha256(value.lower().strip().encode()).hexdigest()


class EncryptedString(TypeDecorator):
    """SQLAlchemy TypeDecorator that transparently encrypts/decrypts string columns.

    Use for PII fields: phone numbers, email addresses, physical addresses from skip traces.
    Encrypted values are longer than plaintext — size the underlying column accordingly (1024+).
    """

    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return encrypt_value(str(value))

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        try:
            return decrypt_value(value)
        except InvalidToken:
            return value
