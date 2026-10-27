import { DEFAULT_PRODUCT } from "./market-overview";

export type FilterField = "product" | "region" | "actor";
const PRICE_FILTERS: readonly FilterField[] = ["product", "region", "actor"];
const PRODUCT_FILTERS: readonly FilterField[] = ["product"];
export function filterFieldsForPath(path: string): readonly FilterField[] {
  const route = path.split(/[?#]/)[0].replace(/\/+$/, "") || "/";
  if (route === "/" || route === "/prices") return PRICE_FILTERS;
  if (route === "/map" || route === "/trade") return PRODUCT_FILTERS;
  return [];
}

// Exact identities in the readonly 2026-10-27 inventory, not a name/prefix heuristic.
const LEGACY_DQ_PRODUCTS = new Set([
  "rice_dq_116994", "rice_dq_24280c", "rice_dq_2563c9", "rice_dq_290ecc",
  "rice_dq_2a0441", "rice_dq_2c5609", "rice_dq_3f7e39", "rice_dq_502781",
  "rice_dq_6b2ea9", "rice_dq_6c90e2", "rice_dq_85a4f6", "rice_dq_96230a",
  "rice_dq_b53bb8", "rice_dq_c5076c", "rice_dq_c6cd0e", "rice_dq_c763be",
]);
export const DQ_SELECTION_MESSAGE = "Cette référence est réservée aux essais de qualité. Choisissez un produit du catalogue métier.";
export function isLegacyDQProduct(code: string): boolean { return LEGACY_DQ_PRODUCTS.has(code); }
export interface ProductReference { product_code: string; canonical_name_fr: string; }
export function businessProducts<T extends ProductReference>(rows: readonly T[]): T[] {
  return rows.filter(row => !isLegacyDQProduct(row.product_code));
}

export const SALE_STAGES = [
  { code: "", label: "Tous les stades" },
  { code: "producer", label: "Producteur" },
  { code: "farmgate", label: "Bord champ" },
  { code: "wholesale", label: "Gros" },
  { code: "retail", label: "Détail" },
  { code: "official_ppn", label: "Prix réglementé" },
  { code: "listing", label: "Prix d’annonce" },
  { code: "unknown", label: "Non renseigné" },
] as const;
export function saleStageLabel(code: string | null | undefined): string {
  return SALE_STAGES.find(stage => stage.code !== "" && stage.code === code)?.label || "Non renseigné";
}
export function resetVisibleFilters(query: string, fields: readonly FilterField[]): URLSearchParams {
  const params = new URLSearchParams(query);
  for (const field of fields) {
    if (field === "product") params.set(field, DEFAULT_PRODUCT);
    else params.delete(field);
  }
  return params;
}
