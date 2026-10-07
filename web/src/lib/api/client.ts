import createClient from "openapi-fetch";
import type { paths } from "./schema";

// Determine base URL: inside Docker SSR uses internal API port 8000, browser uses host port 8090
const getBaseUrl = (): string => {
  if (typeof window !== "undefined") {
    return process.env.NEXT_PUBLIC_API_URL || "http://localhost:8090";
  }
  return (
    process.env.INTERNAL_API_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "http://api:8000"
  );
};

export const api = createClient<paths>({
  baseUrl: getBaseUrl(),
  headers: {
    "Content-Type": "application/json",
  },
  credentials: "include",
});

export type ApiPaths = paths;
export type ApiResponse<T extends keyof paths, M extends keyof paths[T]> =
  paths[T][M] extends { responses: { 200: { content: { "application/json": infer R } } } }
    ? R
    : never;
