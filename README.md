# AgentBrowser

AI-powered browser automation agent combining three projects into one unified tool:

- **GenericAgent** - AI agent engine with task planning and memory
- **browser-harness** - CDP-based browser control with compositor-level input
- **CloakBrowser** - Anti-detection browser with patched Chromium, fingerprint spoofing, and human-like behavior

## Features

- Natural language task description (tell the AI what to do, it does it)
- Stealth browser with anti-detection (passes bot detection tests)
- CloakBrowser patched Chromium binary (C++ level anti-detection)
- Human-like mouse/keyboard/scroll behavior (Bezier curves, realistic timing)
- CAPTCHA auto-detection and solving (reCAPTCHA, Turnstile, hCaptcha, slider)
- Task scheduling for timed operations (e.g., ticket booking at specific time)
- **Millisecond-precision ticket grabbing** (12306, JD flash sales, Taobao flash sales)
- Persistent login sessions with encrypted credential storage
- Automatic session expiry detection and re-login
- API key encryption (stored encrypted in config, never plaintext)
- Data extraction and web scraping
- Both CLI and Web GUI interfaces
- Multi-LLM support (OpenAI, Anthropic, DeepSeek, any OpenAI-compatible API)
- Custom API base URL support (for third-party/self-hosted LLMs)
- AI connection verification (`ab doctor`)

## Quick Start

### Install

```bash
# Clone and install
git clone <repo-url>
cd agent-browser
pip install -e .

# Install CloakBrowser's patched Chromium (recommended)
ab chromium install

# Or install Playwright's default Chromium (fallback)
playwright install chromium

# Configure
ab configure
```

### CLI Usage

```bash
# Interactive mode
ab run

# Single task
ab run "Go to google.com and search for 'Python tutorials'"

# With options
ab run --no-headless --provider anthropic "Extract prices from amazon.com/dp/B09V3KXJPB"

# Use persistent login profile
ab run --profile my-amazon "Check my Amazon order status"

# Use custom LLM API (e.g. DeepSeek)
ab run --provider openai --base-url https://api.deepseek.com --model deepseek-chat "Search for news"

# Schedule a task
ab schedule "Book ticket on example.com" "2025-12-31T21:15:00" --pre-check

# Millisecond-precision ticket grabbing (抢票/秒杀)
ab grab "在12306上抢北京到上海的G1列车" -t 2026-05-20T21:00:00
ab grab "Buy iPhone on JD flash sale" -t "2026-06-18T10:00:00" --retry 10 --interval 50

# List tasks
ab tasks

# Manage session profiles
ab profiles list
ab profiles create my-taobao
ab profiles info my-taobao
ab profiles delete my-taobao

# Manage CloakBrowser Chromium
ab chromium install
ab chromium info
ab chromium clear-cache

# System check
ab doctor

# Show version
ab version
```

### Web GUI

```bash
ab web
# Open http://localhost:8899
```

### Python API

```python
import asyncio
from agent_browser import AgentBrowser
from agent_browser.config import AppConfig, LLMConfig

async def main():
    config = AppConfig(llm=LLMConfig(
        api_key="your-api-key",
        provider="openai",          # or "anthropic"
        model="gpt-4o",
        base_url=None,              # custom API URL if needed
    ))

    # Use a named profile for persistent login
    agent = AgentBrowser(config, profile_name="my-profile")
    result = await agent.run_task("Go to example.com and get the page title")
    print(f"Success: {result.success}, Result: {result.result}")
    await agent.close()

asyncio.run(main())
```

#### Using DeepSeek or other third-party LLMs

```python
config = AppConfig(llm=LLMConfig(
    api_key="sk-your-deepseek-key",
    provider="openai",                    # DeepSeek uses OpenAI-compatible format
    model="deepseek-chat",
    base_url="https://api.deepseek.com",  # No need to add /v1
))
agent = AgentBrowser(config)
```

For Anthropic-format proxies:
```python
config = AppConfig(llm=LLMConfig(
    api_key="sk-your-key",
    provider="anthropic",
    model="claude-sonnet-4-20250514",
    base_url="https://api.deepseek.com/anthropic",
))
```

## Architecture

