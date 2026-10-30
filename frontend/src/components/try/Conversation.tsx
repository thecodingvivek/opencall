"use client";

import { useEffect, useRef, useState } from "react";
import { useRoomContext } from "@livekit/components-react";
import { ConnectionState } from "livekit-client";

type Message = { id: string; identity: string; text: string };

function ConversationContent() {
  const room = useRoomContext();
  const [messages, setMessages] = useState<Message[]>([]);
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let mounted = true;
    room.registerTextStreamHandler("lk.transcription", async (reader, participant) => {
      const id = reader.info.attributes?.["lk.segment_id"] || reader.info.id;
      let text = "";
      try {
        for await (const chunk of reader) {
          text += chunk;
          if (!mounted) continue;
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
    {messages.length === 0 && <p className="text-sm text-[#999]">Your conversation will appear here.</p>}
    {messages.map(message => <div key={`${message.identity}:${message.id}`}>
      <h2 className="text-xs font-semibold uppercase tracking-wider text-[#777]">
        {message.identity === room.localParticipant.identity ? "User" : "Agent"}
      </h2>
      <p className="mt-2 whitespace-pre-wrap break-words text-sm leading-6 text-[#343433]">{message.text}</p>
    </div>)}
    <div ref={bottom} />
  </div>;
}

export function Conversation({ connected }: { connected: boolean }) {
  return <section aria-label="Conversation" className="relative min-w-0 px-6 text-left">
    <div className="absolute inset-x-6 bottom-1/2 mx-auto max-h-[calc(50vh-2rem)] w-auto max-w-sm overflow-y-auto" aria-live="polite" aria-relevant="additions text">
      {connected ? <ConversationContent /> : <p className="text-sm text-[#999]">Your conversation will appear here.</p>}
    </div>
  </section>;
}
