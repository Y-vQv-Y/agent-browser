"""Tests for the Web GUI API - uses subprocess to avoid async event loop conflicts."""

import json
import subprocess
import sys

import pytest


WEB_TEST_SCRIPT = '''
import sys
import json

from agent_browser.config import AppConfig
from agent_browser.web.app import create_app
from fastapi.testclient import TestClient

config = AppConfig(llm={"provider": "openai", "api_key": "test-key", "model": "gpt-4o"})
app = create_app(config)
client = TestClient(app)

test_name = sys.argv[1]
results = {}

if test_name == "test_index":
    resp = client.get("/")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    assert "AgentBrowser" in resp.text, "AgentBrowser not in page"
    results = {"status": resp.status_code}

elif test_name == "test_status":
    resp = client.get("/api/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "config" in data
    results = data

elif test_name == "test_list_tasks_empty":
    resp = client.get("/api/tasks")
    assert resp.status_code == 200
    data = resp.json()
    assert "tasks" in data
    assert isinstance(data["tasks"], list)
    results = data

elif test_name == "test_submit_task_empty":
    resp = client.post("/api/task", json={"task": ""})
    assert resp.status_code == 400
    results = {"status": resp.status_code}

elif test_name == "test_schedule_task":
    resp = client.post("/api/schedule", json={
        "task": "Test scheduled task",
        "execute_at": "2025-12-31T21:15:00",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "task_id" in data
    assert data["description"] == "Test scheduled task"
    results = data

print(json.dumps({"ok": True, "results": results}))
'''


def _run_web_test(test_name: str):
    """Run a web test in a subprocess to avoid event loop conflicts."""
    result = subprocess.run(
        [sys.executable, "-c", WEB_TEST_SCRIPT, test_name],
        capture_output=True, text=True, timeout=15,
        cwd=str(__import__("pathlib").Path(__file__).parent.parent),
    )
    if result.returncode != 0:
        pytest.fail(f"Web test {test_name} failed:\nstdout: {result.stdout}\nstderr: {result.stderr}")
    output = json.loads(result.stdout.strip().split("\n")[-1])
    assert output["ok"] is True
    return output["results"]


class TestWebAPI:
    def test_index(self):
        result = _run_web_test("test_index")
        assert result["status"] == 200

    def test_status(self):
        result = _run_web_test("test_status")
        assert "status" in result
        assert "config" in result

    def test_list_tasks_empty(self):
        result = _run_web_test("test_list_tasks_empty")
        assert "tasks" in result

    def test_submit_task_empty(self):
        result = _run_web_test("test_submit_task_empty")
        assert result["status"] == 400

    def test_schedule_task(self):
        result = _run_web_test("test_schedule_task")
        assert "task_id" in result
        assert result["description"] == "Test scheduled task"
