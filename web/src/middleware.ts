import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/** The server owns session validity; a cookie value alone never grants access. */
export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  if (pathname.startsWith("/_next/") || pathname.startsWith("/api/") || pathname === "/favicon.ico" || pathname === "/about" || pathname === "/about/") {
    return NextResponse.next();
  }
  const token = request.cookies.get("session_token")?.value;
  const isLogin = pathname === "/login";
  const login = () => {
    const url = new URL("/login", request.url);
    if (!isLogin) url.searchParams.set("from", pathname + request.nextUrl.search);
    const response = isLogin ? NextResponse.next() : NextResponse.redirect(url);
    response.cookies.delete("session_token");
    response.cookies.delete("ketrika_token");
    return response;
  };
  if (!token) return isLogin ? NextResponse.next() : login();

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 5000);
  try {
    const upstream = await fetch(new URL("/v1/auth/me", process.env.API_INTERNAL_URL || "http://api:8000"), {
      headers: { Cookie: `session_token=${token}` },
      cache: "no-store", redirect: "error", signal: controller.signal,
    });
    if (upstream.status === 401 || upstream.status === 403) return login();
    if (!upstream.ok) throw new Error("Session service unavailable");
    return isLogin ? NextResponse.redirect(new URL("/", request.url)) : NextResponse.next();
  } catch {
    // Keep the login form usable; fail closed on business pages during an outage.
    return isLogin ? NextResponse.next() : NextResponse.json({ detail: "Vérification de session indisponible. Réessayez dans un instant." }, { status: 503 });
  } finally {
    clearTimeout(timeout);
  }
}

export const config = { matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"] };