```
agent-browser/
├── src/agent_browser/
│   ├── core/              # Agent engine, LLM, memory, scheduler
│   │   ├── agent.py       # Main agent loop (from GenericAgent)
│   │   ├── llm.py         # Multi-LLM client with tool calling
│   │   ├── grabber.py     # Millisecond-precision ticket grabbing engine
│   │   ├── memory.py      # Layered memory system (L1-L3)
│   │   └── scheduler.py   # Task scheduling (one-shot + cron)
│   ├── browser/           # Browser control layer
│   │   ├── engine.py      # Playwright + CDP control (from browser-harness)
│   │   ├── stealth.py     # Anti-detection launch (from CloakBrowser)
│   │   ├── chromium.py    # CloakBrowser patched Chromium binary manager
│   │   ├── session.py     # Persistent login session profiles
│   │   ├── humanize.py    # Human-like behavior (Bezier curves, timing)
│   │   └── captcha.py     # CAPTCHA detection and solving
│   ├── cli/               # Command-line interface
│   │   └── main.py        # Click-based CLI (ab command)
│   └── web/               # Web GUI
│       ├── app.py         # FastAPI + WebSocket
│       ├── templates/     # HTML templates
│       └── static/        # CSS + JS
├── tests/                 # 238+ tests (unit + integration)
├── .github/workflows/     # CI/CD (lint, test, build, release)
├── Dockerfile
├── Dockerfile.playwright
└── Makefile
```

## LLM Tools (18 tools)

The AI agent has 18 tools available:

| Tool | Description |
|------|-------------|
| `navigate` | Navigate to any URL |
| `click` | Click at (x, y) coordinates |
| `type_text` | Type text (with optional CSS selector) |
| `press_key` | Press keyboard key (Enter, Tab, etc.) |
| `screenshot` | Take a screenshot |
| `get_page_info` | Get page URL, title, content, links, form inputs |
| `scroll` | Scroll up/down/left/right |
| `run_javascript` | Execute JavaScript in the page |
| `wait` | Wait for element, page load, or fixed time |
| `extract_data` | Extract structured data via CSS selectors |
| `handle_captcha` | Auto-detect and solve CAPTCHAs |
| `prepare_grab` | Prepare millisecond-precision grab plan (抢票/秒杀) |
| `execute_grab` | Execute a prepared grab (immediate or timed) |
| `create_plan` | Create a multi-step task plan |
| `schedule_task` | Schedule a task for future execution |
| `ask_user` | Ask the user for input (credentials, choices) |
| `save_login` | Save login credentials (encrypted) and session cookies |
| `check_login` | Check if we have a saved login for a website |
| `task_complete` | Mark task as done with result |

## Millisecond-Precision Ticket Grabbing

Two-phase architecture for time-critical operations like 12306 ticket booking, JD/Taobao flash sales:

**Phase 1: PREPARE** (LLM-driven, normal speed)
- Agent navigates to site, logs in, fills forms, identifies buy button
- Agent calls `prepare_grab` to create a pre-computed action plan

**Phase 2: EXECUTE** (Direct browser, no LLM, millisecond precision)
- Three-phase precision timer: long sleep → short sleep (3ms) → spin-wait
- Direct Playwright operations bypass the agent loop entirely
- Rapid retry (default 5 attempts, 100ms intervals)
- Post-grab verification via CSS selector or page text

### CLI

```bash
# 12306 ticket grabbing
ab grab "Book Beijing to Shanghai G1 train on 12306" -t 2026-06-01T21:00:00

# JD flash sale
ab grab "Buy iPhone 16 on JD flash sale" -t "2026-06-18T10:00:00" --retry 10 --interval 50

# With login profile
ab grab "Taobao Singles Day flash sale" -t "2026-11-11T00:00:00" --profile my-taobao
```

### Python API

```python
from agent_browser.core.grabber import TicketGrabber, GrabPlan, GrabAction

plan = GrabPlan(
    target_time=1748800000.0,  # Unix timestamp
    actions=[GrabAction(type="click_selector", selector="#submitOrder_id")],
    verify_text="Order submitted",
    retry_count=5,
    retry_interval_ms=100,
)

grabber = TicketGrabber()
result = await grabber.execute(page, plan)
print(f"Success: {result.success}, Latency: {result.latency_ms}ms")
```

## Testing

```bash
# All tests (238+ tests)
python -m pytest tests/ -v

# Specific test file
python -m pytest tests/test_integration.py -v

# With coverage
python -m pytest tests/ --cov=agent_browser --cov-report=term-missing

# Lint
ruff check src/ tests/
```

## Docker

```bash
# Step 1: Download CloakBrowser Chromium (required for default Dockerfile)
curl -LO https://cloakbrowser.dev/chromium-v146.0.7680.177.3/cloakbrowser-linux-x64.tar.gz

# Step 2: Build (archive must be in the same directory as Dockerfile)
docker build -t agent-browser .

# Run
docker run -it -e AB_LLM_API_KEY=your-key agent-browser run "your task"

# Alternative: use Playwright's Chromium (no pre-download needed, no anti-detection)
docker build -f Dockerfile.playwright -t agent-browser .
```

