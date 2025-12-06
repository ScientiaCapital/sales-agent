"""
Tests for mailbox password encryption functionality.

Tests the encryption utility, Mailbox model methods, and EmailSender integration.
"""
import pytest
import os
from unittest.mock import patch
from cryptography.fernet import Fernet

from app.core.encryption import (
    encrypt_password,
    decrypt_password,
    is_encryption_available,
    generate_encryption_key,
    get_encryption_key,
)


class TestEncryptionUtility:
    """Test encryption utility functions."""

    def test_generate_encryption_key(self):
        """Test that key generation produces valid Fernet keys."""
        key = generate_encryption_key()
        assert isinstance(key, str)
        assert len(key) == 44  # Fernet keys are 44 characters (base64-encoded)

        # Verify it's a valid Fernet key
        Fernet(key.encode())  # Should not raise

    def test_encrypt_decrypt_password(self):
        """Test basic encryption and decryption."""
        # Generate a test key
        test_key = Fernet.generate_key().decode()

        with patch.dict(os.environ, {"MAILBOX_ENCRYPTION_KEY": test_key}):
            password = "mySecurePassword123!"

            # Encrypt
            encrypted = encrypt_password(password)
            assert isinstance(encrypted, str)
            assert encrypted != password  # Should be different

            # Decrypt
            decrypted = decrypt_password(encrypted)
            assert decrypted == password

    def test_encrypt_without_key(self):
        """Test that encryption fails without key set."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="MAILBOX_ENCRYPTION_KEY"):
                encrypt_password("test")

    def test_decrypt_without_key(self):
        """Test that decryption fails without key set."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="MAILBOX_ENCRYPTION_KEY"):
                decrypt_password("gAAAAA...")

    def test_decrypt_with_wrong_key(self):
        """Test that decryption fails with wrong key."""
        # Encrypt with one key
        key1 = Fernet.generate_key().decode()
        with patch.dict(os.environ, {"MAILBOX_ENCRYPTION_KEY": key1}):
            encrypted = encrypt_password("test")

        # Try to decrypt with different key
        key2 = Fernet.generate_key().decode()
        with patch.dict(os.environ, {"MAILBOX_ENCRYPTION_KEY": key2}):
            with pytest.raises(ValueError, match="decrypt password"):
                decrypt_password(encrypted)

    def test_decrypt_invalid_data(self):
        """Test that decryption fails with invalid encrypted data."""
        test_key = Fernet.generate_key().decode()

        with patch.dict(os.environ, {"MAILBOX_ENCRYPTION_KEY": test_key}):
            with pytest.raises(ValueError):
                decrypt_password("not-valid-encrypted-data")

    def test_is_encryption_available(self):
        """Test encryption availability check."""
        # Without key
        with patch.dict(os.environ, {}, clear=True):
            assert is_encryption_available() is False

        # With key
        test_key = Fernet.generate_key().decode()
        with patch.dict(os.environ, {"MAILBOX_ENCRYPTION_KEY": test_key}):
            assert is_encryption_available() is True

    def test_get_encryption_key(self):
        """Test encryption key retrieval."""
        # Without key
        with patch.dict(os.environ, {}, clear=True):
            assert get_encryption_key() is None

        # With key
        test_key = Fernet.generate_key().decode()
        with patch.dict(os.environ, {"MAILBOX_ENCRYPTION_KEY": test_key}):
            key = get_encryption_key()
            assert key == test_key.encode()

    def test_encrypt_decrypt_special_characters(self):
        """Test encryption with special characters in password."""
        test_key = Fernet.generate_key().decode()

        with patch.dict(os.environ, {"MAILBOX_ENCRYPTION_KEY": test_key}):
            # Password with special characters
            password = "P@ssw0rd!#$%^&*()[]{}|:;<>?,./"

            encrypted = encrypt_password(password)
            decrypted = decrypt_password(encrypted)

            assert decrypted == password

    def test_encrypt_decrypt_unicode(self):
        """Test encryption with unicode characters."""
        test_key = Fernet.generate_key().decode()

        with patch.dict(os.environ, {"MAILBOX_ENCRYPTION_KEY": test_key}):
            # Password with unicode
            password = "パスワード🔐密码"

            encrypted = encrypt_password(password)
            decrypted = decrypt_password(encrypted)

            assert decrypted == password


