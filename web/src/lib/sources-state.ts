export function measuredFreshness(days: unknown, stale: unknown): boolean | null {
  return typeof days === "number" && Number.isFinite(days) && days >= 0 && typeof stale === "boolean" ? stale : null;
}

export function freshnessLabel(status: string, stale?: boolean | null): string {
  if (status !== "active") return "Source indisponible";
  if (stale === true) return "Données anciennes";
  if (stale === false) return "Dans le délai suivi";
  return "Fraîcheur non mesurée";
}

export function freshnessSummary(sources: { status: string; isStale?: boolean | null }[]) {
  const measured = sources.filter((s) => s.status === "active" && typeof s.isStale === "boolean");
  const fresh = measured.filter((s) => s.isStale === false).length;
  return { measured: measured.length, fresh, percent: measured.length ? Math.round(fresh / measured.length * 100) : null };
}

export async function recomputeIndicators(url: string) {
  const response = await fetch(url, { method: "POST", credentials: "include" });
  if (!response.ok) {
    if (response.status === 401) throw new Error("Reconnectez-vous pour continuer.");
    if (response.status === 403) throw new Error("Cette action est réservée aux administrateurs.");
    if (response.status === 409) throw new Error("Recalcul déjà en cours ou source indisponible.");
    throw new Error("Recalcul refusé ou interrompu. Aucune collecte ni fraîcheur nouvelle confirmée.");
  }
  const result = await response.json();
  if (result.success !== true || result.action !== "recompute" || result.collection_performed !== false ||
      result.new_records_count !== 0 || !Array.isArray(result.views_refreshed) ||
      result.views_refreshed.some((view: unknown) => typeof view !== "string")) {
    throw new Error("Réponse non confirmée : rechargez le catalogue avant de réessayer.");
  }
  return "Indicateurs recalculés à partir des données existantes. Aucune nouvelle collecte.";
}
