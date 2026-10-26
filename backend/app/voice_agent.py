"""Run with: python -m app.voice_agent dev (alongside the FastAPI server)."""
import asyncio
import json
import logging

from livekit.agents import Agent, AgentServer, AgentSession, JobContext, cli, function_tool, room_io
from livekit.plugins import gnani, openai, silero

from app.core.config import get_settings
from app.services.conversation import AGENT_NAME, ConversationOptions
from app.services.phonebook import (
    get_phonebook_store, memory_instructions, retry_pending_memory, save_call_memory,
)
from app.services.realtime_speech import ConversationTTS

settings = get_settings()
server = AgentServer(
    ws_url=settings.livekit_url, api_key=settings.livekit_api_key,
    api_secret=settings.livekit_api_secret.get_secret_value(),
    shutdown_process_timeout=45,
)


@server.rtc_session(agent_name=AGENT_NAME)
async def conversation(ctx: JobContext):
    if not settings.gnani_api_key or not settings.groq_api_key:
        raise RuntimeError("Set GNANI_API_KEY and GROQ_API_KEY before starting the worker.")
    metadata = json.loads(ctx.job.metadata or "{}")
    options = ConversationOptions.model_validate(metadata)
    identity = metadata.get("participant_identity")
    if not isinstance(identity, str) or not identity.startswith("user-"):
        raise ValueError("Conversation dispatch is missing its participant identity")
    call_id = metadata.get("call_id")
    if not isinstance(call_id, str):
        raise ValueError("Conversation dispatch is missing its account-bound call")
    store = get_phonebook_store()
    call = await asyncio.to_thread(store.activate, call_id, ctx.job.room.name, identity)
    user_id = call["user_id"]
    session = None

    async def close_and_save():
        try:
            if session is not None:
                await session.aclose()
        finally:
            # Worker-owned finalization also runs after tab close, network loss, timeout,
            # or a provider error; it does not depend on a browser "end" request.
            await asyncio.to_thread(store.end_call, call_id)
            await save_call_memory(store, call_id)

    ctx.add_shutdown_callback(close_and_save)

    # Recover a prior summary failure before reading this account's latest memory.
    try:
        await asyncio.wait_for(retry_pending_memory(store, user_id), timeout=12)
    except TimeoutError:
        logging.getLogger(__name__).warning("Phonebook retry deferred", extra={"call_id": call_id})
    entry = await asyncio.to_thread(store.get, user_id)

    @function_tool
    async def lookup_phonebook() -> str:
        """Read the current caller's saved profile and previous call summary when relevant."""
        current = await asyncio.to_thread(store.get, user_id)
        return current.model_dump_json()

    session = AgentSession(
        stt=gnani.STT(api_key=settings.gnani_api_key.get_secret_value(),
                      language=options.language_code, sample_rate=16000, use_streaming=True),
        llm=openai.LLM(
            base_url="https://api.groq.com/openai/v1",
            api_key=settings.groq_api_key.get_secret_value(), model=settings.groq_model,
            max_completion_tokens=512,
        ),
        tts=ConversationTTS(api_key=settings.gnani_api_key.get_secret_value(),
                            voice=options.voice, language=options.language_code),
        vad=silero.VAD.load(min_silence_duration=0.35),
        turn_handling={
            "turn_detection": "vad",
            "endpointing": {"min_delay": 0.5, "max_delay": 3.0},
            "interruption": {"enabled": True, "mode": "vad", "min_duration": 0.35,
                             "min_words": 0, "resume_false_interruption": True},
        },
    )

    @session.on("conversation_item_added")
    def record_turn(event):
        item = event.item
        if item.role in {"user", "assistant"} and item.text_content:
            store.append_turn(call_id, item.id, item.role, item.text_content)
    @session.on("close")
    def on_close(_event):
        # Finalize immediately when the user leaves, without waiting for room expiry.
        ctx.shutdown(reason="conversation ended")

    @session.on("error")
    def on_error(event):
        if not event.error.recoverable:
            logging.getLogger(__name__).error("Conversation provider failed; ending session")
            session.shutdown()
            ctx.shutdown(reason="conversation provider failed")

    async def limit_duration():
        await asyncio.sleep(settings.conversation_max_seconds)
        session.shutdown()
        ctx.shutdown(reason="conversation duration limit")

    limit = asyncio.create_task(limit_duration())

    async def cancel_limit():
        limit.cancel()
        await asyncio.gather(limit, return_exceptions=True)

    ctx.add_shutdown_callback(cancel_limit)
    await ctx.connect()
    await ctx.wait_for_participant(identity=identity)
    await session.start(
        room=ctx.room,
        agent=Agent(instructions=(
            "You are OpenCall, a helpful conversational voice assistant. "
            f"Speak in the language identified by {options.language_code}. "
            "Keep responses brief and natural, usually one to three sentences. "
            "Do not use Markdown, lists, or read punctuation aloud. "
            "Listen when interrupted and respond to the user's newest request."
            + memory_instructions(entry)
        ), tools=[lookup_phonebook]),
        room_options=room_io.RoomOptions(
            participant_identity=identity, close_on_disconnect=True,
            audio_input=room_io.AudioInputOptions(sample_rate=16000, num_channels=1),
            video_input=False, text_input=False,
        ),
    )
    session.generate_reply(instructions=(
        "Greet the user briefly in their chosen language and ask how you can help. "
        "If saved context is relevant, acknowledge it naturally without assuming their current intent."
    ))


if __name__ == "__main__":
    cli.run_app(server)
