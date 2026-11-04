import { backendUrl } from "@/lib/auth";
import { isSameOrigin } from "@/lib/request-origin";

async function proxy(request: Request, context: { params: Promise<{ path: string[] }> }) {
  const path = (await context.params).path.join("/");
  const allowed = request.method === "POST" ? ["connect", "guest-connect", "rooms", "rooms/join"].includes(path) : path === "phonebook";
  if (!allowed) return Response.json({ detail: "Not found" }, { status: 404 });
  if (request.method !== "GET" && !isSameOrigin(request)) {
    return Response.json({ detail: "Invalid request origin" }, { status: 403 });
  }
  try {
    const response = await fetch(`${backendUrl}/api/v1/conversation/${path}`, {
      method: request.method,
      headers: { "Content-Type": "application/json", Cookie: request.headers.get("cookie") || "" },
      body: request.method !== "GET" ? await request.text() : undefined,
      cache: "no-store", signal: AbortSignal.timeout(10000),
    });
    return new Response(await response.text(), {
      status: response.status,
      headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
    });
  } catch {
    return Response.json({ detail: "Cannot reach the conversation service. Check that the backend is running." },
      { status: 503, headers: { "Cache-Control": "no-store" } });
  }
}

export const POST = proxy;
export const GET = proxy;

export const PUT = proxy;
