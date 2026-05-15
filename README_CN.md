# AgentBrowser

AI 驱动的浏览器自动化代理，将三个开源项目合并为一个统一工具：

- **GenericAgent** - AI 代理引擎，支持任务规划和记忆
- **browser-harness** - 基于 CDP 的浏览器控制，compositor 级别输入
- **CloakBrowser** - 反检测浏览器，内置补丁 Chromium、指纹伪装和拟人行为

## 功能特性

- **自然语言任务描述** - 用自然语言告诉 AI 要做什么，它自动执行
- **反检测浏览器** - 使用 CloakBrowser 补丁 Chromium（C++ 级别反检测）
- **拟人化操作** - 贝塞尔曲线鼠标移动、真实打字节奏、平滑滚动
- **验证码自动处理** - reCAPTCHA、Turnstile、hCaptcha、滑块验证
- **定时任务** - 支持定时执行（如：21:15 抢票）
- **毫秒级抢票/秒杀** - 12306 抢票、京东/淘宝秒杀，直接绕过 LLM 循环，毫秒精度
- **登录状态持久化** - 命名会话配置，Cookie 跨会话保留，凭证加密存储
- **会话过期检测** - 自动检测 Cookie 过期并重新登录
- **API 密钥加密** - 配置文件中密钥加密存储，不明文保存
- **数据提取** - 网页数据抓取和结构化提取
- **双界面** - 命令行 CLI + Web 图形界面
- **多 LLM 支持** - OpenAI、Anthropic、DeepSeek 及任何 OpenAI 兼容 API
- **自定义 API 地址** - 支持第三方/自建 LLM 接口
- **AI 连接验证** - `ab doctor` 验证 LLM API 连接是否正常

## 快速开始

### 安装

```bash
# 克隆并安装
git clone <repo-url>
cd agent-browser
pip install -e .

# 安装 CloakBrowser 补丁 Chromium（推荐）
ab chromium install

# 或安装 Playwright 默认 Chromium（备选）
playwright install chromium

# 配置
ab configure
```

### CLI 命令行使用

```bash
# 交互模式
ab run

# 执行单个任务
ab run "打开淘宝搜索 iPhone 15 并获取价格"

# 使用 DeepSeek API
ab run --provider openai --base-url https://api.deepseek.com --model deepseek-chat "搜索最新新闻"

# 使用持久登录配置
ab run --profile my-taobao "查看我的淘宝订单"

# 非无头模式（显示浏览器窗口）
ab run --no-headless "在京东上搜索手机壳"

# 定时任务（抢票示例）
ab schedule "打开12306购买北京到上海21:15的车票" "2026-06-01T21:10:00" --pre-check

# 毫秒级抢票/秒杀（两阶段：AI 准备 + 精确执行）
ab grab "在12306上抢北京到上海的G1高铁票" -t 2026-06-01T21:00:00
ab grab "京东秒杀iPhone" -t "2026-06-18T10:00:00" --retry 10 --interval 50
ab grab "淘宝双11秒杀" -t "2026-11-11T00:00:00" --profile my-taobao

# 查看任务列表
ab tasks

# 管理登录会话
ab profiles list              # 列出所有配置
ab profiles create my-taobao  # 创建新配置
ab profiles info my-taobao    # 查看配置详情
ab profiles delete my-taobao  # 删除配置

# 管理 CloakBrowser Chromium
ab chromium install            # 下载安装
ab chromium info               # 查看安装信息
ab chromium clear-cache        # 清除缓存

# 系统检查
ab doctor

# 显示版本
ab version
```

### Web 图形界面

```bash
ab web
# 打开 http://localhost:8899
```

### Python API

```python
import asyncio
from agent_browser import AgentBrowser
from agent_browser.config import AppConfig, LLMConfig

async def main():
    config = AppConfig(llm=LLMConfig(
        api_key="your-api-key",
        provider="openai",
        model="gpt-4o",
    ))

    # 使用命名配置实现登录持久化
    agent = AgentBrowser(config, profile_name="my-profile")
    result = await agent.run_task("打开淘宝搜索 iPhone 15 并获取最低价格")
    print(f"成功: {result.success}, 结果: {result.result}")
    await agent.close()

asyncio.run(main())
```

#### 使用 DeepSeek 或其他第三方 LLM

```python
# DeepSeek（OpenAI 兼容格式）
config = AppConfig(llm=LLMConfig(
    api_key="sk-your-deepseek-key",
    provider="openai",
    model="deepseek-chat",
    base_url="https://api.deepseek.com",  # 不需要加 /v1
))

# DeepSeek（Anthropic 格式）
config = AppConfig(llm=LLMConfig(
    api_key="sk-your-key",
    provider="anthropic",
    model="deepseek-chat",
    base_url="https://api.deepseek.com/anthropic",
))

# 本地 LLM（如 Ollama）
config = AppConfig(llm=LLMConfig(
    api_key="ollama",
    provider="openai",
    model="llama3",
    base_url="http://localhost:11434/v1",
))
```

## 项目架构

