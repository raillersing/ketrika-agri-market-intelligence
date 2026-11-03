/**
 * Normative formatting utilities for French locale (fr-FR) per SPECS §22.
 * Handles numbers, prices in Ariary (MGA), weights, dates, and value kinds.
 */

export type ValueKind = "observed" | "imputed" | "forecast" | "composite";

/**
 * Format a number according to French locale (thin/non-breaking space for thousands, comma for decimals).
 */
export function formatNumber(
  val: number | null | undefined,
  decimals = 0
): string {
  if (val === null || val === undefined || isNaN(val)) {
    return "—";
  }
  return new Intl.NumberFormat("fr-FR", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(val);
}

/**
 * Format price in Ariary (e.g. "2 850 Ar/kg" or "2 850 Ar").
 */
export function formatPrice(
  val: number | null | undefined,
  unit = "kg",
  currency = "Ar"
): string {
  if (val === null || val === undefined || isNaN(val)) {
    return "—";
  }
  const formatted = formatNumber(val, 0);
  return unit ? `${formatted} ${currency}/${unit}` : `${formatted} ${currency}`;
}

/**
 * Format variation percentage with sign (e.g. "+5,2 %", "-3,1 %").
 */
export function formatPercent(
  val: number | null | undefined,
  decimals = 1
): string {
  if (val === null || val === undefined || isNaN(val)) {
    return "—";
  }
  const formatted = formatNumber(Math.abs(val * 100), decimals);
  const sign = val > 0 ? "+" : val < 0 ? "-" : "";
  return `${sign}${formatted} %`;
}

/**
 * Format date string (YYYY-MM-DD or YYYY-MM) to French month year (e.g. "sept. 2026").
 */
export function formatMonthYear(dateStr: string | null | undefined): string {
  if (!dateStr) return "—";
  try {
    // If only YYYY-MM, append day
    const fullDate = dateStr.length === 7 ? `${dateStr}-01` : dateStr;
    const d = new Date(fullDate);
    if (isNaN(d.getTime())) return dateStr;
    return new Intl.DateTimeFormat("fr-FR", {
      month: "short",
      year: "numeric",
    }).format(d);
  } catch {
    return dateStr;
  }
}

/**
 * Metadata and display info for ValueKind.
 */
export interface ValueKindInfo {
  label: string;
  description: string;
  badgeClass: string;
}

export const VALUE_KIND_MAP: Record<ValueKind, ValueKindInfo> = {
  observed: {
    label: "Observé",
    description: "Donnée brute directement observée sur le marché",
    badgeClass: "bg-emerald-100 text-emerald-800 border-emerald-300 dark:bg-emerald-950 dark:text-emerald-300",
  },
  imputed: {
    label: "Imputé",
    description: "Valeur manquante estimée par modèle statistique ou source secondaire",
    badgeClass: "bg-sky-100 text-sky-800 border-sky-300 dark:bg-sky-950 dark:text-sky-300",
  },
  forecast: {
    label: "Prévision",
    description: "Projection future issue d'un modèle prédictif",
    badgeClass: "bg-orange-100 text-orange-900 border-orange-300 dark:bg-orange-950/60 dark:text-orange-300 dark:border-orange-700/50",
  },
  composite: {
    label: "Composite",
    description: "Indicateur composite agrégé calculé",
    badgeClass: "bg-amber-100 text-amber-800 border-amber-300 dark:bg-amber-950 dark:text-amber-300",
  },
};

export function getValueKindInfo(kind: string | null | undefined): ValueKindInfo {
  if (kind && kind in VALUE_KIND_MAP) {
    return VALUE_KIND_MAP[kind as ValueKind];
  }
  return {
    label: kind || "Non spécifié",
    description: "Nature de la valeur",
    badgeClass: "bg-slate-100 text-slate-800 border-slate-300",
  };
}
