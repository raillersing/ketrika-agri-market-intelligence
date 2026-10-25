/** Price rows retain their comparison grain; an absent fact never becomes a demo. */
export const DEFAULT_PRODUCT = "RICE_WHITE_LOCAL";

export interface MarketPrice {
  product_code: string;
  location_pcode: string | null;
  location_name: string | null;
  actor_level: string;
  month: string;
  median_price: number;
  min_price: number | null;
  max_price: number | null;
  currency: string;
  unit: string;
  value_kind: string;
  sources: string[];
}

export function comparisonKey(row: MarketPrice): string {
  return JSON.stringify([row.product_code, row.location_pcode, row.actor_level, row.currency, row.unit]);
}

export function summarizePrices(rows: MarketPrice[]) {
  const ordered = [...rows].sort((a, b) => b.month.localeCompare(a.month) || comparisonKey(a).localeCompare(comparisonKey(b)));
  const latest = ordered[0] ?? null;
  // Pick one explicitly labelled series instead of mixing regional/actor prices.
  const series = latest ? ordered.filter((row) => comparisonKey(row) === comparisonKey(latest)).reverse() : [];
  return { latest, series, sources: Array.from(new Set(rows.flatMap((row) => row.sources))) };
}
