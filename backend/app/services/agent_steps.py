"""Small, best-effort progress events for the participant in the current room."""
import json
import logging
from datetime import datetime, timezone

from livekit.agents import get_job_context


async def send_step(step: str, data: dict) -> bool:
    context = get_job_context(required=False)
    if context is None:
        return False
    payload = json.dumps({"type": "agent_step", "step": step, "data": data,
                          "timestamp": datetime.now(timezone.utc).isoformat()}).encode()
    try:
        await context.room.local_participant.publish_data(payload, reliable=True, topic="agent_observability")
        return True
    except Exception:
        logging.getLogger(__name__).warning("Could not publish agent step", exc_info=True)
        return False
