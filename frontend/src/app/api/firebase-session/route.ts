import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { backendUrl, currentUser } from "@/lib/auth";

const COOKIE = "firebase_session";
const secure = process.env.NODE_ENV === "production";

export async function GET() {
  try {
    const user = await currentUser();
    const response = NextResponse.json({ authenticated: !!user }, { headers: { "Cache-Control": "no-store" } });
    // Drop a stale or revoked cookie so the home page offers sign-in again.
    if (!user && (await cookies()).has(COOKIE)) {
      response.cookies.set(COOKIE, "", { httpOnly: true, secure, sameSite: "lax", path: "/", maxAge: 0 });
    }
    return response;
  } catch (error) {
    console.error("Session check unavailable", error instanceof Error ? error.name : "UnknownError");
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
    // The backend verifies the ID token, mints the session cookie and syncs the account.
    const created = await fetch(`${backendUrl}/api/v1/auth/session`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ idToken }), cache: "no-store", signal: AbortSignal.timeout(15000),
    });
    if (created.status === 401) {
      return NextResponse.json({ error: "Invalid or expired sign-in" }, { status: 401 });
    }
    if (!created.ok) {
      console.error("Session creation unavailable", created.status);
      return NextResponse.json({ error: "Account sync unavailable" }, { status: 503 });
    }
    const data: unknown = await created.json();
    const session = data && typeof data === "object" && "session" in data ? data.session : undefined;
    const expiresIn = data && typeof data === "object" && "expires_in" in data ? data.expires_in : undefined;
    if (typeof session !== "string" || !session || typeof expiresIn !== "number" || expiresIn <= 0) {
      throw new Error("Invalid session response");
    }
    const response = NextResponse.json({ ok: true }, { headers: { "Cache-Control": "no-store" } });
    response.cookies.set(COOKIE, session, { httpOnly: true, secure, sameSite: "lax", path: "/", maxAge: expiresIn });
    return response;
  } catch (error) {
    console.error("Login service unavailable", error instanceof Error ? error.name : "UnknownError");
    return NextResponse.json({ error: "Login service unavailable. Please try again." }, { status: 503 });
  }
}
