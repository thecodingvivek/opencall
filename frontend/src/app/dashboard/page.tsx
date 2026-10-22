"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Room, RoomEvent } from "livekit-client";
import {
  RoomContext, RoomAudioRenderer, useVoiceAssistant, useTranscriptions,
  useLocalParticipant, useRoomContext, useConnectionState,
} from "@livekit/components-react";

const languages = [["en-IN", "English (India)"], ["hi-IN", "Hindi"], ["te-IN", "Telugu"],
  ["ta-IN", "Tamil"], ["kn-IN", "Kannada"], ["ml-IN", "Malayalam"],
  ["mr-IN", "Marathi"], ["gu-IN", "Gujarati"], ["bn-IN", "Bengali"], ["pa-IN", "Punjabi"]];
const voices = ["Shivani", "Avinash", "Lakshmi", "Kalpana", "Chetana", "Vasudha", "Riyaa",
  "Tarika", "Shubham", "Prakash", "Devansh", "Yashraj", "Harshad"];
const button = "cursor-pointer rounded-xl border border-[#cadbb6] bg-[#d9ee93] px-5 py-3 text-sm font-medium disabled:cursor-default disabled:opacity-50";

function ActiveConversation({ end }: { end: () => void }) {
  const room = useRoomContext();
  const { agent, state } = useVoiceAssistant();
  const connection = useConnectionState();
  const { localParticipant, isMicrophoneEnabled } = useLocalParticipant();
  const messages = useTranscriptions();
  const [issue, setIssue] = useState("");
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => { bottom.current?.scrollIntoView({ behavior: "smooth", block: "nearest" }); }, [messages]);
  useEffect(() => {
    if (agent) return;
    const timeout = setTimeout(() => setIssue("The voice assistant hasn’t joined. End the session and check that the agent worker is running."), 30000);
    return () => clearTimeout(timeout);
  }, [agent]);
  useEffect(() => {
    const failed = () => setIssue("Your microphone was interrupted. Check its browser permission and try unmuting.");
    const playback = () => { if (!room.canPlaybackAudio) setIssue("Audio playback needs your permission. Click Enable audio."); };
    room.on(RoomEvent.MediaDevicesError, failed).on(RoomEvent.AudioPlaybackStatusChanged, playback);
    return () => { room.off(RoomEvent.MediaDevicesError, failed).off(RoomEvent.AudioPlaybackStatusChanged, playback); };
  }, [room]);

  async function toggleMicrophone() {
    try { await localParticipant.setMicrophoneEnabled(!isMicrophoneEnabled); setIssue(""); }
    catch { setIssue("Cannot access the microphone. Check browser permissions."); }
  }
  async function enableAudio() {
    try { await room.startAudio(); setIssue(""); }
    catch { setIssue("Audio is still blocked. Allow sound for this site and try again."); }
  }
  const label = connection === "reconnecting" || connection === "signalReconnecting" ? "Reconnecting…"
    : !agent ? "Connecting your assistant…" : !isMicrophoneEnabled ? "Microphone muted"
    : state === "speaking" ? "Speaking — you can interrupt" : state === "thinking" ? "Thinking…"
    : state === "listening" ? "Listening to you" : "Getting ready…";

  return <>
    <RoomAudioRenderer />
    <section className="rounded-3xl border border-[#dfe5d9] bg-[#fffefa] p-7 text-center">
      <div className={`mx-auto my-6 grid size-28 place-items-center rounded-full bg-[#e4edcd] text-4xl motion-reduce:animate-none ${state === "speaking" || state === "listening" ? "animate-pulse" : ""}`} aria-hidden="true">◎</div>
      <p role="status" className="text-xl font-medium">{label}</p>
      <p className="mx-auto mt-3 max-w-md text-sm leading-6 text-[#758078]">Keep talking naturally. Pause for a reply, or speak while the assistant talks to interrupt it.</p>
      <div className="mt-7 flex flex-wrap justify-center gap-3">
        <button className={button} onClick={toggleMicrophone} disabled={connection !== "connected"}>{isMicrophoneEnabled ? "Mute microphone" : "Unmute microphone"}</button>
        <button className="cursor-pointer rounded-xl border border-[#e7c8b5] bg-[#f1e0d5] px-5 py-3 text-sm" onClick={end}>End conversation</button>
        <button className="cursor-pointer rounded-xl border border-[#dfe5d9] px-4 py-3 text-sm" onClick={enableAudio}>Enable audio</button>
      </div>
      {issue && <p className="mt-5 text-sm text-[#91492d]" role="alert">{issue}</p>}
    </section>
    <section className="mt-6 rounded-3xl border border-[#dfe5d9] bg-white p-6" aria-label="Conversation transcript">
      <h2 className="font-medium">Your conversation</h2>
      <div className="mt-5 max-h-[440px] min-h-36 space-y-4 overflow-y-auto" aria-live="polite" aria-relevant="additions text">
        {messages.length === 0 && <p className="text-sm text-[#758078]">Your words and the assistant’s replies will appear here.</p>}
        {messages.map(message => <div key={message.streamInfo.id} className={`max-w-[90%] rounded-2xl p-4 ${message.participantInfo.identity === room.localParticipant.identity ? "ml-auto bg-[#edf2e5]" : "bg-[#f6f8f3]"}`}>
          <span className="mb-1 block text-[10px] uppercase tracking-widest text-[#758078]">{message.participantInfo.identity === room.localParticipant.identity ? "You" : "OpenCall"}</span>
          <p className="whitespace-pre-wrap text-sm leading-7 [overflow-wrap:anywhere]">{message.text}</p>
        </div>)}
        <div ref={bottom} />
      </div>
    </section>
  </>;
}

