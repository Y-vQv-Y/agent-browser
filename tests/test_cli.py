"""Tests for the CLI interface."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from agent_browser.cli.main import cli


@pytest.fixture
def runner():
    return CliRunner()


class TestCLI:
    def test_version(self, runner):
        result = runner.invoke(cli, ["version"])
        assert result.exit_code == 0
        assert "AgentBrowser" in result.output
        assert "1.0.0" in result.output

    def test_help(self, runner):
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "AgentBrowser" in result.output

    def test_run_help(self, runner):
        result = runner.invoke(cli, ["run", "--help"])
        assert result.exit_code == 0
        assert "task" in result.output.lower()

    def test_configure_help(self, runner):
        result = runner.invoke(cli, ["configure", "--help"])
        assert result.exit_code == 0

    def test_schedule_help(self, runner):
        result = runner.invoke(cli, ["schedule", "--help"])
        assert result.exit_code == 0

    def test_tasks_empty(self, runner, tmp_path):
        result = runner.invoke(cli, ["tasks"], env={"AB_DATA_DIR": str(tmp_path)})
        assert result.exit_code == 0

    def test_doctor_command(self, runner):
        result = runner.invoke(cli, ["doctor"])
        assert result.exit_code == 0
        assert "Python version" in result.output

    def test_web_help(self, runner):
        result = runner.invoke(cli, ["web", "--help"])
        assert result.exit_code == 0
        assert "host" in result.output.lower()

    def test_run_no_api_key(self, runner, tmp_path):
        """Run should fail gracefully when no API key is set."""
        result = runner.invoke(cli, ["run", "test task"], env={
            "AB_DATA_DIR": str(tmp_path),
            "AB_LLM_API_KEY": "",
        })
        assert result.exit_code != 0 or "API key" in result.output or "Error" in result.output
