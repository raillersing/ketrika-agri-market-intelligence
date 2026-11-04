import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { ChoroplethMap, type RegionPriceData } from "./components/maps/ChoroplethMap";

const point: RegionPriceData = {
  pcode: "UI_REGION", name: "Zone synthétique", price: 100,
  currency: "USD", unit: "t", valueKind: "observed", sources: ["ui_fixture"],
};
const render = (points: RegionPriceData[], selectedPcode?: string) =>
  renderToStaticMarkup(React.createElement(ChoroplethMap, { regionPrices: points, selectedPcode }));

describe("territorial points retain their recorded dimensions", () => {
  it("keeps an empty regional selection empty instead of inventing coverage", () => {
    const html = render([]);
    expect(html).toContain("Aucun point régional disponible");
    expect(html).not.toContain("<button");
    expect(html).toContain("ne représente pas des frontières");
  });
  it("preserves zero with the actual currency and unit", () => {
    const html = render([{ ...point, price: 0 }]);
    expect(html).toContain("0 USD/t");
    expect(html).not.toContain("Ar/kg");
  });
  it("keeps missing prices distinct from zero", () => {
    const html = render([{ ...point, price: null }]);
    expect(html).toContain("—");
    expect(html).not.toContain("0 USD/t");
  });
  it("does not fill missing dimensions with kg or Ariary", () => {
    const html = render([{ ...point, unit: "", currency: "" }]);
    expect(html).toContain("Devise non renseignée/Unité non renseignée");
    expect(html).not.toContain("Ar/kg");
  });
  it("shows the recorded nature and source for each point", () => {
    const html = render([point, { ...point, pcode: "UI_ESTIMATE", valueKind: "imputed", sources: ["ui_other_fixture"] }]);
    expect(html).toContain("Observé");
    expect(html).toContain("Imputé");
    expect(html).toContain("ui_fixture");
    expect(html).toContain("ui_other_fixture");
  });
  it("does not invent an official source when provenance is missing", () => {
    const html = render([{ ...point, sources: [] }]);
    expect(html).toContain("Source non renseignée");
    expect(html).not.toContain("parite_nationale");
  });
  it("does not compare heterogeneous units or derive a territorial diagnosis", () => {
    const html = render([point, { ...point, pcode: "UI_OTHER", price: 200, currency: "MGA", unit: "kg" }]);
    expect(html).toContain("100 USD/t");
    expect(html).toContain("200 Ar/kg");
    expect(html).not.toContain("Écart");
    expect(html).not.toContain("%");
    expect(html).toContain("Aucun diagnostic territorial");
  });
  it("preserves duplicate scoped points and exposes the controlled selection", () => {
    const html = render([point, { ...point, price: 200 }], point.pcode);
    expect(html.match(/<button/g)).toHaveLength(2);
    expect(html.match(/aria-pressed="true"/g)).toHaveLength(2);
    expect(render([point], "OTHER")).toContain('aria-pressed="false"');
  });
});