export default function Dashboard() {
  const [language, setLanguage] = useState("en-IN");
  const [voice, setVoice] = useState("Shivani");
  const [room, setRoom] = useState<Room | null>(null);
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState("");
  const active = useRef<Room | null>(null);
  const request = useRef<AbortController | null>(null);
  const generation = useRef(0);
  const busy = useRef(false);

  useEffect(() => () => {
    generation.current++;
    request.current?.abort();
    void active.current?.disconnect();
    active.current = null;
  }, []);

  function end() {
    generation.current++;
    busy.current = false;
    request.current?.abort();
    const previous = active.current;
    active.current = null;
    void previous?.disconnect();
    setRoom(null);
    setConnecting(false);
  }

  async function start() {
    if (busy.current || active.current) return;
    busy.current = true;
    const attempt = ++generation.current;
    setError(""); setConnecting(true);
    const controller = new AbortController();
    request.current = controller;
    const timeout = setTimeout(() => controller.abort(), 15000);
    let next: Room | null = null;
    try {
      if (!navigator.mediaDevices?.getUserMedia) throw new Error("Use localhost or HTTPS with a supported browser to access your microphone.");
      const api = (process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
      const response = await fetch(`${api}/api/v1/conversation/connect`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ language_code: language, voice }), signal: controller.signal,
      });
      const details = await response.json();
      if (!response.ok) throw new Error(typeof details.detail === "string" ? details.detail : "Could not create a conversation.");
      if (typeof details.server_url !== "string" || typeof details.participant_token !== "string") throw new Error("Invalid conversation connection details.");
      if (attempt !== generation.current) return;
      next = new Room({ adaptiveStream: true, audioCaptureDefaults: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
      active.current = next;
      setRoom(next);
      const connectedRoom = next;
      next.on(RoomEvent.Disconnected, () => {
        if (active.current !== connectedRoom) return;
        active.current = null; busy.current = false; generation.current++;
        setRoom(null); setConnecting(false);
        setError("The conversation ended. You can start a new one.");
      });
      next.on(RoomEvent.ParticipantDisconnected, participant => {
        if (!participant.isAgent || active.current !== connectedRoom) return;
        end();
        setError("The assistant disconnected. Start a new conversation to reconnect.");
      });
      await next.connect(details.server_url, details.participant_token);
      if (attempt !== generation.current) { await next.disconnect(); return; }
      await next.localParticipant.setMicrophoneEnabled(true);
      if (attempt !== generation.current) {
        await next.localParticipant.setMicrophoneEnabled(false); await next.disconnect(); return;
      }
      await next.startAudio().catch(() => { /* Enable audio remains available. */ });
      setConnecting(false);
    } catch (cause) {
      if (active.current === next) active.current = null;
      await next?.disconnect();
      if (attempt === generation.current) {
        setRoom(null); setConnecting(false);
        setError(cause instanceof Error && cause.name === "NotAllowedError" ? "Microphone access was denied. Allow it in your browser settings, then try again."
          : cause instanceof Error && cause.name === "AbortError" ? "Connection timed out. Check that the backend is running."
          : cause instanceof Error ? cause.message : "Could not connect to the conversation.");
      }
    } finally {
      clearTimeout(timeout);
      if (attempt === generation.current) busy.current = false;
    }
  }

  return <main className="min-h-screen bg-[#f6f8f3] px-5 py-8 font-sans text-[#21372d] sm:px-10">
    <div className="mx-auto max-w-4xl">
      <header className="mb-12 flex flex-wrap items-center justify-between gap-4"><Link className="text-2xl font-semibold tracking-tight" href="/">◉ opencall</Link><a href="/dashboard/transcribe" className="text-xs text-[#65785c] underline underline-offset-4">Recording & transcription studio ↗</a></header>
      <p className="text-[10px] tracking-[2px] text-[#65785c]">VOICE CONVERSATION</p>
      <h1 className="mt-4 text-4xl font-medium tracking-tight sm:text-5xl">A conversation that flows.</h1>
      <p className="mt-4 mb-8 max-w-xl text-sm leading-7 text-[#758078]">Start once, then speak freely. Your assistant listens, replies out loud, and makes room when you have something to say.</p>
      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
        <label className="text-xs text-[#65785c]">Speaking language<select className="mt-2 block w-full rounded-xl border border-[#dfe5d9] bg-white p-3 text-sm disabled:opacity-60" value={language} onChange={event => setLanguage(event.target.value)} disabled={!!room || connecting}>{languages.map(([code, name]) => <option value={code} key={code}>{name}</option>)}</select></label>
        <label className="text-xs text-[#65785c]">Assistant voice<select className="mt-2 block w-full rounded-xl border border-[#dfe5d9] bg-white p-3 text-sm disabled:opacity-60" value={voice} onChange={event => setVoice(event.target.value)} disabled={!!room || connecting}>{voices.map(name => <option key={name}>{name}</option>)}</select></label>
      </div>
      {room ? <RoomContext.Provider value={room}><ActiveConversation end={end} /></RoomContext.Provider> : <section className="rounded-3xl border border-[#dfe5d9] bg-[#fffefa] p-8 text-center sm:p-14">
        <div className="mx-auto mb-6 grid size-24 place-items-center rounded-full bg-[#e4edcd] text-4xl" aria-hidden="true">◎</div>
        <h2 className="text-xl font-medium">Ready when you are.</h2>
        <p className="mt-3 mb-7 text-sm text-[#758078]">Your microphone stays open until you mute it or end the conversation.</p>
        <button className={button} disabled={connecting} onClick={start}>{connecting ? "Connecting…" : "Start conversation"}</button>
        {connecting && <button className="ml-4 cursor-pointer text-sm underline" onClick={end}>Cancel</button>}
      </section>}
      {error && <p className="mt-5 rounded-xl border border-[#edc7b5] bg-[#fff0e8] p-4 text-sm text-[#91492d]" role="alert">{error}</p>}
      <p className="mt-6 text-center text-xs leading-6 text-[#758078]">Use headphones for the clearest conversation. Audio is sent to the speech providers while connected. Transcripts stay in this tab.</p>
    </div>
  </main>;
}
