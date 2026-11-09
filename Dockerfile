FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/app/backend
WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
COPY backend/observability/requirements.txt /app/backend/observability/requirements.txt
COPY voiceagent/requirements.txt /app/voiceagent/requirements.txt
RUN pip install --no-cache-dir -r voiceagent/requirements.txt
RUN useradd --create-home --uid 10001 agent
COPY backend/app /app/backend/app
COPY backend/tools /app/backend/tools
COPY backend/observability /app/backend/observability
COPY voiceagent /app/voiceagent
ENV PHOENIX_ENABLED=false
USER agent
RUN python -m livekit.agents download-files
CMD ["python", "-m", "voiceagent.worker", "start"]
