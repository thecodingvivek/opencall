"use client";

import { getApps, initializeApp } from "firebase/app";
import { getAuth, GoogleAuthProvider, inMemoryPersistence, setPersistence, signInWithPopup, signOut, type Auth } from "firebase/auth";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

const config = {
  apiKey: "AIzaSyARo01cf7wL85vNa1smTbyAwCRPRPeYjTw",
  authDomain: "opencall-62354.firebaseapp.com",
  projectId: "opencall-62354",
  storageBucket: "opencall-62354.firebasestorage.app",
  messagingSenderId: "505673443999",
  appId: "1:505673443999:web:79b3d462b4f149427450aa",
};

export default function GoogleStart() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [authReady, setAuthReady] = useState(false);
  const authRef = useRef<Auth | null>(null);
  const [error, setError] = useState("");
  const [session, setSession] = useState<"checking" | "signed-in" | "signed-out" | "unavailable">("checking");

  useEffect(() => {
    let active = true;
    const auth = getAuth(getApps()[0] ?? initializeApp(config));
    void setPersistence(auth, inMemoryPersistence).then(() => {
      if (active) {
        authRef.current = auth;
        setAuthReady(true);
      }
    }).catch(() => {
      if (active) setError("Could not initialize Google sign-in. Reload and try again.");
    });
    fetch("/api/firebase-session", { cache: "no-store" })
      .then(async response => {
        if (!response.ok) throw new Error("Session check failed");
        return response.json();
      })
      .then(data => { if (active) setSession(data.authenticated ? "signed-in" : "signed-out"); })
      .catch(() => { if (active) setSession("unavailable"); });
    return () => { active = false; };
  }, []);

  async function start() {
    if (session === "signed-in") {
      router.push("/try");
      return;
    }
    const auth = authRef.current;
    if (!auth) return;
    setBusy(true);
    setError("");
    try {
      const result = await signInWithPopup(auth, new GoogleAuthProvider());
      const idToken = await result.user.getIdToken();
      const response = await fetch("/api/firebase-session", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ idToken }),
      });
      if (!response.ok) {
        const message = response.status === 401
          ? "Your Google sign-in expired. Please try again."
          : "Your Google account was verified, but the account service is unavailable. Please try again.";
        throw new Error(message);
      }
      // A failure clearing the temporary client session must not undo a
      // successfully created server session.
      void signOut(auth).catch(() => {});
      router.push("/try");
    } catch (err) {
      const code = err && typeof err === "object" && "code" in err ? err.code : undefined;
      console.error("Google sign-in failed", typeof code === "string" ? code : err instanceof Error ? err.name : "UnknownError");
      const message = code === "auth/popup-blocked" ? "Allow pop-ups for this site and try again."
        : code === "auth/popup-closed-by-user" ? "Google sign-in was closed. Please try again."
        : code === "auth/unauthorized-domain" ? "Google sign-in is not configured for this website address."
        : code === "auth/network-request-failed" ? "Could not reach Google. Check your connection and try again."
        : err instanceof Error && err.message.startsWith("Your Google ") ? err.message
        : "Google sign-in failed. Please try again.";
      setError(message);
      setBusy(false);
    }
  }

  return <div className="flex flex-col items-center gap-2">
    <button type="button" onClick={start} disabled={busy || session === "checking" || (!authReady && session !== "signed-in")} className="home-pill inline-flex items-center gap-2 cursor-pointer disabled:opacity-60" data-cuelume-tap="">
      <svg aria-hidden="true" className="size-4" viewBox="0 0 24 24" fill="none">
        <path fill="#4285F4" d="M23.49 12.27c0-.79-.07-1.55-.2-2.27H12v4.3h6.44a5.5 5.5 0 0 1-2.39 3.61v3h3.87c2.27-2.09 3.57-5.17 3.57-8.64Z" />
        <path fill="#34A853" d="M12 24c3.24 0 5.95-1.07 7.93-2.9l-3.87-3c-1.07.72-2.44 1.15-4.06 1.15-3.13 0-5.79-2.11-6.74-4.95H1.26v3.09A12 12 0 0 0 12 24Z" />
        <path fill="#FBBC05" d="M5.26 14.3A7.2 7.2 0 0 1 4.88 12c0-.8.14-1.57.38-2.3V6.61H1.26A12 12 0 0 0 0 12c0 1.94.46 3.77 1.26 5.39l4-3.09Z" />
        <path fill="#EA4335" d="M12 4.75c1.76 0 3.34.61 4.59 1.81l3.44-3.44C17.95 1.18 15.24 0 12 0A12 12 0 0 0 1.26 6.61l4 3.09C6.21 6.86 8.87 4.75 12 4.75Z" />
      </svg>
      <span>{busy ? "SIGNING IN…" : "GET STARTED"}</span>
    </button>
    {error && <p role="alert" className="text-xs text-red-700">{error}</p>}
  </div>;
}
