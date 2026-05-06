"""
Secure Integration Example - Email Service
Shows how to use the credential system for integrations
"""

import logging
import smtplib
from typing import Optional, List
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

logger = logging.getLogger(__name__)


class SecureEmailService:
    """
    Secure email service using credential vault

    Example of how to implement integrations with secure credentials
    """

    def __init__(self, credential_manager):
        """
        Initialize email service

        Args:
            credential_manager: CredentialManager instance
        """
        self.credential_manager = credential_manager
        self.smtp_server = None
        self.authenticated = False

    def authenticate(self, provider: str = "gmail") -> bool:
        """
        Authenticate with email service

        Args:
            provider: Email provider ("gmail", "outlook")

        Returns:
            True if authenticated
        """
        try:
            if provider.lower() == "gmail":
                email = self.credential_manager.get_credential("gmail", "email")
                password = self.credential_manager.get_credential("gmail", "password")
                smtp_server = "smtp.gmail.com"
                smtp_port = 587
            elif provider.lower() == "outlook":
                email = self.credential_manager.get_credential("outlook", "email")
                password = self.credential_manager.get_credential("outlook", "password")
                smtp_server = "smtp.live.com"
                smtp_port = 587
            else:
                logger.error(f"Unknown email provider: {provider}")
                return False

            if not email or not password:
                logger.error(f"Missing credentials for {provider}")
                return False

            # Connect to SMTP server
            self.smtp_server = smtplib.SMTP(smtp_server, smtp_port)
            self.smtp_server.starttls()
            self.smtp_server.login(email, password)

            self.authenticated = True
            logger.info(f"Authenticated with {provider}")
            return True

        except Exception as e:
            logger.error(f"Email authentication failed: {e}")
            self.authenticated = False
            return False

    def send_email(
        self,
        recipient: str,
        subject: str,
        body: str,
        attachments: Optional[List[str]] = None,
    ) -> bool:
        """
        Send an email

        Args:
            recipient: Recipient email address
            subject: Email subject
            body: Email body
            attachments: List of file paths to attach

        Returns:
            True if sent successfully
        """
        if not self.authenticated:
            logger.error("Not authenticated with email service")
            return False

        try:
            sender = self.credential_manager.get_credential("gmail", "email")

            msg = MIMEMultipart()
            msg["From"] = sender
            msg["To"] = recipient
            msg["Subject"] = subject

            msg.attach(MIMEText(body, "plain"))

            # Add attachments
            if attachments:
                for filepath in attachments:
                    try:
                        with open(filepath, "rb") as attachment:
                            part = MIMEBase("application", "octet-stream")
                            part.set_payload(attachment.read())
                            encoders.encode_base64(part)
                            part.add_header(
                                "Content-Disposition",
                                f"attachment; filename= {filepath}",
                            )
                            msg.attach(part)
                    except Exception as e:
                        logger.error(f"Failed to attach file {filepath}: {e}")

            # Send email
            self.smtp_server.sendmail(sender, recipient, msg.as_string())
            logger.info(f"Email sent to {recipient}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

    def disconnect(self) -> None:
        """Disconnect from SMTP server"""
        if self.smtp_server:
            try:
                self.smtp_server.quit()
                logger.info("SMTP connection closed")
            except Exception as e:
                logger.error(f"Error closing SMTP connection: {e}")

    def __del__(self):
        """Cleanup on deletion"""
        self.disconnect()
