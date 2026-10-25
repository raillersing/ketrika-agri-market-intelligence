import { describe, expect, it } from "vitest";
import { summarizePrices, type MarketPrice } from "./lib/market-overview";

const point: MarketPrice = { product_code: "RICE_WHITE_LOCAL", location_pcode: "MDG11", location_name: "Analamanga", actor_level: "retail", month: "2026-09-01", median_price: 2700, min_price: null, max_price: null, currency: "MGA", unit: "kg", value_kind: "imputed", sources: ["worldbank"] };
describe("market overview comparison grain", () => {
  it("keeps absence explicit", () => { expect(summarizePrices([])).toEqual({ latest: null, series: [], sources: [] }); });
  it("keeps real estimates and excludes other zones, actors and units from the chart", () => {
    const rows = [point, { ...point, month: "2026-10-01", median_price: 2800 }, { ...point, location_pcode: "MDG12", median_price: 9999 }, { ...point, actor_level: "wholesale" }, { ...point, unit: "tonne" }];
    const result = summarizePrices(rows);
    expect(result.latest?.median_price).toBe(2800);
    expect(result.latest?.value_kind).toBe("imputed");
    expect(result.series.map((r) => r.median_price)).toEqual([2700, 2800]);
    expect(result.sources).toEqual(["worldbank"]);
    expect(rows[0]).toBe(point);
  });
});
