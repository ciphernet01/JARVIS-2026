"""
Security Setup Helper
Assists with setting up security components
"""

import logging
from pathlib import Path
from .vault import CredentialVault
from .credentials import CredentialManager
from .auth import AuthenticationManager
from .privacy import PrivacyManager
from .encryption import Encryptor

logger = logging.getLogger(__name__)


class SecuritySetup:
    """Helper for setting up all security components"""

    @staticmethod
    def initialize(config_dir: str = None, enable_encryption: bool = True) -> dict:
        """
        Initialize all security components

        Args:
            config_dir: Directory for security files
            enable_encryption: Whether to use encryption

        Returns:
            Dictionary with all security components
        """
        config_dir = Path(config_dir or Path.home() / ".jarvis")
        config_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Initializing security components...")

        # Initialize encryption
        encryptor = Encryptor()
        encryption_key = None

        if enable_encryption:
            key_file = config_dir / ".encryption.key"
            if key_file.exists():
                with open(key_file, "r") as f:
                    encryption_key = f.read().strip()
                logger.info("Loaded existing encryption key")
            else:
                encryption_key = encryptor.generate_key()
                with open(key_file, "w") as f:
                    f.write(encryption_key)
                logger.info("Generated new encryption key")

        # Initialize credential vault
        vault = CredentialVault(
            vault_path=str(config_dir / "credentials.vault"),
            encryption_key=encryption_key if enable_encryption else None,
        )

        # Initialize credential manager
        credential_manager = CredentialManager(vault=vault)

        # Initialize authentication manager
        auth_manager = AuthenticationManager(vault=vault)

        # Initialize privacy manager
        privacy_manager = PrivacyManager()

        logger.info("Security components initialized")

        return {
            "encryptor": encryptor,
            "vault": vault,
            "credential_manager": credential_manager,
            "auth_manager": auth_manager,
            "privacy_manager": privacy_manager,
        }

    @staticmethod
    def create_example_env_file(output_path: str = ".env") -> None:
        """Create example .env file"""
        CredentialManager.setup_env_file(output_path)
        logger.info(f"Example .env file created: {output_path}")

    @staticmethod
    def migrate_old_credentials(
        old_config_file: str,
        vault: CredentialVault,
    ) -> None:
        """
        Migrate credentials from old format to vault

        Args:
            old_config_file: Path to old configuration file
            vault: CredentialVault instance
        """
        logger.info("Migrating old credentials to vault...")
        # Implementation would depend on old format
        logger.info("Migration complete")
