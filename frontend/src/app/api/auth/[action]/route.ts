import { backendUrl } from "@/lib/auth";

export async function POST(request: Request, context: { params: Promise<{ action: string }> }) {
  const { action } = await context.params;
  if (!["logout", "onboarding"].includes(action)) return Response.json({ detail: "Not found" }, { status: 404 });
  if (request.headers.get("origin") !== new URL(request.url).origin) {
    return Response.json({ detail: "Invalid request origin" }, { status: 403 });
  }
  if (action === "logout") {
    const response = new Response(null, { status: 204, headers: { "Cache-Control": "no-store" } });
    response.headers.append("Set-Cookie", `firebase_session=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0${process.env.NODE_ENV === "production" ? "; Secure" : ""}`);
    return response;
  }
  try {
    const response = await fetch(`${backendUrl}/api/v1/auth/${action}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Cookie: request.headers.get("cookie") || "" },
      body: await request.text(),
      cache: "no-store", signal: AbortSignal.timeout(10000),
    });
    const headers = new Headers({ "Cache-Control": "no-store" });
    const cookie = response.headers.get("set-cookie");
    if (cookie) headers.set("Set-Cookie", cookie);
    if (response.headers.has("content-type")) headers.set("Content-Type", response.headers.get("content-type")!);
    return new Response(response.status === 204 ? null : await response.text(), { status: response.status, headers });
  } catch (error) {
    console.error("Account service request failed", action, error instanceof Error ? error.name : "UnknownError");
    return Response.json({ detail: "Cannot reach the login service. Start the backend and try again." }, { status: 503 });
  }
}
