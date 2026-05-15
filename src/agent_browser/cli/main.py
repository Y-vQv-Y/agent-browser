"""
CLI Interface - Rich terminal interface for AgentBrowser.
Supports interactive mode, single-task mode, and scheduled tasks.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.prompt import Prompt

from agent_browser.config import AppConfig, get_config

console = Console()


def setup_logging(level: str = "INFO"):
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


@click.group()
@click.option("--debug", is_flag=True, help="Enable debug mode")
@click.option("--config", "config_path", type=click.Path(), help="Config file path")
@click.pass_context
def cli(ctx, debug: bool, config_path: Optional[str]):
    """AgentBrowser - AI-powered browser automation agent."""
    ctx.ensure_object(dict)
    config = AppConfig.load(Path(config_path) if config_path else None)
    if debug:
        config.debug = True
        config.log_level = "DEBUG"
    ctx.obj["config"] = config
    setup_logging(config.log_level)


@cli.command()
@click.pass_context
def configure(ctx):
    """Interactive configuration setup."""
    config = ctx.obj["config"]
    console.print(Panel.fit("[bold]AgentBrowser Configuration[/bold]"))

    # LLM Provider
    provider = Prompt.ask(
        "LLM Provider",
        choices=["openai", "anthropic"],
        default=config.llm.provider,
    )
    config.llm.provider = provider

    # API Key
    api_key = Prompt.ask(
        f"{provider.title()} API Key",
        default=config.llm.api_key or "(not set)",
    )
    if api_key != "(not set)":
        config.llm.api_key = api_key

    # Model
    default_model = "gpt-4o" if provider == "openai" else "claude-sonnet-4-20250514"
    model = Prompt.ask("Model", default=config.llm.model or default_model)
    config.llm.model = model

    # Base URL
    base_url_hint = {
        "openai": "https://api.openai.com/v1",
        "anthropic": "https://api.anthropic.com/v1",
    }.get(provider, "")
    base_url = Prompt.ask(
        f"API Base URL (empty for default: {base_url_hint})",
        default=config.llm.base_url or "",
    )
    config.llm.base_url = base_url or None

    # Browser
    headless = Prompt.ask("Headless mode", choices=["yes", "no"], default="yes")
    config.browser.headless = headless == "yes"

    humanize = Prompt.ask("Human-like behavior", choices=["yes", "no"], default="yes")
    config.browser.humanize = humanize == "yes"

    proxy = Prompt.ask("Proxy URL (empty for none)", default=config.browser.proxy or "")
    config.browser.proxy = proxy or None

    # Save
    config.save()
    console.print(f"\n[green]Configuration saved to {config.data_path / 'config.json'}[/green]")


@cli.command()
@click.argument("task", required=False)
@click.option("--headless/--no-headless", default=None, help="Headless browser mode")
@click.option("--proxy", help="Proxy URL")
@click.option("--model", help="LLM model name")
@click.option("--provider", help="LLM provider")
@click.option("--base-url", "base_url", help="Custom LLM API base URL")
@click.option("--profile", default=None, help="Session profile name (preserves login state)")
@click.pass_context
def run(ctx, task: Optional[str], headless, proxy, model, provider, base_url, profile):
    """Run a task or enter interactive mode.

    Examples:
      ab run "Search for Python tutorials on Google"
      ab run  # Interactive mode
    """
    config: AppConfig = ctx.obj["config"]

    # Override config from CLI flags
    if headless is not None:
        config.browser.headless = headless
    if proxy:
        config.browser.proxy = proxy
    if model:
        config.llm.model = model
    if provider:
        config.llm.provider = provider
    if base_url:
        config.llm.base_url = base_url

    if not config.llm.api_key:
        console.print("[red]Error: No API key configured. Run 'ab configure' first.[/red]")
        sys.exit(1)

    # Use default profile if none specified (enables persistent login)
    profile_name = profile or "default"

    if task:
        asyncio.run(_run_single_task(config, task, profile_name))
    else:
        asyncio.run(_run_interactive(config, profile_name))


async def _run_single_task(config: AppConfig, task: str, profile_name: str = "default"):
    """Execute a single task."""
    from agent_browser.core.agent import AgentBrowser

    console.print(Panel(f"[bold]Task:[/bold] {task}", title="AgentBrowser"))

    agent = AgentBrowser(config, profile_name=profile_name)

    async def on_step(step):
        status = "[green]OK[/green]" if step.success else "[red]FAIL[/red]"
        console.print(f"  [{status}] {step.tool_name}({json.dumps(step.arguments)[:80]}...) [{step.duration:.1f}s]")

    agent.set_step_callback(on_step)

    async def user_input(question: str) -> str:
        return Prompt.ask(f"\n[yellow]{question}[/yellow]")

    agent.set_user_input_callback(user_input)

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task("Running agent...", total=None)
            result = await agent.run_task(task)

        console.print()
        if result.success:
            console.print(Panel(
                f"[green]{result.result}[/green]",
                title="Task Completed",
                border_style="green",
            ))
        else:
            console.print(Panel(
                f"[red]{result.result}[/red]",
                title="Task Failed",
                border_style="red",
            ))

        # Show step summary
        if result.steps:
            table = Table(title="Execution Steps")
            table.add_column("#", width=4)
            table.add_column("Tool", style="cyan")
            table.add_column("Status")
            table.add_column("Time", justify="right")

            for i, step in enumerate(result.steps, 1):
                status = "[green]OK[/green]" if step.success else "[red]FAIL[/red]"
                table.add_row(str(i), step.tool_name, status, f"{step.duration:.1f}s")

            console.print(table)

        console.print(f"\nTotal time: {result.duration:.1f}s | Steps: {len(result.steps)}")

    finally:
        await agent.close()


async def _run_interactive(config: AppConfig, profile_name: str = "default"):
    """Run in interactive mode."""
    from agent_browser.core.agent import AgentBrowser

    console.print(Panel.fit(
        "[bold]AgentBrowser Interactive Mode[/bold]\n"
        "Type your task in natural language. The AI agent will control the browser.\n"
        "Commands: [cyan]quit[/cyan] | [cyan]tasks[/cyan] | [cyan]screenshot[/cyan] | [cyan]help[/cyan]",
        border_style="blue",
    ))

    agent = AgentBrowser(config, profile_name=profile_name)

    async def on_step(step):
        status = "[green]OK[/green]" if step.success else "[red]FAIL[/red]"
        console.print(f"  [{status}] {step.tool_name} [{step.duration:.1f}s]")

    agent.set_step_callback(on_step)

    async def user_input(question: str) -> str:
        return Prompt.ask(f"\n[yellow]{question}[/yellow]")

    agent.set_user_input_callback(user_input)

    try:
        while True:
            try:
                task = Prompt.ask("\n[bold blue]Task[/bold blue]")
            except (EOFError, KeyboardInterrupt):
                break

            task = task.strip()
            if not task:
                continue
            if task.lower() in ("quit", "exit", "q"):
                break
            if task.lower() == "help":
                console.print(Markdown("""