```
agent-browser/
├── src/agent_browser/
│   ├── core/              # 代理引擎核心
│   │   ├── agent.py       # 主代理循环（源自 GenericAgent）
│   │   ├── llm.py         # 多 LLM 客户端（工具调用）
│   │   ├── grabber.py     # 毫秒级抢票/秒杀引擎
│   │   ├── memory.py      # 分层记忆系统（L1-L3）
│   │   └── scheduler.py   # 任务调度（单次 + cron）
│   ├── browser/           # 浏览器控制层
│   │   ├── engine.py      # Playwright + CDP 控制（源自 browser-harness）
│   │   ├── stealth.py     # 反检测启动（源自 CloakBrowser）
│   │   ├── chromium.py    # CloakBrowser 补丁 Chromium 管理器
│   │   ├── session.py     # 持久登录会话管理
│   │   ├── humanize.py    # 拟人行为（贝塞尔曲线、打字节奏）
│   │   └── captcha.py     # 验证码检测与解决
│   ├── cli/               # 命令行界面
│   │   └── main.py        # Click CLI（ab 命令）
│   └── web/               # Web 图形界面
│       ├── app.py         # FastAPI + WebSocket
│       ├── templates/     # HTML 模板
│       └── static/        # CSS + JS
├── tests/                 # 238+ 个测试（单元 + 集成）
├── .github/workflows/     # CI/CD（lint、测试、构建、发布）
├── Dockerfile               # Docker 构建（CloakBrowser Chromium）
├── Dockerfile.playwright    # Docker 构建（Playwright 默认 Chromium）
└── Makefile
```

## AI 工具列表（18 个工具）

| 工具 | 说明 |
|------|------|
| `navigate` | 导航到任意 URL |
| `click` | 在 (x, y) 坐标点击 |
| `type_text` | 输入文本（支持 CSS 选择器） |
| `press_key` | 按键（Enter、Tab 等） |
| `screenshot` | 截图 |
| `get_page_info` | 获取页面 URL、标题、内容、链接、表单 |
| `scroll` | 上下左右滚动 |
| `run_javascript` | 在页面执行 JavaScript |
| `wait` | 等待元素、页面加载或固定时间 |
| `extract_data` | 通过 CSS 选择器提取结构化数据 |
| `handle_captcha` | 自动检测并解决验证码 |
| `prepare_grab` | 准备毫秒级抢票/秒杀计划 |
| `execute_grab` | 执行已准备的抢票（立即或定时） |
| `create_plan` | 创建多步骤任务计划 |
| `schedule_task` | 安排定时任务 |
| `ask_user` | 向用户询问信息（账号密码等） |
| `save_login` | 保存登录凭证（加密存储）和会话 Cookie |
| `check_login` | 检查是否已有网站的登录信息 |
| `task_complete` | 标记任务完成 |

## 测试

```bash
# 运行全部测试（193+ 个）
python -m pytest tests/ -v

# 运行集成测试
python -m pytest tests/test_integration.py -v

# 带覆盖率报告
python -m pytest tests/ --cov=agent_browser --cov-report=term-missing

# 代码检查
ruff check src/ tests/
```

## 配置

通过环境变量或 `~/.agent-browser/config.json` 配置：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `AB_LLM_PROVIDER` | openai | LLM 提供商（openai/anthropic） |
| `AB_LLM_API_KEY` | | API 密钥 |
| `AB_LLM_MODEL` | gpt-4o | 模型名称 |
| `AB_LLM_BASE_URL` | | 自定义 API 地址（如 `https://api.deepseek.com`） |
| `AB_BROWSER_HEADLESS` | true | 无头模式 |
| `AB_BROWSER_STEALTH` | true | 反检测 |
| `AB_BROWSER_HUMANIZE` | true | 拟人行为 |
| `AB_BROWSER_PROXY` | | 代理 URL |
| `CLOAKBROWSER_BINARY_PATH` | | 自定义 CloakBrowser Chromium 路径 |
| `CLOAKBROWSER_CACHE_DIR` | `~/.cloakbrowser` | 二进制缓存目录 |

### API 地址配置示例

```bash
# 默认 OpenAI
export AB_LLM_PROVIDER=openai
export AB_LLM_API_KEY=sk-xxx

# DeepSeek（OpenAI 兼容格式）
export AB_LLM_PROVIDER=openai
export AB_LLM_BASE_URL=https://api.deepseek.com
export AB_LLM_MODEL=deepseek-chat
export AB_LLM_API_KEY=sk-xxx

# DeepSeek（Anthropic 兼容格式）
export AB_LLM_PROVIDER=anthropic
export AB_LLM_BASE_URL=https://api.deepseek.com/anthropic
export AB_LLM_MODEL=deepseek-chat
export AB_LLM_API_KEY=sk-xxx

# 本地 LLM（Ollama）
export AB_LLM_PROVIDER=openai
export AB_LLM_BASE_URL=http://localhost:11434/v1
export AB_LLM_MODEL=llama3
export AB_LLM_API_KEY=ollama
```

## CloakBrowser 补丁 Chromium

AgentBrowser 使用 CloakBrowser 的补丁 Chromium 二进制文件实现最强反检测：

