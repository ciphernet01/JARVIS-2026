"""
Authentication Manager for JARVIS
Handles user authentication and session management
"""

import logging
import hashlib
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import uuid

logger = logging.getLogger(__name__)


class AuthenticationManager:
    """Manage user authentication"""

    def __init__(self, vault=None):
        """
        Initialize authentication manager

        Args:
            vault: CredentialVault instance for storing password hashes
        """
        self.vault = vault
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.failed_attempts: Dict[str, int] = {}
        self.max_attempts = 5
        self.lockout_duration = 300  # 5 minutes

    def hash_password(self, password: str) -> str:
        """Hash a password"""
        return hashlib.sha256(password.encode()).hexdigest()

    def register_user(self, username: str, password: str, email: str = None) -> bool:
        """
        Register a new user

        Args:
            username: Username
            password: Password
            email: Email address

        Returns:
            True if registration successful
        """
        if not self.vault:
            logger.warning("Vault not available, cannot register user")
            return False

        # Check if user already exists
        if self.vault.has_credential(username, category="users"):
            logger.warning(f"User already exists: {username}")
            return False

        # Store password hash
        password_hash = self.hash_password(password)
        self.vault.store(username, password_hash, category="users")

        # Store email if provided
        if email:
            self.vault.store(f"{username}_email", email, category="users")

        logger.info(f"User registered: {username}")
        return True

    def authenticate(self, username: str, password: str) -> Optional[str]:
        """
        Authenticate a user

        Args:
            username: Username
            password: Password

        Returns:
            Session token if authentication successful, None otherwise
        """
        if not self.vault:
            logger.warning("Vault not available, cannot authenticate")
            return None

        # Check failed attempts
        if username in self.failed_attempts and self.failed_attempts[username] >= self.max_attempts:
            logger.warning(f"Account locked due to failed attempts: {username}")
            return None

        # Get stored password hash
        stored_hash = self.vault.retrieve(username, category="users")

        if not stored_hash:
            logger.warning(f"User not found: {username}")
            self.failed_attempts[username] = self.failed_attempts.get(username, 0) + 1
            return None

        # Verify password
        password_hash = self.hash_password(password)

        if password_hash != stored_hash:
            logger.warning(f"Authentication failed for user: {username}")
            self.failed_attempts[username] = self.failed_attempts.get(username, 0) + 1
            return None

        # Clear failed attempts
        self.failed_attempts[username] = 0

        # Create session token
        session_token = str(uuid.uuid4())
        self.sessions[session_token] = {
            "username": username,
            "created_at": datetime.now(),
            "last_activity": datetime.now(),
            "ip": "local",  # In real app, would capture actual IP
        }

        logger.info(f"User authenticated: {username}")
        return session_token

    def validate_session(self, session_token: str, timeout_minutes: int = 30) -> bool:
        """
        Validate a session token

        Args:
            session_token: Session token to validate
            timeout_minutes: Session timeout in minutes

        Returns:
            True if session valid
        """
        if session_token not in self.sessions:
            logger.warning(f"Invalid session token")
            return False

        session = self.sessions[session_token]
        last_activity = session["last_activity"]
        timeout = datetime.now() - timedelta(minutes=timeout_minutes)

        if last_activity < timeout:
            logger.warning(f"Session expired: {session_token}")
            del self.sessions[session_token]
            return False

        # Update last activity
        session["last_activity"] = datetime.now()
        return True

    def logout(self, session_token: str) -> bool:
        """
        Logout a user

        Args:
            session_token: Session token

        Returns:
            True if logout successful
        """
        if session_token in self.sessions:
            username = self.sessions[session_token]["username"]
            del self.sessions[session_token]
            logger.info(f"User logged out: {username}")
            return True
        return False

    def change_password(self, username: str, old_password: str, new_password: str) -> bool:
        """
        Change user password

        Args:
            username: Username
            old_password: Current password
            new_password: New password

        Returns:
            True if password changed
        """
        if not self.vault:
            logger.warning("Vault not available")
            return False

        # Verify old password
        stored_hash = self.vault.retrieve(username, category="users")
        if not stored_hash or self.hash_password(old_password) != stored_hash:
            logger.warning(f"Invalid password for user: {username}")
            return False

        # Store new password
        new_hash = self.hash_password(new_password)
        self.vault.store(username, new_hash, category="users")

        logger.info(f"Password changed for user: {username}")
        return True

    def get_current_user(self, session_token: str) -> Optional[str]:
        """Get current logged-in user"""
        if session_token in self.sessions:
            return self.sessions[session_token]["username"]
        return None
