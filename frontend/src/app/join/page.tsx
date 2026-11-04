"use client";
import { useEffect, useRef, useState } from "react";
import { Room, RoomEvent } from "livekit-client";
import { RoomAudioRenderer, RoomContext, useVoiceAssistant } from "@livekit/components-react";
import CuelumeSounds from "@/components/CuelumeSounds";
import FooterGradient from "@/components/FooterGradient";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

function AgentStatus() {
  const { state } = useVoiceAssistant();
  return <><RoomAudioRenderer /><p aria-live="polite" className="text-sm text-[#777]">Agent: {state}</p></>;
}

export default function JoinPage() {
  const [code, setCode] = useState("");
  const [room, setRoom] = useState<Room | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const active = useRef<Room | null>(null);
  const joining = useRef(false);
  const generation = useRef(0);
  useEffect(() => () => { generation.current++; void active.current?.disconnect(); }, []);

  async function join(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (joining.current || active.current) return;
    joining.current = true;
    const attempt = ++generation.current;
    setPending(true); setError("");
    let next: Room | null = null;
    let redeemed = false;
    try {
      if (!navigator.mediaDevices?.getUserMedia) throw new Error("Microphone access requires HTTPS.");
      const permission = await navigator.mediaDevices.getUserMedia({ audio: true });
      permission.getTracks().forEach(track => track.stop());
      if (generation.current !== attempt) return;
      const guest = await fetch("/api/auth/guest", { method: "POST" });
      if (!guest.ok) throw new Error("Could not start a session. Please try again.");
      const response = await fetch("/api/conversation/rooms/join", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code, language_code: "en-IN", voice: "Shivani" }),
      });
      const details = await response.json();
      if (!response.ok) throw new Error(typeof details.detail === "string" ? details.detail : "Could not join the room.");
      redeemed = true;
      if (generation.current !== attempt) return;
      next = new Room({ audioCaptureDefaults: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
      active.current = next;
      const current = next;
      next.on(RoomEvent.Disconnected, () => {
        if (active.current !== current) return;
        active.current = null; setRoom(null);
        setError("The call disconnected. Generate a new room code to try again.");
      });
      await next.connect(details.server_url, details.participant_token);
      if (generation.current !== attempt) { await next.disconnect(); return; }
      await next.localParticipant.setMicrophoneEnabled(true);
      await next.startAudio();
      if (generation.current !== attempt) { await next.disconnect(); return; }
      setRoom(next);
    } catch (cause) {
      if (active.current === next) active.current = null;
      await next?.disconnect();
      if (generation.current === attempt) {
        const message = cause instanceof Error && cause.name === "NotAllowedError" ? "Allow microphone access to join the call." : cause instanceof Error ? cause.message : "Could not join the room.";
        setError(redeemed ? `${message} Generate a new room code to try again.` : message);
      }
    } finally {
      if (generation.current === attempt) { joining.current = false; setPending(false); }
    }
  }
  function end() {
    generation.current++;
    const previous = active.current; active.current = null;
    setRoom(null); setCode(""); void previous?.disconnect();
  }
  return <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-white px-6">
    <CuelumeSounds />
    <nav aria-label="Main navigation" className="absolute inset-x-0 top-0 z-10 flex items-center justify-between px-6 py-5">
      <span className="text-base font-medium tracking-tight text-[#171717]">Opencall</span>
      <a href="/get-started" className="home-pill home-pill-quiet nav-back">Back</a>
    </nav>
    <div className="relative z-10 flex w-full max-w-xs -translate-y-[clamp(2rem,8vh,6rem)] flex-col gap-4">
      <h1 className="text-lg font-medium text-[#171717]">{room ? "Connected" : "Join a room"}</h1>
      {room ? <RoomContext.Provider value={room}>
        <AgentStatus />
        <Button type="button" onClick={end} variant="secondary" className="h-10 w-full rounded-full">End call</Button>
      </RoomContext.Provider> : <form onSubmit={join} className="flex flex-col gap-4">
        <label htmlFor="room-number" className="text-sm text-[#343433]">Enter the room code from your laptop</label>
        <Input id="room-number" value={code} onChange={event => setCode(event.target.value.replace(/\D/g, "").slice(0, 8))} inputMode="numeric" autoComplete="off" placeholder="8-digit room code" required pattern="[0-9]{8}" className="h-12 rounded-full border border-[#e2e2e2] bg-white px-5 text-sm" />
        <Button type="submit" disabled={pending || code.length !== 8} variant="secondary" className="h-10 w-full rounded-full">{pending ? "Connecting…" : "Join and talk"}</Button>
      </form>}
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
    </div>
    <FooterGradient />
  </main>;
}
