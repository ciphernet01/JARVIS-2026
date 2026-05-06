"""
Integration Skills for JARVIS
Skills that connect the assistant to external services and persistence
"""

import logging
import os
import platform
import re
import sys
import webbrowser
from typing import Any, Dict, List, Optional

import requests

from .base import Skill
from ..integration.email_service import SecureEmailService

logger = logging.getLogger(__name__)


class WebSearchSkill(Skill):
    """Open a web search for the user's query"""

    def __init__(self):
        super().__init__("web_search_skill", "1.0")

    @property
    def keywords(self) -> List[str]:
        return ["search for", "google", "look up", "search web", "web search"]

    @property
    def description(self) -> str:
        return "Search the web and open results in a browser"

    def execute(self, query: str, context: Dict[str, Any] = None) -> str:
        search_term = query
        for prefix in ["search for", "google", "look up", "search web", "web search"]:
            if prefix in search_term.lower():
                search_term = re.sub(prefix, "", search_term, flags=re.IGNORECASE).strip()
        if not search_term:
            return "Please tell me what you want me to search for."

        url = f"https://www.google.com/search?q={requests.utils.quote(search_term)}"
        try:
            webbrowser.open(url)
            logger.info(f"Opened web search for: {search_term}")
            return f"Searching the web for {search_term}. I've opened the results in your browser."
        except Exception as e:
            logger.error(f"Failed to open browser: {e}")
            return f"I could not open the browser, but here is the search link: {url}"


class OpenLinkSkill(Skill):
    """Directly open a website or URL"""

    def __init__(self):
        super().__init__("open_link_skill", "1.0")
        self.popular_sites = {
            "youtube": "https://www.youtube.com",
            "instagram": "https://www.instagram.com",
            "google": "https://www.google.com",
            "facebook": "https://www.facebook.com",
            "twitter": "https://www.twitter.com",
            "github": "https://www.github.com",
            "reddit": "https://www.reddit.com",
            "gmail": "https://mail.google.com",
            "chatgpt": "https://chat.openai.com",
        }

    @property
    def keywords(self) -> List[str]:
        return ["open youtube", "open instagram", "go to", "open link", "visit"]

    @property
    def description(self) -> str:
        return "Open a specific website or URL directly in the browser"

    def execute(self, query: str, context: Dict[str, Any] = None) -> str:
        target = query.lower()
        for prefix in ["open youtube", "open instagram", "go to", "open link", "visit", "open"]:
            if target.startswith(prefix):
                target = target.replace(prefix, "").strip()
                break
        
        if not target:
            return "Please specify what you'd like me to open."

        # Check for popular sites
        url = self.popular_sites.get(target)
        if not url:
            # Try to see if it's a domain name
            if "." in target:
                url = f"https://{target}" if not target.startswith("http") else target
            else:
                # Fallback to search query if no clear link
                url = f"https://www.google.com/search?q={requests.utils.quote(target)}"

        try:
            webbrowser.open(url)
            logger.info(f"Opened URL: {url}")
            return f"Directly opening {target} for you now."
        except Exception as e:
            logger.error(f"Failed to open URL {url}: {e}")
            return f"I failed to open the link, but you can find it here: {url}"


class WeatherSkill(Skill):
    """Get current weather using wttr.in"""

    def __init__(self):
        super().__init__("weather_skill", "1.0")

    @property
    def keywords(self) -> List[str]:
        return ["weather", "temperature", "forecast"]

    @property
    def description(self) -> str:
        return "Get current weather information"

    def execute(self, query: str, context: Dict[str, Any] = None) -> str:
        match = re.search(r"weather(?: in)?\s+(.*)", query, re.IGNORECASE)
        city = match.group(1).strip() if match and match.group(1).strip() else ""
        if not city:
            city = context.get("default_city") if context else None
        if not city:
            return "Tell me the city you want the weather for."

        try:
            response = requests.get(
                f"https://wttr.in/{requests.utils.quote(city)}?format=3",
                timeout=10,
                headers={"User-Agent": "JARVIS/1.0"},
            )
            if response.status_code == 200:
                return response.text.strip()
            return f"I could not get the weather for {city}."
        except Exception as e:
            logger.error(f"Weather lookup failed: {e}")
            return f"Weather service is unavailable for {city}."


class SystemInfoSkill(Skill):
    """Report system information"""

    def __init__(self):
        super().__init__("system_info_skill", "1.0")

    @property
    def keywords(self) -> List[str]:
        return ["system info", "system status", "device info", "computer info"]

    @property
    def description(self) -> str:
        return "Report basic system information"

    def execute(self, query: str, context: Dict[str, Any] = None) -> str:
        return (
            f"Running on {platform.system()} {platform.release()} with Python {sys.version_info.major}.{sys.version_info.minor}. "
            f"Machine: {platform.machine()}."
        )


