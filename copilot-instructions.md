# JARVIS — GitHub Copilot Instructions

## What you are building

JARVIS is a voice-controlled AI assistant that autonomously builds software — apps, services,
scripts, and APIs — from natural language commands. Think Iron Man's JARVIS: the user speaks,
JARVIS thinks, writes code, runs it, fixes errors, and reports back. Hardware control is out of
scope for now. Future goal: full OS control via voice.

This is NOT a chatbot. JARVIS is an **autonomous agent** that uses LLMs to reason and then
executes real tools (shell, file system, code runner) to get things done.

---

## Project layout

```
jarvis-core/
├── core/
│   ├── assistant.py        # Main orchestrator — conversation loop lives here
│   ├── agent.py            # ReAct agent loop — THIS IS THE BRAIN (build here next)
│   ├── llm_router.py       # Routes queries to right LLM (build here next)
│   ├── config.py           # ConfigManager — already exists
│   └── exceptions.py       # Custom exceptions — already exists
│
├── modules/
│   ├── voice/              # STT + TTS — already built
│   ├── skills/             # Skill registry — already built, being replaced by agent loop
│   ├── tools/              # Agent tools — shell, file, code runner (build here next)
│   ├── memory/             # Short + long term memory (build later)
│   ├── security/           # Credential vault — already built
│   └── services/           # Service manager for apps JARVIS builds (build later)
│
├── config/
│   └── jarvis.json         # Runtime config
├── tests/
└── main.py
```

---

## LLM stack — free models only

JARVIS uses a three-tier LLM stack. Never suggest paid APIs (no OpenAI, no Anthropic API).

### Tier 1 — Gemini (Google AI Studio, free)
- **Gemini 2.5 Pro**: heavy reasoning, architecture decisions, complex code generation
- **Gemini 2.0 Flash**: fast tasks, summarisation, quick rewrites
- API base: `https://generativelanguage.googleapis.com/v1beta`
- Python SDK: `google-generativeai`
- Key from env: `GEMINI_API_KEY`
- Free limits: 50 req/day (Pro), 1500 req/day (Flash)
- **Supports native function calling** — use this for all tool/agent work

### Tier 2 — Groq (free tier)
- **Model**: `llama-3.3-70b-versatile` or `mixtral-8x7b-32768`
- Use for: real-time voice response loop — it returns ~500 tokens/sec
- API is OpenAI-compatible: use `openai` SDK with `base_url="https://api.groq.com/openai/v1"`
- Key from env: `GROQ_API_KEY`
- Free limits: 14,400 req/day
- **Supports tool/function calling**

### Tier 3 — Ollama (local, fully free)
- Use for: offline fallback, private/sensitive tasks, embeddings
- Best models: `qwen2.5-coder:7b` (code), `mistral:7b` (general), `nomic-embed-text` (embeddings)
- API: `http://localhost:11434` (OpenAI-compatible via `/v1` endpoint)
- Use `openai` SDK with `base_url="http://localhost:11434/v1"` and `api_key="ollama"`
- Zero cost, requires local GPU or 16GB+ RAM

### LLM routing logic
```
Voice / real-time response    → Groq (speed priority)
Code generation / build tasks → Gemini 2.5 Pro (quality priority)
Quick rewrites / summaries    → Gemini 2.0 Flash
Offline / quota exceeded      → Ollama qwen2.5-coder
Embeddings / memory           → Ollama nomic-embed-text
```

---

## The agent loop — most important thing to build

JARVIS must use a **ReAct loop** (Reason + Act), not hardcoded keyword matching.

### How it works
1. User speaks → STT → text query
2. Query + tool list sent to LLM (Gemini with function calling)
3. LLM responds with either: a tool call OR a final answer
4. If tool call: execute the tool → feed result back to LLM → repeat from step 3
5. If final answer: speak it back via TTS

### Core agent tools JARVIS must have

Every tool is a Python function with a clear docstring. Register them with the LLM as
function-calling schemas.

```python
# modules/tools/shell.py
def run_shell(command: str, timeout: int = 30) -> dict:
    """Run a shell command. Returns stdout, stderr, returncode."""

# modules/tools/files.py
def write_file(path: str, content: str) -> dict:
    """Write content to a file. Creates directories if needed."""

def read_file(path: str) -> dict:
    """Read a file and return its content."""

def list_directory(path: str) -> dict:
    """List files and folders at a path."""

# modules/tools/code_runner.py
def run_python(code: str, timeout: int = 30) -> dict:
    """Execute Python code in a subprocess sandbox. Returns output."""

def run_node(code: str, timeout: int = 30) -> dict:
    """Execute Node.js code in a subprocess sandbox. Returns output."""

# modules/tools/web.py
def search_web(query: str) -> dict:
    """Search the web using DuckDuckGo (no API key needed). Returns top results."""

def fetch_url(url: str) -> dict:
    """Fetch the text content of a URL."""
```

### Tool execution safety rules
- Always run shell commands in a subprocess with `timeout`
- Never run shell commands without capturing stderr
- Sanitise paths — never allow `..` traversal outside the workspace
- Code runner uses a temp directory, not the main project
- Log every tool call to a local audit file

---

## Builder capability — how JARVIS builds apps

