# Build & Install Guide / 编译安装手册

## Table of Contents / 目录

- [System Requirements / 系统要求](#system-requirements--系统要求)
- [Quick Install / 快速安装](#quick-install--快速安装)
- [CentOS 7 Install / CentOS 7 安装](#centos-7-install--centos-7-安装)
- [Step-by-Step Build / 逐步编译](#step-by-step-build--逐步编译)
- [Build Output / 编译产物](#build-output--编译产物)
- [CloakBrowser Chromium / 浏览器下载](#cloakbrowser-chromium--浏览器下载)
- [Troubleshooting / 常见问题](#troubleshooting--常见问题)
- [Docker Build / Docker 构建](#docker-build--docker-构建)
- [GitHub Actions CI / CI 自动化](#github-actions-ci--ci-自动化)
- [Development Setup / 开发环境](#development-setup--开发环境)

---

## System Requirements / 系统要求

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | 3.10 - 3.13 | Python 3.12 recommended / 推荐 Python 3.12 |
| pip | >= 23.0 | **Must upgrade** - old pip causes editable install errors / **必须升级** |
| setuptools | >= 68.0 | Required for PEP 660 editable installs |
| GCC/C++ | >= 4.9 (C++11) | Required by `greenlet` (playwright dependency) / `greenlet` 需要 C++11 |
| OS | Linux / macOS / Windows | Linux recommended / 推荐 Linux |
| RAM | >= 4 GB | Browser + LLM client |
| Disk | >= 500 MB | Chromium binary ~200MB |

> **Important / 重要**: `playwright` depends on `greenlet`, which is a C extension. On most systems, pip will install a pre-built binary wheel automatically. On older Linux systems (CentOS 7, RHEL 7) where pre-built wheels are unavailable, a C++11 compiler (GCC >= 4.9) is required. See [CentOS 7 Install](#centos-7-install--centos-7-安装) for solutions.

### System Dependencies (Ubuntu / Debian)

```bash
sudo apt-get update && sudo apt-get install -y \
    python3 python3-pip python3-venv \
    wget curl git \
    libglib2.0-0 libnss3 libnspr4 libdbus-1-3 \
    libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
    libgbm1 libpango-1.0-0 libcairo2 libasound2 \
    libatspi2.0-0 libxshmfence1
```

### System Dependencies (CentOS 7 / RHEL 7)

```bash
# Basic dependencies / 基本依赖
sudo yum install -y python3 python3-pip wget curl git \
    nss nspr dbus-libs atk at-spi2-atk cups-libs libdrm \
    libXcomposite libXdamage libXfixes libXrandr mesa-libgbm \
    pango cairo alsa-lib at-spi2-core libxshmfence

# C++11 compiler (REQUIRED for greenlet) / C++11 编译器（greenlet 必需）
# CentOS 7 default GCC 4.8.x does NOT support C++11!
# CentOS 7 默认 GCC 4.8.x 不支持 C++11！
sudo yum install -y centos-release-scl
sudo yum install -y devtoolset-9-gcc devtoolset-9-gcc-c++

# Activate GCC 9 (current session) / 激活 GCC 9（当前会话）
scl enable devtoolset-9 bash
# Or permanently / 或永久设置:
echo 'source /opt/rh/devtoolset-9/enable' >> ~/.bashrc
```

### System Dependencies (CentOS 8+ / RHEL 8+)

```bash
sudo dnf install -y python3 python3-pip wget curl git gcc-c++ \
    nss nspr dbus-libs atk at-spi2-atk cups-libs libdrm \
    libXcomposite libXdamage libXfixes libXrandr mesa-libgbm \
    pango cairo alsa-lib at-spi2-core libxshmfence
```

### System Dependencies (macOS)

```bash
brew install python@3.12
```

### System Dependencies (Windows)

```powershell
# Install Python from https://python.org
# Ensure "Add Python to PATH" is checked during installation
# 安装 Python，确保勾选 "Add Python to PATH"
```

---

## Quick Install / 快速安装

```bash
# 1. Clone the repository / 克隆仓库
git clone <repo-url>
cd agent-browser

# 2. Upgrade pip (IMPORTANT!) / 升级 pip（重要！）
python -m pip install --upgrade pip setuptools wheel

# 3. Pre-install greenlet binary wheel / 预安装 greenlet 二进制包
#    This avoids C++ compilation issues on older systems
#    这可避免旧系统上的 C++ 编译问题
pip install greenlet --only-binary=greenlet

# 4. Install package / 安装包
pip install -e .

# 5. Install browser / 安装浏览器
#    Option A: CloakBrowser patched Chromium (recommended / 推荐)
ab chromium install
#    Option B: Playwright default Chromium (fallback / 备选)
playwright install chromium

# 6. Configure / 配置
ab configure

# 7. Verify / 验证
ab doctor
ab version
```

---

## CentOS 7 Install / CentOS 7 安装

CentOS 7 ships with GCC 4.8.x which **does NOT support C++11**. The `greenlet` package (required by `playwright`) needs C++11 features (`nullptr`, `noexcept`, `thread_local`). There are **three solutions**:

CentOS 7 默认 GCC 4.8.x **不支持 C++11**。`greenlet` 包（`playwright` 依赖）需要 C++11 特性。有**三种解决方案**：

### Solution A: Pre-built binary wheel (Recommended / 推荐)

Try installing greenlet as a pre-built wheel. If a manylinux wheel is available for your Python version and architecture, no C++ compiler is needed.

尝试安装预编译的 greenlet wheel。如果有匹配你 Python 版本和架构的 manylinux wheel，则不需要 C++ 编译器。

```bash
# 1. Create virtual environment / 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 2. Upgrade pip to latest (CRITICAL for manylinux2014 wheel support)
#    升级 pip 到最新版（manylinux2014 wheel 支持需要）
python -m pip install --upgrade pip setuptools wheel

# 3. Install greenlet binary wheel FIRST / 先安装 greenlet 二进制包
pip install greenlet --only-binary=greenlet
# If this fails with "No matching distribution", use Solution B or C
# 如果报 "No matching distribution"，请使用方案 B 或 C

# 4. Install agent-browser / 安装 agent-browser
pip install -e .

# 5. Install browser / 安装浏览器
ab chromium install
```

### Solution B: Upgrade GCC via devtoolset (Most reliable / 最可靠)

Install a newer GCC with C++11 support from Software Collections.

通过 Software Collections 安装支持 C++11 的新版 GCC。

```bash
# 1. Install devtoolset-9 / 安装 devtoolset-9
sudo yum install -y centos-release-scl
sudo yum install -y devtoolset-9-gcc devtoolset-9-gcc-c++

# 2. Enable devtoolset-9 / 启用 devtoolset-9
scl enable devtoolset-9 bash

# 3. Verify GCC version / 验证 GCC 版本
gcc --version
# Should show gcc 9.x / 应显示 gcc 9.x

# 4. Now install normally / 正常安装
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
pip install -e .
ab chromium install
```

To make devtoolset permanent / 永久启用 devtoolset:
```bash
echo 'source /opt/rh/devtoolset-9/enable' >> ~/.bashrc
source ~/.bashrc
```

### Solution C: Manual dependency install (Fallback / 备选)

Skip greenlet entirely and install only pure-Python dependencies.

跳过 greenlet，仅安装纯 Python 依赖。

```bash
# 1. Upgrade pip / 升级 pip
python -m pip install --upgrade pip setuptools wheel

# 2. Install without dependencies / 不安装依赖
pip install -e . --no-deps

# 3. Manually install all dependencies (greenlet excluded)
#    手动安装所有依赖（排除 greenlet）
pip install click rich pydantic pydantic-settings \
    openai anthropic httpx websockets Pillow \
    fastapi uvicorn jinja2 apscheduler \
    beautifulsoup4 lxml

# 4. Install playwright (will try to install greenlet)
#    安装 playwright（会尝试安装 greenlet）
pip install playwright --only-binary=greenlet || \
pip install playwright --no-deps
# Note: playwright without greenlet may have limited sync API support
# 注意：没有 greenlet 的 playwright 同步 API 功能可能受限

# 5. Install browser / 安装浏览器
playwright install chromium
ab chromium install
```

### CentOS 7 Complete Example / CentOS 7 完整示例

```bash
#!/bin/bash
# Complete CentOS 7 installation script
# CentOS 7 完整安装脚本

set -e

# Install system deps / 安装系统依赖
sudo yum install -y epel-release centos-release-scl
sudo yum install -y python3 python3-pip python3-devel wget curl git \
    devtoolset-9-gcc devtoolset-9-gcc-c++ \
    nss nspr dbus-libs atk at-spi2-atk cups-libs libdrm \
    libXcomposite libXdamage libXfixes libXrandr mesa-libgbm \
    pango cairo alsa-lib at-spi2-core libxshmfence

# Enable C++11 compiler / 启用 C++11 编译器
source /opt/rh/devtoolset-9/enable

# Create venv / 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# Upgrade pip / 升级 pip
python -m pip install --upgrade pip setuptools wheel

# Install / 安装
pip install -e .

# Install CloakBrowser Chromium / 安装 CloakBrowser Chromium
ab chromium install

# Verify / 验证
ab doctor
ab version

echo "Installation complete! / 安装完成！"
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

### Step 3: Pre-install greenlet (optional but recommended) / 预安装 greenlet

```bash
# Install pre-built binary wheel to avoid C++ compilation
# 安装预编译二进制包以避免 C++ 编译
pip install greenlet --only-binary=greenlet
```

If this fails, you need a C++11 compiler. See [CentOS 7 Install](#centos-7-install--centos-7-安装).

如果失败，你需要 C++11 编译器。参见 [CentOS 7 安装](#centos-7-install--centos-7-安装)。

### Step 4: Install package / 安装包

```bash
# Production install / 生产安装
pip install -e .

# Development install (includes test tools) / 开发安装（含测试工具）
pip install -e ".[dev]"
```

### Step 5: Install browser binary / 安装浏览器

```bash
# Recommended: CloakBrowser patched Chromium / 推荐：CloakBrowser 补丁 Chromium
ab chromium install

# Check installation / 检查安装
ab chromium info
```

Output / 输出:
```
CloakBrowser Chromium
  Platform: linux-x64
  Chromium Version: 146.0.7680.177.3
  Installed: Yes
  Binary Path: /home/user/.cloakbrowser/chromium-146.0.7680.177.3/chrome
  Cache Dir: /home/user/.cloakbrowser
```

### Step 6: Configure LLM / 配置 LLM

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

### Step 7: Verify installation / 验证安装

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

### Step 8: Run / 运行

```bash
# Interactive mode / 交互模式
ab run

# Single task / 单个任务
ab run "Go to google.com and search for Python tutorials"

# With persistent login / 持久登录
ab run --profile my-profile "Check my order status on amazon.com"
```

---

## Build Output / 编译产物

### pip install -e . output files / pip install -e . 输出文件

After `pip install -e .`, the following is installed:

执行 `pip install -e .` 后，安装以下内容：

| Output | Location | Description |
|--------|----------|-------------|
| `ab` CLI | `venv/bin/ab` | Main command-line tool / 主命令行工具 |
| `agent-browser` CLI | `venv/bin/agent-browser` | Alias for `ab` / `ab` 的别名 |
| Package | `src/agent_browser/` (editable link) | Python package (editable mode) / Python 包（可编辑模式） |
| Metadata | `src/agent_browser.egg-info/` | Package metadata / 包元数据 |

### python -m build output files / python -m build 输出文件

After `python -m build`, distributable packages are created:

执行 `python -m build` 后，创建可分发的包：

| Output | Location | Description |
|--------|----------|-------------|
| Source dist | `dist/agent_browser-1.0.0.tar.gz` | Source distribution / 源码分发包 |
| Wheel | `dist/agent_browser-1.0.0-py3-none-any.whl` | Built wheel (pure Python) / 构建的 wheel 包 |

```bash
# Build distributable packages / 构建可分发包
pip install build
python -m build

# Check build output / 检查构建产物
ls -lh dist/
# dist/agent_browser-1.0.0.tar.gz      ~150KB  源码分发包
# dist/agent_browser-1.0.0-py3-none-any.whl  ~120KB  wheel 包

# Install from wheel (no source needed) / 从 wheel 安装（不需要源码）
pip install dist/agent_browser-1.0.0-py3-none-any.whl
```

### Install from distributable package / 从分发包安装

```bash
# Install from wheel (recommended, fastest) / 从 wheel 安装（推荐，最快）
pip install agent_browser-1.0.0-py3-none-any.whl

# Install from source tarball / 从源码包安装
pip install agent_browser-1.0.0.tar.gz
```

---

## CloakBrowser Chromium / 浏览器下载

`ab chromium install` downloads a patched Chromium binary with built-in anti-detection at the C++ level.

`ab chromium install` 下载在 C++ 层面内置反检测的补丁 Chromium 浏览器。

### Download Details / 下载详情

| Platform | Version | Archive | Size |
|----------|---------|---------|------|
| linux-x64 | 146.0.7680.177.3 | `cloakbrowser-linux-x64.tar.gz` | ~200MB |
| linux-arm64 | 146.0.7680.177.3 | `cloakbrowser-linux-arm64.tar.gz` | ~200MB |
| darwin-arm64 (Apple Silicon) | 145.0.7632.109.2 | `cloakbrowser-darwin-arm64.tar.gz` | ~250MB |
| darwin-x64 (Intel Mac) | 145.0.7632.109.2 | `cloakbrowser-darwin-x64.tar.gz` | ~250MB |
| windows-x64 | 146.0.7680.177.4 | `cloakbrowser-windows-x64.zip` | ~220MB |

### Download Sources / 下载源

Downloads are attempted in order / 按顺序尝试下载：

1. **Primary CDN / 主 CDN**: `https://cloakbrowser.dev/chromium-v{version}/{archive}`
2. **GitHub Releases / GitHub 发布**: `https://github.com/CloakHQ/cloakbrowser/releases/download/chromium-v{version}/{archive}`

Example URL for linux-x64 / linux-x64 示例 URL：
```
https://cloakbrowser.dev/chromium-v146.0.7680.177.3/cloakbrowser-linux-x64.tar.gz
https://github.com/CloakHQ/cloakbrowser/releases/download/chromium-v146.0.7680.177.3/cloakbrowser-linux-x64.tar.gz
```

### Install Location / 安装位置

| Platform | Binary Path |
|----------|-------------|
| Linux | `~/.cloakbrowser/chromium-{version}/chrome` |
| macOS | `~/.cloakbrowser/chromium-{version}/Chromium.app/Contents/MacOS/Chromium` |
| Windows | `~/.cloakbrowser/chromium-{version}/chrome.exe` |

Cache directory / 缓存目录: `~/.cloakbrowser/`

### Manual Download / 手动下载

If automatic download fails, download manually:

如果自动下载失败，可以手动下载：

```bash
# 1. Download the archive / 下载压缩包
wget https://cloakbrowser.dev/chromium-v146.0.7680.177.3/cloakbrowser-linux-x64.tar.gz

# 2. Verify checksum / 验证校验和
wget https://cloakbrowser.dev/chromium-v146.0.7680.177.3/SHA256SUMS
sha256sum -c SHA256SUMS --ignore-missing

# 3. Extract / 解压
mkdir -p ~/.cloakbrowser/chromium-146.0.7680.177.3
tar xzf cloakbrowser-linux-x64.tar.gz -C ~/.cloakbrowser/chromium-146.0.7680.177.3

# 4. Set executable permission / 设置执行权限
chmod +x ~/.cloakbrowser/chromium-146.0.7680.177.3/chrome

# 5. Verify / 验证
ab chromium info
```

### Environment Variables / 环境变量

| Variable | Description |
|----------|-------------|
| `CLOAKBROWSER_BINARY_PATH` | Custom path to chrome binary / 自定义 chrome 路径 |
| `CLOAKBROWSER_CACHE_DIR` | Custom cache directory (default: `~/.cloakbrowser`) / 自定义缓存目录 |
| `CLOAKBROWSER_DOWNLOAD_URL` | Custom download base URL / 自定义下载 URL |
| `CLOAKBROWSER_SKIP_CHECKSUM` | Set to `true` to skip SHA-256 verification / 设为 `true` 跳过校验 |

```bash
# Use a custom binary / 使用自定义二进制文件
export CLOAKBROWSER_BINARY_PATH=/opt/chromium/chrome

# Custom cache location / 自定义缓存位置
export CLOAKBROWSER_CACHE_DIR=/opt/cloakbrowser

# Custom mirror / 自定义镜像
export CLOAKBROWSER_DOWNLOAD_URL=https://mirror.example.com/cloakbrowser
```

---

## Troubleshooting / 常见问题

### 1. pip install fails: "missing the 'build_editable' hook"

**Cause / 原因**: pip version too old (< 23.0) / pip 版本过旧

```bash
python -m pip install --upgrade pip setuptools wheel
# Then retry / 然后重试
pip install -e .
```

### 2. greenlet build fails (C++ compilation error on CentOS 7)

**Cause / 原因**: `greenlet` is a C extension required by `playwright`. It needs a C++11 compiler. CentOS 7's default GCC 4.8.x does NOT support C++11 (`nullptr`, `noexcept`, `thread_local`).

`greenlet` 是 `playwright` 需要的 C 扩展。它需要 C++11 编译器。CentOS 7 默认的 GCC 4.8.x 不支持 C++11。

**Error / 报错**:
```
error: 'nullptr' was not declared in this scope
error: 'noexcept' does not name a type
error: 'thread_local' does not name a type
Failed to build greenlet
```

**Fix / 解决**:

```bash
# Solution A: Use pre-built wheel (no compiler needed)
# 方案 A: 使用预编译 wheel（无需编译器）
pip install --upgrade pip    # pip >= 23.0 for manylinux2014 support
pip install greenlet --only-binary=greenlet
pip install -e .

# Solution B: Upgrade GCC on CentOS 7
# 方案 B: CentOS 7 升级 GCC
sudo yum install -y centos-release-scl
sudo yum install -y devtoolset-9-gcc devtoolset-9-gcc-c++
scl enable devtoolset-9 bash
pip install -e .

# Solution C: Skip greenlet
# 方案 C: 跳过 greenlet
pip install -e . --no-deps
pip install click rich pydantic pydantic-settings openai anthropic httpx \
    websockets Pillow fastapi uvicorn jinja2 apscheduler \
    beautifulsoup4 lxml
pip install playwright --no-deps
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
# Install Playwright Chromium / 安装 Playwright Chromium
playwright install chromium

# Or install with system deps / 或安装系统依赖
playwright install --with-deps chromium
```

### 6. CloakBrowser Chromium download fails

```bash
# Check the download URL / 查看下载地址
ab chromium info

# Force re-download / 强制重新下载
ab chromium install --force

# Manual download / 手动下载
wget https://cloakbrowser.dev/chromium-v146.0.7680.177.3/cloakbrowser-linux-x64.tar.gz
mkdir -p ~/.cloakbrowser/chromium-146.0.7680.177.3
tar xzf cloakbrowser-linux-x64.tar.gz -C ~/.cloakbrowser/chromium-146.0.7680.177.3
chmod +x ~/.cloakbrowser/chromium-146.0.7680.177.3/chrome

# Or set custom binary path / 或设置自定义路径
export CLOAKBROWSER_BINARY_PATH=/path/to/your/chrome
```

### 7. Permission denied on Linux

```bash
# Make CloakBrowser binary executable / 设置可执行权限
chmod +x ~/.cloakbrowser/chromium-*/chrome
```

### 8. lxml build fails on CentOS 7

```bash
# Install pre-built wheel / 安装预编译包
pip install lxml --only-binary=lxml

# Or install development headers / 或安装开发头文件
sudo yum install -y libxml2-devel libxslt-devel
```

---

## Docker Build / Docker 构建

Docker avoids all compilation issues - recommended for CentOS 7 and other older systems.

Docker 可以避免所有编译问题 - 推荐在 CentOS 7 等旧系统上使用。

### Option 1: CloakBrowser Chromium (recommended / 推荐)

The default `Dockerfile` uses CloakBrowser's patched Chromium for anti-detection. You must pre-download the binary archive before building.

默认 `Dockerfile` 使用 CloakBrowser 补丁 Chromium（反检测）。构建前需先下载二进制文件。

```bash
# Step 1: Download CloakBrowser Chromium archive / 下载 CloakBrowser Chromium
# Linux x64:
curl -LO https://cloakbrowser.dev/chromium-v146.0.7680.177.3/cloakbrowser-linux-x64.tar.gz

# Linux arm64:
# curl -LO https://cloakbrowser.dev/chromium-v146.0.7680.177.3/cloakbrowser-linux-arm64.tar.gz

# If CDN is inaccessible, use GitHub Releases / 如果 CDN 不可用，使用 GitHub:
# curl -LO https://github.com/CloakHQ/cloakbrowser/releases/download/chromium-v146.0.7680.177.3/cloakbrowser-linux-x64.tar.gz

# Step 2: Build image (archive must be in the same directory as Dockerfile)
# 构建镜像（压缩包需放在 Dockerfile 同目录下）
docker build -t agent-browser:latest .

# For arm64 / arm64 架构:
# docker build --build-arg CLOAKBROWSER_ARCHIVE=cloakbrowser-linux-arm64.tar.gz -t agent-browser:latest .
```

### Option 2: Playwright Chromium (simple, no anti-detection)

If you don't need anti-detection, use `Dockerfile.playwright` which auto-downloads Playwright's default Chromium.

如果不需要反检测功能，使用 `Dockerfile.playwright` 自动下载 Playwright 默认 Chromium。

```bash
docker build -f Dockerfile.playwright -t agent-browser:latest .
```

### Option 3: Mount CloakBrowser at runtime / 运行时挂载 CloakBrowser

If you have CloakBrowser Chromium installed on the host, mount it into the container at runtime.

如果主机已安装 CloakBrowser Chromium，运行时挂载进容器。

```bash
# Build with Playwright Dockerfile (no browser baked in)
docker build -f Dockerfile.playwright -t agent-browser:latest .

# Run with host CloakBrowser binary mounted / 挂载主机 CloakBrowser 运行
docker run -it \
  -v ~/.cloakbrowser:/root/.cloakbrowser:ro \
  -e CLOAKBROWSER_BINARY_PATH=/root/.cloakbrowser \
  -e AB_LLM_API_KEY=sk-your-key \
  agent-browser run "your task"
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

# Persistent data + login sessions / 持久化数据 + 登录会话
docker run -it \
  -v agent-data:/root/.agent-browser \
  -e AB_LLM_API_KEY=sk-your-key \
  agent-browser run --profile my-profile "your task"
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
pip install greenlet --only-binary=greenlet  # Avoid C++ compilation / 避免 C++ 编译
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
│   │   ├── grabber.py       # Millisecond-precision ticket grabbing engine
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
├── tests/                   # 238+ tests
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
│   ├── test_chromium.py     # 31 tests
│   ├── test_session.py      # 25 tests
│   ├── test_crypto.py       # 16 tests
│   ├── test_grabber.py      # 31 tests
│   └── test_integration.py  # 17 tests
├── .github/workflows/
│   ├── ci.yml               # CI pipeline
│   └── release.yml          # Release pipeline
├── pyproject.toml           # Project config
├── Makefile                 # Build commands
├── Dockerfile               # Docker build
├── BUILD.md                 # This file / 本文件
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
