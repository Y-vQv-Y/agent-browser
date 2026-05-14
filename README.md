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
- Persistent login sessions (named browser profiles, cookies preserved)
- Data extraction and web scraping
- Both CLI and Web GUI interfaces
- Multi-LLM support (OpenAI, Anthropic, DeepSeek, any OpenAI-compatible API)
- Custom API base URL support (for third-party/self-hosted LLMs)

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
├── tests/                 # 188 tests (unit + integration)
├── .github/workflows/     # CI/CD (lint, test, build, release)
├── Dockerfile
└── Makefile
```

## LLM Tools (14 tools)

The AI agent has 14 tools available:

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
| `create_plan` | Create a multi-step task plan |
| `schedule_task` | Schedule a task for future execution |
| `ask_user` | Ask the user for input (credentials, choices) |
| `task_complete` | Mark task as done with result |

## Testing

```bash
# All tests (188 tests)
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
# Build
docker build -t agent-browser .

# Run
docker run -it -e AB_LLM_API_KEY=your-key agent-browser run "your task"
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

Each profile maintains:
- Browser cookies and localStorage (via Playwright persistent context)
- Login state tracking (which sites are logged in)
- Independent Chrome user data directory

## License

MIT
