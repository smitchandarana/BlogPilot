"""
One-time credential setup script.

Run this ONCE to encrypt and save your LinkedIn credentials:

    python -m backend.utils.setup_credentials

Credentials are stored encrypted in config/.secrets/linkedin.json
using Fernet (AES-128-CBC) with a machine-derived key.
They are NEVER stored in plaintext anywhere.
"""
import os
import sys

# Ensure project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def main():
    print()
    print("=" * 50)
    print("  LinkedIn AI Engine — Credential Setup")
    print("=" * 50)
    print()
    print("Credentials will be stored encrypted at:")
    print("  config/.secrets/linkedin.json")
    print()
    print("They are encrypted with a machine-specific key.")
    print("They CANNOT be transferred to another machine.")
    print()

    email = input("LinkedIn email address: ").strip()
    if not email:
        print("ERROR: email cannot be empty")
        sys.exit(1)

    import getpass
    password = getpass.getpass("LinkedIn password (hidden): ").strip()
    if not password:
        print("ERROR: password cannot be empty")
        sys.exit(1)

    confirm = getpass.getpass("Confirm password: ").strip()
    if password != confirm:
        print("ERROR: passwords do not match")
        sys.exit(1)

    try:
        from backend.automation.linkedin_login import save_credentials
        save_credentials(email, password)
        print()
        print("✓ Credentials saved and encrypted successfully.")
        print("  You can now start the engine.")
        print()
    except Exception as e:
        print(f"ERROR saving credentials: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
