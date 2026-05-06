"""
Privacy Manager for JARVIS
Handles data privacy and consent management
"""

import logging
from typing import Optional, Dict, List, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class PrivacyManager:
    """Manage user privacy and data consent"""

    def __init__(self):
        """Initialize privacy manager"""
        self.consents: Dict[str, Dict[str, Any]] = {}
        self.data_deletion_requests: Dict[str, datetime] = {}
        self.tracking_enabled = False
        self.analytics_enabled = True

    def set_consent(
        self,
        user_id: str,
        feature: str,
        enabled: bool,
        reason: Optional[str] = None,
    ) -> None:
        """
        Set user consent for a feature

        Args:
            user_id: User ID
            feature: Feature name (e.g., "voice_logging", "analytics")
            enabled: Consent granted
            reason: Reason for change
        """
        if user_id not in self.consents:
            self.consents[user_id] = {}

        self.consents[user_id][feature] = {
            "enabled": enabled,
            "timestamp": datetime.now().isoformat(),
            "reason": reason,
        }

        status = "granted" if enabled else "revoked"
        logger.info(f"Consent {status} for {user_id}: {feature}")

    def has_consent(self, user_id: str, feature: str) -> bool:
        """Check if user has given consent for a feature"""
        if user_id not in self.consents:
            return False

        if feature not in self.consents[user_id]:
            return False

        return self.consents[user_id][feature]["enabled"]

    def get_consents(self, user_id: str) -> Dict[str, Any]:
        """Get all consents for a user"""
        return self.consents.get(user_id, {})

    def enable_voice_logging(self, user_id: str, enable: bool = True) -> None:
        """Enable/disable voice conversation logging"""
        self.set_consent(user_id, "voice_logging", enable)

    def enable_analytics(self, user_id: str, enable: bool = True) -> None:
        """Enable/disable analytics"""
        self.set_consent(user_id, "analytics", enable)

    def request_data_deletion(self, user_id: str) -> None:
        """
        Request data deletion for a user

        Args:
            user_id: User ID
        """
        self.data_deletion_requests[user_id] = datetime.now()
        logger.warning(f"Data deletion requested for user: {user_id}")

    def is_deletion_requested(self, user_id: str) -> bool:
        """Check if data deletion was requested"""
        return user_id in self.data_deletion_requests

    def clear_user_data(self, user_id: str) -> None:
        """
        Clear all user data (GDPR right to be forgotten)

        Args:
            user_id: User ID
        """
        # Remove consents
        if user_id in self.consents:
            del self.consents[user_id]

        # Remove deletion request
        if user_id in self.data_deletion_requests:
            del self.data_deletion_requests[user_id]

        logger.warning(f"User data cleared: {user_id}")

    def should_track(self, user_id: str) -> bool:
        """Check if user should be tracked"""
        return self.tracking_enabled and self.has_consent(user_id, "analytics")

    def get_privacy_policy(self) -> str:
        """Get privacy policy text"""
        return """
JARVIS Privacy Policy
=====================

1. Data Collection:
   - Voice commands (if logging enabled)
   - User interactions
   - System analytics (if enabled)

2. Data Usage:
   - Improve service quality
   - Personalize experience
   - Generate analytics

3. Data Protection:
   - Encryption at rest and in transit
   - Secure credential storage
   - Access logging

4. User Rights:
   - Right to access your data
   - Right to delete your data (GDPR)
   - Right to opt-out of analytics

5. Contact:
   - Privacy concerns: privacy@jarvis.local
"""
