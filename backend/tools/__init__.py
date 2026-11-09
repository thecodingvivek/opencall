"""Tools available to the voice agent."""
from .weather import get_weather
from .tasks import update_farming_task

AGENT_TOOLS = [get_weather, update_farming_task]