class ReminderSkill(Skill):
    """Store reminders in persistence"""

    def __init__(self):
        super().__init__("reminder_skill", "1.0")

    @property
    def keywords(self) -> List[str]:
        return ["remind me", "reminder", "schedule reminder", "add reminder"]

    @property
    def description(self) -> str:
        return "Create reminders stored in the persistence layer"

    def execute(self, query: str, context: Dict[str, Any] = None) -> str:
        persistence = context.get("persistence") if context else None
        user_id = context.get("user_id") if context else None
        task_store = persistence.get("task_store") if persistence else None
        if not task_store or not user_id:
            return "Reminder storage is not available yet."

        text = re.sub(r"^(remind me to|add reminder to|reminder to)\s*", "", query, flags=re.IGNORECASE).strip()
        if not text:
            return "Tell me what I should remind you about."

        task_id = task_store.create_task(user_id=user_id, task_name=text, schedule="manual", status="pending")
        if task_id:
            return f"Reminder saved: {text}"
        return "I could not save that reminder."


class CalendarSkill(Skill):
    """Create and list calendar-style tasks"""

    def __init__(self):
        super().__init__("calendar_skill", "1.0")

    @property
    def keywords(self) -> List[str]:
        return ["calendar", "appointment", "meeting", "schedule"]

    @property
    def description(self) -> str:
        return "Manage calendar-like scheduled tasks"

    def execute(self, query: str, context: Dict[str, Any] = None) -> str:
        persistence = context.get("persistence") if context else None
        user_id = context.get("user_id") if context else None
        task_store = persistence.get("task_store") if persistence else None
        if not task_store or not user_id:
            return "Calendar scheduling is not available."

        if "list" in query.lower():
            tasks = task_store.get_user_tasks(user_id)
            if not tasks:
                return "You have no scheduled items."
            lines = [f"- {task['task_name']} ({task.get('status', 'pending')})" for task in tasks[:10]]
            return "Your scheduled items:\n" + "\n".join(lines)

        task_name = re.sub(r"^(calendar|appointment|meeting|schedule)\s*", "", query, flags=re.IGNORECASE).strip()
        if not task_name:
            return "Tell me what should be scheduled."

        task_id = task_store.create_task(user_id=user_id, task_name=task_name, schedule="manual", status="scheduled")
        if task_id:
            return f"Scheduled: {task_name}"
        return "I could not create that schedule."


class EmailSkill(Skill):
    """Send email using the secure email service"""

    def __init__(self):
        super().__init__("email_skill", "1.0")

    @property
    def keywords(self) -> List[str]:
        return ["send email", "email", "mail"]

    @property
    def description(self) -> str:
        return "Send an email using stored credentials"

    def execute(self, query: str, context: Dict[str, Any] = None) -> str:
        security = context.get("security") if context else None
        credential_manager = security.get("credential_manager") if security else None
        if not credential_manager:
            return "Email credentials are not configured."

        service = context.get("email_provider", "gmail") if context else "gmail"
        email_service = SecureEmailService(credential_manager)
        if not email_service.authenticate(service):
            return f"I could not authenticate with {service}."

        match = re.search(r"send email to (.+?) subject[: ](.+?) body[: ](.+)$", query, re.IGNORECASE)
        if not match:
            email_service.disconnect()
            return "Use: send email to recipient subject: your subject body: your message"

        recipient = match.group(1).strip()
        subject = match.group(2).strip()
        body = match.group(3).strip()
        sent = email_service.send_email(recipient, subject, body)
        email_service.disconnect()
        if sent:
            return f"Email sent to {recipient}."
        return f"I could not send the email to {recipient}."


class CameraSkill(Skill):
    """Capture webcam frames and detect faces"""

    def __init__(self):
        super().__init__("camera_skill", "1.0")

    @property
    def keywords(self) -> List[str]:
        return ["open camera", "camera", "take photo", "face detect", "detect faces", "vision"]

    @property
    def description(self) -> str:
        return "Open the webcam and detect faces"

    def execute(self, query: str, context: Dict[str, Any] = None) -> str:
        vision = context.get("vision") if context else None
        if not vision:
            return "Computer vision is not initialized yet."

        lowered = query.lower()
        if "face" in lowered or "detect" in lowered:
            result = vision.detect_faces(save_annotated=True)
            if not result.get("success"):
                return result.get("message", "I could not analyze the camera feed.")
            count = result.get("faces_detected", 0)
            path = result.get("output_path")
            if count == 0:
                return f"Camera checked. No faces detected. Snapshot saved to {path}."
            return f"Detected {count} face(s). Snapshot saved to {path}."

        result = vision.capture_snapshot(save_annotated=True)
        if not result.get("success"):
            return result.get("message", "I could not access the camera.")
        count = result.get("faces_detected", 0)
        path = result.get("output_path")
        if count:
            return f"Camera activated. Detected {count} face(s). Snapshot saved to {path}."
        return f"Camera activated. No faces detected. Snapshot saved to {path}."
