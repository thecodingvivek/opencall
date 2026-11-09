import { backendUrl } from "@/lib/auth";

async function proxy(request: Request, context: { params: Promise<{ path: string[] }> }) {
  const path = (await context.params).path.join("/");
  const allowed = request.method === "POST" ? path === "connect" || path === "guest-connect" :
    request.method === "GET" ? path === "phonebook" || path === "tasks" : path === "phonebook";
  if (!allowed) return Response.json({ detail: "Not found" }, { status: 404 });
  if (request.method !== "GET" && request.headers.get("origin") !== new URL(request.url).origin) {
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
  } catch (error) {
    console.error("Conversation service request failed", path, error instanceof Error ? error.name : "UnknownError");
    return Response.json({ detail: "Cannot reach the conversation service. Check that the backend is running." },
      { status: 503, headers: { "Cache-Control": "no-store" } });
  }
}

export const POST = proxy;
export const GET = proxy;

export const PUT = proxy;
