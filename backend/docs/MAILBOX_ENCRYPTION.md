# Mailbox Password Encryption

## Overview

Mailbox passwords are encrypted using **Fernet symmetric encryption** (AES-128 CBC with HMAC) from the `cryptography` library. This ensures that passwords stored in the database are never in plaintext.

## Quick Start

### 1. Generate Encryption Key

```bash
python scripts/generate_encryption_key.py
```

This outputs a key like:
```
MAILBOX_ENCRYPTION_KEY=WuuobfPxN6DWTB36JecSnMD6u3GIf7E9peSu3AvPySw=
```

### 2. Add to .env File

```bash
# Mailbox Password Encryption Key (for Fernet encryption)
MAILBOX_ENCRYPTION_KEY=WuuobfPxN6DWTB36JecSnMD6u3GIf7E9peSu3AvPySw=
```

### 3. Use in Code

#### Storing a Password (Encryption)

```python
from app.models.mailbox import Mailbox

mailbox = Mailbox(
    email="sender@example.com",
    smtp_host="smtp.gmail.com",
    smtp_port=587
)

# Encrypt and store password
mailbox.set_password("mySecurePassword123!")

# The password_encrypted field now contains encrypted data
# Example: gAAAAABmX7k2... (base64-encoded encrypted bytes)
```

#### Retrieving a Password (Decryption)

```python
from app.models.mailbox import Mailbox

# Fetch mailbox from database
mailbox = session.query(Mailbox).filter_by(email="sender@example.com").first()

# Decrypt password for use
plain_password = mailbox.get_password()

# Use with SMTP
import smtplib
with smtplib.SMTP(mailbox.smtp_host, mailbox.smtp_port) as server:
    server.starttls()
    server.login(mailbox.email, plain_password)
    # ...
```

#### EmailSender Integration (Production Mode)

The `EmailSender` class automatically decrypts passwords when sending emails in production mode:

```python
from app.services.sequences.sender import EmailSender

# Production mode (test_mode=False)
sender = EmailSender(session, test_mode=False)

result = await sender.send_email(
    mailbox=mailbox,  # Password will be automatically decrypted
    to_email="recipient@example.com",
    subject="Hello",
    body="Email body"
)
```

**Test mode** does NOT require encryption (passwords are not used):

```python
# Test mode (test_mode=True) - no SMTP, no encryption needed
sender = EmailSender(session, test_mode=True)

result = await sender.send_email(
    mailbox=mailbox,  # Password not used in test mode
    to_email="recipient@example.com",
    subject="Test",
    body="Test body"
)
# Email is logged to database, not actually sent
```

## API Reference

### Encryption Utility (`app/core/encryption.py`)

#### `encrypt_password(password: str) -> str`

Encrypts a plaintext password.

**Parameters:**
- `password` (str): Plaintext password to encrypt

**Returns:**
- `str`: Base64-encoded encrypted password

**Raises:**
- `ValueError`: If `MAILBOX_ENCRYPTION_KEY` not set

**Example:**
```python
from app.core.encryption import encrypt_password

encrypted = encrypt_password("myPassword123")
# Returns: "gAAAAABmX7k2..."
```

#### `decrypt_password(encrypted: str) -> str`

Decrypts an encrypted password.

**Parameters:**
- `encrypted` (str): Base64-encoded encrypted password

**Returns:**
- `str`: Plaintext password

**Raises:**
- `ValueError`: If `MAILBOX_ENCRYPTION_KEY` not set or decryption fails
- `InvalidToken`: If encrypted data is invalid or key is wrong

**Example:**
```python
from app.core.encryption import decrypt_password

plain = decrypt_password("gAAAAABmX7k2...")
# Returns: "myPassword123"
```

#### `is_encryption_available() -> bool`

Checks if encryption is configured.

**Returns:**
- `bool`: True if encryption key is set, False otherwise

**Example:**
```python
from app.core.encryption import is_encryption_available

if is_encryption_available():
    print("Encryption is configured")
else:
    print("WARNING: Encryption key not set")
```

#### `generate_encryption_key() -> str`

Generates a new Fernet encryption key.

**Returns:**
- `str`: Base64-encoded encryption key (44 characters)

**Example:**
```python
from app.core.encryption import generate_encryption_key

key = generate_encryption_key()
print(f"MAILBOX_ENCRYPTION_KEY={key}")
```

### Mailbox Model Methods

#### `Mailbox.set_password(password: str) -> None`

Encrypts and stores password in `password_encrypted` field.

**Example:**
```python
mailbox = Mailbox(email="test@example.com")
mailbox.set_password("myPassword")
# mailbox.password_encrypted now contains encrypted data
```

#### `Mailbox.get_password() -> str`

Decrypts and returns the stored password.

**Example:**
```python
password = mailbox.get_password()
# Returns plaintext password
```

## Security Best Practices

### 1. Key Management

- **Generate Once**: Create the encryption key once and store it securely
- **Never Commit**: Add `.env` to `.gitignore` (already configured)
- **Secrets Vault**: In production, use a secrets manager (AWS Secrets Manager, HashiCorp Vault, etc.)
- **Backup Securely**: Store a backup of the key in a secure location (password manager)

