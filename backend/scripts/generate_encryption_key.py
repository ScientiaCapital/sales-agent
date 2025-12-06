#!/usr/bin/env python3
"""
Generate a Fernet encryption key for mailbox password encryption.

Usage:
    python scripts/generate_encryption_key.py

This will output a MAILBOX_ENCRYPTION_KEY that you can add to your .env file.
"""
from cryptography.fernet import Fernet


def main():
    """Generate and display a new encryption key."""
    key = Fernet.generate_key().decode()

    print("=" * 80)
    print("MAILBOX PASSWORD ENCRYPTION KEY GENERATED")
    print("=" * 80)
    print()
    print("Add this to your .env file:")
    print()
    print(f"MAILBOX_ENCRYPTION_KEY={key}")
    print()
    print("=" * 80)
    print("IMPORTANT:")
    print("- Keep this key secret and secure")
    print("- Do NOT commit this key to version control")
    print("- Store it in a secure location (password manager, secrets vault)")
    print("- If you lose this key, you cannot decrypt existing passwords")
    print("- Changing this key will invalidate all existing encrypted passwords")
    print("=" * 80)


if __name__ == "__main__":
    main()
