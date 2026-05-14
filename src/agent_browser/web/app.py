"""
Web GUI - FastAPI-based web interface for AgentBrowser.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from agent_browser.config import AppConfig

logger = logging.getLogger(__name__)

# Global agent reference
_agent = None
_tasks_queue: dict[str, asyncio.Queue] = {}


def create_app(config: Optional[AppConfig] = None) -> FastAPI:
    """Create the FastAPI application."""
    config = config or AppConfig()

    app = FastAPI(title="AgentBrowser", version="1.0.0")

    static_dir = Path(__file__).parent / "static"
    templates_dir = Path(__file__).parent / "templates"
    static_dir.mkdir(exist_ok=True)
    templates_dir.mkdir(exist_ok=True)

    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    templates = Jinja2Templates(directory=str(templates_dir))

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        """Main page."""
        return templates.TemplateResponse(request=request, name="index.html")

    @app.get("/api/status")
    async def status():
        """Get agent status."""
        global _agent
        return {
            "status": "running" if _agent and _agent._running else "idle",
            "browser_launched": _agent.browser._launched if _agent and _agent.browser else False,
            "config": {
                "provider": config.llm.provider,
                "model": config.llm.model,
                "headless": config.browser.headless,
            },
        }

    @app.post("/api/task")
    async def submit_task(request: Request):
        """Submit a new task."""
        global _agent
        data = await request.json()
        task_text = data.get("task", "")

        if not task_text:
            return JSONResponse({"error": "No task provided"}, status_code=400)

        task_id = str(uuid.uuid4())[:8]

        if _agent is None:
            from agent_browser.core.agent import AgentBrowser
            _agent = AgentBrowser(config)

        # Run task in background
        _tasks_queue[task_id] = asyncio.Queue()

        async def run_bg():
            try:
                result = await _agent.run_task(task_text)
                await _tasks_queue[task_id].put({
                    "type": "complete",
                    "success": result.success,
                    "result": result.result,
                    "steps": len(result.steps),
                    "duration": result.duration,
                })
            except Exception as e:
                await _tasks_queue[task_id].put({
                    "type": "error",
                    "error": str(e),
                })

        asyncio.create_task(run_bg())

        return {"task_id": task_id, "status": "started"}

    @app.get("/api/tasks")
    async def list_tasks():
        """List scheduled tasks."""
        global _agent
        if _agent is None:
            return {"tasks": []}
        return {
            "tasks": [t.to_dict() for t in _agent.scheduler.list_tasks()],
        }

    @app.post("/api/schedule")
    async def schedule_task(request: Request):
        """Schedule a future task."""
        global _agent
        data = await request.json()

        if _agent is None:
            from agent_browser.core.agent import AgentBrowser
            _agent = AgentBrowser(config)

        task = _agent.scheduler.add_task(
            description=data["task"],
            execute_at=data.get("execute_at"),
            cron=data.get("cron"),
            pre_check=data.get("pre_check", False),
        )
        return task.to_dict()

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        """WebSocket for real-time task updates."""
        await websocket.accept()
        global _agent

        try:
            while True:
                data = await websocket.receive_json()
                action = data.get("action")

                if action == "run_task":
                    task_text = data.get("task", "")
                    if not task_text:
                        await websocket.send_json({"error": "No task provided"})
                        continue

                    if _agent is None:
                        from agent_browser.core.agent import AgentBrowser
                        _agent = AgentBrowser(config)

                    async def on_step(step):
                        await websocket.send_json({
                            "type": "step",
                            "tool": step.tool_name,
                            "success": step.success,
                            "duration": step.duration,
                            "result": str(step.result)[:200],
                        })

                    _agent.set_step_callback(on_step)

                    await websocket.send_json({"type": "start", "task": task_text})

                    try:
                        result = await _agent.run_task(task_text)
                        await websocket.send_json({
                            "type": "complete",
                            "success": result.success,
                            "result": result.result,
                            "steps": len(result.steps),
                            "duration": result.duration,
                        })
                    except Exception as e:
                        await websocket.send_json({
                            "type": "error",
                            "error": str(e),
                        })

                elif action == "screenshot":
                    if _agent and _agent.browser and _agent.browser._launched:
                        img = await _agent.browser.screenshot()
                        await websocket.send_json({
                            "type": "screenshot",
                            "image": img,
                        })

        except WebSocketDisconnect:
            logger.info("WebSocket client disconnected")
        except Exception as e:
            logger.error("WebSocket error: %s", e)

    return app