## Commands
- **quit** - Exit the program
- **tasks** - List scheduled tasks
- **screenshot** - Take a screenshot of current page
- Type any task in natural language to execute it

## Example Tasks
- "Go to google.com and search for Python tutorials"
- "Login to example.com with user@email.com"
- "Extract all product prices from this page"
- "Book a ticket at 21:15 on example.com"
"""))
                continue
            if task.lower() == "tasks":
                tasks = agent.scheduler.list_tasks()
                if tasks:
                    table = Table(title="Scheduled Tasks")
                    table.add_column("ID")
                    table.add_column("Task")
                    table.add_column("Status")
                    table.add_column("Execute At")
                    for t in tasks:
                        table.add_row(t.task_id, t.description[:50], t.status, t.execute_at or "")
                    console.print(table)
                else:
                    console.print("[dim]No scheduled tasks[/dim]")
                continue
            if task.lower() == "screenshot":
                if agent.browser and agent.browser._launched:
                    img = await agent.browser.screenshot()
                    console.print(f"[green]Screenshot saved ({len(img)} bytes base64)[/green]")
                else:
                    console.print("[yellow]Browser not launched yet[/yellow]")
                continue

            result = await agent.run_task(task)
            if result.success:
                console.print(f"\n[green]Result: {result.result}[/green]")
            else:
                console.print(f"\n[red]Failed: {result.result}[/red]")

    finally:
        await agent.close()
        console.print("[dim]Goodbye![/dim]")


@cli.command()
@click.argument("task")
@click.argument("execute_at")
@click.option("--pre-check", is_flag=True, help="Run pre-execution validation")
@click.pass_context
def schedule(ctx, task: str, execute_at: str, pre_check: bool):
    """Schedule a task for future execution.

    Examples:
      ab schedule "Book ticket on example.com" "2024-12-31T21:15:00"
      ab schedule "Check prices daily" "0 9 * * *"
    """
    config: AppConfig = ctx.obj["config"]
    from agent_browser.core.scheduler import TaskScheduler

    scheduler = TaskScheduler(config.data_path / "tasks")
    is_cron = any(c in execute_at for c in ["*", "/"])
    scheduled = scheduler.add_task(
        description=task,
        execute_at=None if is_cron else execute_at,
        cron=execute_at if is_cron else None,
        pre_check=pre_check,
    )
    console.print(f"[green]Task scheduled![/green]")
    console.print(f"  ID: {scheduled.task_id}")
    console.print(f"  Task: {task}")
    console.print(f"  Execute at: {execute_at}")


@cli.command()
@click.pass_context
def tasks(ctx):
    """List all scheduled tasks."""
    config: AppConfig = ctx.obj["config"]
    from agent_browser.core.scheduler import TaskScheduler

    scheduler = TaskScheduler(config.data_path / "tasks")
    all_tasks = scheduler.list_tasks()

    if not all_tasks:
        console.print("[dim]No tasks found[/dim]")
        return

    table = Table(title="Scheduled Tasks")
    table.add_column("ID", style="cyan")
    table.add_column("Description")
    table.add_column("Status")
    table.add_column("Execute At")
    table.add_column("Created")

    for t in all_tasks:
        status_color = {
            "pending": "yellow",
            "running": "blue",
            "completed": "green",
            "failed": "red",
        }.get(t.status, "white")
        table.add_row(
            t.task_id,
            t.description[:60],
            f"[{status_color}]{t.status}[/{status_color}]",
            t.execute_at or t.cron or "",
            t.created_at[:19],
        )

    console.print(table)


@cli.command()
@click.option("--host", default=None, help="Web GUI host")
@click.option("--port", default=None, type=int, help="Web GUI port")
@click.pass_context
def web(ctx, host: Optional[str], port: Optional[int]):
    """Start the Web GUI."""
    config: AppConfig = ctx.obj["config"]
    h = host or config.web_host
    p = port or config.web_port

    console.print(f"[bold]Starting Web GUI at http://{h}:{p}[/bold]")

    from agent_browser.web.app import create_app
    import uvicorn

    app = create_app(config)
    uvicorn.run(app, host=h, port=p)


@cli.command()
def version():
    """Show version information."""
    from agent_browser import __version__
    from agent_browser.browser.chromium import get_info

    console.print(f"AgentBrowser v{__version__}")
    console.print("Components:")
    console.print("  - Agent Engine (GenericAgent-inspired)")
    console.print("  - Browser Control (browser-harness CDP)")
    console.print("  - Stealth Mode (CloakBrowser anti-detection)")
    console.print("  - CAPTCHA Handler")
    console.print("  - Task Scheduler")

    info = get_info()
    console.print(f"\nCloakBrowser Chromium:")
    console.print(f"  Version: {info['chromium_version']}")
    console.print(f"  Platform: {info['platform']}")
    installed = "[green]Yes[/green]" if info["installed"] else "[red]No[/red]"
    console.print(f"  Installed: {installed}")
    if info["installed"]:
        console.print(f"  Path: {info['binary_path']}")


@cli.command()
@click.pass_context
def doctor(ctx):
    """Check system dependencies and configuration."""
    console.print("[bold]System Check[/bold]\n")

    checks = [
        ("Python version", _check_python),
        ("Playwright installed", _check_playwright),
        ("CloakBrowser Chromium", _check_cloakbrowser),
        ("Browser binary", _check_browser),
        ("LLM API key", lambda: _check_api_key(ctx.obj["config"])),
        ("LLM connection", lambda: _check_llm_connection(ctx.obj["config"])),
        ("Config file", lambda: _check_config(ctx.obj["config"])),
        ("Encryption key", lambda: _check_encryption(ctx.obj["config"])),
    ]

    all_ok = True
    for name, check_fn in checks:
        try:
            ok, msg = check_fn()
            status = "[green]OK[/green]" if ok else "[red]FAIL[/red]"
            if not ok:
                all_ok = False
            console.print(f"  {status} {name}: {msg}")
        except Exception as e:
            all_ok = False
            console.print(f"  [red]FAIL[/red] {name}: {e}")

    console.print()
    if all_ok:
        console.print("[green]All checks passed![/green]")
    else:
        console.print("[yellow]Some checks failed. Run 'ab configure' to fix.[/yellow]")


def _check_python():
    v = sys.version_info
    ok = v >= (3, 10)
    return ok, f"{v.major}.{v.minor}.{v.micro}"


def _check_playwright():
    try:
        import playwright
        version = getattr(playwright, "__version__", None)
        if version:
            return True, f"v{version}"
        # Fallback: check if the package is importable
        return True, "installed (version unknown)"
    except ImportError:
        return False, "Not installed. Run: pip install playwright && playwright install chromium"


def _check_browser():
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            path = p.chromium.executable_path
            return bool(path), str(path) if path else "Not found"
    except OSError as e:
        error_msg = str(e)
        if "GLIBC" in error_msg or "GLIBCXX" in error_msg or "CXXABI" in error_msg:
            return False, (
                "System glibc too old for Playwright's bundled Node.js. "
                "CentOS 7 requires Docker or system upgrade. "
                "CloakBrowser Chromium can still work via CLOAKBROWSER_BINARY_PATH."
            )
        return False, f"Error: {e}"
    except Exception as e:
        error_msg = str(e)
        if "Connection closed" in error_msg or "GLIBC" in error_msg:
            return False, (
                "Playwright driver incompatible with this system. "
                "Try Docker build or upgrade OS. See BUILD.md."
            )
        return False, f"Error: {e}"


def _check_api_key(config):
    if config.llm.api_key:
        from agent_browser.crypto import mask_value
        masked = mask_value(config.llm.api_key)
        return True, f"{config.llm.provider}: {masked}"
    return False, "Not configured. Run: ab configure"


def _check_config(config):
    p = config.data_path / "config.json"
    if p.exists():
        return True, str(p)
    return False, "No config file found"


def _check_cloakbrowser():
    try:
        from agent_browser.browser.chromium import is_binary_installed, get_binary_path, get_chromium_version
        if is_binary_installed():
            return True, f"v{get_chromium_version()} at {get_binary_path()}"
        return False, f"Not installed. Run: ab chromium install"
    except Exception as e:
        return False, f"Error: {e}"


def _check_llm_connection(config):
    """Verify the LLM API connection is working."""
    if not config.llm.api_key:
        return False, "No API key configured"
    try:
        import asyncio
        from agent_browser.core.llm import LLMClient
        client = LLMClient(
            provider=config.llm.provider,
            api_key=config.llm.api_key,
            model=config.llm.model,
            base_url=config.llm.base_url,
        )
        loop = asyncio.new_event_loop()
        try:
            ok, msg = loop.run_until_complete(client.verify_connection())
            return ok, msg
        finally:
            loop.run_until_complete(client.close())
            loop.close()
    except Exception as e:
        return False, f"Connection check failed: {e}"


def _check_encryption(config):
    """Check if the encryption key exists."""
    from agent_browser.crypto import _get_key_path
    key_path = _get_key_path(config.data_path)
    if key_path.exists():
        return True, str(key_path)
    return True, "Will be created on first use"


@cli.command()
@click.argument("task")
@click.option("--time", "-t", "target_time", required=True, help="Target time in ISO 8601 format (e.g. 2026-05-20T21:00:00)")
@click.option("--profile", "-p", default=None, help="Session profile name")
@click.option("--retry", default=5, type=int, help="Retry count (default 5)")
@click.option("--interval", default=100, type=int, help="Retry interval in ms (default 100)")
@click.option("--headless/--no-headless", default=None, help="Headless browser mode")
@click.option("--model", help="LLM model name")
@click.option("--provider", help="LLM provider")
@click.option("--base-url", "base_url", help="Custom LLM API base URL")
@click.pass_context
def grab(ctx, task, target_time, profile, retry, interval, headless, model, provider, base_url):
    """Execute a millisecond-precision ticket grab task.

    Two-phase execution:
      Phase 1 (PREPARE): LLM navigates, logs in, fills forms, identifies the buy button
      Phase 2 (EXECUTE): Direct browser actions at exact target time, no LLM

    Examples:
      ab grab "在12306上抢北京到上海的G1列车" -t 2026-05-20T21:00:00
      ab grab "Buy iPhone on JD flash sale" -t "2026-06-18T10:00:00"
    """
    config: AppConfig = ctx.obj["config"]

    if headless is not None:
        config.browser.headless = headless
    if model:
        config.llm.model = model
    if provider:
        config.llm.provider = provider
    if base_url:
        config.llm.base_url = base_url

    if not config.llm.api_key:
        console.print("[red]Error: No API key configured. Run 'ab configure' first.[/red]")
        sys.exit(1)

    profile_name = profile or "default"

    asyncio.run(_run_grab_task(config, task, target_time, profile_name, retry, interval))


async def _run_grab_task(
    config: AppConfig, task: str, target_time: str,
    profile_name: str, retry_count: int, retry_interval_ms: int,
):
    """Execute a grab task: LLM preparation + millisecond-precision execution."""
    from agent_browser.core.agent import AgentBrowser

    console.print(Panel(
        f"[bold]Grab Task:[/bold] {task}\n"
        f"[bold]Target Time:[/bold] {target_time}\n"
        f"[bold]Retry:[/bold] {retry_count}x @ {retry_interval_ms}ms intervals",
        title="AgentBrowser - Ticket Grabber",
        border_style="magenta",
    ))

    agent = AgentBrowser(config, profile_name=profile_name)

    async def on_step(step):
        status = "[green]OK[/green]" if step.success else "[red]FAIL[/red]"
        console.print(f"  [{status}] {step.tool_name}({json.dumps(step.arguments)[:80]}...) [{step.duration:.1f}s]")

    agent.set_step_callback(on_step)

    async def user_input(question: str) -> str:
        return Prompt.ask(f"\n[yellow]{question}[/yellow]")

    agent.set_user_input_callback(user_input)

    try:
        # Phase 1: LLM-driven preparation
        # The task prompt instructs the LLM to prepare, then call prepare_grab + execute_grab
        grab_task = (
            f"{task}\n\n"
            f"[GRAB MODE] This is a millisecond-precision grab task. Follow these steps:\n"
            f"1. Navigate to the website, log in if needed, fill in all required forms\n"
            f"2. Identify the target button/element to click at the exact time\n"
            f"3. Call prepare_grab with target_time='{target_time}', the actions to execute, "
            f"retry_count={retry_count}, retry_interval_ms={retry_interval_ms}\n"
            f"4. Call execute_grab with mode='confirm' to start the precision timer\n"
            f"5. Report the grab result with task_complete"
        )

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task("Running grab agent...", total=None)
            result = await agent.run_task(grab_task)

        console.print()
        if result.success:
            console.print(Panel(
                f"[green]{result.result}[/green]",
                title="Grab Completed",
                border_style="green",
            ))
        else:
            console.print(Panel(
                f"[red]{result.result}[/red]",
                title="Grab Failed",
                border_style="red",
            ))

        if result.steps:
            table = Table(title="Execution Steps")
            table.add_column("#", width=4)
            table.add_column("Tool", style="cyan")
            table.add_column("Status")
            table.add_column("Time", justify="right")

            for i, step in enumerate(result.steps, 1):
                status = "[green]OK[/green]" if step.success else "[red]FAIL[/red]"
                table.add_row(str(i), step.tool_name, status, f"{step.duration:.1f}s")

            console.print(table)

        console.print(f"\nTotal time: {result.duration:.1f}s | Steps: {len(result.steps)}")

    finally:
        await agent.close()


@cli.command()
@click.argument("profile_name")
@click.argument("url")
@click.option("--timeout", "-t", default=120, type=int, help="Login timeout in seconds (default 120)")
@click.pass_context
def login(ctx, profile_name: str, url: str, timeout: int):
    """Open a visible browser for manual login (QR code, password, etc).

    Launches a non-headless browser so you can scan QR codes or enter credentials
    directly. The session is saved to the named profile for future use.

    Examples:
      ab login my-taobao https://www.taobao.com
      ab login my-jd https://www.jd.com
      ab login my-12306 https://www.12306.cn
    """
    config: AppConfig = ctx.obj["config"]
    asyncio.run(_run_login(config, profile_name, url, timeout))


async def _run_login(config: AppConfig, profile_name: str, url: str, timeout: int):
    """Launch visible browser for manual login, then save session."""
    from agent_browser.browser.session import SessionManager, SessionProfile

    manager = SessionManager(config.data_path)
    profile = manager.get_or_create(profile_name)
    domain = SessionProfile.extract_domain(url)

    console.print(Panel(
        f"[bold]Login Profile:[/bold] {profile_name}\n"
        f"[bold]URL:[/bold] {url}\n"
        f"[bold]Timeout:[/bold] {timeout}s\n\n"
        f"A browser window will open. Please login manually\n"
        f"(scan QR code, enter password, etc).\n"
        f"After login, press [cyan]Enter[/cyan] here to save the session.",
        title="AgentBrowser - Manual Login",
        border_style="yellow",
    ))

    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            # Use persistent context so cookies are saved to the profile directory
            user_data_dir = profile.user_data_dir

            # Determine executable path
            try:
                from agent_browser.browser.chromium import get_binary_path, is_binary_installed
                executable = get_binary_path() if is_binary_installed() else None
            except Exception:
                executable = None

            launch_args = [
                "--no-first-run",
                "--disable-blink-features=AutomationControlled",
            ]

            context = await p.chromium.launch_persistent_context(
                user_data_dir,
                headless=False,  # Always visible for login
                executable_path=executable,
                args=launch_args,
                viewport={"width": 1280, "height": 800},
                locale="zh-CN",
            )

            page = context.pages[0] if context.pages else await context.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)

            console.print(f"\n[yellow]Browser opened at {url}[/yellow]")
            console.print("[yellow]Please login in the browser window...[/yellow]")

            # Wait for user to press Enter
            try:
                Prompt.ask("\n[bold green]Press Enter after you have logged in[/bold green]")
            except (EOFError, KeyboardInterrupt):
                pass

            # Save cookies
            cookies = await context.cookies()
            profile.cookies_file.write_text(json.dumps(cookies, indent=2))
            profile.mark_logged_in(domain, username="manual-login")

            await context.close()

        console.print(f"\n[green]Login session saved![/green]")
        console.print(f"  Profile: {profile_name}")
        console.print(f"  Site: {domain}")
        console.print(f"  Cookies: {len(cookies)} saved")
        console.print(f"\n[dim]Now use: ab run --profile {profile_name} \"your task\"[/dim]")

    except Exception as e:
        console.print(f"\n[red]Login failed: {e}[/red]")
        sys.exit(1)


# --- Profile Management ---

@cli.group()
def profiles():
    """Manage browser session profiles (persistent login)."""
    pass


@profiles.command(name="list")
@click.pass_context
def profiles_list(ctx):
    """List all session profiles."""
    config: AppConfig = ctx.obj["config"]
    from agent_browser.browser.session import SessionManager

    manager = SessionManager(config.data_path)
    names = manager.list_profiles()

    if not names:
        console.print("[dim]No profiles found. Use 'ab run' to auto-create one.[/dim]")
        return

    table = Table(title="Session Profiles")
    table.add_column("Name", style="cyan")
    table.add_column("Sites Logged In")
    table.add_column("Created")

    for name in names:
        profile = manager.get(name)
        if profile:
            sites = list(profile.meta.get("sites", {}).keys())
            sites_str = ", ".join(sites[:5]) if sites else "[dim]none[/dim]"
            created = time.strftime("%Y-%m-%d", time.localtime(profile.meta.get("created_at", 0)))
            table.add_row(name, sites_str, created)

    console.print(table)


@profiles.command(name="create")
@click.argument("name")
@click.pass_context
def profiles_create(ctx, name):
    """Create a new session profile."""
    config: AppConfig = ctx.obj["config"]
    from agent_browser.browser.session import SessionManager

    manager = SessionManager(config.data_path)
    profile = manager.get_or_create(name)
    console.print(f"[green]Profile '{name}' created at {profile.profile_dir}[/green]")
    console.print(f"[dim]To login, run: ab login {name} <url>[/dim]")


@profiles.command(name="delete")
@click.argument("name")
@click.pass_context
def profiles_delete(ctx, name):
    """Delete a session profile and all its data."""
    config: AppConfig = ctx.obj["config"]
    from agent_browser.browser.session import SessionManager

    manager = SessionManager(config.data_path)
    if manager.delete(name):
        console.print(f"[green]Profile '{name}' deleted.[/green]")
    else:
        console.print(f"[red]Profile '{name}' not found.[/red]")


@profiles.command(name="info")
@click.argument("name")
@click.pass_context
def profiles_info(ctx, name):
    """Show details about a session profile."""
    config: AppConfig = ctx.obj["config"]
    from agent_browser.browser.session import SessionManager

    manager = SessionManager(config.data_path)
    profile = manager.get(name)
    if not profile:
        console.print(f"[red]Profile '{name}' not found.[/red]")
        return

    console.print(Panel.fit(f"[bold]Profile: {name}[/bold]"))
    console.print(f"  Directory: {profile.profile_dir}")
    console.print(f"  User Data Dir: {profile.user_data_dir}")

    sites = profile.meta.get("sites", {})
    if sites:
        table = Table(title="Logged-in Sites")
        table.add_column("Site", style="cyan")
        table.add_column("Username")
        table.add_column("Last Login")
        for site, info in sites.items():
            last_login = time.strftime("%Y-%m-%d %H:%M", time.localtime(info.get("last_login", 0)))
            table.add_row(site, info.get("username", ""), last_login)
        console.print(table)
    else:
        console.print("  [dim]No recorded logins[/dim]")


# --- CloakBrowser Chromium Management ---

@cli.group()
def chromium():
    """Manage CloakBrowser patched Chromium binary."""
    pass


@chromium.command(name="install")
@click.option("--force", is_flag=True, help="Force re-download even if already installed")
def chromium_install(force):
    """Download and install CloakBrowser Chromium."""
    from agent_browser.browser.chromium import download_binary, get_chromium_version, get_platform_tag

    tag = get_platform_tag()
    version = get_chromium_version(tag)
    console.print(f"[bold]Installing CloakBrowser Chromium v{version} for {tag}...[/bold]")

    try:
        path = download_binary(force=force)
        console.print(f"\n[green]Installed successfully![/green]")
        console.print(f"  Binary: {path}")
    except Exception as e:
        console.print(f"\n[red]Installation failed: {e}[/red]")
        sys.exit(1)


@chromium.command(name="info")
def chromium_info():
    """Show CloakBrowser Chromium installation info."""
    from agent_browser.browser.chromium import get_info

    info = get_info()
    console.print(Panel.fit("[bold]CloakBrowser Chromium[/bold]"))
    console.print(f"  Platform: {info['platform']}")
    console.print(f"  Chromium Version: {info['chromium_version']}")
    installed = "[green]Yes[/green]" if info["installed"] else "[red]No[/red]"
    console.print(f"  Installed: {installed}")
    console.print(f"  Binary Path: {info['binary_path']}")
    console.print(f"  Cache Dir: {info['cache_dir']}")
    console.print(f"  Download URL: {info['download_url']}")


@chromium.command(name="clear-cache")
@click.confirmation_option(prompt="Delete all cached CloakBrowser binaries?")
def chromium_clear_cache():
    """Remove all cached CloakBrowser binaries."""
    from agent_browser.browser.chromium import clear_cache

    clear_cache()
    console.print("[green]Cache cleared.[/green]")


if __name__ == "__main__":
    cli()
