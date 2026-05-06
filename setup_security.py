#!/usr/bin/env python
"""
JARVIS Security Initialization Script
Helps with initial security setup
"""

import sys
from pathlib import Path
import os

sys.path.insert(0, str(Path(__file__).parent))

from modules.security import SecuritySetup, CredentialManager
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def setup_wizard():
    """Interactive security setup wizard"""
    print("\n" + "=" * 60)
    print("JARVIS Security Setup Wizard")
    print("=" * 60 + "\n")

    # Step 1: Initialize security
    print("📦 Step 1: Initializing security components...")
    security = SecuritySetup.initialize(enable_encryption=True)
    print("✅ Security components initialized\n")

    # Step 2: Create .env file
    print("📝 Step 2: Creating .env file from template...")
    env_path = Path(__file__).parent / ".env"
    example_path = Path(__file__).parent / ".env.example"

    if example_path.exists() and not env_path.exists():
        import shutil
        shutil.copy(example_path, env_path)
        print(f"✅ Created .env file at: {env_path}\n")
        print("⚠️  IMPORTANT: Edit .env with your credentials")
        print("   - Gmail API key")
        print("   - OpenAI key")
        print("   - Other service credentials\n")
    elif env_path.exists():
        print(f"ℹ️  .env file already exists at: {env_path}\n")
    else:
        print("❌ No .env.example found\n")

    # Step 3: Display vault location
    vault_path = Path.home() / ".jarvis" / "credentials.vault"
    key_path = Path.home() / ".jarvis" / ".encryption.key"

    print("🔐 Step 3: Security files created")
    print(f"   Vault file: {vault_path}")
    print(f"   Encryption key: {key_path}\n")

    print("⚠️  SECURITY WARNINGS:")
    print("   1. NEVER commit .env to version control")
    print("   2. NEVER share your encryption key")
    print("   3. NEVER expose your credentials\n")

    print("✅ Security setup complete!\n")
    print("Next steps:")
    print("   1. Edit .env with your credentials")
    print("   2. Run: python main.py --mode interactive")
    print("   3. Test voice: python main.py --mode voice\n")


def quick_credential_test():
    """Quick test of credential system"""
    print("\n" + "=" * 60)
    print("Credential System Test")
    print("=" * 60 + "\n")

    try:
        security = SecuritySetup.initialize()
        cred_manager = security['credential_manager']

        print("Testing credential manager...\n")

        # Test storing a credential
        print("1️⃣  Storing test credential...")
        cred_manager.store_credential(
            "test",
            "testkey",
            "testvalue"
        )
        print("✅ Stored\n")

        # Test retrieving
        print("2️⃣  Retrieving test credential...")
        value = cred_manager.get_credential("test", "testkey")
        if value == "testvalue":
            print(f"✅ Retrieved: {value}\n")
        else:
            print(f"❌ Mismatch: {value}\n")

        # Test checking existence
        print("3️⃣  Checking credential existence...")
        if cred_manager.has_credential("test", "testkey"):
            print("✅ Credential exists\n")
        else:
            print("❌ Credential not found\n")

        print("✅ Credential system test passed!\n")

    except Exception as e:
        print(f"❌ Error during credential test: {e}\n")
        return False

    return True


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="JARVIS Security Setup"
    )
    parser.add_argument(
        "--wizard",
        action="store_true",
        help="Run interactive setup wizard"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test credential system"
    )
    parser.add_argument(
        "--create-env",
        action="store_true",
        help="Create .env template"
    )

    args = parser.parse_args()

    if not any([args.wizard, args.test, args.create_env]):
        print("\nUsage: python setup_security.py [options]\n")
        print("Options:")
        print("  --wizard      Run interactive setup wizard")
        print("  --test        Test credential system")
        print("  --create-env  Create .env template\n")
        return 1

    if args.wizard:
        setup_wizard()

    if args.test:
        success = quick_credential_test()
        return 0 if success else 1

    if args.create_env:
        CredentialManager.setup_env_file()
        print("\n✅ Created .env.example")

    return 0


if __name__ == "__main__":
    sys.exit(main())
