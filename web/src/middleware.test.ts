import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { middleware } from "./middleware";

const request = (path: string, token?: string) => new NextRequest(`http://web:3000${path}`, { headers: token ? { Cookie: `session_token=${token}` } : {} });
afterEach(() => vi.unstubAllGlobals());
describe("server-validated web sessions", () => {
  it("serves only the exact public About paths without checking a session", async () => {
    const fetcher = vi.fn(); vi.stubGlobal("fetch", fetcher);
    for (const path of ["/about", "/about/"]) {
      for (const token of [undefined, "arbitrary"]) {
        expect((await middleware(request(path, token))).headers.get("x-middleware-next")).toBe("1");
      }
    }
    expect(fetcher).not.toHaveBeenCalled();
  });
  it("does not make About prefixes, subroutes or business data public", async () => {
    const fetcher = vi.fn(); vi.stubGlobal("fetch", fetcher);
    for (const path of ["/about.csv", "/about/private", "/about-other", "/prices"]) {
      const response = await middleware(request(path));
      expect(response.status).toBe(307);
      expect(response.headers.get("location")).toContain("/login");
    }
    expect(fetcher).not.toHaveBeenCalled();
  });
  it("redirects anonymous business pages, including a path containing a dot", async () => {
    const fetcher = vi.fn(); vi.stubGlobal("fetch", fetcher);
    const response = await middleware(request("/prices.csv"));
    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toContain("/login");
    expect(fetcher).not.toHaveBeenCalled();
  });
  it("rejects an arbitrary cookie and clears it without a login loop", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("", { status: 401 })));
    const response = await middleware(request("/prices", "arbitrary"));
    expect(response.status).toBe(307);
    expect(response.headers.get("set-cookie")).toContain("session_token=;");
    const login = await middleware(request("/login", "arbitrary"));
    expect(login.headers.get("location")).toBeNull();
  });
  it("uses the upstream session check without caching or redirects", async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", fetcher);
    const response = await middleware(request("/prices", "signed-test"));
    expect(response.headers.get("x-middleware-next")).toBe("1");
    const options = fetcher.mock.calls[0][1];
    expect(options.cache).toBe("no-store"); expect(options.redirect).toBe("error");
    expect(options.headers.Cookie).toBe("session_token=signed-test");
  });
  it("fails closed on storage/backend outage while leaving login usable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("", { status: 503 })));
    expect((await middleware(request("/prices", "signed-test"))).status).toBe(503);
    expect((await middleware(request("/login", "signed-test"))).headers.get("x-middleware-next")).toBe("1");
  });
  it("keeps proxy and framework assets on their server paths", async () => {
    const fetcher = vi.fn(); vi.stubGlobal("fetch", fetcher);
    for (const path of ["/_next/static/chunk.js", "/api/v1/auth/login", "/favicon.ico"]) {
      expect((await middleware(request(path))).headers.get("x-middleware-next")).toBe("1");
    }
    expect(fetcher).not.toHaveBeenCalled();
  });
});
