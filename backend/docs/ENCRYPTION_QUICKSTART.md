# Mailbox Encryption - Quick Start

## TL;DR

Mailbox passwords are now encrypted. You need to set `MAILBOX_ENCRYPTION_KEY` in your `.env` file.

## Setup (3 Steps)

### 1. Generate Key
```bash
cd backend
python scripts/generate_encryption_key.py
```

### 2. Add to .env
Copy the output and add to your `.env` file:
```bash
MAILBOX_ENCRYPTION_KEY=WuuobfPxN6DWTB36JecSnMD6u3GIf7E9peSu3AvPySw=
```

### 3. Restart Server
```bash
# Ctrl+C to stop
uvicorn app.main:app --reload
```

## Usage Examples

### Creating a Mailbox
```python
from app.models.mailbox import Mailbox

mailbox = Mailbox(email="sender@example.com")
mailbox.set_password("myPassword123!")  # Encrypted automatically
session.add(mailbox)
session.commit()
```

### Sending Emails (Production)
```python
from app.services.sequences.sender import EmailSender

sender = EmailSender(session, test_mode=False)
await sender.send_email(mailbox, "to@example.com", "Subject", "Body")
# Password decrypted automatically
```

### Testing (No Encryption Needed)
```python
sender = EmailSender(session, test_mode=True)
await sender.send_email(mailbox, "to@example.com", "Subject", "Body")
# Works without encryption key (doesn't actually send)
```

## Common Issues

### "MAILBOX_ENCRYPTION_KEY environment variable not set"
**Solution:** Run step 1-2 above

### Test mode doesn't require encryption
**This is correct!** Test mode logs emails instead of sending them.

### Production deployment
Set `MAILBOX_ENCRYPTION_KEY` in your platform's environment variables (Vercel, Railway, etc.)

## Need Help?

See full documentation: `docs/MAILBOX_ENCRYPTION.md`

## Security Notes

- Never commit `.env` to git (already in `.gitignore`)
- Keep the encryption key secret
- Store production key in secrets manager (AWS Secrets Manager, etc.)
- Different keys for dev/staging/production
