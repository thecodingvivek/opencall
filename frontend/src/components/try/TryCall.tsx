"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Room, RoomEvent, Track } from "livekit-client";
import { RoomAudioRenderer, RoomContext, useVoiceAssistant } from "@livekit/components-react";
import { Phone, PhoneOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Conversation } from "./Conversation";
import { Orb } from "./Orb";
import { Phonebook, type PhonebookState } from "./Phonebook";
import { PhoneScreen } from "./PhoneScreen";
import { voices } from "./voices";
import FooterGradient from "../FooterGradient";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";

type Status = "idle" | "connecting" | "active";

function AgentAudio({ onSpeaking, onTrack }: { onSpeaking: () => void; onTrack: (track: MediaStreamTrack | null) => void }) {
  const { state, audioTrack } = useVoiceAssistant();
  const track = audioTrack?.publication.track?.mediaStreamTrack ?? null;
  useEffect(() => { if (state === "speaking") onSpeaking(); }, [state, onSpeaking]);
  useEffect(() => { onTrack(track); return () => onTrack(null); }, [track, onTrack]);
  return <RoomAudioRenderer />;
}

export function TryCall() {
  const reducedMotion = useReducedMotion();
  const [status, setStatus] = useState<Status>("idle");
  const [voice, setVoice] = useState("Shivani");
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
        body: JSON.stringify({ language_code: "en-IN", voice }), signal: controller.signal,
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
    <main className="relative grid min-h-screen grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] overflow-hidden bg-white">
      <FooterGradient />
      <motion.div aria-hidden="true" className="pointer-events-none absolute bottom-0 left-1/2 z-10 w-[min(70vw,320px)] -translate-x-1/2"
        initial={false}
        animate={{ y: status === "idle" ? "100%" : "30%" }}
        transition={reducedMotion ? { duration: 0 } : { duration: 0.8, ease: [0.22, 1, 0.36, 1] }}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/test.svg" alt="" className="block h-auto w-full" />
        <PhoneScreen status={status} />
      </motion.div>
      <nav aria-label="Main navigation" className="absolute inset-x-0 top-0 z-10 flex items-center justify-between px-6 py-5">
        <span className="text-base font-medium tracking-tight text-[#171717]">Opencall</span>
        <a href="/get-started" className="home-pill home-pill-quiet nav-back">Back</a>
      </nav>
      <Phonebook phonebook={phonebook} />
      <section aria-label="Call" className="relative flex items-center justify-center">
        <label className="absolute bottom-[calc(50%+105px)] left-1/2 z-10 flex -translate-x-1/2 flex-col items-center gap-2 text-xs font-medium text-[#777]">
          Voice
          <select aria-label="Agent voice" value={voice} onChange={event => setVoice(event.target.value)} disabled={status !== "idle"} className="rounded-full border border-[#e2e2e2] bg-white px-4 py-2 text-sm text-[#343433] outline-offset-2 disabled:opacity-50">
            {voices.map(option => <option key={option.name} value={option.name}>{option.name}</option>)}
          </select>
        </label>
        <Orb audioStream={status === "active" ? orbStream : null} active={status === "active"} colors={(voices.find(option => option.name === voice) ?? voices[0]).colors} />
        {room && <RoomContext.Provider value={room}><AgentAudio onSpeaking={onSpeaking} onTrack={setAgentTrack} /></RoomContext.Provider>}
        <div className="absolute inset-x-0 bottom-10 z-20 flex flex-col items-center gap-3">
          <AnimatePresence mode="wait" initial={false}>
          <motion.div key={status === "idle" ? "start" : "call"}
            initial={reducedMotion ? false : { y: 80, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={reducedMotion ? { opacity: 0 } : { y: 100, opacity: 0 }}
            transition={reducedMotion ? { duration: 0 } : { duration: 0.4, ease: [0.22, 1, 0.36, 1] }}>
          <Button type="button" className={`home-pill call-pill ${status === "connecting" ? "call-connecting" : status === "active" ? "call-ending" : ""}`} disabled={status === "connecting"} onClick={status === "active" ? end : start}>
            {status === "connecting" ? <>Connecting <span className="typing-dots" aria-hidden="true"><i /><i /><i /></span></> : status === "active" ? <><PhoneOff aria-hidden="true" /> End call</> : <><Phone aria-hidden="true" /> Call agent</>}
          </Button>
          </motion.div>
          </AnimatePresence>
          {error && <p role="alert" className="w-64 text-center text-sm text-red-700">{error}</p>}
        </div>
      </section>
      {room ? <RoomContext.Provider value={room}><Conversation connected /></RoomContext.Provider> : <Conversation connected={false} />}
    </main>
  );
}
