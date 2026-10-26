import "server-only";
import { cookies } from "next/headers";

export const backendUrl = (process.env.API_URL || process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

export async function currentUser(): Promise<{ username: string; display_name: string } | null> {
  const session = (await cookies()).get("opencall_session")?.value;
  if (!session) return null;
  const response = await fetch(`${backendUrl}/api/v1/auth/me`, {
    headers: { Cookie: `opencall_session=${encodeURIComponent(session)}` },
    cache: "no-store", signal: AbortSignal.timeout(5000),
  });
  if (response.status === 401) return null;
  if (!response.ok) throw new Error("Login service is unavailable. Check that the backend is running.");
  return response.json();
}
