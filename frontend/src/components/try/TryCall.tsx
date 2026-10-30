"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Room, RoomEvent, Track } from "livekit-client";
import { RoomAudioRenderer, RoomContext, useVoiceAssistant } from "@livekit/components-react";
import { Phone, PhoneOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Conversation } from "./Conversation";
import { Orb } from "./Orb";
import { Phonebook, type PhonebookState } from "./Phonebook";

type Status = "idle" | "connecting" | "active";

function AgentAudio({ onSpeaking, onTrack }: { onSpeaking: () => void; onTrack: (track: MediaStreamTrack | null) => void }) {
  const { state, audioTrack } = useVoiceAssistant();
  const track = audioTrack?.publication.track?.mediaStreamTrack ?? null;
  useEffect(() => { if (state === "speaking") onSpeaking(); }, [state, onSpeaking]);
  useEffect(() => { onTrack(track); return () => onTrack(null); }, [track, onTrack]);
  return <RoomAudioRenderer />;
}

export function TryCall() {
  const [status, setStatus] = useState<Status>("idle");
  const [room, setRoom] = useState<Room | null>(null);
  const [audioStream, setAudioStream] = useState<MediaStream | null>(null);
  const [agentTrack, setAgentTrack] = useState<MediaStreamTrack | null>(null);
  const orbStream = useMemo(() => {
    const tracks = [...(audioStream?.getAudioTracks() ?? []), ...(agentTrack ? [agentTrack] : [])];
    return tracks.length ? new MediaStream(tracks) : null;
  }, [audioStream, agentTrack]);
  const [error, setError] = useState("");
  const [phonebook, setPhonebook] = useState<PhonebookState>({ status: "loading" });
  const active = useRef<Room | null>(null);
  const request = useRef<AbortController | null>(null);
  const generation = useRef(0);
  const busy = useRef(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onSpeaking = useCallback(() => { if (timer.current) clearTimeout(timer.current); setStatus("active"); }, []);

  useEffect(() => {
    let cancelled = false;
    let timeout: ReturnType<typeof setTimeout>;
    async function refresh() {
      try {
        const response = await fetch("/api/conversation/phonebook", { cache: "no-store" });
        if (cancelled) return;
        if (response.status === 401) {
          const guest = await fetch("/api/auth/guest", { method: "POST" });
          if (!guest.ok) throw new Error("Could not create guest session");
          const entry = await fetch("/api/conversation/phonebook", { cache: "no-store" });
          if (!entry.ok) throw new Error("Could not load guest phonebook");
          const data = await entry.json();
          if (!cancelled) setPhonebook(typeof data.username === "string" && typeof data.description === "string"
            ? { status: "ready", username: data.username, description: data.description } : { status: "error" });
        }
        else if (!response.ok) setPhonebook({ status: "error" });
        else {
          const data = await response.json();
          if (!cancelled) setPhonebook(typeof data.username === "string" && typeof data.description === "string"
            ? { status: "ready", username: data.username, description: data.description } : { status: "error" });
        }
      } catch {
        if (!cancelled) setPhonebook({ status: "error" });
      } finally {
        if (!cancelled) timeout = setTimeout(refresh, 3000);
      }
    }
    void refresh();
    return () => { cancelled = true; clearTimeout(timeout); };
  }, []);

  function end() {
    generation.current++;
    request.current?.abort();
    if (timer.current) clearTimeout(timer.current);
    const previous = active.current;
    active.current = null;
    busy.current = false;
    setRoom(null);
    setAudioStream(null);
    setAgentTrack(null);
    setStatus("idle");
    void previous?.disconnect();
  }

  useEffect(() => () => {
    generation.current++;
    request.current?.abort();
    if (timer.current) clearTimeout(timer.current);
    void active.current?.disconnect();
  }, []);

  async function start() {
    if (busy.current || active.current) return;
    busy.current = true;
    const attempt = ++generation.current;
    const controller = new AbortController();
    request.current = controller;
    setError("");
    setStatus("connecting");
    timer.current = setTimeout(() => {
      if (generation.current !== attempt) return;
      end();
      setError("The agent did not respond. Please try again.");
    }, 45000);
    let next: Room | null = null;
    try {
      if (!navigator.mediaDevices?.getUserMedia) throw new Error("Microphone access requires localhost or HTTPS.");
      if (phonebook.status !== "ready") throw new Error("Phonebook is unavailable. Please try again.");
      const response = await fetch("/api/conversation/connect", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ language_code: "en-IN", voice: "Shivani" }), signal: controller.signal,
      });
      const details = await response.json();
      if (!response.ok) throw new Error(typeof details.detail === "string" ? details.detail : "Could not start the call.");
      if (typeof details.server_url !== "string" || typeof details.participant_token !== "string") throw new Error("Invalid connection details.");
      if (generation.current !== attempt) return;
      next = new Room({ adaptiveStream: true, audioCaptureDefaults: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
      active.current = next;
      const currentRoom = next;
      next.on(RoomEvent.Disconnected, () => {
        if (active.current !== currentRoom) return;
        end();
        setError("The call disconnected. Please try again.");
      });
      next.on(RoomEvent.ParticipantDisconnected, participant => {
        if (!participant.isAgent || active.current !== currentRoom) return;
        end();
        setError("The agent disconnected. Please try again.");
      });
      await next.connect(details.server_url, details.participant_token);
      if (generation.current !== attempt) { await next.disconnect(); return; }
      await next.localParticipant.setMicrophoneEnabled(true);
      if (generation.current !== attempt) { await next.disconnect(); return; }
      const microphone = next.localParticipant.getTrackPublication(Track.Source.Microphone)?.track?.mediaStreamTrack;
      if (microphone) setAudioStream(new MediaStream([microphone]));
      await next.startAudio();
      if (generation.current !== attempt) { await next.disconnect(); return; }
      setRoom(next);
    } catch (cause) {
      if (active.current === next) active.current = null;
      await next?.disconnect();
      if (generation.current === attempt) {
        end();
        setError(cause instanceof Error && cause.name === "NotAllowedError" ? "Allow microphone and audio access to start the call." : cause instanceof Error ? cause.message : "Could not start the call.");
      }
    } finally {
      if (generation.current === attempt) busy.current = false;
    }
  }

  return (
    <main className="grid min-h-screen grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] bg-white">
      <Phonebook phonebook={phonebook} />
      <section aria-label="Call" className="relative flex items-center justify-center">
        <Orb audioStream={status === "active" ? orbStream : null} active={status === "active"} />
        {room && <RoomContext.Provider value={room}><AgentAudio onSpeaking={onSpeaking} onTrack={setAgentTrack} /></RoomContext.Provider>}
        <div className="absolute inset-x-0 bottom-10 flex flex-col items-center gap-3">
          <Button type="button" className={`home-pill call-pill ${status === "connecting" ? "call-connecting" : status === "active" ? "call-ending" : ""}`} disabled={status === "connecting"} onClick={status === "active" ? end : start}>
            {status === "connecting" ? <>Connecting <span className="typing-dots" aria-hidden="true"><i /><i /><i /></span></> : status === "active" ? <><PhoneOff aria-hidden="true" /> End call</> : <><Phone aria-hidden="true" /> Call agent</>}
          </Button>
          {error && <p role="alert" className="w-64 text-center text-sm text-red-700">{error}</p>}
        </div>
      </section>
      <Conversation />
    </main>
  );
}
