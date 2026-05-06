# PHASE 3: Security & Credentials Management - Migration Guide

## Overview

This document explains how to migrate from the old 2020 JARVIS code (with hardcoded credentials) to the secure credential vault system.

## Problem: Old Approach

The original code had security vulnerabilities:

```python
# ❌ DANGEROUS - NEVER DO THIS
smtpserver.login('ss9415767850@gmail.com', 'shr941@gma.com')  # Hardcoded!
```

Issues:
- Credentials visible in source code
- Anyone with repo access gets passwords
- Can't share code publicly
- No audit trail
- Can't rotate credentials easily

## Solution: New Security Architecture

```
┌─────────────────────────────────────────┐
│      User / Application Code            │
└────────────────┬────────────────────────┘
                 │
        ┌────────▼─────────┐
        │ Credential Manager│  (Unified interface)
        │ (credentials.py)  │
        └────────┬─────────┘
                 │
    ┌────────────┼────────────┐
    │            │            │
┌───▼──┐   ┌────▼────┐   ┌──▼──┐
│.env  │   │Vault DB │   │Env  │
│File  │   │(Encrypted)  │  Vars  │
└──────┘   └─────────┘   └──────┘
```

## Step 1: Initialize Security Foundation

### 1.1 Run Security Setup

```bash
# Initialize encryption and credential vault
python main.py --setup-security

# Output:
# - Encryption key generated: ~/.jarvis/.encryption.key
# - Vault created: ~/.jarvis/credentials.vault
# - Auth system ready
```

### 1.2 Create .env File

```bash
# Copy example and customize
cp .env.example .env

# Edit with your credentials
# JARVIS_GMAIL_EMAIL=your-email@gmail.com
# JARVIS_GMAIL_PASSWORD=your-app-password-here
# # etc.
```

## Step 2: Migrate Old Code

### Example 1: Email Service Migration

### OLD CODE ❌

```python
# main.py (VULNERABLE)
from email.mime.multipart import MIMEMultipart
import smtplib

def sendEmail(to, mail):
    smtpserver = smtplib.SMTP('smtp.gmail.com', 587)
    smtpserver.ehlo()
    smtpserver.starttls()
    smtpserver.login('ss9415767850@gmail.com', 'shr941@gma.com')  # EXPOSED!
    smtpserver.sendmail('ss9415767850@gmail.com', to, mail)
    smtpserver.close()

# Usage
sendEmail('recipient@example.com', 'Hello!')
```

### NEW CODE ✅

```python
from modules.security import CredentialManager, SecuritySetup
from modules.integration import SecureEmailService

# Initialize security
security = SecuritySetup.initialize()
credential_manager = security['credential_manager']

# Create email service
email_service = SecureEmailService(credential_manager)

# Authenticate (credentials loaded from vault/env)
email_service.authenticate(provider="gmail")

# Send email (secure)
email_service.send_email(
    recipient='recipient@example.com',
    subject='Hello',
    body='This is a secure email'
)

# Cleanup
email_service.disconnect()
```

### Example 2: API Integration Migration

### OLD CODE ❌

```python
import requests

# Hardcoded API key!
OPENAI_API_KEY = "sk-12345abcde67890..."

def get_response(prompt):
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers=headers,
        json={"model": "gpt-4", "messages": [{"role": "user", "content": prompt}]}
    )
    return response.json()
```

### NEW CODE ✅

```python
import requests
from modules.security import CredentialManager, SecuritySetup

# Initialize security
security = SecuritySetup.initialize()
credential_manager = security['credential_manager']

def get_response(prompt):
    # Load API key securely (from env or vault)
    api_key = credential_manager.get_credential("openai", "api_key")
    
    if not api_key:
        raise ValueError("OpenAI API key not configured")
    
    headers = {"Authorization": f"Bearer {api_key}"}
    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers=headers,
        json={"model": "gpt-4", "messages": [{"role": "user", "content": prompt}]}
    )
    return response.json()
```

## Step 3: Use Credential Manager

### Store a Credential

