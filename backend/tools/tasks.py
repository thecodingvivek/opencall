"""Publish session-local farming task updates to the caller's interface."""
import re
from typing import Literal

from livekit.agents import ToolError, function_tool

from app.services.agent_steps import send_step


@function_tool
async def update_farming_task(task_id: str, title: str, status: Literal["in_progress", "completed", "blocked"]) -> str:
    """Update a farming task in the caller's jobs panel; this does not perform the work.

    Args:
        task_id: Short stable ID for this request, reused for later updates (letters, digits, hyphens).
        title: Brief farming-related task, such as "Find fertilizer shops near Ettimadai".
        status: in_progress while real work is underway, completed only after doing it, or blocked if unavailable.
    """
    task_id = task_id.strip()
    title = " ".join(title.split())
    if not re.fullmatch(r"[A-Za-z0-9-]{1,40}", task_id) or not 1 <= len(title) <= 100:
        raise ToolError("Use a short task ID and a task title of at most 100 characters.")
    if status not in {"in_progress", "completed", "blocked"}:
        raise ToolError("Invalid task status.")
    if not await send_step("farming_task", {"id": task_id, "title": title, "status": status}):
        raise ToolError("The task list could not be updated. Tell the user if this matters.")
    return "Task list updated; this does not perform the task."
