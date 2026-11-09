"""Tools available to the voice agent."""
from .weather import get_weather
from .tasks import update_farming_task
from .crop_knowledge import search_crop_knowledge

AGENT_TOOLS = [get_weather, update_farming_task, search_crop_knowledge]
