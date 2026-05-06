# Test Credentials

## Authentication
- **Method**: Biometric simulation (no username/password)
- **Login**: Click "Initialize Bio-Scan" button on login page
- **Token**: Auto-generated UUID stored in localStorage as `jarvis_token`
- **API Auth**: Include `X-JARVIS-TOKEN: <token>` header in all protected requests

## API Access
- **Base URL**: https://fa677ab0-6bef-4972-bbf0-b73fcf0fca9b.preview.emergentagent.com
- **Public endpoints**: `/api/health`, `/api/llm/status`
- **Protected endpoints**: All others require X-JARVIS-TOKEN header

## LLM Integration
- **Provider**: Gemini 2.5 Flash via Emergent LLM Key
- **Key Location**: /app/backend/.env (EMERGENT_LLM_KEY)
