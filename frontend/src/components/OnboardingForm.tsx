"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default function OnboardingForm() {
  const router = useRouter();
  const [phone, setPhone] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(phoneNumber: string | null) {
    setBusy(true);
    setError("");
    try {
      const response = await fetch("/api/auth/onboarding", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone_number: phoneNumber }),
      });
      if (!response.ok) {
        const result = await response.json();
        throw new Error(typeof result.detail === "string" ? result.detail : "Could not save your choice.");
      }
      router.push("/try");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save your choice.");
      setBusy(false);
    }
  }

  return <div className="relative z-10 flex w-full max-w-xs -translate-y-[clamp(2rem,8vh,6rem)] flex-col items-center gap-4">
    <label htmlFor="mobile" className="w-full text-sm text-[#343433]">enter number you want to call with</label>
    <Input id="mobile" name="mobile" type="tel" autoComplete="tel" placeholder="+91…" value={phone} onChange={event => setPhone(event.target.value)} className="h-12 w-full rounded-full border border-[#e2e2e2] bg-white px-5 text-sm" />
    <Button type="button" disabled={busy || !phone.trim()} onClick={() => void submit(phone.trim())} variant="secondary" className="h-10 w-full rounded-full bg-[#f3f3f3] text-[#343433]">CONTINUE</Button>
    <Button type="button" disabled={busy} onClick={() => void submit(null)} variant="secondary" className="h-10 w-full rounded-full bg-[#f3f3f3] text-[#343433]">try without mobile</Button>
    {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
  </div>;
}
