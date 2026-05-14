"""AgentBrowser - AI-powered browser automation agent."""

__version__ = "1.0.0"
__all__ = ["AgentBrowser", "BrowserEngine", "StealthLauncher", "TaskScheduler"]

from agent_browser.core.agent import AgentBrowser
from agent_browser.browser.engine import BrowserEngine
from agent_browser.browser.stealth import StealthLauncher
from agent_browser.core.scheduler import TaskScheduler
