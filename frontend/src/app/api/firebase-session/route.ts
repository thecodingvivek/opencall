import { getAuth } from "firebase-admin/auth";
import { NextResponse } from "next/server";
import { getFirebaseAdminApp } from "@/lib/firebase-admin";
import { backendUrl, currentUser } from "@/lib/auth";

export async function GET() {
  try {
    const user = await currentUser();
    return NextResponse.json({ authenticated: !!user }, { headers: { "Cache-Control": "no-store" } });
  } catch {
    return NextResponse.json({ error: "Login service unavailable" }, { status: 503, headers: { "Cache-Control": "no-store" } });
  }
}

export async function POST(request: Request) {
  if (request.headers.get("origin") !== new URL(request.url).origin) {
    return NextResponse.json({ error: "Invalid request origin" }, { status: 403 });
  }
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid request body" }, { status: 400 });
  }
  const idToken = body && typeof body === "object" && "idToken" in body ? body.idToken : undefined;
  if (typeof idToken !== "string" || !idToken || idToken.length > 16384) {
      return NextResponse.json({ error: "Invalid token" }, { status: 400 });
  }
  try {
    const auth = getAuth(getFirebaseAdminApp());
    const decoded = await auth.verifyIdToken(idToken);
    if (Date.now() / 1000 - decoded.auth_time > 300) {
      return NextResponse.json({ error: "Recent sign-in required" }, { status: 401 });
    }
    const expiresIn = 5 * 24 * 60 * 60 * 1000;
    const session = await auth.createSessionCookie(idToken, { expiresIn });
    const synced = await fetch(`${backendUrl}/api/v1/auth/me`, {
      headers: { Cookie: `firebase_session=${encodeURIComponent(session)}` },
      cache: "no-store", signal: AbortSignal.timeout(15000),
    });
    if (!synced.ok) return NextResponse.json({ error: "Account sync unavailable" }, { status: 503 });
    const response = NextResponse.json({ ok: true }, { headers: { "Cache-Control": "no-store" } });
    response.cookies.set("firebase_session", session, {
      httpOnly: true, secure: process.env.NODE_ENV === "production", sameSite: "lax", path: "/", maxAge: expiresIn / 1000,
    });
    return response;
  } catch (error) {
    const code = error && typeof error === "object" && "code" in error ? error.code : undefined;
    if (typeof code === "string" && ["auth/argument-error", "auth/invalid-id-token", "auth/id-token-expired", "auth/id-token-revoked"].includes(code)) {
      return NextResponse.json({ error: "Invalid or expired sign-in" }, { status: 401 });
    }
    console.error("Firebase session service unavailable", error instanceof Error ? error.name : "UnknownError");
    return NextResponse.json({ error: "Login service unavailable. Please try again." }, { status: 503 });
  }
}
