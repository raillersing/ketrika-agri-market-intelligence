import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { GET, POST } from "./app/api/[...path]/route";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("same-origin API proxy", () => {
  it("forwards bounded credentials, query and HttpOnly cookies", async () => {
    vi.stubEnv("API_INTERNAL_URL", "http://api:8000");
    const fetchMock = vi.fn().mockResolvedValue(new Response("{\"token\":\"fixture\"}", {
      headers: { "content-type": "application/json", "set-cookie": "session_token=fixture; Path=/; HttpOnly; SameSite=Lax" },
    }));
    vi.stubGlobal("fetch", fetchMock);
    const request = new NextRequest("http://web:3000/api/v1/prices?limit=3", {
      headers: { cookie: "session_token=fixture", authorization: "Bearer fixture", "x-untrusted-instruction": "ignored" },
    });
    const response = await GET(request, { params: { path: ["v1", "prices"] } });
    const [target, options] = fetchMock.mock.calls[0];
    expect(target.toString()).toBe("http://api:8000/v1/prices?limit=3");
    expect(options.headers.get("cookie")).toBe("session_token=fixture");
    expect(options.headers.has("x-untrusted-instruction")).toBe(false);
    expect(options.redirect).toBe("manual");
    expect(response.headers.get("set-cookie")).toContain("HttpOnly");
    expect(response.status).toBe(200);
  });

  it("forwards POST body without changing the API contract", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("{}"));
    vi.stubGlobal("fetch", fetchMock);
    const request = new NextRequest("http://web:3000/api/v1/auth/logout", { method: "POST", body: "{}" });
    await POST(request, { params: { path: ["v1", "auth", "logout"] } });
    const options = fetchMock.mock.calls[0][1];
    expect(options.method).toBe("POST");
    expect(new TextDecoder().decode(options.body)).toBe("{}");
  });

  it.each([["v2", "prices"], ["v1", ".."]])("refuses out-of-scope path %j", async (...parts) => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const result = await GET(new NextRequest("http://web:3000/api/v1/prices"), { params: { path: parts } });
    expect(result.status).toBe(404);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("returns non-success when the backend is unavailable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("unavailable")));
    const result = await GET(new NextRequest("http://web:3000/api/v1/prices"), { params: { path: ["v1", "prices"] } });
    expect(result.status).toBe(503);
    expect(result.headers.get("content-type")).toContain("application/problem+json");
  });
});
