"""Persistent OS preference management for JARVIS."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional


SUPPORTED_LANGUAGES = {
    "en-US": "English (US)",
    "en-GB": "English (UK)",
    "hi-IN": "Hindi (India)",
    "es-ES": "Spanish",
    "fr-FR": "French",
    "de-DE": "German",
}

SUPPORTED_TTS_VOICES = {"system", "calm", "concise", "high-clarity"}


@dataclass(frozen=True)
class OSPreferences:
    language: str = "en-US"
    tts_voice: str = "system"
    high_contrast: bool = False
    reduced_motion: bool = False
    large_text: bool = False
    scanlines: bool = True
    telemetry_refresh_seconds: int = 5
    updated_at: Optional[str] = None


class OSPreferencesManager:
    """Load, validate, and persist user-facing OS preferences."""

    def __init__(self, workspace_root: Optional[str] = None):
        root = Path(workspace_root).resolve() if workspace_root else Path(__file__).resolve().parents[2]
        self.preferences_path = root / "memory" / "preferences" / "os_preferences.json"

    def defaults(self) -> OSPreferences:
        return OSPreferences()

    def state(self) -> OSPreferences:
        if not self.preferences_path.exists():
            return self.defaults()
        try:
            with self.preferences_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            return OSPreferences(**self._validate(data))
        except Exception:
            return self.defaults()

    def update(self, changes: Dict[str, Any], updated_at: str) -> OSPreferences:
        current = asdict(self.state())
        current.update(changes)
        current["updated_at"] = updated_at
        validated = self._validate(current)
        self.preferences_path.parent.mkdir(parents=True, exist_ok=True)
        with self.preferences_path.open("w", encoding="utf-8") as handle:
            json.dump(validated, handle, indent=2, sort_keys=True)
        return OSPreferences(**validated)

    def reset(self, updated_at: str) -> OSPreferences:
        prefs = asdict(self.defaults())
        prefs["updated_at"] = updated_at
        self.preferences_path.parent.mkdir(parents=True, exist_ok=True)
        with self.preferences_path.open("w", encoding="utf-8") as handle:
            json.dump(prefs, handle, indent=2, sort_keys=True)
        return OSPreferences(**prefs)

    def capabilities(self) -> Dict[str, Any]:
        return {
            "languages": [{"code": code, "label": label} for code, label in SUPPORTED_LANGUAGES.items()],
            "tts_voices": sorted(SUPPORTED_TTS_VOICES),
            "telemetry_refresh_range": {"min": 3, "max": 30},
        }

    def _validate(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        defaults = asdict(self.defaults())
        data = {**defaults, **raw}
        if data["language"] not in SUPPORTED_LANGUAGES:
            data["language"] = defaults["language"]
        if data["tts_voice"] not in SUPPORTED_TTS_VOICES:
            data["tts_voice"] = defaults["tts_voice"]
        for key in ["high_contrast", "reduced_motion", "large_text", "scanlines"]:
            data[key] = bool(data[key])
        try:
            data["telemetry_refresh_seconds"] = int(data["telemetry_refresh_seconds"])
        except (TypeError, ValueError):
            data["telemetry_refresh_seconds"] = defaults["telemetry_refresh_seconds"]
        data["telemetry_refresh_seconds"] = max(3, min(30, data["telemetry_refresh_seconds"]))
        return data
