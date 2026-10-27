export function escapeHtml(value: string): string {
  const entities: Record<string, string> = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
  return value.replace(/[&<>"']/g, character => entities[character]);
}

export function humanDate(value: string | null | undefined): string {
  if (!value) return "Date non renseignée";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Date non renseignée" : new Intl.DateTimeFormat("fr-FR", { dateStyle: "medium", timeZone: "Indian/Antananarivo" }).format(date);
}
export function alertSeverityLabel(value: string): string {
  return ({ high: "Priorité élevée", medium: "À surveiller", low: "Information" } as Record<string, string>)[value] || "Niveau non renseigné";
}
export function alertStateLabel(value: string): string {
  return ({ open: "À examiner", acknowledged: "Prise en compte", resolved: "Résolue" } as Record<string, string>)[value] || "État non reconnu";
}
export function bulletinStateLabel(value: string): string {
  return ({ draft: "Brouillon", approved: "Approuvé", sent: "Envoi enregistré" } as Record<string, string>)[value] || "État non reconnu";
}
export interface RecordedFact { id: string; label: string; display: string | null; unit: string | null; sources: string[]; observationIds: string[]; }
function strings(value: unknown): string[] { return Array.isArray(value) ? value.filter((entry): entry is string => typeof entry === "string") : []; }
export function recordedFacts(facts: Record<string, unknown>): RecordedFact[] {
  return Object.entries(facts).flatMap<RecordedFact>(([id, raw]) => {
    if (raw === null || raw === undefined) return [{ id, label: id, display: null, unit: null, sources: [], observationIds: [] }];
    const scalar = typeof raw === "number" ? (Number.isFinite(raw) ? String(raw) : null) : typeof raw === "string" ? raw : null;
    if (typeof raw !== "object" || Array.isArray(raw)) return scalar === null ? [] : [{ id, label: id, display: scalar, unit: null, sources: [], observationIds: [] }];
    const item = raw as Record<string, unknown>;
    if (!("value" in item) && !("display" in item)) return [];
    const value = typeof item.value === "number" && Number.isFinite(item.value) ? item.value.toLocaleString("fr-FR") : typeof item.value === "string" ? item.value : null;
    const display = typeof item.display === "string" && item.display.trim() ? item.display : value;
    return [{ id, label: typeof item.label === "string" && item.label.trim() ? item.label : id, display,
      unit: typeof item.unit === "string" && !(typeof item.display === "string" && item.display.trim()) ? item.unit : null,
      sources: strings(item.sources), observationIds: strings(item.observation_ids).filter(value => /^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/i.test(value)) }];
  });
}
