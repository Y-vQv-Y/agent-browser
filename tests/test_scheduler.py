"""Tests for the task scheduler."""

import json
import tempfile
from pathlib import Path

import pytest

from agent_browser.core.scheduler import TaskScheduler, ScheduledTask


class TestScheduledTask:
    def test_creation(self):
        task = ScheduledTask(
            task_id="abc123",
            description="Test task",
            execute_at="2025-12-31T21:15:00",
        )
        assert task.task_id == "abc123"
        assert task.description == "Test task"
        assert task.status == "pending"

    def test_to_dict(self):
        task = ScheduledTask(
            task_id="abc",
            description="Test",
            execute_at="2025-12-31T00:00:00",
        )
        d = task.to_dict()
        assert d["task_id"] == "abc"
        assert d["description"] == "Test"
        assert d["status"] == "pending"
        assert d["execute_at"] == "2025-12-31T00:00:00"


class TestTaskScheduler:
    @pytest.fixture
    def scheduler(self, tmp_path):
        return TaskScheduler(data_dir=tmp_path / "tasks")

    def test_add_task(self, scheduler):
        task = scheduler.add_task(
            description="Book ticket",
            execute_at="2025-12-31T21:15:00",
        )
        assert task.task_id
        assert task.description == "Book ticket"
        assert task.status == "pending"

    def test_list_tasks(self, scheduler):
        scheduler.add_task(description="Task 1", execute_at="2025-01-01T00:00:00")
        scheduler.add_task(description="Task 2", execute_at="2025-01-02T00:00:00")
        tasks = scheduler.list_tasks()
        assert len(tasks) == 2

    def test_list_tasks_by_status(self, scheduler):
        t1 = scheduler.add_task(description="Task 1", execute_at="2025-01-01T00:00:00")
        t2 = scheduler.add_task(description="Task 2", execute_at="2025-01-02T00:00:00")
        t1.status = "completed"
        scheduler._save_tasks()

        pending = scheduler.list_tasks(status="pending")
        assert len(pending) == 1
        assert pending[0].description == "Task 2"

    def test_get_task(self, scheduler):
        task = scheduler.add_task(description="Find me", execute_at="2025-01-01T00:00:00")
        found = scheduler.get_task(task.task_id)
        assert found is not None
        assert found.description == "Find me"

    def test_get_nonexistent_task(self, scheduler):
        assert scheduler.get_task("nonexistent") is None

    def test_cancel_task(self, scheduler):
        task = scheduler.add_task(description="Cancel me", execute_at="2025-01-01T00:00:00")
        assert scheduler.cancel_task(task.task_id) is True
        assert scheduler.get_task(task.task_id).status == "cancelled"

    def test_cancel_completed_task_fails(self, scheduler):
        task = scheduler.add_task(description="Done", execute_at="2025-01-01T00:00:00")
        task.status = "completed"
        assert scheduler.cancel_task(task.task_id) is False

    def test_persist_tasks(self, tmp_path):
        # Create and save
        s1 = TaskScheduler(data_dir=tmp_path / "tasks")
        s1.add_task(description="Persist me", execute_at="2025-06-01T00:00:00")

        # Load and verify
        s2 = TaskScheduler(data_dir=tmp_path / "tasks")
        tasks = s2.list_tasks()
        assert len(tasks) == 1
        assert tasks[0].description == "Persist me"

    def test_cron_task(self, scheduler):
        task = scheduler.add_task(
            description="Check prices",
            cron="0 9 * * *",
        )
        assert task.cron == "0 9 * * *"
        assert task.execute_at is None

    def test_pre_check_flag(self, scheduler):
        task = scheduler.add_task(
            description="Book ticket",
            execute_at="2025-12-31T21:15:00",
            pre_check=True,
        )
        assert task.pre_check is True

    def test_shutdown(self, scheduler):
        scheduler.shutdown()  # Should not raise
