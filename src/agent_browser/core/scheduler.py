"""
Task Scheduler - Internalized from GenericAgent's reflect/scheduler.py.
Provides cron-like task scheduling and one-shot timed execution.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class ScheduledTask:
    """A scheduled task definition."""

    def __init__(
        self,
        task_id: str,
        description: str,
        execute_at: Optional[str] = None,
        cron: Optional[str] = None,
        pre_check: bool = False,
        callback: Optional[Callable] = None,
        status: str = "pending",
        created_at: Optional[str] = None,
        result: Optional[str] = None,
    ):
        self.task_id = task_id
        self.description = description
        self.execute_at = execute_at
        self.cron = cron
        self.pre_check = pre_check
        self.callback = callback
        self.status = status  # pending, pre_checking, ready, running, completed, failed
        self.created_at = created_at or datetime.now().isoformat()
        self.result = result

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "description": self.description,
            "execute_at": self.execute_at,
            "cron": self.cron,
            "pre_check": self.pre_check,
            "status": self.status,
            "created_at": self.created_at,
            "result": self.result,
        }


class TaskScheduler:
    """
    Task scheduler supporting one-shot and recurring tasks.
    Uses APScheduler as the underlying engine.
    """

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or Path("~/.agent-browser/tasks").expanduser()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.tasks: dict[str, ScheduledTask] = {}
        self._scheduler = None
        self._task_executor: Optional[Callable] = None
        self._load_tasks()

    def _load_tasks(self):
        """Load pending tasks from disk."""
        tasks_file = self.data_dir / "tasks.json"
        if tasks_file.exists():
            try:
                data = json.loads(tasks_file.read_text())
                for task_data in data:
                    task = ScheduledTask(**task_data)
                    self.tasks[task.task_id] = task
            except Exception as e:
                logger.warning("Failed to load tasks: %s", e)

    def _save_tasks(self):
        """Save tasks to disk."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        data = [t.to_dict() for t in self.tasks.values()]
        (self.data_dir / "tasks.json").write_text(json.dumps(data, indent=2))

    def set_executor(self, executor: Callable):
        """Set the callback function that executes tasks."""
        self._task_executor = executor

    def add_task(
        self,
        description: str,
        execute_at: Optional[str] = None,
        cron: Optional[str] = None,
        pre_check: bool = False,
    ) -> ScheduledTask:
        """Add a new scheduled task."""
        task = ScheduledTask(
            task_id=str(uuid.uuid4())[:8],
            description=description,
            execute_at=execute_at,
            cron=cron,
            pre_check=pre_check,
        )
        self.tasks[task.task_id] = task
        self._save_tasks()

        if execute_at:
            self._schedule_one_shot(task)
        elif cron:
            self._schedule_cron(task)

        logger.info("Task scheduled: %s (id=%s, at=%s)", description, task.task_id, execute_at or cron)
        return task

    def _schedule_one_shot(self, task: ScheduledTask):
        """Schedule a one-shot task using APScheduler."""
        try:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler
            from apscheduler.triggers.date import DateTrigger

            if self._scheduler is None:
                self._scheduler = AsyncIOScheduler()
                self._scheduler.start()

            trigger = DateTrigger(run_date=datetime.fromisoformat(task.execute_at))
            self._scheduler.add_job(
                self._execute_task,
                trigger=trigger,
                args=[task.task_id],
                id=task.task_id,
            )
        except ImportError:
            logger.warning("APScheduler not available, task will need manual execution")
        except Exception as e:
            logger.error("Failed to schedule task: %s", e)

    def _schedule_cron(self, task: ScheduledTask):
        """Schedule a recurring cron task."""
        try:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler
            from apscheduler.triggers.cron import CronTrigger

            if self._scheduler is None:
                self._scheduler = AsyncIOScheduler()
                self._scheduler.start()

            trigger = CronTrigger.from_crontab(task.cron)
            self._scheduler.add_job(
                self._execute_task,
                trigger=trigger,
                args=[task.task_id],
                id=task.task_id,
            )
        except ImportError:
            logger.warning("APScheduler not available")
        except Exception as e:
            logger.error("Failed to schedule cron task: %s", e)

    async def _execute_task(self, task_id: str):
        """Execute a scheduled task."""
        task = self.tasks.get(task_id)
        if not task:
            return

        task.status = "running"
        self._save_tasks()
        logger.info("Executing scheduled task: %s", task.description)

        try:
            if self._task_executor:
                result = await self._task_executor(task.description)
                task.result = str(result)
                task.status = "completed"
            else:
                task.result = "No executor configured"
                task.status = "failed"
        except Exception as e:
            task.result = f"Error: {e}"
            task.status = "failed"
            logger.error("Task execution failed: %s", e)

        self._save_tasks()

    def get_task(self, task_id: str) -> Optional[ScheduledTask]:
        return self.tasks.get(task_id)

    def list_tasks(self, status: Optional[str] = None) -> list[ScheduledTask]:
        """List tasks, optionally filtered by status."""
        tasks = list(self.tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        return sorted(tasks, key=lambda t: t.created_at, reverse=True)

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending task."""
        task = self.tasks.get(task_id)
        if task and task.status in ("pending", "ready"):
            task.status = "cancelled"
            self._save_tasks()
            if self._scheduler:
                try:
                    self._scheduler.remove_job(task_id)
                except Exception:
                    pass
            return True
        return False

    def shutdown(self):
        """Shutdown the scheduler."""
        if self._scheduler:
            self._scheduler.shutdown(wait=False)
