from modules.services.preferences_manager import OSPreferencesManager


def test_preferences_default_state(tmp_path):
    manager = OSPreferencesManager(workspace_root=str(tmp_path))

    prefs = manager.state()

    assert prefs.language == "en-US"
    assert prefs.scanlines is True
    assert prefs.telemetry_refresh_seconds == 5


def test_preferences_update_validates_and_persists(tmp_path):
    manager = OSPreferencesManager(workspace_root=str(tmp_path))

    prefs = manager.update(
        {
            "language": "hi-IN",
            "tts_voice": "high-clarity",
            "high_contrast": True,
            "telemetry_refresh_seconds": 99,
        },
        "2026-05-17T00:00:00Z",
    )
    reloaded = OSPreferencesManager(workspace_root=str(tmp_path)).state()

    assert prefs.language == "hi-IN"
    assert prefs.tts_voice == "high-clarity"
    assert prefs.high_contrast is True
    assert prefs.telemetry_refresh_seconds == 30
    assert reloaded.language == "hi-IN"


def test_preferences_reject_unknown_options(tmp_path):
    manager = OSPreferencesManager(workspace_root=str(tmp_path))

    prefs = manager.update(
        {
            "language": "xx-YY",
            "tts_voice": "unknown",
            "telemetry_refresh_seconds": 1,
        },
        "2026-05-17T00:00:00Z",
    )

    assert prefs.language == "en-US"
    assert prefs.tts_voice == "system"
    assert prefs.telemetry_refresh_seconds == 3


def test_preferences_reset(tmp_path):
    manager = OSPreferencesManager(workspace_root=str(tmp_path))
    manager.update({"large_text": True, "scanlines": False}, "2026-05-17T00:00:00Z")

    prefs = manager.reset("2026-05-17T00:01:00Z")

    assert prefs.large_text is False
    assert prefs.scanlines is True