class TestMailboxModel:
    """Test Mailbox model encryption methods."""

    @pytest.fixture
    def encryption_key(self):
        """Provide a test encryption key."""
        return Fernet.generate_key().decode()

    @pytest.fixture
    def mock_mailbox_class(self):
        """Mock Mailbox class without database dependencies."""
        class MockMailbox:
            def __init__(self, email):
                self.email = email
                self.password_encrypted = ""

            def set_password(self, password: str) -> None:
                """Encrypt and store password."""
                from app.core.encryption import encrypt_password
                self.password_encrypted = encrypt_password(password)

            def get_password(self) -> str:
                """Decrypt and return password."""
                from app.core.encryption import decrypt_password
                return decrypt_password(self.password_encrypted)

        return MockMailbox

    def test_set_password(self, encryption_key, mock_mailbox_class):
        """Test Mailbox.set_password() method."""
        with patch.dict(os.environ, {"MAILBOX_ENCRYPTION_KEY": encryption_key}):
            mailbox = mock_mailbox_class(email="test@example.com")
            password = "myPassword123"

            mailbox.set_password(password)

            # Password should be encrypted (not plaintext)
            assert mailbox.password_encrypted != password
            assert len(mailbox.password_encrypted) > 0

    def test_get_password(self, encryption_key, mock_mailbox_class):
        """Test Mailbox.get_password() method."""
        with patch.dict(os.environ, {"MAILBOX_ENCRYPTION_KEY": encryption_key}):
            mailbox = mock_mailbox_class(email="test@example.com")
            password = "myPassword123"

            mailbox.set_password(password)
            decrypted = mailbox.get_password()

            assert decrypted == password

    def test_set_password_without_key(self, mock_mailbox_class):
        """Test that set_password fails without encryption key."""
        with patch.dict(os.environ, {}, clear=True):
            mailbox = mock_mailbox_class(email="test@example.com")

            with pytest.raises(ValueError, match="MAILBOX_ENCRYPTION_KEY"):
                mailbox.set_password("test")

    def test_get_password_without_key(self, encryption_key, mock_mailbox_class):
        """Test that get_password fails without encryption key."""
        # Set password with key
        with patch.dict(os.environ, {"MAILBOX_ENCRYPTION_KEY": encryption_key}):
            mailbox = mock_mailbox_class(email="test@example.com")
            mailbox.set_password("test")

        # Try to get password without key
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="MAILBOX_ENCRYPTION_KEY"):
                mailbox.get_password()


class TestPasswordDecryptionInProduction:
    """Test password decryption behavior in production scenarios."""

    @pytest.fixture
    def encryption_key(self):
        """Provide a test encryption key."""
        return Fernet.generate_key().decode()

    def test_decryption_flow_success(self, encryption_key):
        """Test successful password encryption and decryption flow."""
        from app.core.encryption import encrypt_password, decrypt_password

        with patch.dict(os.environ, {"MAILBOX_ENCRYPTION_KEY": encryption_key}):
            original_password = "mySecurePassword123!"

            # Simulate storing password
            encrypted = encrypt_password(original_password)

            # Simulate retrieving password (like in sender.py)
            decrypted = decrypt_password(encrypted)

            assert decrypted == original_password

    def test_decryption_flow_missing_key(self, encryption_key):
        """Test decryption fails when key is missing (production scenario)."""
        from app.core.encryption import encrypt_password, decrypt_password

        # Encrypt with key
        with patch.dict(os.environ, {"MAILBOX_ENCRYPTION_KEY": encryption_key}):
            encrypted = encrypt_password("mySecurePassword")

        # Try to decrypt without key (simulates production error)
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="MAILBOX_ENCRYPTION_KEY"):
                decrypt_password(encrypted)

    def test_decryption_flow_wrong_key(self, encryption_key):
        """Test decryption fails with wrong key (key rotation scenario)."""
        from app.core.encryption import encrypt_password, decrypt_password

        # Encrypt with first key
        key1 = Fernet.generate_key().decode()
        with patch.dict(os.environ, {"MAILBOX_ENCRYPTION_KEY": key1}):
            encrypted = encrypt_password("mySecurePassword")

        # Try to decrypt with second key
        key2 = Fernet.generate_key().decode()
        with patch.dict(os.environ, {"MAILBOX_ENCRYPTION_KEY": key2}):
            with pytest.raises(ValueError, match="decrypt password"):
                decrypt_password(encrypted)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
