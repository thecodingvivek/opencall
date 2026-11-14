"""Save farming task requests and notify the caller's interface."""
import asyncio
import json
import logging
import re
from typing import Literal
from uuid import UUID

from livekit.agents import ToolError, function_tool, get_job_context

from app.services.agent_steps import send_step
from app.services.tasks import save_task


@function_tool
async def update_farming_task(task_id: str, title: str, status: Literal["requested"]) -> str:
    """Save an explicitly requested farming-related call; no call is made or scheduled.

    Args:
        task_id: Stable request ID using letters, digits, or hyphens; reuse for updates.
        title: Brief call request, e.g. "Call fertilizer shop to check stock".
        status: Always requested.
    """
    task_id = task_id.strip()
    title = " ".join(title.split())
    if not re.fullmatch(r"[A-Za-z0-9-]{1,40}", task_id) or not 1 <= len(title) <= 100:
        raise ToolError("Use a short task ID and a task title of at most 100 characters.")
    if status != "requested":
        raise ToolError("Only requested is available: outbound calls are not supported yet.")
    context = get_job_context(required=False)
    try:
        if context is None:
            raise ValueError("Missing job context")
        metadata = json.loads(context.job.metadata or "{}")
        if metadata.get("guest") is True:
            raise ValueError("A signed-in user is required")
        user_id = str(UUID(metadata["username"]))
        room_name = context.job.room.name
        if not room_name:
            raise ValueError("Missing room name")
        task = await asyncio.to_thread(save_task, user_id, room_name, task_id, title, status)
    except Exception as error:
        logging.getLogger(__name__).warning("Could not save farming task: %s", type(error).__name__)
        raise ToolError("The task could not be saved. Tell the user and do not claim it was added.") from None
    await send_step("farming_task", task)
    return "Request saved to the task list; calling is not available yet and no call is scheduled."
