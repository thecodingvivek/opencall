"use client";
import { useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";

export function RoomCode() {
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  async function createRoom() {
    setPending(true); setError("");
    try {
      const response = await fetch("/api/conversation/rooms", { method: "POST" });
      const result = await response.json();
      if (!response.ok || typeof result.code !== "string") throw new Error("Could not create a room. Please try again.");
      setCode(result.code);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not create a room."); }
    finally { setPending(false); }
  }
  return <div className="w-full space-y-3 rounded-2xl border border-[#e2e2e2] bg-white p-4 text-center">
    <p className="text-sm font-medium text-[#343433]">Talk on your phone</p>
    {code ? <div aria-live="polite">
      <p className="text-xs text-[#777]">Enter this room code on your phone</p>
      <p className="mt-2 text-2xl font-medium tracking-[0.2em] text-[#171717]">{code}</p>
      <p className="mt-2 text-xs text-[#777]">Open this website on your phone and select Join a room. Code expires in 10 minutes.</p>
    </div> : <p className="text-xs text-[#777]">Create a code to connect your phone.</p>}
    <Button type="button" onClick={createRoom} disabled={pending} variant="secondary" className="h-10 w-full rounded-full">{pending ? "Creating…" : code ? "Generate another code" : "Generate room code"}</Button>
    <Link href="/join" className="inline-block text-sm text-[#343433] underline underline-offset-4">Join a room</Link>
    {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
  </div>;
}
