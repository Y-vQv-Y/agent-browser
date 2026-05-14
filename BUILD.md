# Build & Install Guide / 编译安装手册

## Table of Contents / 目录

- [System Requirements / 系统要求](#system-requirements--系统要求)
- [Quick Install / 快速安装](#quick-install--快速安装)
- [Step-by-Step Build / 逐步编译](#step-by-step-build--逐步编译)
- [Troubleshooting / 常见问题](#troubleshooting--常见问题)
- [Docker Build / Docker 构建](#docker-build--docker-构建)
- [GitHub Actions CI / CI 自动化](#github-actions-ci--ci-自动化)
- [Development Setup / 开发环境](#development-setup--开发环境)

---

## System Requirements / 系统要求

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | 3.10 - 3.13 | Python 3.12 recommended |
| pip | >= 23.0 | **Must upgrade** - old pip causes editable install errors |
| setuptools | >= 68.0 | Required for PEP 660 editable installs |
| OS | Linux / macOS / Windows | Linux recommended for CI |
| RAM | >= 4 GB | Browser + LLM client |
| Disk | >= 500 MB | Chromium binary ~200MB |

### System Dependencies (Linux)

```bash
# Ubuntu / Debian
sudo apt-get update && sudo apt-get install -y \
    python3 python3-pip python3-venv \
    wget curl git \
    libglib2.0-0 libnss3 libnspr4 libdbus-1-3 \
    libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
    libgbm1 libpango-1.0-0 libcairo2 libasound2 \
    libatspi2.0-0 libxshmfence1

# CentOS / RHEL
sudo yum install -y python3 python3-pip wget curl git \
    nss nspr dbus-libs atk at-spi2-atk cups-libs libdrm \
    libXcomposite libXdamage libXfixes libXrandr mesa-libgbm \
    pango cairo alsa-lib at-spi2-core libxshmfence
```

### System Dependencies (macOS)

```bash
# Install Python via Homebrew
brew install python@3.12
```

### System Dependencies (Windows)

```powershell
# Install Python from https://python.org
# Ensure "Add Python to PATH" is checked during installation
```

---

## Quick Install / 快速安装

```bash
# 1. Clone the repository / 克隆仓库
git clone <repo-url>
cd agent-browser

# 2. Upgrade pip (IMPORTANT!) / 升级 pip（重要！）
python -m pip install --upgrade pip setuptools wheel

# 3. Install package / 安装包
pip install -e .

# 4. Install browser / 安装浏览器
#    Option A: CloakBrowser patched Chromium (recommended / 推荐)
ab chromium install
#    Option B: Playwright default Chromium (fallback / 备选)
playwright install chromium

# 5. Configure / 配置
ab configure

# 6. Verify / 验证
ab doctor
ab version
```

---

## Step-by-Step Build / 逐步编译

### Step 1: Create virtual environment / 创建虚拟环境

```bash
python3 -m venv venv
source venv/bin/activate    # Linux/macOS
# venv\Scripts\activate     # Windows
```

### Step 2: Upgrade pip / 升级 pip

**This step is critical!** Old pip (< 23.0) does not support PEP 660 editable installs and will fail with:

> ERROR: Project has a 'pyproject.toml' and its build backend is missing the 'build_editable' hook.

**这一步很关键！** 旧版 pip (< 23.0) 不支持 PEP 660 可编辑安装，会报错。

```bash
python -m pip install --upgrade pip setuptools wheel
pip --version   # Should be >= 23.0 / 应 >= 23.0
```

### Step 3: Install package / 安装包

```bash
# Production install / 生产安装
pip install -e .

# Development install (includes test tools) / 开发安装（含测试工具）
pip install -e ".[dev]"
```

### Step 4: Install browser binary / 安装浏览器

```bash
# Recommended: CloakBrowser patched Chromium / 推荐：CloakBrowser 补丁 Chromium
ab chromium install

# Check installation / 检查安装
ab chromium info
```

Output:
```
CloakBrowser Chromium
  Platform: linux-x64
  Chromium Version: 146.0.7680.177.3
  Installed: Yes
  Binary Path: /home/user/.cloakbrowser/chromium-146.0.7680.177.3/chrome
  Cache Dir: /home/user/.cloakbrowser
```

### Step 5: Configure LLM / 配置 LLM

```bash
# Interactive setup / 交互式设置
ab configure
```

Or via environment variables / 或通过环境变量:

```bash
# OpenAI
export AB_LLM_PROVIDER=openai
export AB_LLM_API_KEY=sk-your-key-here
export AB_LLM_MODEL=gpt-4o

# DeepSeek (OpenAI-compatible / OpenAI 兼容格式)
export AB_LLM_PROVIDER=openai
export AB_LLM_BASE_URL=https://api.deepseek.com
export AB_LLM_MODEL=deepseek-chat
export AB_LLM_API_KEY=sk-your-deepseek-key

# DeepSeek (Anthropic-compatible / Anthropic 兼容格式)
export AB_LLM_PROVIDER=anthropic
export AB_LLM_BASE_URL=https://api.deepseek.com/anthropic
export AB_LLM_MODEL=deepseek-chat
export AB_LLM_API_KEY=sk-your-deepseek-key

# Anthropic
export AB_LLM_PROVIDER=anthropic
export AB_LLM_API_KEY=sk-ant-your-key-here
export AB_LLM_MODEL=claude-sonnet-4-20250514

# Local LLM (Ollama / 本地 LLM)
export AB_LLM_PROVIDER=openai
export AB_LLM_BASE_URL=http://localhost:11434/v1
export AB_LLM_MODEL=llama3
export AB_LLM_API_KEY=ollama
```

### Step 6: Verify installation / 验证安装

```bash
ab doctor
```

Expected output / 预期输出:
```
System Check

  OK Python version: 3.12.x
  OK Playwright installed: v1.x.x
  OK CloakBrowser Chromium: v146.0.7680.177.3 at /home/user/.cloakbrowser/...
  OK Browser binary: /home/user/.cloakbrowser/.../chrome
  OK LLM API key: openai: sk-xxx...xxxx
  OK Config file: /home/user/.agent-browser/config.json

All checks passed!
```

### Step 7: Run / 运行

```bash
# Interactive mode / 交互模式
ab run

# Single task / 单个任务
ab run "Go to google.com and search for Python tutorials"

# With persistent login / 持久登录
ab run --profile my-profile "Check my order status on amazon.com"
```

---

## Troubleshooting / 常见问题

### 1. pip install fails: "missing the 'build_editable' hook"

**Cause / 原因**: pip version too old.

```bash
python -m pip install --upgrade pip setuptools wheel
# Then retry / 然后重试
pip install -e .
```

### 2. greenlet build fails (C++ compilation error)

**Cause / 原因**: `greenlet` requires a C++ compiler. This happens when `uvicorn[standard]` pulls in native extensions.

**Fix / 解决**: The project now uses `uvicorn` without `[standard]` extras, so `greenlet` is not required. If you still see this:

```bash
# Option A: Install pre-built wheel / 安装预编译包
pip install greenlet --only-binary=greenlet

# Option B: Install C++ compiler / 安装 C++ 编译器
sudo apt-get install -y build-essential g++

# Option C: Skip greenlet entirely / 完全跳过 greenlet
pip install -e . --no-deps
pip install click rich pydantic pydantic-settings openai anthropic httpx \
    websockets Pillow playwright fastapi uvicorn jinja2 apscheduler \
    beautifulsoup4 lxml
```

### 3. pytest-asyncio errors: "mark.asyncio accepts only a keyword argument 'loop_scope'"

**Cause / 原因**: Using `@pytest.mark.asyncio(mode="strict")` with newer pytest-asyncio.

**Fix / 解决**: Already fixed in the codebase. Global `asyncio_mode = "strict"` is set in `pyproject.toml`, so markers only need `@pytest.mark.asyncio` without arguments.

### 4. Tests hang during collection

**Cause / 原因**: `anyio` plugin conflict with pytest-asyncio.

**Fix / 解决**: Already configured in `pyproject.toml`:
```toml
[tool.pytest.ini_options]
asyncio_mode = "strict"
addopts = "-p no:anyio"
```

### 5. Playwright browser not found

```bash
# Install Playwright Chromium
playwright install chromium

# Or install with system deps / 或安装系统依赖
playwright install --with-deps chromium
```

### 6. CloakBrowser Chromium download fails

```bash
# Manual download / 手动下载
# Check the download URL
ab chromium info

# Force re-download / 强制重新下载
ab chromium install --force

# Or set custom binary path / 或设置自定义路径
export CLOAKBROWSER_BINARY_PATH=/path/to/your/chrome
```

### 7. Permission denied on Linux

```bash
# Make CloakBrowser binary executable
chmod +x ~/.cloakbrowser/chromium-*/chrome
```

---

## Docker Build / Docker 构建

### Build image / 构建镜像

```bash
docker build -t agent-browser:latest .
```

### Run / 运行

```bash
# Interactive task / 交互任务
docker run -it \
  -e AB_LLM_API_KEY=sk-your-key \
  -e AB_LLM_PROVIDER=openai \
  agent-browser run "Search Google for Python tutorials"

# With DeepSeek / 使用 DeepSeek
docker run -it \
  -e AB_LLM_API_KEY=sk-your-deepseek-key \
  -e AB_LLM_PROVIDER=openai \
  -e AB_LLM_BASE_URL=https://api.deepseek.com \
  -e AB_LLM_MODEL=deepseek-chat \
  agent-browser run "Search for latest news"

# Web GUI / Web 界面
docker run -it -p 8899:8899 \
  -e AB_LLM_API_KEY=sk-your-key \
  agent-browser web --host 0.0.0.0

# System check / 系统检查
docker run --rm agent-browser doctor
```

### Docker Compose

```yaml
version: '3.8'
services:
  agent-browser:
    build: .
    environment:
      - AB_LLM_API_KEY=${AB_LLM_API_KEY}
      - AB_LLM_PROVIDER=openai
      - AB_LLM_MODEL=gpt-4o
    ports:
      - "8899:8899"
    volumes:
      - agent-data:/root/.agent-browser
    command: web --host 0.0.0.0

volumes:
  agent-data:
```

---

## GitHub Actions CI / CI 自动化

### CI Workflow

The project includes `.github/workflows/ci.yml` that runs:

1. **Lint** - `ruff check` + `mypy` on Python 3.12
2. **Test** - `pytest` on Python 3.10, 3.11, 3.12, 3.13
3. **Build** - Package distribution
4. **Docker** - Docker image build (on main branch push)

### Running CI locally / 本地运行 CI

```bash
# Lint / 代码检查
make lint

# Tests / 测试
make test          # All tests (unit + integration)
make test-unit     # Unit tests only
make test-integration  # Integration tests only
make test-cov      # Tests with coverage report

# Build package / 构建包
make build

# Full CI check / 完整 CI 检查
make lint && make test && make build
```

### CI Configuration Tips / CI 配置提示

**Key settings in `pyproject.toml`:**
```toml
[tool.pytest.ini_options]
asyncio_mode = "strict"    # pytest-asyncio strict mode globally
addopts = "-p no:anyio"    # Disable anyio plugin to prevent hangs
```

**Key CI steps:**
```yaml
- name: Install dependencies
  run: |
    python -m pip install --upgrade pip setuptools wheel  # IMPORTANT!
    pip install -e ".[dev]"
```

---

## Development Setup / 开发环境

### Full development install / 完整开发安装

```bash
# Clone / 克隆
git clone <repo-url>
cd agent-browser

# Virtual env / 虚拟环境
python3 -m venv venv
source venv/bin/activate

# Install (dev mode) / 安装（开发模式）
python -m pip install --upgrade pip setuptools wheel
pip install -e ".[dev]"

# Install browser / 安装浏览器
ab chromium install

# Run all tests / 运行所有测试
make test

# Run with coverage / 运行并查看覆盖率
make test-cov
```

### Project Structure / 项目结构

```
agent-browser/
├── src/agent_browser/
│   ├── __init__.py          # Package version
│   ├── config.py            # Configuration (Pydantic)
│   ├── core/
│   │   ├── agent.py         # Main agent loop
│   │   ├── llm.py           # LLM client (OpenAI/Anthropic/custom)
│   │   ├── memory.py        # Layered memory (L1-L3)
│   │   └── scheduler.py     # Task scheduler (APScheduler)
│   ├── browser/
│   │   ├── engine.py        # Browser engine (Playwright)
│   │   ├── stealth.py       # Anti-detection launcher
│   │   ├── chromium.py      # CloakBrowser binary manager
│   │   ├── session.py       # Login session persistence
│   │   ├── humanize.py      # Human-like behavior
│   │   └── captcha.py       # CAPTCHA solver
│   ├── cli/
│   │   └── main.py          # CLI (Click)
│   └── web/
│       ├── app.py           # Web GUI (FastAPI)
│       ├── templates/
│       └── static/
├── tests/                   # 188 tests
│   ├── test_config.py       # 9 tests
│   ├── test_llm.py          # 19 tests
│   ├── test_memory.py       # 13 tests
│   ├── test_scheduler.py    # 13 tests
│   ├── test_stealth.py      # 14 tests
│   ├── test_humanize.py     # 14 tests
│   ├── test_captcha.py      # 8 tests
│   ├── test_agent.py        # 14 tests
│   ├── test_cli.py          # 9 tests
│   ├── test_web.py          # 5 tests
│   ├── test_chromium.py     # 28 tests
│   ├── test_session.py      # 25 tests
│   └── test_integration.py  # 17 tests
├── .github/workflows/
│   ├── ci.yml               # CI pipeline
│   └── release.yml          # Release pipeline
├── pyproject.toml           # Project config
├── Makefile                 # Build commands
├── Dockerfile               # Docker build
├── README.md                # English docs
└── README_CN.md             # Chinese docs / 中文文档
```

### Available Make commands / 可用 Make 命令

```bash
make help              # Show all commands / 显示所有命令
make install           # Install package / 安装
make dev               # Install with dev deps / 开发安装
make test              # Run all tests / 运行所有测试
make test-unit         # Unit tests only / 仅单元测试
make test-integration  # Integration tests / 集成测试
make test-cov          # Tests with coverage / 覆盖率测试
make lint              # Lint check / 代码检查
make lint-fix          # Auto-fix lint / 自动修复
make type-check        # Type check / 类型检查
make build             # Build package / 构建包
make docker            # Build Docker image / 构建 Docker 镜像
make clean             # Clean artifacts / 清理
make run-cli           # Run CLI / 运行命令行
make run-web           # Start Web GUI / 启动 Web 界面
make doctor            # System check / 系统检查
make configure         # Configure agent / 配置代理
make chromium-install  # Install CloakBrowser Chromium / 安装 Chromium
make chromium-info     # Show Chromium info / 显示 Chromium 信息
make profiles          # List session profiles / 列出会话配置
```
