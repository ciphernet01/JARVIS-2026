"""
Credential Vault for JARVIS
Secure storage and retrieval of API keys and credentials
"""

import logging
import json
from typing import Optional, Dict, Any
from pathlib import Path
from .encryption import Encryptor

logger = logging.getLogger(__name__)


class CredentialVault:
    """Secure credential storage"""

    def __init__(self, vault_path: Optional[str] = None, encryption_key: Optional[str] = None):
        """
        Initialize credential vault

        Args:
            vault_path: Path to vault file
            encryption_key: Encryption key (generates new one if not provided)
        """
        self.vault_path = Path(vault_path or Path.home() / ".jarvis" / "credentials.vault")
        self.vault_path.parent.mkdir(parents=True, exist_ok=True)

        self.encryptor = Encryptor()
        self.credentials: Dict[str, Any] = {}
        self.is_encrypted = False

        if encryption_key:
            self.encryptor.initialize_key(encryption_key)
            self.is_encrypted = True
            logger.info("Vault initialized with encryption")
        else:
            logger.info("Vault initialized without encryption")

        self._load_vault()

    def _load_vault(self) -> None:
        """Load credentials from vault file"""
        if not self.vault_path.exists():
            logger.info("Vault file does not exist, starting fresh")
            return

        try:
            with open(self.vault_path, "r") as f:
                data = json.load(f)

            if self.is_encrypted:
                # Decrypt each credential
                for key, value in data.items():
                    if isinstance(value, str):
                        self.credentials[key] = self.encryptor.decrypt(value)
                    else:
                        self.credentials[key] = value
            else:
                self.credentials = data

            logger.info(f"Loaded {len(self.credentials)} credentials from vault")
        except Exception as e:
            logger.error(f"Failed to load vault: {e}")

    def _save_vault(self) -> None:
        """Save credentials to vault file"""
        try:
            data_to_save = {}

            if self.is_encrypted:
                # Encrypt each credential
                for key, value in self.credentials.items():
                    if isinstance(value, str):
                        data_to_save[key] = self.encryptor.encrypt(value)
                    else:
                        data_to_save[key] = value
            else:
                data_to_save = self.credentials

            # Save with restricted permissions
            with open(self.vault_path, "w") as f:
                json.dump(data_to_save, f, indent=2)

            # Set file permissions (Windows doesn't support chmod like Unix)
            logger.info("Vault saved securely")
        except Exception as e:
            logger.error(f"Failed to save vault: {e}")

    def store(self, key: str, value: str, category: str = "general") -> None:
        """
        Store a credential

        Args:
            key: Credential key
            value: Credential value
            category: Category (e.g., "email", "api", "social_media")
        """
        full_key = f"{category}:{key}"
        self.credentials[full_key] = value
        self._save_vault()
        logger.info(f"Stored credential: {full_key}")

    def retrieve(self, key: str, category: str = "general") -> Optional[str]:
        """
        Retrieve a credential

        Args:
            key: Credential key
            category: Category

        Returns:
            Credential value or None
        """
        full_key = f"{category}:{key}"
        value = self.credentials.get(full_key)

        if value:
            logger.debug(f"Retrieved credential: {full_key}")
        else:
            logger.warning(f"Credential not found: {full_key}")

        return value

    def delete(self, key: str, category: str = "general") -> bool:
        """
        Delete a credential

        Args:
            key: Credential key
            category: Category

        Returns:
            True if deleted, False if not found
        """
        full_key = f"{category}:{key}"
        if full_key in self.credentials:
            del self.credentials[full_key]
            self._save_vault()
            logger.info(f"Deleted credential: {full_key}")
            return True
        return False

    def list_keys(self, category: Optional[str] = None) -> list:
        """
        List all credential keys

        Args:
            category: Filter by category (optional)

        Returns:
            List of keys
        """
        if category:
            prefix = f"{category}:"
            return [k.replace(prefix, "") for k in self.credentials.keys() if k.startswith(prefix)]
        else:
            return list(self.credentials.keys())

    def has_credential(self, key: str, category: str = "general") -> bool:
        """Check if credential exists"""
        full_key = f"{category}:{key}"
        return full_key in self.credentials

    def get_category_credentials(self, category: str) -> Dict[str, str]:
        """Get all credentials in a category"""
        prefix = f"{category}:"
        return {
            k.replace(prefix, ""): v
            for k, v in self.credentials.items()
            if k.startswith(prefix)
        }

    def clear(self, category: Optional[str] = None) -> None:
        """Clear credentials (dangerous!)"""
        if category:
            prefix = f"{category}:"
            keys_to_delete = [k for k in self.credentials.keys() if k.startswith(prefix)]
            for k in keys_to_delete:
                del self.credentials[k]
            logger.warning(f"Cleared credentials for category: {category}")
        else:
            self.credentials.clear()
            logger.warning("Cleared ALL credentials - this is permanent!")

        self._save_vault()
