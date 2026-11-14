"""Tools available to the voice agent."""
from .weather import get_weather
from .tasks import update_farming_task
from .crop_knowledge import search_crop_knowledge
from .places import search_farming_places

AGENT_TOOLS = [get_weather, update_farming_task, search_crop_knowledge, search_farming_places]
