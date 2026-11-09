"use client";

import { useEffect, useRef, useState } from "react";
import { useRoomContext, useVoiceAssistant } from "@livekit/components-react";
import { ConnectionState, RoomEvent } from "livekit-client";

type Message = { id: string; identity: string; text: string };

function EmptyConversation() {
  return <div>
    <h2 className="text-xs font-semibold uppercase tracking-wider text-[#777]">Agent</h2>
    <p className="mt-2 text-sm leading-6 text-[#999]">Your conversation will appear here.</p>
  </div>;
}

function ConversationContent() {
  const room = useRoomContext();
  const [messages, setMessages] = useState<Message[]>([]);
  const [steps, setSteps] = useState<string[]>([]);
  const [showSteps, setShowSteps] = useState(false);
  const { state } = useVoiceAssistant();
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (state === "thinking") setShowSteps(true);
    if (state === "speaking") { setShowSteps(false); setSteps([]); }
  }, [state]);

  useEffect(() => {
    function onData(payload: Uint8Array, participant: { isAgent: boolean } | undefined, _kind: unknown, topic?: string) {
      if (topic !== "agent_observability" || !participant?.isAgent || payload.length > 4096) return;
      try {
        const event = JSON.parse(new TextDecoder().decode(payload));
        if (event.type !== "agent_step") return;
        const labels: Record<string, string> = {
          phonebook_lookup: event.data?.found ? "Found phonebook details" : "Checked phonebook",
          weather_started: "Checking weather",
          weather_completed: "Weather data received",
          weather_failed: "Weather lookup unavailable",
        };
        const label = labels[event.step];
        if (label) { setShowSteps(true); setSteps(previous => [...previous, label].slice(-12)); }
      } catch { /* Ignore malformed or unrelated messages. */ }
    }
    function announce() {
      void room.localParticipant.publishData(new Uint8Array([1]), { reliable: true, topic: "agent_observability_ready" }).catch(() => {});
    }
    room.on(RoomEvent.DataReceived, onData);
    room.on(RoomEvent.ParticipantConnected, announce);
    announce();
    return () => { room.off(RoomEvent.DataReceived, onData); room.off(RoomEvent.ParticipantConnected, announce); };
  }, [room]);

  useEffect(() => {
    let mounted = true;
    room.registerTextStreamHandler("lk.transcription", async (reader, participant) => {
      const id = reader.info.attributes?.["lk.segment_id"] || reader.info.id;
      let text = "";
      try {
        for await (const chunk of reader) {
          text += chunk;
          if (!mounted) continue;
          if (participant.identity !== room.localParticipant.identity && text.trim()) {
            setShowSteps(false);
            setSteps([]);
          }
          setMessages(previous => {
            const index = previous.findIndex(message => message.id === id && message.identity === participant.identity);
            const message = { id, identity: participant.identity, text };
            if (index < 0) return [...previous, message];
            const next = previous.slice();
            next[index] = message;
            return next;
          });
        }
      } catch (error) {
        if (mounted && room.state !== ConnectionState.Disconnected) {
          console.warn("A transcription stream ended early.", error);
        }
      }
    });
    return () => { mounted = false; room.unregisterTextStreamHandler("lk.transcription"); };
  }, [room]);

  useEffect(() => { bottom.current?.scrollIntoView({ block: "nearest" }); }, [messages]);

  return <div className="space-y-6">
    {messages.length === 0 && <EmptyConversation />}
    {messages.map(message => <div key={`${message.identity}:${message.id}`}>
      <h2 className="text-xs font-semibold uppercase tracking-wider text-[#777]">
        {message.identity === room.localParticipant.identity ? "User" : "Agent"}
      </h2>
      <p className="mt-2 whitespace-pre-wrap break-words text-sm leading-6 text-[#343433]">{message.text}</p>
    </div>)}
    {showSteps && <div>
      <h2 className="text-xs font-semibold uppercase tracking-wider text-[#777]">Agent</h2>
      <p className="agent-processing mt-2 w-fit text-sm" role="status">Processing…</p>
      {steps.length > 0 && <ul className="mt-2 space-y-1 text-xs text-[#999]">{steps.map((step, index) => <li key={`${index}-${step}`}>{step}</li>)}</ul>}
    </div>}
    <div ref={bottom} />
  </div>;
}

export function Conversation({ connected }: { connected: boolean }) {
  return (
    <section aria-label="Conversation" className="relative min-w-0 px-6 text-left">
      <div className="conversation-scroll absolute inset-x-6 bottom-1/2 mx-auto max-h-[calc(50vh-2rem)] w-auto max-w-sm overflow-y-auto" aria-live="polite" aria-relevant="additions text">
        {connected ? <ConversationContent /> : <EmptyConversation />}
      </div>
      <div className="absolute inset-x-6 top-1/2 mx-auto w-auto max-w-sm pt-8">
        <div className="flex h-24 w-full flex-col gap-3 rounded-2xl border border-[#e5e5e5] bg-[#f7f7f7] px-4 py-3">
          <p className="text-xs font-semibold uppercase tracking-wider text-[#777]">Subagents and jobs</p>
          <p className="text-sm text-[#999]">No current jobs</p>
        </div>
      </div>
    </section>
  );
}
