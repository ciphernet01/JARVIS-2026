import pytest
from unittest.mock import patch, MagicMock

@pytest.fixture
def mock_pyautogui():
    with patch("modules.tools.os_control.pyautogui") as mock:
        yield mock



def test_press_key(mock_pyautogui):
    from modules.tools.os_control import PYAUTOGUI_AVAILABLE, press_key
    
    if not PYAUTOGUI_AVAILABLE:
        pytest.skip("pyautogui missing")
        
    res = press_key("enter")
    assert res["success"] is True
    mock_pyautogui.press.assert_called_once_with("enter")


def test_type_text(mock_pyautogui):
    from modules.tools.os_control import PYAUTOGUI_AVAILABLE, type_text
    
    if not PYAUTOGUI_AVAILABLE:
        pytest.skip("pyautogui missing")
        
    res = type_text("hello", 0.1)
    assert res["success"] is True
    mock_pyautogui.write.assert_called_once_with("hello", interval=0.1)


def test_click_screen(mock_pyautogui):
    from modules.tools.os_control import PYAUTOGUI_AVAILABLE, click_screen
    
    if not PYAUTOGUI_AVAILABLE:
        pytest.skip("pyautogui missing")
        
    res = click_screen(100, 200)
    assert res["success"] is True
    mock_pyautogui.click.assert_called_once_with(100, 200)


def test_send_notification():
    from modules.tools.os_control import TOAST_AVAILABLE, send_notification
    
    if not TOAST_AVAILABLE:
        pytest.skip("win10toast missing")
        
    # We must patch the threading behavior or wait for it.
    with patch("threading.Thread") as mock_thread, patch("modules.tools.os_control.toaster") as mock_toaster:
        res = send_notification("Title", "Message")
    
    assert res["success"] is True
    mock_thread.assert_called_once()
