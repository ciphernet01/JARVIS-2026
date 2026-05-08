# JARVIS AI Assistant - Modern Modular Architecture

## Canonical Web Stack

J.A.R.V.I.S uses one active web setup:

- Frontend: React on `http://localhost:3000`
- Backend: FastAPI on `http://localhost:8001`

Run the backend:

```powershell
cd backend
uvicorn server:app --host 0.0.0.0 --port 8001
```

Run the frontend:

```powershell
cd frontend
$env:REACT_APP_BACKEND_URL="http://localhost:8001"
npm start
```

The older Flask/static dashboard files are legacy only. Use the React/FastAPI stack above for active development.

## Overview

This is the modernized, production-ready version of JARVIS with a clean modular architecture, separating concerns into distinct, testable components.

**Latest Updates (Phase 3 Complete):**
- ✅ Modular architecture with separation of concerns
- ✅ Voice I/O with multiple engine support
- ✅ Extensible skill system for easy feature adding
- ✅ Secure credential management (no hardcoded passwords!)
- ✅ Encryption for sensitive data
- ✅ User authentication system
- ✅ Privacy & consent management (GDPR compliant)

## Architecture

```
jarvis-core/
├── core/                  # Core framework
│   ├── config.py         # Configuration management
│   ├── assistant.py      # Main orchestrator
│   └── exceptions.py     # Custom exceptions
│
├── modules/
│   ├── voice/            # Voice I/O (TTS + STT)
│   ├── skills/           # Extensible skill system
│   ├── integration/      # External service integrations
│   ├── vision/           # Computer vision (future)
│   ├── ui/               # User interfaces (future)
│   ├── security/         # Security & auth (future)
│   └── persistence/      # Data storage (future)
│
├── tests/                # Unit & integration tests
├── config/               # Configuration files
└── main.py              # Entry point
```

## Key Features

### 1. **Modular Voice I/O**
```python
from modules.voice import Synthesizer, Recognizer

# Text-to-Speech
synthesizer = Synthesizer(engine_type="pyttsx3", voice_id="0")
synthesizer.speak("Hello world")
synthesizer.set_rate(150)
synthesizer.set_volume(1.0)

# Speech-to-Text
recognizer = Recognizer(language="en-US", timeout=10)
text = recognizer.listen_once()
```

### 2. **Extensible Skill System**
```python
from modules.skills import Skill, SkillRegistry

# Create custom skill
class MySkill(Skill):
    @property
    def keywords(self):
        return ["my command", "trigger"]
    
    @property
    def description(self):
        return "What this skill does"
    
    def execute(self, query, context=None):
        return "Response to user"

# Register and use
registry = SkillRegistry()
registry.register(MySkill())
response = registry.execute_query("my command")
```

### 4. **Security & Credential Management**
```python
from modules.security import CredentialManager, SecuritySetup

# Initialize security
security = SecuritySetup.initialize()
credential_manager = security['credential_manager']

# Get credential (from env variable, vault, or default)
api_key = credential_manager.get_credential(
    service="openai",
    key="api_key",
    default="fallback-key"
)

# Store credential securely
credential_manager.store_credential(
    service="gmail",
    5ey="password",
    value="app-password-here"
)

# Works with encrypted vault
vault = security['vault']
vault.store("apikey", "secret123", category="myservice")
retrieved = vault.retrieve("apikey", category="myservice")
```
```python
from core import ConfigManager

config = ConfigManager()

# Voice configuration
config.voice.engine = "pyttsx3"
config.voice.speech_rate = 150

# Security configuration
config.security.enable_encryption = True
config.security.password_required = True

# Save configuration
config.save()
```

### 4. **Main Assistant Orchestrator**
```python
from core import Assistant, ConfigManager
from modules.voice import Synthesizer, Recognizer
from modules.skills import SkillRegistry

# Setup
config = ConfigManager()
synthesizer = Synthesizer()
recognizer = Recognizer()
skill_registry = SkillRegistry()

# Create assistant
assistant = Assistant(
    config_manager=config,
    skill_registry=skill_registry,
    synthesizer=synthesizer,
    recognizer=recognizer,
)

# Run in interactive mode (console input)
assistant.interactive_mode()

# Or run in voice mode (microphone input)
# assistant.voice_mode()
```

## Usage

### Quick Start

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Run in interactive mode (no microphone needed):**
```bash
python main.py --mode interactive
```

3. **Run in voice mode (requires microphone):**
```bash
python main.py --mode voice
```

### Example: Adding a Custom Skill

Create `my_weather_skill.py`:

