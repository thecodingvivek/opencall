"""Publish session-local farming task updates to the caller's interface."""
import re
from typing import Literal

from livekit.agents import ToolError, function_tool

from app.services.agent_steps import send_step


@function_tool
async def update_farming_task(task_id: str, title: str, status: Literal["requested"]) -> str:
    """Add a requested farming-related phone call to the jobs panel; no call is made yet.

    Args:
        task_id: Short stable ID for this request, reused for later updates (letters, digits, hyphens).
        title: Brief requested call, such as "Call fertilizer shop to check stock".
        status: Always requested: outbound calling is not available yet.
    """
    task_id = task_id.strip()
    title = " ".join(title.split())
    if not re.fullmatch(r"[A-Za-z0-9-]{1,40}", task_id) or not 1 <= len(title) <= 100:
        raise ToolError("Use a short task ID and a task title of at most 100 characters.")
    if status != "requested":
        raise ToolError("Only requested is available: outbound calls are not supported yet.")
    if not await send_step("farming_task", {"id": task_id, "title": title, "status": status}):
        raise ToolError("The task list could not be updated. Tell the user if this matters.")
    return "Request added for this conversation only; calling is not available yet, and no call is scheduled."
