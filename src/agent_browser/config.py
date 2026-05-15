"""Configuration management for AgentBrowser."""

from __future__ import annotations

import os
import json
import secrets
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class LLMConfig(BaseSettings):
    """LLM provider configuration."""

    provider: str = Field(default="openai", description="LLM provider: openai, anthropic")
    api_key: str = Field(default="", description="API key for LLM provider")
    model: str = Field(default="gpt-4o", description="Model name")
    base_url: Optional[str] = Field(default=None, description="Custom API base URL")
    max_tokens: int = Field(default=4096, description="Max output tokens")
    temperature: float = Field(default=0.1, description="Sampling temperature")

    model_config = {"env_prefix": "AB_LLM_"}


class BrowserConfig(BaseSettings):
    """Browser configuration."""

    headless: bool = Field(default=True, description="Run browser headless")
    stealth: bool = Field(default=True, description="Enable anti-detection")
    humanize: bool = Field(default=True, description="Enable human-like behavior")
    human_preset: str = Field(default="default", description="Human behavior preset")
    viewport_width: int = Field(default=1920, description="Viewport width")
    viewport_height: int = Field(default=1080, description="Viewport height")
    proxy: Optional[str] = Field(default=None, description="Proxy URL")
    user_data_dir: Optional[str] = Field(default=None, description="Chrome user data dir")
    fingerprint_seed: Optional[str] = Field(default=None, description="Fingerprint seed")
    timeout: int = Field(default=30000, description="Default timeout in ms")
    screenshot_dir: str = Field(default="./screenshots", description="Screenshot directory")

    model_config = {"env_prefix": "AB_BROWSER_"}


class AppConfig(BaseSettings):
    """Application-level configuration."""

    debug: bool = Field(default=False, description="Debug mode")
    log_level: str = Field(default="INFO", description="Log level")
    data_dir: str = Field(default="~/.agent-browser", description="Data directory")
    web_host: str = Field(default="0.0.0.0", description="Web GUI host")
    web_port: int = Field(default=8899, description="Web GUI port")
    secret_key: str = Field(default_factory=lambda: secrets.token_hex(32))

    llm: LLMConfig = Field(default_factory=LLMConfig)
    browser: BrowserConfig = Field(default_factory=BrowserConfig)

    model_config = {"env_prefix": "AB_"}

    @property
    def data_path(self) -> Path:
        return Path(self.data_dir).expanduser()

    def save(self, path: Optional[Path] = None, encrypt_keys: bool = True):
        """Save config to JSON file. Optionally encrypts sensitive values."""
        p = path or self.data_path / "config.json"
        p.parent.mkdir(parents=True, exist_ok=True)

        data = self.model_dump()

        if encrypt_keys:
            from agent_browser.crypto import encrypt
            data_dir = self.data_path
            # Encrypt API key
            if data.get("llm", {}).get("api_key"):
                data["llm"]["api_key"] = encrypt(data["llm"]["api_key"], data_dir)

        p.write_text(json.dumps(data, indent=2, default=str))

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "AppConfig":
        """Load config from JSON file, falling back to defaults + env vars."""
        p = path or Path("~/.agent-browser/config.json").expanduser()
        if p.exists():
            data = json.loads(p.read_text())
            # Decrypt sensitive values
            data_dir = Path(data.get("data_dir", "~/.agent-browser")).expanduser()
            from agent_browser.crypto import decrypt, is_encrypted
            if data.get("llm", {}).get("api_key"):
                api_key = data["llm"]["api_key"]
                if is_encrypted(api_key):
                    data["llm"]["api_key"] = decrypt(api_key, data_dir)
            return cls(**data)
        return cls()

    def get_api_key(self) -> str:
        """Get the decrypted API key."""
        return self.llm.api_key


def get_config() -> AppConfig:
    """Get or create the global config."""
    return AppConfig.load()