- **C++ 级别补丁** - 从源码级别移除 `navigator.webdriver`、自动化标记
- **原生指纹伪装** - 通过 CLI 参数实现硬件、屏幕、WebGL、插件伪装
- **自动下载** - 二进制自动下载并缓存到 `~/.cloakbrowser/`
- **SHA-256 校验** - 所有下载文件进行完整性校验
- **降级链** - CloakBrowser 二进制 → 自动下载 → Playwright 默认 Chromium

## 持久登录会话

支持命名浏览器配置，跨会话保持登录状态：

```bash
# 创建配置
ab profiles create my-taobao

# 使用配置运行（首次会要求登录，之后保持登录）
ab run --profile my-taobao "查看我的淘宝订单"

# 查看所有配置
ab profiles list

# 查看某个配置的登录历史
ab profiles info my-taobao
```

**登录工作流：**
1. **首次访问** - AI 导航到登录页面，通过 `ask_user` 工具向用户索取账号密码
2. **登录成功后** - 凭证加密保存，Cookie 自动缓存
3. **再次访问** - 自动加载缓存的 Cookie，无需重复登录
4. **会话过期** - 系统检测 Cookie 过期，使用已存储的凭证自动重新登录
5. **凭证存储** - 用户名/密码使用机器本地密钥加密（非明文）

每个配置维护：
- 浏览器 Cookie 和 localStorage（通过 Playwright 持久化上下文）
- 登录状态跟踪（记录哪些网站已登录）
- 加密的登录凭证（用户名/密码）
- Cookie 过期检测
- 独立的 Chrome 用户数据目录

## 安全

### API 密钥加密

API 密钥在保存到 `~/.agent-browser/config.json` 前自动加密：

```bash
# 运行配置时自动加密
ab configure

# 配置文件中显示加密值
cat ~/.agent-browser/config.json
# "api_key": "ENC:base64encodedcipher..."
```

- 加密密钥存储于 `~/.agent-browser/.secret_key`（权限 0600）
- 使用 PBKDF2 派生密钥，100,000 次迭代
- 环境变量（`AB_LLM_API_KEY`）不加密（正常行为）
- 加载配置时自动解密

### 网站登录凭证

网站的登录凭证（用户名/密码）同样加密存储：

```
~/.agent-browser/profiles/<配置名>/credentials.json  (加密, 权限 0600)
```

## 使用场景

- **商品价格监控** - "打开京东搜索 MacBook Pro 并提取所有价格"
- **外卖价格对比** - "在美团上搜索附近的披萨店并对比配送费"
- **抢票** - "在 21:15 准时打开 12306 购买北京到上海的高铁票"
- **毫秒级抢票/秒杀** - `ab grab "12306抢票" -t 2026-06-01T21:00:00`
- **数据采集** - "从豆瓣电影 Top250 提取所有电影名称和评分"
- **自动填表** - "打开报名网站并填写表单信息"
- **账户操作** - "登录我的 GitHub 并查看最新的 Pull Request"

## 毫秒级抢票/秒杀 (Ticket Grabbing)

两阶段架构实现毫秒精度的抢票/秒杀功能：

**Phase 1: PREPARE (AI 驱动)**
AI 代理导航网页、登录、填写表单、识别购买按钮

**Phase 2: EXECUTE (直接浏览器操作，无 AI)**
精准等待到目标时间 → 直接执行预设动作 → 快速重试 → 验证结果

### CLI 使用

```bash
# 12306 抢票
ab grab "在12306上抢北京到上海的G1高铁票" -t 2026-06-01T21:00:00

# 京东秒杀
ab grab "京东秒杀iPhone 16" -t "2026-06-18T10:00:00" --retry 10 --interval 50

# 淘宝秒杀（使用已登录的配置）
ab grab "淘宝双11秒杀手机壳" -t "2026-11-11T00:00:00" --profile my-taobao
```

### Python API

```python
from agent_browser.core.grabber import TicketGrabber, GrabPlan, GrabAction

# 创建抢票计划
plan = GrabPlan(
    target_time=1748800000.0,  # Unix 时间戳
    actions=[
        GrabAction(type="click_selector", selector="#submitOrder_id"),
    ],
    verify_text="订单提交成功",
    retry_count=5,
    retry_interval_ms=100,
)

# 执行
grabber = TicketGrabber()
result = await grabber.execute(page, plan)
print(f"成功: {result.success}, 延迟: {result.latency_ms}ms")
```

### 技术特点

- **三阶段精确定时器**: 长等待 (>1s sleep) → 短等待 (3ms chunks) → 自旋等待 (最终 ~10ms)
- **绕过 LLM 循环**: 执行阶段完全不经过 AI，直接调用 Playwright API
- **直接 Playwright 操作**: `page.click(force=True, no_wait_after=True)` 最快路径
- **JavaScript 降级**: 如果 Playwright click 失败，自动降级到 `document.querySelector().click()`
- **快速重试**: 默认 5 次重试，100ms 间隔
- **页面预刷新**: 目标时间前 2 秒刷新页面获取最新 DOM
- **成功验证**: 通过 CSS 选择器或页面文本验证抢票结果

## 许可证

MIT
