import { describe, expect, it } from "vitest";
import { businessProducts, filterFieldsForPath, isLegacyDQProduct, resetVisibleFilters, saleStageLabel } from "./lib/market-filters";

describe("business choices and effective filters", () => {
  it("excludes recorded test identities even if verified while retaining genuine names and aliases", () => {
    const rows = [
      { product_code: "rice_dq_116994", canonical_name_fr: "Riz Test DQ", verified: true },
      { product_code: "RICE_WHITE_LOCAL", canonical_name_fr: "Riz blanc local", verified: true },
      { product_code: "RICE_WHITE_IMPORTED", canonical_name_fr: "Riz blanc importé", verified: true },
      { product_code: "rice_milled", canonical_name_fr: "Riz blanc", verified: true },
      { product_code: "test_local_business", canonical_name_fr: "Riz Test DQ", verified: false },
    ];
    expect(businessProducts(rows).map(row => row.product_code)).toEqual(["RICE_WHITE_LOCAL", "RICE_WHITE_IMPORTED", "rice_milled", "test_local_business"]);
    expect(rows).toHaveLength(5);
    expect(isLegacyDQProduct("rice_dq_c763be")).toBe(true);
    expect(isLegacyDQProduct("rice_dq_customer_product")).toBe(false);
  });
  it("shows only filters consumed by each actual route", () => {
    expect(filterFieldsForPath("/")).toEqual(["product", "region", "actor"]);
    expect(filterFieldsForPath("/prices/?actor=unknown")).toEqual(["product", "region", "actor"]);
    expect(filterFieldsForPath("/map")).toEqual(["product"]);
    expect(filterFieldsForPath("/trade")).toEqual(["product"]);
    for (const page of ["/economy", "/climate", "/copilot", "/alerts", "/bulletins", "/bulletins/123", "/sources", "/system", "/prices-other"]) expect(filterFieldsForPath(page)).toEqual([]);
  });
  it("resets visible filters without discarding dates, source or unrelated scope", () => {
    const query = "product=maize&region=MDG11&actor=unknown&from=2026-01-01&source=worldbank";
    expect(Object.fromEntries(resetVisibleFilters(query, filterFieldsForPath("/prices")))).toEqual({ product: "RICE_WHITE_LOCAL", from: "2026-01-01", source: "worldbank" });
    expect(resetVisibleFilters(query, filterFieldsForPath("/map")).get("actor")).toBe("unknown");
    expect(resetVisibleFilters(query, []).toString()).toBe(query);
  });
  it("never relabels an absent or unknown sale stage as consumer retail", () => {
    for (const stage of [null, undefined, "", "unknown", "unexpected"]) expect(saleStageLabel(stage)).toBe("Non renseigné");
    expect(saleStageLabel("retail")).toBe("Détail");
    expect(saleStageLabel("official_ppn")).toBe("Prix réglementé");
    expect(saleStageLabel("farmgate")).toBe("Bord champ");
  });
});
