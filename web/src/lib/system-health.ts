/**
 * Truthful runtime API health labels.
 *
 * A successful health probe establishes only API reachability at the time of
 * the request. It does not certify Docker, MinIO, Dagster, sources, or models.
 */
export type ApiHealth = "checking" | "reachable" | "unverified";

export function classifyApiHealth(responseOk: boolean, payload: unknown): ApiHealth {
  if (!responseOk || payload === null || typeof payload !== "object") {
    return "unverified";
  }
  return "status" in payload && payload.status === "ok" ? "reachable" : "unverified";
}

export function apiHealthLabel(state: ApiHealth): string {
  if (state === "checking") return "Vérification API en cours";
  if (state === "reachable") return "API accessible (autres services non vérifiés)";
  return "État API non vérifié";
}
