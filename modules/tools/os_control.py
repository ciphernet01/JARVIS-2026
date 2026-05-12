"""
OS Control tools for JARVIS agent.
Provides GUI automation and OS level notifications.
"""

import logging
from typing import Dict

logger = logging.getLogger(__name__)

try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
    # Fail-safe to prevent runaway automation
    pyautogui.FAILSAFE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False
    logger.warning("pyautogui is not installed. OS control features will be limited.")

try:
    from win10toast import ToastNotifier
    toaster = ToastNotifier()
    TOAST_AVAILABLE = True
except ImportError:
    TOAST_AVAILABLE = False
    logger.warning("win10toast is not installed. System notifications will be limited.")


def press_key(key: str) -> Dict[str, object]:
    """Press a single keyboard key (e.g., 'enter', 'win', 'esc')."""
    logger.info(f"Tool press_key: {key}")
    if not PYAUTOGUI_AVAILABLE:
        return {"success": False, "output": "", "error": "pyautogui is not installed"}
    
    try:
        pyautogui.press(key)
        return {"success": True, "output": f"Successfully pressed key: {key}", "error": None}
    except Exception as exc:
        logger.error(f"press_key failed: {exc}")
        return {"success": False, "output": "", "error": str(exc)}


def type_text(text: str, interval: float = 0.0) -> Dict[str, object]:
    """Type out the given text string."""
    logger.info(f"Tool type_text: {text[:20]}...")
    if not PYAUTOGUI_AVAILABLE:
        return {"success": False, "output": "", "error": "pyautogui is not installed"}
    
    try:
        pyautogui.write(text, interval=interval)
        return {"success": True, "output": "Text typed successfully", "error": None}
    except Exception as exc:
        logger.error(f"type_text failed: {exc}")
        return {"success": False, "output": "", "error": str(exc)}


def click_screen(x: int, y: int) -> Dict[str, object]:
    """Click at the specified screen coordinates (x, y)."""
    logger.info(f"Tool click_screen: ({x}, {y})")
    if not PYAUTOGUI_AVAILABLE:
        return {"success": False, "output": "", "error": "pyautogui is not installed"}
    
    try:
        pyautogui.click(x, y)
        return {"success": True, "output": f"Clicked at ({x}, {y})", "error": None}
    except Exception as exc:
        logger.error(f"click_screen failed: {exc}")
        return {"success": False, "output": "", "error": str(exc)}


def send_notification(title: str, message: str) -> Dict[str, object]:
    """Send a system-level desktop notification to the user."""
    logger.info(f"Tool send_notification: {title}")
    if not TOAST_AVAILABLE:
        return {"success": False, "output": "", "error": "win10toast is not installed"}
    
    try:
        # Run asynchronously to avoid blocking the toolkit thread
        import threading
        def _notify():
            try:
                toaster.show_toast(
                    title,
                    message,
                    icon_path=None,
                    duration=5,
                    threaded=True
                )
            except Exception as e:
                logger.error(f"background notification failed: {e}")
                
        threading.Thread(target=_notify, daemon=True).start()
        
        return {"success": True, "output": f"Notification '{title}' triggered", "error": None}
    except Exception as exc:
        logger.error(f"send_notification failed: {exc}")
        return {"success": False, "output": "", "error": str(exc)}
