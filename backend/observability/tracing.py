"""Keep tracing configuration, attributes and shutdown handling out of agent code."""
import asyncio
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
import json
import logging
import os
from pathlib import Path

from opentelemetry import trace
from opentelemetry.context import Context
from opentelemetry.sdk.trace import SpanProcessor, TracerProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.trace import Status, StatusCode

from .config import get_observability_settings

_provider = None
_metadata = ContextVar("opencall_trace_metadata", default={})


class SessionAttributes(SpanProcessor):
    def on_start(self, span, parent_context=None):
        for key, value in _metadata.get().items():
            span.set_attribute(key, value)
        if not (span.attributes or {}).get("openinference.span.kind"):
            span.set_attribute("openinference.span.kind", "AGENT" if span.name == "agent_session" else "CHAIN")

    def on_end(self, span):
        pass

    def shutdown(self):
        pass

    def force_flush(self, timeout_millis=30000):
        return True


def configure():
    global _provider
    settings = get_observability_settings()
    if not settings.enabled:
        return None
    if _provider is not None:
        return _provider
    try:
        os.environ.setdefault("PHOENIX_WORKING_DIR", str(Path(__file__).resolve().parent / "data"))
        from phoenix.otel import BatchSpanProcessor
        from openinference.instrumentation import TraceConfig
        from openinference.instrumentation.openai import OpenAIInstrumentor
        from livekit.agents.telemetry import set_tracer_provider

        # Use a standard SDK provider: Phoenix's convenience provider replaces
        # its default exporter when LiveKit attaches its redaction processor.
        provider = TracerProvider(resource=Resource.create({
            "openinference.project.name": settings.project_name, "service.name": "opencall.voice",
        }))
        provider.add_span_processor(SessionAttributes())
        OpenAIInstrumentor().instrument(tracer_provider=provider, config=TraceConfig(
            hide_inputs=not settings.capture_content, hide_outputs=not settings.capture_content,
            hide_input_messages=not settings.capture_content, hide_output_messages=not settings.capture_content,
        ))
        set_tracer_provider(provider, allow_pii=settings.capture_content)
        provider.add_span_processor(BatchSpanProcessor(endpoint=settings.collector_endpoint,
                                                      protocol="http/protobuf"))
        _provider = provider
        return provider
    except Exception:
        logging.getLogger(__name__).exception("Phoenix tracing could not start; continuing without tracing")
        return None


def tracer():
    return (_provider or trace.NoOpTracerProvider()).get_tracer("opencall")


class SessionObservation:
    def __init__(self, username: str, room_name: str, language: str, voice: str):
        self.provider = configure()
        self.metadata = {"session.id": room_name, "user.id": username,
                         "opencall.language": language, "opencall.voice": voice}
        self.span = tracer().start_span("opencall.session", context=Context(), attributes={
            **self.metadata, "openinference.span.kind": "AGENT",
        })

    @contextmanager
    def activate(self):
        token = _metadata.set(self.metadata)
        try:
            with trace.use_span(self.span, end_on_exit=False, record_exception=False,
                                set_status_on_exception=False):
                try:
                    yield
                except Exception as error:
                    self.span.set_attribute("error.type", type(error).__name__)
                    self.span.set_status(Status(StatusCode.ERROR, type(error).__name__))
                    raise
        finally:
            _metadata.reset(token)

    async def finish(self):
        self.span.end()
        if self.provider is not None:
            try:
                await asyncio.to_thread(self.provider.force_flush, timeout_millis=3000)
            except Exception:
                logging.getLogger(__name__).warning("Phoenix traces could not be flushed")


def observed(name: str, kind: str = "CHAIN"):
    """Trace our custom async work; LiveKit/OpenAI instrument voice model calls."""
    def decorate(function):
        @wraps(function)
        async def wrapped(*args, **kwargs):
            with tracer().start_as_current_span(name, attributes={"openinference.span.kind": kind},
                record_exception=False, set_status_on_exception=False) as span:
                if kind == "LLM":
                    from app.core.config import get_settings
                    span.set_attribute("llm.model_name", get_settings().groq_model)
                    span.set_attribute("llm.provider", "groq")
                if kind == "TOOL":
                    span.set_attribute("tool.name", function.__name__)
                if kind in {"LLM", "TOOL"} and get_observability_settings().capture_content:
                    span.set_attribute("input.value", json.dumps({"args": args, "kwargs": kwargs}, ensure_ascii=False))
                try:
                    result = await function(*args, **kwargs)
                except Exception as error:
                    record_outcome("failed", error)
                    raise
                if kind in {"LLM", "TOOL"} and get_observability_settings().capture_content:
                    span.set_attribute("output.value", str(result))
                return result
        return wrapped
    return decorate


def record_llm_usage(response: dict):
    span = trace.get_current_span()
    usage = response.get("usage") or {}
    for source, target in [("prompt_tokens", "prompt"), ("completion_tokens", "completion"), ("total_tokens", "total")]:
        if isinstance(usage.get(source), int):
            span.set_attribute("llm.token_count." + target, usage[source])


def record_outcome(outcome: str, error: Exception | None = None):
    span = trace.get_current_span()
    span.set_attribute("opencall.outcome", outcome)
    if error is not None:
        span.set_attribute("error.type", type(error).__name__)
        span.set_status(Status(StatusCode.ERROR, type(error).__name__))
