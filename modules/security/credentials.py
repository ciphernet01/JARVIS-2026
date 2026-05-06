"""
Environment and Credential Loader
Manages API keys and credentials from environment variables and vault
"""

import logging
import os
from typing import Optional, Dict, Any
from .vault import CredentialVault
from .encryption import Encryptor

logger = logging.getLogger(__name__)


class CredentialManager:
    """Unified credential management"""

    def __init__(self, vault: Optional[CredentialVault] = None):
        """
        Initialize credential manager

        Args:
            vault: CredentialVault instance
        """
        self.vault = vault
        self.env_prefix = "JARVIS_"
        logger.info("Credential manager initialized")

    def get_credential(
        self,
        service: str,
        key: str,
        default: Optional[str] = None,
    ) -> Optional[str]:
        """
        Get a credential from environment, vault, or default

        Lookup order:
        1. Environment variable: JARVIS_{SERVICE}_{KEY}
        2. Vault storage
        3. Default value

        Args:
            service: Service name (e.g., "GMAIL", "OPENAI")
            key: Credential key (e.g., "PASSWORD", "API_KEY")
            default: Default value if not found

        Returns:
            Credential value or None
        """
        # Try environment variable first (high priority)
        env_var = f"{self.env_prefix}{service.upper()}_{key.upper()}"
        env_value = os.getenv(env_var)
        if env_value:
            logger.debug(f"Got credential from environment: {env_var}")
            return env_value

        # Try vault
        if self.vault:
            vault_key = key.lower()
            vault_category = service.lower()
            vault_value = self.vault.retrieve(vault_key, category=vault_category)
            if vault_value:
                logger.debug(f"Got credential from vault: {service}:{vault_key}")
                return vault_value

        # Use default
        if default is not None:
            logger.debug(f"Using default credential for {service}:{key}")
            return default

        logger.warning(f"Credential not found: {service}:{key}")
        return None

    def store_credential(
        self,
        service: str,
        key: str,
        value: str,
        use_vault: bool = True,
    ) -> None:
        """
        Store a credential

        Args:
            service: Service name
            key: Credential key
            value: Credential value
            use_vault: Store in vault (otherwise store only in memory)
        """
        if use_vault and self.vault:
            self.vault.store(key.lower(), value, category=service.lower())
            logger.info(f"Credential stored in vault: {service}:{key}")
        else:
            logger.info(f"Credential stored (not persisted): {service}:{key}")

    def get_service_credentials(self, service: str) -> Dict[str, str]:
        """
        Get all credentials for a service

        Args:
            service: Service name

        Returns:
            Dictionary of credentials
        """
        credentials = {}

        # Get from vault
        if self.vault:
            vault_creds = self.vault.get_category_credentials(service.lower())
            credentials.update(vault_creds)

        logger.info(f"Retrieved {len(credentials)} credentials for {service}")
        return credentials

    def has_credential(self, service: str, key: str) -> bool:
        """Check if credential exists"""
        env_var = f"{self.env_prefix}{service.upper()}_{key.upper()}"
        if os.getenv(env_var):
            return True

        if self.vault:
            return self.vault.has_credential(key.lower(), category=service.lower())

        return False

    def list_services(self) -> list:
        """List all services with stored credentials"""
        if not self.vault:
            return []

        services = set()
        for key in self.vault.list_keys():
            if ":" in key:
                service = key.split(":")[0]
                services.add(service)

        return sorted(list(services))

    @staticmethod
    def setup_env_file(env_file_path: str = ".env.example") -> None:
        """
        Create example .env file with common services

        Args:
            env_file_path: Path to .env file
        """
        example_env = """# JARVIS Environment Configuration
# Copy this to .env and fill in your actual values

# OpenAI API (for future GPT integration)
JARVIS_OPENAI_API_KEY=your-openai-key-here

# Gmail Configuration
JARVIS_GMAIL_EMAIL=your-email@gmail.com
JARVIS_GMAIL_PASSWORD=your-app-password-here

# Microsoft Outlook
JARVIS_OUTLOOK_EMAIL=your-email@outlook.com
JARVIS_OUTLOOK_PASSWORD=your-password-here

# Google APIs
JARVIS_GOOGLE_API_KEY=your-google-api-key

# Twitter/X API
JARVIS_TWITTER_API_KEY=your-api-key
JARVIS_TWITTER_API_SECRET=your-api-secret

# Spotify
JARVIS_SPOTIFY_CLIENT_ID=your-client-id
JARVIS_SPOTIFY_CLIENT_SECRET=your-client-secret

# OpenAI/Whisper (for advanced speech recognition)
JARVIS_WHISPER_API_KEY=your-whisper-key

# Home Assistant (for smart home integration)
JARVIS_HOME_ASSISTANT_URL=http://localhost:8123
JARVIS_HOME_ASSISTANT_TOKEN=your-token

# Database
JARVIS_DATABASE_URL=postgresql://user:password@localhost/jarvis_db

# Security
JARVIS_ENCRYPTION_KEY=your-encryption-key-here
JARVIS_SECRET_KEY=your-secret-key-for-sessions
"""

        try:
            with open(env_file_path, "w") as f:
                f.write(example_env)
            logger.info(f"Created example .env file: {env_file_path}")
        except Exception as e:
            logger.error(f"Failed to create .env file: {e}")
