import { NextRequest } from "next/server";

export const dynamic = "force-dynamic";

async function proxy(request: NextRequest, context: { params: { path: string[] } }) {
  const parts = context.params.path;
  if (parts[0] !== "v1" || parts.some((part) => part === "." || part === "..")) {
    return Response.json({ detail: "Unknown API path" }, { status: 404 });
  }
  const base = process.env.API_INTERNAL_URL || process.env.INTERNAL_API_URL || "http://api:8000";
  const target = new URL(`/${parts.map(encodeURIComponent).join("/")}`, base);
  target.search = request.nextUrl.search;
  const headers = new Headers();
  for (const name of ["authorization", "cookie", "content-type", "accept", "x-api-key"]) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  try {
    const upstream = await fetch(target, {
      method: request.method,
      headers,
      body: ["GET", "HEAD"].includes(request.method) ? undefined : await request.arrayBuffer(),
      redirect: "manual",
      cache: "no-store",
    });
    const responseHeaders = new Headers();
    for (const name of ["content-type", "content-disposition", "retry-after", "cache-control"]) {
      const value = upstream.headers.get(name);
      if (value) responseHeaders.set(name, value);
    }
    for (const cookie of upstream.headers.getSetCookie()) responseHeaders.append("set-cookie", cookie);
    return new Response(upstream.body, { status: upstream.status, headers: responseHeaders });
  } catch {
    return Response.json(
      { type: "about:blank", title: "Backend unavailable", status: 503 },
      { status: 503, headers: { "content-type": "application/problem+json" } },
    );
  }
}

export { proxy as GET, proxy as HEAD, proxy as POST, proxy as PUT, proxy as PATCH, proxy as DELETE };
