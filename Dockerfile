FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/app/backend FASTEMBED_CACHE_PATH=/app/model-cache
WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
COPY voiceagent/requirements.txt /app/voiceagent/requirements.txt
RUN pip install --no-cache-dir -r voiceagent/requirements.txt
RUN useradd --create-home --uid 10001 agent
COPY backend/app /app/backend/app
COPY backend/tools /app/backend/tools
COPY voiceagent /app/voiceagent
USER agent
RUN python -c "from fastembed import TextEmbedding; TextEmbedding(model_name='sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')"
RUN python -m livekit.agents download-files
CMD ["python", "-m", "voiceagent.worker", "start"]
