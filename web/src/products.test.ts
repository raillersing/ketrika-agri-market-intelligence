import { describe, expect, it } from "vitest";
import { findNavigationPage, isNavigationPageActive, searchNavigationPages } from "./lib/navigation";
import { businessProducts } from "./lib/market-filters";

describe("Products catalog navigation and business filters (ADR-165)", () => {
  it("resolves the /products management route correctly", () => {
    expect(isNavigationPageActive("/products", "/products")).toBe(true);
    const page = findNavigationPage("/products");
    expect(page).toBeDefined();
    expect(page?.label).toBe("Produits");
    expect(page?.group).toBe("Gestion des données");
  });

  it("finds products catalog via search keywords", () => {
    const hits = searchNavigationPages("produits denrées");
    expect(hits.some((p) => p.href === "/products")).toBe(true);
  });

  it("includes dynamically added custom products in businessProducts filter", () => {
    const catalog = [
      { product_code: "RICE_WHITE_LOCAL", canonical_name_fr: "Riz blanc local" },
      { product_code: "rice_dq_3f7e39", canonical_name_fr: "Riz Test DQ" },
      { product_code: "VANILLA", canonical_name_fr: "Vanille naturelle" },
      { product_code: "CLOVE_SPICE", canonical_name_fr: "Girofle" },
    ];
    const filtered = businessProducts(catalog);
    expect(filtered).toHaveLength(3);
    expect(filtered.map((p) => p.product_code)).toEqual(["RICE_WHITE_LOCAL", "VANILLA", "CLOVE_SPICE"]);
    expect(filtered.some((p) => p.product_code === "rice_dq_3f7e39")).toBe(false);
  });
});
