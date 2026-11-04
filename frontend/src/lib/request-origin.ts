/** Check browser mutations against the public host when behind a reverse proxy. */
export function isSameOrigin(request: Request): boolean {
  const origin = request.headers.get("origin");
  if (!origin) return false;
  try {
    const parsed = new URL(origin);
    if (parsed.origin !== origin || !["http:", "https:"].includes(parsed.protocol)) return false;
    const forwardedHost = request.headers.get("x-forwarded-host")?.split(",")[0].trim();
    const host = forwardedHost || request.headers.get("host");
    const forwardedProto = request.headers.get("x-forwarded-proto")?.split(",")[0].trim();
    const protocol = forwardedProto ? `${forwardedProto}:` : new URL(request.url).protocol;
    return !!host && parsed.host === host.toLowerCase() && parsed.protocol === protocol;
  } catch {
    return false;
  }
}
