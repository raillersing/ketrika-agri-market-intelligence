import createClient from "openapi-fetch";
import type { paths } from "./schema";

// Browser credentials stay on the web origin; SSR uses the internal API.
const getBaseUrl = (): string => {
  if (typeof window !== "undefined") {
    return "/api";
  }
  return (
    process.env.API_INTERNAL_URL || process.env.INTERNAL_API_URL ||
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