```python
from modules.skills import Skill
from typing import List

claSecurity Features

### Secure Credential Management

Replace hardcoded credentials like:
```python
# OLD ❌ - NEVER DO THIS
smtpserver.login('user@gmail.com', 'password123')
```

With secure vault:
```python
# NEW ✅ - Use vault or environment variables
api_key = credential_manager.get_credential("gmail", "password")
```

### Three-Level Credential Lookup

1. **Environment Variables** (highest priority)
   ```bash
   export JARVIS_GMAIL_PASSWORD=app-password-here
   ```

2. **Encrypted Vault** (persistent storage)
   ```python
   vault.store("password", "secret", category="gmail")
   ```

3. **Default Values** (fallback)
   ```python
   credential_manager.get_credential("service", "key", default="fallback")
   ```

### Encryption & Privacy

```python
from modules.security import Encryptor, PrivacyManager

# Encrypt sensitive data
encryptor = Encryptor()
encrypted = encryptor.encrypt("sensitive data")
decrypted = encryptor.decrypt(encrypted)

# Privacy management (GDPR compliant)
privacy_manager = PrivacyManager()
privacy_manager.set_consent(user_id, "voice_logging", enabled=True)

# Request data deletion
privacy_manager.request_data_deletion(user_id)
```

See [SECURITY_MIGRATION.md](SECURITY_MIGRATION.md) for complete security guide.ll(Skill):
    def __init__(self):
        super().__init__("weather_skill", "1.0")
    
    @property
    def keywords(self) -> List[str]:
        return ["weather", "temperature", "forecast"]
    
    @property
    def description(self) -> str:
        return "Get weather information"
    
    def execute(self, query: str, context=None):
        # Todo: Call weather API
        return "Today's weather is sunny, 72°F"
```

Then in `main.py`:

```python
from my_weather_skill import WeatherSkill

# In setup_skills function
registry.register(WeatherSkill())
```

## Configuration

Configuration can be customized via:

1. **Configuration file** (`~/.jarvis/jarvis.json`):
```json
{
  "voice": {
    "engine": "pyttsx3",
    "speech_rate": 150,
    "volume": 1.0
  },
  "security": {
    "enable_encryption": true,
    "password_required": false
  },
  "ui": {
    "theme": "dark",
    "always_on_top": false
  }
}
```

2. **Environment variables**:
```bash
export OPENAI_API_KEY="your-key-here"
export GMAIL_PASSWORD="your-password-here"
```

3. **Programmatically**:
```python
config = ConfigManager()
config.voice.speech_rate = 150
config.save()
```

## Built-in Skills

- **TimeSkill** - Tell current time
- **DateSkill** - Tell current date
- **GreetingSkill** - Greet user
- **HelpSkill** - Show available skills
- **StatusSkill** - Report assistant status
 (Phase 1)
- Voice I/O with TTS + STT (Phase 1)
- Extensible skill system (Phase 1)
- Configuration management (Phase 1)
- Built-in basic skills (Phase 1)
- Interactive and voice modes (Phase 1)
- Secure credential vault (Phase 3) ✨
- Encryption & privacy management (Phase 3) ✨
- Authentication system (Phase 3) ✨
- Environment variable support (Phase 3) ✨
- GDPR-compliant privacy controls (Phase 3) ✨UG level and above)

## Troubleshooting

### Microphone not working?
Run in interactive mode instead: `python main.py --mode interactive`

### Voice not working?
Check available voices:
```python
from modules.voice import Synthesizer
s = Synthesizer()
voices = s.get_available_voices()
for v in voices:
    print(v)
```

### Can't import modules?
Make sure you're in the `jarvis-core` directory and Python path includes it:
```bash
cd jarvis-core
python main.py
```

## Next Steps

### Phase 2: Advanced Features (Coming soon)
- GPT-4 integration for intelligent responses
- Natural language understanding
- Context management
- Long-term memory

### Phase 3: Integration
- Email (Gmail, Outlook)
- Calendar (Google, Outlook)
- Web search
- Smart home integration

### Phase 4: UI Enhancement
- Desktop GUI (PyQt5/Tkinter)
- Web dashboard (FastAPI + React)
- System tray integration

### Phase 5: Security
- User authentication
- Encrypted configuration
- API key vault
- Audit logging

## Testing

Run tests with:
```bash
pytest tests/
```

## Contributing

To add new skills:

1. Create skill in `modules/skills/`
2. Inherit from `Skill` base class
3. Implement `keywords`, `description`, and `execute` methods
4. Register in `main.py`

## License

MIT License

## Changelog

**v1.0.0 (May 3, 2026)**
- Initial modular architecture
- Voice I/O (TTS + STT)
- Extensible skill system
- Configuration management
- Built-in basic skills
- Interactive and voice modes
