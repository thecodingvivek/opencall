import { getAuth } from "firebase-admin/auth";
import { NextResponse } from "next/server";
import { getFirebaseAdminApp } from "@/lib/firebase-admin";

export async function POST(request: Request) {
  if (request.headers.get("origin") !== new URL(request.url).origin) {
    return NextResponse.json({ error: "Invalid request origin" }, { status: 403 });
  }
  try {
    const { idToken } = await request.json();
    if (typeof idToken !== "string" || idToken.length > 16384) {
      return NextResponse.json({ error: "Invalid token" }, { status: 400 });
    }
    const auth = getAuth(getFirebaseAdminApp());
    const decoded = await auth.verifyIdToken(idToken);
    if (Date.now() / 1000 - decoded.auth_time > 300) {
      return NextResponse.json({ error: "Recent sign-in required" }, { status: 401 });
    }
    const expiresIn = 5 * 24 * 60 * 60 * 1000;
    const session = await auth.createSessionCookie(idToken, { expiresIn });
    const response = NextResponse.json({ ok: true }, { headers: { "Cache-Control": "no-store" } });
    response.cookies.set("firebase_session", session, {
      httpOnly: true, secure: process.env.NODE_ENV === "production", sameSite: "lax", path: "/", maxAge: expiresIn / 1000,
    });
    return response;
  } catch (error) {
    console.error("Firebase session creation failed", error);
    return NextResponse.json({ error: "Could not create session" }, { status: 401 });
  }
}
