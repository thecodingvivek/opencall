"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function Logout() {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  async function logout() {
    setPending(true);
    setError("");
    try {
      const response = await fetch("/api/auth/logout", { method: "POST" });
      if (!response.ok) throw new Error();
      router.replace("/login");
      router.refresh();
    } catch {
      setError("Could not log out. Try again.");
      setPending(false);
    }
  }
  return <div className="text-right">
    <button onClick={logout} disabled={pending} className="cursor-pointer rounded-lg border border-[#cadbb6] px-4 py-2 text-sm disabled:opacity-50">{pending ? "Logging out…" : "Log out"}</button>
    {error && <p role="alert" className="mt-2 text-sm text-[#91492d]">{error}</p>}
  </div>;
}
