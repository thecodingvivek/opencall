import { describe, expect, test } from "bun:test";
import { isSameOrigin } from "../src/lib/request-origin";

describe("request origin", () => {
  test("accepts local and forwarded public origins", () => {
    expect(isSameOrigin(new Request("http://localhost:3000/api", {
      headers: { host: "localhost:3000", origin: "http://localhost:3000" },
    }))).toBe(true);
    expect(isSameOrigin(new Request("http://localhost:3000/api", {
      headers: { host: "localhost:3000", "x-forwarded-host": "example.ngrok-free.app", "x-forwarded-proto": "https", origin: "https://example.ngrok-free.app" },
    }))).toBe(true);
  });
  test("rejects foreign, missing and wrong-scheme origins", () => {
    const headers = { host: "localhost:3000", "x-forwarded-host": "example.ngrok-free.app", "x-forwarded-proto": "https" };
    for (const origin of ["https://attacker.example", "http://example.ngrok-free.app", "null"]) {
      expect(isSameOrigin(new Request("http://localhost:3000/api", { headers: { ...headers, origin } }))).toBe(false);
    }
    expect(isSameOrigin(new Request("http://localhost:3000/api", { headers }))).toBe(false);
  });
});
