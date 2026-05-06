"""
Audit Logging
Log user actions for security and compliance
"""

import logging
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


class AuditLogger:
    """Log user actions for audit trail"""

    def __init__(self, db_manager):
        """
        Initialize audit logger

        Args:
            db_manager: DatabaseManager instance
        """
        self.db = db_manager

    def log_action(
        self,
        user_id: Optional[str],
        action: str,
        details: Optional[Dict[str, Any]] = None,
        success: bool = True,
        ip_address: Optional[str] = None,
    ) -> Optional[str]:
        """
        Log an action

        Args:
            user_id: User ID (optional)
            action: Action name
            details: Action details
            success: Whether action succeeded
            ip_address: IP address of requestor

        Returns:
            Log entry ID
        """
        try:
            log_id = str(uuid.uuid4())
            details_json = __import__("json").dumps(details or {})

            self.db.execute("""
                INSERT INTO audit_log (id, user_id, action, details, success, ip_address)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (log_id, user_id, action, details_json, success, ip_address))

            self.db.commit()
            logger.info(f"Action logged: {action} (success={success})")
            return log_id

        except Exception as e:
            logger.error(f"Failed to log action: {e}")
            return None

    def log_login(self, user_id: str, success: bool = True, ip_address: Optional[str] = None) -> Optional[str]:
        """Log login attempt"""
        return self.log_action(
            user_id=user_id,
            action="login",
            details={"attempt": True},
            success=success,
            ip_address=ip_address,
        )

    def log_logout(self, user_id: str, ip_address: Optional[str] = None) -> Optional[str]:
        """Log logout"""
        return self.log_action(
            user_id=user_id,
            action="logout",
            success=True,
            ip_address=ip_address,
        )

    def log_credential_access(self, user_id: str, service: str, success: bool = True) -> Optional[str]:
        """Log credential access"""
        return self.log_action(
            user_id=user_id,
            action="credential_access",
            details={"service": service},
            success=success,
        )

    def log_data_export(self, user_id: str, export_type: str) -> Optional[str]:
        """Log data export"""
        return self.log_action(
            user_id=user_id,
            action="data_export",
            details={"export_type": export_type},
            success=True,
        )

    def log_data_deletion(self, user_id: str) -> Optional[str]:
        """Log data deletion (GDPR)"""
        return self.log_action(
            user_id=user_id,
            action="data_deletion",
            details={"gdpr_request": True},
            success=True,
        )

    def log_permission_denied(self, user_id: Optional[str], action: str) -> Optional[str]:
        """Log permission denied"""
        return self.log_action(
            user_id=user_id,
            action=action,
            details={"permission_denied": True},
            success=False,
        )

    def get_user_audit_log(
        self,
        user_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Get audit log for a user

        Args:
            user_id: User ID
            limit: Number of entries to return
            offset: Offset for pagination

        Returns:
            List of audit log entries
        """
        try:
            cursor = self.db.execute("""
                SELECT * FROM audit_log
                WHERE user_id = ?
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?
            """, (user_id, limit, offset))

            if not cursor:
                return []

            entries = []
            for row in cursor.fetchall():
                entries.append(dict(row))

            return entries

        except Exception as e:
            logger.error(f"Failed to retrieve audit log: {e}")
            return []

    def get_failed_actions(self, user_id: str, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Get failed actions (security analysis)

        Args:
            user_id: User ID
            hours: Number of hours to look back

        Returns:
            List of failed actions
        """
        try:
            cursor = self.db.execute("""
                SELECT * FROM audit_log
                WHERE user_id = ? AND success = 0 AND timestamp > datetime('now', '-' || ? || ' hours')
                ORDER BY timestamp DESC
            """, (user_id, hours))

            if not cursor:
                return []

            return [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Failed to get failed actions: {e}")
            return []

    def detect_suspicious_activity(self, user_id: str) -> bool:
        """
        Detect suspicious activity

        Args:
            user_id: User ID

        Returns:
            True if suspicious activity detected
        """
        # Check for multiple failed login attempts in last hour
        failed_logins = self.db.execute("""
            SELECT COUNT(*) as count FROM audit_log
            WHERE user_id = ? AND action = 'login' AND success = 0
            AND timestamp > datetime('now', '-1 hour')
        """, (user_id,))

        if failed_logins:
            row = failed_logins.fetchone()
            if row and row[0] > 5:
                logger.warning(f"Suspicious activity detected for user {user_id}: multiple failed logins")
                return True

        return False