When asked to build something, JARVIS must:

1. **Plan** (Gemini Pro): break the request into files needed, tech stack, steps
2. **Scaffold** (Gemini Pro + write_file tool): write each file
3. **Install deps** (run_shell tool): `pip install` or `npm install`
4. **Run / test** (run_shell tool): execute and capture output
5. **Fix errors** (Gemini Pro): if there are errors, feed them back to the LLM and rewrite
6. **Report**: tell the user what was built, where it lives, how to run it

The build loop runs until tests pass or max 5 retries reached.

---

## Coding conventions — always follow these

### General
- Python 3.11+, type hints everywhere, no `Any` unless unavoidable
- `async/await` for all I/O (LLM calls, shell, file reads)
- Pydantic models for all structured data (tool inputs, tool outputs, LLM responses)
- Never hardcode API keys — always use `os.getenv("KEY_NAME")` or the existing `CredentialManager`
- All new modules must have a corresponding test in `tests/`

### LLM calls
- Always set a `timeout` on API calls (30s default)
- Always handle quota errors (`429`) by routing to the next tier
- Always validate LLM output before executing — don't trust raw JSON from LLM without parsing
- Log every LLM call: model used, token count, latency

### Tool results
- Every tool returns a `dict` with at minimum: `success: bool`, `output: str`, `error: str | None`
- Never raise exceptions from tools — catch internally and return `success: False`

### Voice loop
- Groq responses must begin within 800ms of receiving the query
- Keep voice responses under 3 sentences unless user asks for detail
- Strip markdown from any text going to TTS

### File organisation
- One class per file for major components
- Tool functions in `modules/tools/`, one file per tool category
- New skills in `modules/skills/`, inheriting from the existing `Skill` base class
- Agent-specific code in `core/agent.py` only

---

## Environment variables

```bash
# .env (never commit this)
GEMINI_API_KEY=your_key_here
GROQ_API_KEY=your_key_here
JARVIS_WORKSPACE=~/jarvis-workspace   # where JARVIS writes built apps
JARVIS_LOG_LEVEL=INFO
```

Load with `python-dotenv` at startup in `main.py`.

---

## What to build next — priority order

1. `core/llm_router.py` — LLMRouter class with fallback chain
2. `modules/tools/` — shell, file, code_runner, web tools
3. `core/agent.py` — ReAct loop using Gemini function calling
4. Wire agent into `core/assistant.py` replacing the old SkillRegistry path
5. `modules/memory/short_term.py` — conversation buffer (last N turns)
6. `skills/builder.py` — app scaffolding skill on top of the agent loop
7. `modules/services/manager.py` — start/stop/monitor built services
8. `modules/memory/long_term.py` — SQLite + Ollama embeddings

---

## What NOT to do

- Do NOT use `openai` package pointing at OpenAI's servers — Groq and Ollama both use
  OpenAI-compatible APIs, point `base_url` at them instead
- Do NOT use hardcoded `if "weather" in query` style matching — route everything through the LLM
- Do NOT import from `modules/skills/` in the agent loop — skills are legacy, agent tools replace them
- Do NOT use `asyncio.run()` inside async functions — use `await` throughout
- Do NOT let tool calls modify files outside `JARVIS_WORKSPACE` without explicit user confirmation
- Do NOT send raw user voice input to the LLM without stripping filler words first
- Do NOT use `print()` for logging — use the Python `logging` module
- Do NOT generate synchronous blocking HTTP calls — use `httpx` async client

---

## Dependencies to install

```bash
pip install google-generativeai groq openai httpx pydantic python-dotenv \
            duckduckgo-search rich loguru asyncio aiofiles pytest pytest-asyncio
```

Ollama itself is installed separately from https://ollama.com. Models pulled via:
```bash
ollama pull qwen2.5-coder:7b
ollama pull nomic-embed-text
```

---

## Example: how a build request flows end to end

**User says:** "JARVIS, build me a REST API that returns random motivational quotes"

```
STT → "build me a REST API that returns random motivational quotes"

LLMRouter → Gemini 2.5 Pro (build task)

Agent loop iteration 1:
  LLM thinks → calls write_file("workspace/quotes_api/main.py", <FastAPI code>)
  Tool executes → success

Agent loop iteration 2:
  LLM thinks → calls write_file("workspace/quotes_api/requirements.txt", "fastapi\nuvicorn")
  Tool executes → success

Agent loop iteration 3:
  LLM thinks → calls run_shell("cd workspace/quotes_api && pip install -r requirements.txt")
  Tool executes → success

Agent loop iteration 4:
  LLM thinks → calls run_shell("cd workspace/quotes_api && uvicorn main:app &")
  Tool executes → success, PID captured

LLM final answer → "Done. Your quotes API is running at http://localhost:8000.
                    Try GET /quote to get a random quote."

TTS → speaks the response
```

Total tool calls: 4. Total time: ~15 seconds. No human intervention.

---

## Testing approach

- Every tool must have a unit test that mocks the subprocess/LLM call
- Agent loop tests use a mock LLM that returns scripted tool call sequences
- Run tests with: `pytest tests/ -v`
- Target: 80% coverage on `core/` and `modules/tools/`
