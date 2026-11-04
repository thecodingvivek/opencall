import { backendUrl } from "@/lib/auth";
import { isSameOrigin } from "@/lib/request-origin";

export async function POST(request: Request, context: { params: Promise<{ action: string }> }) {
  const { action } = await context.params;
  if (!["login", "logout", "guest"].includes(action)) return Response.json({ detail: "Not found" }, { status: 404 });
  if (!isSameOrigin(request)) {
    return Response.json({ detail: "Invalid request origin" }, { status: 403 });
  }
  try {
    const response = await fetch(`${backendUrl}/api/v1/auth/${action}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Cookie: request.headers.get("cookie") || "" },
      body: action === "login" ? await request.text() : undefined,
      cache: "no-store", signal: AbortSignal.timeout(10000),
    });
    const headers = new Headers({ "Cache-Control": "no-store" });
    const cookie = response.headers.get("set-cookie");
    if (cookie) headers.set("Set-Cookie", cookie);
    if (response.headers.has("content-type")) headers.set("Content-Type", response.headers.get("content-type")!);
    return new Response(response.status === 204 ? null : await response.text(), { status: response.status, headers });
  } catch {
    return Response.json({ detail: "Cannot reach the login service. Start the backend and try again." }, { status: 503 });
  }
}
