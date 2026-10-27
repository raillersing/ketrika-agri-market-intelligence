import { describe, expect, it } from "vitest";
import { summarizePrices, withCalendarGaps, type MarketPrice } from "./lib/market-overview";

const point: MarketPrice = { product_code: "RICE_WHITE_LOCAL", location_pcode: "MDG11", location_name: "Analamanga", actor_level: "retail", month: "2026-09-01", median_price: 2700, min_price: null, max_price: null, currency: "MGA", unit: "kg", value_kind: "imputed", sources: ["worldbank"] };
describe("market overview comparison grain", () => {
  it("breaks a chart across missing months without inserting a price or changing a zero", () => {
    const rows = [{ month: "2025-12-01", value: 0 }, { month: "2026-01-01", value: 5 }, { month: "2026-04-01", value: 8 }];
    expect(withCalendarGaps(rows)).toEqual([rows[0], rows[1], null, rows[2]]);
    expect(rows).toHaveLength(3);
    expect(withCalendarGaps(rows)[0]).toBe(rows[0]);
  });
  it("does not invent a calendar for invalid dates or an empty series", () => {
    const rows = [{ month: "unknown" }, { month: "2026-04-01" }];
    expect(withCalendarGaps(rows)).toEqual(rows);
    expect(withCalendarGaps([])).toEqual([]);
  });
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
