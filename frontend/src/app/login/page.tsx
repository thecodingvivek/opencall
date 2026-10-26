"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";

export default function Login() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  async function login(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setPending(true);
    setError("");
    try {
      const response = await fetch("/api/auth/login", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: form.get("username"), password: form.get("password") }),
      });
      if (!response.ok) {
        const result = await response.json();
        throw new Error(typeof result.detail === "string" ? result.detail : "Check your username and password.");
      }
      router.replace("/dashboard");
      router.refresh();
    } catch (error) {
      setError(error instanceof Error ? error.message : "Could not log in. Try again.");
      setPending(false);
    }
  }

  return <main className="grid min-h-screen place-items-center bg-[#f6f8f3] px-6 text-[#29382e]">
    <section className="w-full max-w-sm rounded-3xl border border-[#dfe5d9] bg-[#fffefa] p-8">
      <p className="text-sm font-medium text-[#758078]">OpenCall</p>
      <h1 className="mt-3 text-3xl font-semibold">Welcome back</h1>
      <p className="mt-2 text-sm text-[#758078]">Log in to open your workspace.</p>
      <form onSubmit={login} className="mt-7 space-y-5">
        <label className="block text-sm">Username
          <input name="username" autoComplete="username" required maxLength={100} className="mt-2 w-full rounded-xl border border-[#cadbb6] bg-white px-4 py-3 outline-offset-4" />
        </label>
        <label className="block text-sm">Password
          <input name="password" type="password" autoComplete="current-password" required maxLength={256} className="mt-2 w-full rounded-xl border border-[#cadbb6] bg-white px-4 py-3 outline-offset-4" />
        </label>
        {error && <p role="alert" className="text-sm text-[#91492d]">{error}</p>}
        <button disabled={pending} className="w-full cursor-pointer rounded-xl border border-[#cadbb6] bg-[#d9ee93] px-5 py-3 text-sm font-medium disabled:cursor-wait disabled:opacity-50">{pending ? "Logging in…" : "Log in"}</button>
      </form>
      <p className="mt-6 rounded-xl bg-[#edf2e5] p-3 text-xs leading-6 text-[#586553]">Local demo account<br />Username: <strong>demo</strong><br />Password: <strong>opencall123</strong></p>
    </section>
  </main>;
}