### 2. Key Rotation

If you need to rotate the encryption key:

1. Generate a new key
2. Decrypt all passwords with the old key
3. Re-encrypt with the new key
4. Update `MAILBOX_ENCRYPTION_KEY` in production

**Migration Script Example:**
```python
from app.core.encryption import decrypt_password, encrypt_password
import os

# Set old key
os.environ["MAILBOX_ENCRYPTION_KEY"] = "old_key_here"

# Fetch all mailboxes
mailboxes = session.query(Mailbox).all()

# Store plaintext passwords temporarily
passwords = {mb.id: mb.get_password() for mb in mailboxes}

# Set new key
os.environ["MAILBOX_ENCRYPTION_KEY"] = "new_key_here"

# Re-encrypt with new key
for mailbox in mailboxes:
    mailbox.set_password(passwords[mailbox.id])

session.commit()
```

### 3. Production Deployment

#### Environment Variables (Vercel, Railway, etc.)

```bash
MAILBOX_ENCRYPTION_KEY=your_key_here
```

#### Docker Secrets

```yaml
# docker-compose.yml
services:
  api:
    environment:
      - MAILBOX_ENCRYPTION_KEY=${MAILBOX_ENCRYPTION_KEY}
    secrets:
      - mailbox_key

secrets:
  mailbox_key:
    external: true
```

#### AWS Secrets Manager

```python
import boto3
import json

client = boto3.client('secretsmanager')
response = client.get_secret_value(SecretId='prod/mailbox-encryption-key')
secret = json.loads(response['SecretString'])
os.environ['MAILBOX_ENCRYPTION_KEY'] = secret['key']
```

## Error Handling

### Missing Encryption Key

```python
from app.core.encryption import encrypt_password

try:
    encrypted = encrypt_password("test")
except ValueError as e:
    print(f"Error: {e}")
    # Error: MAILBOX_ENCRYPTION_KEY environment variable not set.
```

### Invalid Encrypted Data

```python
from app.core.encryption import decrypt_password

try:
    plain = decrypt_password("invalid_data")
except ValueError as e:
    print(f"Error: {e}")
    # Error: Failed to decrypt password. The encryption key may be incorrect.
```

### Production Mode Without Key

If `EmailSender` is used in production mode (`test_mode=False`) without an encryption key:

```python
result = await sender.send_email(mailbox, "to@example.com", "Subject", "Body")

if not result["success"]:
    print(result["error"])
    # Error: Password decryption failed. Ensure MAILBOX_ENCRYPTION_KEY is set.
```

## Testing

### Run Tests

```bash
pytest tests/test_mailbox_encryption.py -v
```

### Test Coverage

- **17 tests** covering:
  - Encryption/decryption utility functions
  - Mailbox model methods
  - Special characters and unicode support
  - Error handling (missing key, wrong key, invalid data)
  - Production flow scenarios

### Manual Testing

```python
# Test encryption
from app.core.encryption import encrypt_password, decrypt_password
import os

os.environ["MAILBOX_ENCRYPTION_KEY"] = "test_key_" + "a" * 36

password = "myPassword123!"
encrypted = encrypt_password(password)
decrypted = decrypt_password(encrypted)

assert decrypted == password
print("Encryption test passed!")
```

## Migration Guide

### Migrating from Plaintext Passwords

If you have existing mailboxes with plaintext passwords in `password_encrypted`:

```python
from app.models.mailbox import Mailbox
from app.core.encryption import encrypt_password
import os

# Set encryption key
os.environ["MAILBOX_ENCRYPTION_KEY"] = "your_new_key_here"

# Fetch all mailboxes
mailboxes = session.query(Mailbox).all()

for mailbox in mailboxes:
    # Assume password_encrypted contains plaintext (old data)
    plaintext = mailbox.password_encrypted

    # Encrypt using new method
    mailbox.set_password(plaintext)

session.commit()
print(f"Migrated {len(mailboxes)} mailbox passwords to encrypted format")
```

## Troubleshooting

### Issue: "MAILBOX_ENCRYPTION_KEY environment variable not set"

**Solution:**
1. Generate a key: `python scripts/generate_encryption_key.py`
2. Add to `.env` file
3. Restart the application

### Issue: "Failed to decrypt password"

**Causes:**
- Wrong encryption key
- Corrupted encrypted data
- Key changed after encryption

**Solution:**
- Verify the encryption key matches the one used during encryption
- Check database for data corruption
- Re-encrypt passwords if key was rotated

### Issue: Test mode emails not sending

**This is expected behavior!** Test mode logs emails instead of sending them:

```python
sender = EmailSender(session, test_mode=True)
result = await sender.send_email(...)

# Check logs
logs = sender.get_test_logs()
for log in logs:
    print(f"Logged email: {log['subject']} to {log['to']}")
```

## References

- [Cryptography Library Documentation](https://cryptography.io/en/latest/)
- [Fernet Specification](https://github.com/fernet/spec)
- [OWASP Password Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)
