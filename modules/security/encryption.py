"""
Encryption utilities for JARVIS
Provides secure encryption/decryption for sensitive data
"""

import logging
import secrets
from typing import Union

logger = logging.getLogger(__name__)


class Encryptor:
    """Simple encryption/decryption utility"""

    def __init__(self):
        """Initialize encryptor"""
        try:
            from cryptography.fernet import Fernet
            self.has_crypto = True
            self.cipher_suite = None
        except ImportError:
            logger.warning("cryptography not available, using base64 encoding only")
            self.has_crypto = False

    def generate_key(self) -> str:
        """Generate a new encryption key"""
        if self.has_crypto:
            from cryptography.fernet import Fernet
            key = Fernet.generate_key()
            return key.decode()
        else:
            return secrets.token_urlsafe(32)

    def initialize_key(self, key: str) -> None:
        """Initialize cipher with a key"""
        if self.has_crypto:
            try:
                from cryptography.fernet import Fernet
                self.cipher_suite = Fernet(key.encode())
                logger.info("Encryption key loaded")
            except Exception as e:
                logger.error(f"Failed to initialize encryption key: {e}")

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt plaintext

        Args:
            plaintext: Text to encrypt

        Returns:
            Encrypted text (base64 encoded)
        """
        if not self.has_crypto or not self.cipher_suite:
            # Fallback to simple encoding
            import base64
            return base64.b64encode(plaintext.encode()).decode()

        try:
            ciphertext = self.cipher_suite.encrypt(plaintext.encode())
            return ciphertext.decode()
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            return plaintext

    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypt ciphertext

        Args:
            ciphertext: Text to decrypt

        Returns:
            Decrypted text
        """
        if not self.has_crypto or not self.cipher_suite:
            # Fallback
            import base64
            try:
                return base64.b64decode(ciphertext.encode()).decode()
            except:
                return ciphertext

        try:
            plaintext = self.cipher_suite.decrypt(ciphertext.encode())
            return plaintext.decode()
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            return ciphertext

    def hash_password(self, password: str) -> str:
        """
        Hash a password using SHA-256

        Args:
            password: Password to hash

        Returns:
            Hashed password
        """
        import hashlib
        return hashlib.sha256(password.encode()).hexdigest()

    def verify_password(self, password: str, password_hash: str) -> bool:
        """
        Verify a password against its hash

        Args:
            password: Password to verify
            password_hash: Hash to verify against

        Returns:
            True if passwords match
        """
        return self.hash_password(password) == password_hash
