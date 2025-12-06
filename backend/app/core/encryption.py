"""
Password encryption utilities using Fernet symmetric encryption.

Provides secure encryption/decryption for sensitive credentials like mailbox passwords.
Uses the cryptography library's Fernet implementation (AES-128 CBC with HMAC).
"""
import os
import logging
from cryptography.fernet import Fernet, InvalidToken
from typing import Optional

logger = logging.getLogger(__name__)


def get_encryption_key() -> Optional[bytes]:
    """
    Get encryption key from environment variable.

    Returns:
        Encryption key as bytes, or None if not set

    Raises:
        ValueError: If key is set but invalid format
    """
    key = os.getenv("MAILBOX_ENCRYPTION_KEY")
    if not key:
        return None

    try:
        return key.encode()
    except Exception as e:
        raise ValueError(f"Invalid MAILBOX_ENCRYPTION_KEY format: {e}")


def encrypt_password(password: str) -> str:
    """
    Encrypt a password using Fernet symmetric encryption.

    Args:
        password: Plain text password to encrypt

    Returns:
        Base64-encoded encrypted password

    Raises:
        ValueError: If encryption key not set
        Exception: If encryption fails
    """
    key = get_encryption_key()
    if not key:
        raise ValueError(
            "MAILBOX_ENCRYPTION_KEY environment variable not set. "
            "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )

    try:
        f = Fernet(key)
        encrypted_bytes = f.encrypt(password.encode())
        return encrypted_bytes.decode()
    except Exception as e:
        logger.error(f"Password encryption failed: {e}")
        raise


def decrypt_password(encrypted: str) -> str:
    """
    Decrypt a password using Fernet symmetric encryption.

    Args:
        encrypted: Base64-encoded encrypted password

    Returns:
        Plain text password

    Raises:
        ValueError: If encryption key not set
        InvalidToken: If encrypted data is invalid or key is wrong
    """
    key = get_encryption_key()
    if not key:
        raise ValueError(
            "MAILBOX_ENCRYPTION_KEY environment variable not set. "
            "Cannot decrypt password without encryption key."
        )

    try:
        f = Fernet(key)
        decrypted_bytes = f.decrypt(encrypted.encode())
        return decrypted_bytes.decode()
    except InvalidToken as e:
        logger.error("Password decryption failed: Invalid token or wrong encryption key")
        raise ValueError("Failed to decrypt password. The encryption key may be incorrect.") from e
    except Exception as e:
        logger.error(f"Password decryption failed: {e}")
        raise


def is_encryption_available() -> bool:
    """
    Check if encryption is available (encryption key is set).

    Returns:
        True if encryption key is configured, False otherwise
    """
    return get_encryption_key() is not None


def generate_encryption_key() -> str:
    """
    Generate a new Fernet encryption key.

    Returns:
        Base64-encoded encryption key (44 characters)

    Example:
        >>> key = generate_encryption_key()
        >>> print(f"MAILBOX_ENCRYPTION_KEY={key}")
    """
    return Fernet.generate_key().decode()
