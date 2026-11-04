"use client";
import { useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { useRouter } from "next/navigation";

export function RoomCode() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  async function createRoom() {
    setPending(true); setError("");
    try {
      const guest = await fetch("/api/auth/guest", { method: "POST" });
      if (!guest.ok) throw new Error("Could not start a session. Please try again.");
      const response = await fetch("/api/conversation/rooms", { method: "POST" });
      const result = await response.json();
      if (!response.ok || typeof result.code !== "string" || typeof result.server_url !== "string" || typeof result.participant_token !== "string") throw new Error(typeof result.detail === "string" ? result.detail : "Could not create a room. Please try again.");
      sessionStorage.setItem("opencall-phone-room", JSON.stringify(result));
      router.push("/dashboard");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not create a room."); }
    finally { setPending(false); }
  }
  return <div className="w-full space-y-3 rounded-2xl border border-[#e2e2e2] bg-white p-4 text-center">
    <p className="text-sm font-medium text-[#343433]">Talk on your phone</p>
    <p className="text-xs text-[#777]">Create a code to connect your phone.</p>
    <Button type="button" onClick={createRoom} disabled={pending} variant="secondary" className="h-10 w-full rounded-full">{pending ? "Creating…" : "Generate room code"}</Button>
    <Link href="/join" className="inline-block text-sm text-[#343433] underline underline-offset-4">Join a room</Link>
    {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
  </div>;
}
