/** Accept a same-origin app path; this base is a non-network parsing sentinel. */
export function safeLoginTarget(value: string | null): string {
  if (!value?.startsWith("/") || /[\\\u0000-\u001f\u007f]/.test(value)) return "/";
  try {
    const base = "https://example.invalid";
    const target = new URL(value, base);
    const path = decodeURIComponent(target.pathname);
    const decoded = decodeURIComponent(value);
    if (target.origin !== base || path.startsWith("//") || /[\\\u0000-\u001f\u007f]/.test(decoded) || path === "/login" || path.startsWith("/login/")) return "/";
    return target.pathname + target.search + target.hash;
  } catch {
    return "/";
  }
}