```python
from modules.security import CredentialManager

credential_manager = CredentialManager(vault=vault)

# Store credential
credential_manager.store_credential(
    service="myservice",
    key="apikey",
    value="secret-key-123"
)
```

### Retrieve a Credential

```python
# Priority: Environment variable > Vault > Default
api_key = credential_manager.get_credential(
    service="myservice",
    key="apikey",
    default="fallback-key"  # Optional
)

if not api_key:
    print("Credential not found!")
```

### Get All Service Credentials

```python
# Get all Gmail-related credentials
gmail_creds = credential_manager.get_service_credentials("gmail")
# Returns: {"email": "user@gmail.com", "password": "app-password", ...}
```

## Step 4: Authentication Flow

### Register User

```python
from modules.security import AuthenticationManager, CredentialVault

vault = CredentialVault()
auth_manager = AuthenticationManager(vault=vault)

# Register new user
success = auth_manager.register_user(
    username="john_doe",
    password="secure_password_123",
    email="john@example.com"
)

if success:
    print("User registered!")
```

### Authenticate User

```python
# Login
session_token = auth_manager.authenticate(
    username="john_doe",
    password="secure_password_123"
)

if session_token:
    print(f"Logged in! Token: {session_token}")
    
    # Validate session later
    if auth_manager.validate_session(session_token):
        print("Session still valid")
```

### Change Password

```python
success = auth_manager.change_password(
    username="john_doe",
    old_password="secure_password_123",
    new_password="new_secure_password"
)
```

## Step 5: Encryption

### Encrypt Sensitive Data

```python
from modules.security import Encryptor

encryptor = Encryptor()

# Generate encryption key
key = encryptor.generate_key()
print(f"Save this key safely: {key}")

# Encrypt data
plaintext = "my secret data"
encrypted = encryptor.encrypt(plaintext)
print(f"Encrypted: {encrypted}")

# Decrypt data
decrypted = encryptor.decrypt(encrypted)
print(f"Decrypted: {decrypted}")
```

### Hash Passwords

```python
# Hash password (one-way)
password_hash = encryptor.hash_password("my_password")

# Verify password
if encryptor.verify_password("my_password", password_hash):
    print("Password matches!")
```

## Step 6: Privacy Management

### Set User Consent

```python
from modules.security import PrivacyManager

privacy_manager = PrivacyManager()

# Enable voice logging
privacy_manager.set_consent(
    user_id="user123",
    feature="voice_logging",
    enabled=True,
    reason="User gave permission"
)

# Enable analytics
privacy_manager.enable_analytics("user123", enable=True)
```

### Check Consent

```python
# Check if user allowed voice logging
if privacy_manager.has_consent("user123", "voice_logging"):
    print("Can log voice conversations")
else:
    print("Cannot log - user opted out")
```

### Respect User Privacy

```python
# Request data deletion (GDPR)
privacy_manager.request_data_deletion("user123")

# Check if deletion requested
if privacy_manager.is_deletion_requested("user123"):
    # Delete all user data
    privacy_manager.clear_user_data("user123")
    print("User data deleted")
```

## Step 7: Environment Variables

### Setup .env File

Create `.env` in your project root:

```env
# Cloud API Keys
JARVIS_OPENAI_API_KEY=sk-...
JARVIS_GOOGLE_API_KEY=AIza...
JARVIS_TWITTER_API_KEY=...

# Email Services
JARVIS_GMAIL_EMAIL=user@gmail.com
JARVIS_GMAIL_PASSWORD=app-password-here

JARVIS_OUTLOOK_EMAIL=user@outlook.com
JARVIS_OUTLOOK_PASSWORD=...

# Smart Home
JARVIS_HOME_ASSISTANT_URL=http://localhost:8123
JARVIS_HOME_ASSISTANT_TOKEN=...

# Security Keys
JARVIS_ENCRYPTION_KEY=...
JARVIS_SECRET_KEY=...
```

### Load from .env

```python
import os
from dotenv import load_dotenv

# Load from .env
load_dotenv()

# Access variables
api_key = os.getenv("JARVIS_OPENAI_API_KEY")
```