## Configuration

Configuration via environment variables or `~/.agent-browser/config.json`:

| Variable | Default | Description |
|----------|---------|-------------|
| `AB_LLM_PROVIDER` | openai | LLM provider (openai/anthropic) |
| `AB_LLM_API_KEY` | | API key |
| `AB_LLM_MODEL` | gpt-4o | Model name |
| `AB_LLM_BASE_URL` | | Custom API base URL (e.g. `https://api.deepseek.com`) |
| `AB_BROWSER_HEADLESS` | true | Headless mode |
| `AB_BROWSER_STEALTH` | true | Anti-detection |
| `AB_BROWSER_HUMANIZE` | true | Human-like behavior |
| `AB_BROWSER_PROXY` | | Proxy URL |
| `CLOAKBROWSER_BINARY_PATH` | | Override CloakBrowser Chromium path |
| `CLOAKBROWSER_CACHE_DIR` | `~/.cloakbrowser` | Cache directory for binaries |

### API Base URL Examples

```bash
# Default OpenAI
export AB_LLM_PROVIDER=openai
export AB_LLM_API_KEY=sk-xxx

# DeepSeek (OpenAI-compatible)
export AB_LLM_PROVIDER=openai
export AB_LLM_BASE_URL=https://api.deepseek.com
export AB_LLM_MODEL=deepseek-chat
export AB_LLM_API_KEY=sk-xxx

# DeepSeek (Anthropic-compatible)
export AB_LLM_PROVIDER=anthropic
export AB_LLM_BASE_URL=https://api.deepseek.com/anthropic
export AB_LLM_MODEL=deepseek-chat
export AB_LLM_API_KEY=sk-xxx

# Self-hosted / local LLM
export AB_LLM_PROVIDER=openai
export AB_LLM_BASE_URL=http://localhost:11434/v1
export AB_LLM_MODEL=llama3
export AB_LLM_API_KEY=ollama
```

## CloakBrowser Chromium

AgentBrowser uses CloakBrowser's patched Chromium binary for maximum anti-detection:

- **C++ level patches**: `navigator.webdriver` removal, automation flag removal
- **Native fingerprint spoofing**: Hardware, screen, WebGL, plugins via CLI flags
- **Auto-download**: Binary is automatically downloaded and cached at `~/.cloakbrowser/`
- **SHA-256 verification**: All downloads are checksum-verified
- **Fallback chain**: CloakBrowser binary -> auto-download -> Playwright default Chromium

```bash
# Install the patched Chromium
ab chromium install

# Check installation
ab chromium info

# Force re-download
ab chromium install --force
```

## Persistent Login Sessions

AgentBrowser supports persistent browser profiles to maintain login state across sessions:

```bash
# Create a profile
ab profiles create my-amazon

# Use it when running tasks
ab run --profile my-amazon "Check my Amazon order status"

# List all profiles
ab profiles list

# See login history
ab profiles info my-amazon
```

**Login Workflow:**
1. **First visit**: AI navigates to login page and uses `ask_user` to request credentials
2. **After login**: Credentials are encrypted and saved; cookies are cached automatically
3. **Subsequent visits**: Cookies are loaded from the persistent profile; login is automatic
4. **Session expired**: System detects expired cookies and re-triggers login with stored credentials
5. **Credential storage**: Username/password encrypted with machine-local key (not plaintext)

Each profile maintains:
- Browser cookies and localStorage (via Playwright persistent context)
- Login state tracking (which sites are logged in)
- Encrypted credentials (username/password)
- Cookie expiry detection
- Independent Chrome user data directory

## Security

### API Key Encryption

API keys are encrypted before being saved to `~/.agent-browser/config.json`:

```bash
# Keys are encrypted automatically when running:
ab configure

# Config file shows encrypted value:
cat ~/.agent-browser/config.json
# "api_key": "ENC:base64encodedcipher..."
```

- Encryption key stored at `~/.agent-browser/.secret_key` (mode 0600)
- PBKDF2-derived cipher with 100,000 iterations
- Environment variables (`AB_LLM_API_KEY`) are NOT encrypted (expected)
- Decryption is automatic when loading config

### Website Credentials

Login credentials (username/password) for websites are also encrypted:

```
~/.agent-browser/profiles/<name>/credentials.json  (encrypted, mode 0600)
```

## License

MIT