## Step 8: Best Practices

### ✅ DO

```python
# ✅ Use environment variables
api_key = os.getenv("JARVIS_API_KEY")

# ✅ Use credential vault
api_key = credential_manager.get_credential("service", "api_key")

# ✅ Use encryption for sensitive data
encrypted = encryptor.encrypt(sensitive_data)

# ✅ Check consent before processing
if privacy_manager.has_consent(user_id, "data_processing"):
    process_data(user_id)

# ✅ Use HTTPS for all API calls
response = requests.get("https://api.example.com/...", ssl_verify=True)
```

### ❌ DON'T

```python
# ❌ Hardcode credentials
api_key = "sk-12345abcde..."

# ❌ Store credentials in files
with open("config.json") as f:
    config = json.load(f)  # Contains passwords!

# ❌ Log sensitive information
logger.info(f"API Key: {api_key}")

# ❌ Send unencrypted passwords
requests.post(url, data={"password": "plaintext"})

# ❌ Store credentials in version control
git add config.json  # Never do this!
```

## Step 9: Migrate Old Skills

### Old Weather Skill (with hardcoded credentials)

```python
import requests

class WeatherSkill:
    def execute(self, query):
        # Hardcoded API key!
        API_KEY = "abc123def456"
        response = requests.get(
            f"https://api.weatherapi.com/v1/current.json?key={API_KEY}&q=London"
        )
        return response.json()
```

### New Weather Skill (secure)

```python
import requests
from modules.skills import Skill

class WeatherSkill(Skill):
    def __init__(self, credential_manager):
        super().__init__("weather_skill", "1.0")
        self.credential_manager = credential_manager
    
    @property
    def keywords(self):
        return ["weather", "forecast", "temperature"]
    
    @property
    def description(self):
        return "Get weather information"
    
    def execute(self, query, context=None):
        # Load API key securely
        api_key = self.credential_manager.get_credential("weather", "api_key")
        
        if not api_key:
            return "Weather API key not configured"
        
        try:
            response = requests.get(
                f"https://api.weatherapi.com/v1/current.json?key={api_key}&q=London"
            )
            data = response.json()
            temp = data['current']['temp_c']
            condition = data['current']['condition']['text']
            return f"Current weather: {temp}°C, {condition}"
        except Exception as e:
            return f"Error getting weather: {e}"
```

## Troubleshooting

### Credential not found

```python
# Debug: Check where credential exists
if os.getenv("JARVIS_SERVICE_KEY"):
    print("Found in environment variable")

if credential_manager.has_credential("service", "key"):
    print("Found in vault")

# Try retrieving with debug
cred = credential_manager.get_credential("service", "key", default="NOT_FOUND")
print(f"Credential: {cred}")
```

### Encryption issues

```python
# If encryption fails, fall back to unencrypted vault
vault = CredentialVault(encryption_key=None)

# But still use encryption for sensitive data at rest
encryptor = Encryptor()
encrypted_secret = encryptor.encrypt(sensitive_data)
```

### Permission errors

```python
# Check vault file permissions (Windows)
import os
import stat

vault_path = Path.home() / ".jarvis" / "credentials.vault"
if vault_path.exists():
    # On Unix: os.chmod(vault_path, stat.S_IRUSR | stat.S_IWUSR)  # 600
    print(f"Vault exists at: {vault_path}")
```

## Verification Checklist

- [ ] Run `python main.py --setup-security`
- [ ] Create and configure `.env` file
- [ ] Test credential retrieval
- [ ] Verify encryption working
- [ ] Test authentication flow
- [ ] Check privacy settings
- [ ] Audit all hardcoded credentials removed
- [ ] Test with environment variables
- [ ] Verify vault file created and encrypted
- [ ] Test credential rotation

## Next Steps

1. ✅ Phase 3: Security Complete!
2. → Phase 4: Database & Persistence (conversation history, user data)
3. → Phase 5: Skills & Integrations (rebuild with secure credentials)
4. → Phase 6: UI Modernization (secure login interface)
