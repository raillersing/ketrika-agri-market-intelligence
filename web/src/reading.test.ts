import { describe, expect, it } from "vitest";
import { alertSeverityLabel, alertStateLabel, bulletinStateLabel, escapeHtml, humanDate, recordedFacts } from "./lib/reading";

describe("recorded facts without invented narrative or qualification", () => {
  it("escapes external labels embedded in chart tooltip markup", () => {
    expect(escapeHtml('<img src="x" onerror=alert(1)>&\'')).toBe('&lt;img src=&quot;x&quot; onerror=alert(1)&gt;&amp;&#39;');
    expect(escapeHtml("Banque mondiale — RTFP")).toBe("Banque mondiale — RTFP");
  });
  it("preserves zero and distinguishes a missing value", () => {
    const result = recordedFacts({ f001: { label: "Valeur nulle", value: 0, unit: "Ar/kg", sources: ["fixture"] }, f002: { label: "Absence", value: null } });
    expect(result[0]).toMatchObject({ label: "Valeur nulle", display: "0", unit: "Ar/kg", sources: ["fixture"] });
    expect(result[1].display).toBeNull();
  });
  it("preserves the recorded display without duplicating its unit or inventing provenance", () => {
    const result = recordedFacts({ f: { value: 2800, display: "2 800 Ar/kg", unit: "Ar/kg", observation_ids: ["not-an-id", "33c9e889-b7e6-471f-8ad7-982b017a6224"], sources: ["wb_rtfp_mdg", null] } });
    expect(result[0]).toMatchObject({ display: "2 800 Ar/kg", unit: null, observationIds: ["33c9e889-b7e6-471f-8ad7-982b017a6224"], sources: ["wb_rtfp_mdg"] });
  });
  it("does not turn an unrecognized structure into a factual market summary", () => {
    expect(recordedFacts({})).toEqual([]);
    expect(recordedFacts({ nested: { arbitrary: 45 }, list: [1, 2], boolean: true, invalid: NaN })).toEqual([]);
    expect(recordedFacts({ direct: 0, missing: null, text: "<script>not executable</script>" }).map(fact => fact.display)).toEqual(["0", null, "<script>not executable</script>"]);
  });
  it("uses clear French states without treating unknown values as validated", () => {
    expect(alertSeverityLabel("high")).toBe("Priorité élevée");
    expect(alertStateLabel("acknowledged")).toBe("Prise en compte");
    expect(bulletinStateLabel("approved")).toBe("Approuvé");
    expect(bulletinStateLabel("sent")).toBe("Envoi enregistré");
    expect(bulletinStateLabel("other")).toBe("État non reconnu");
    expect(alertSeverityLabel("other")).toBe("Niveau non renseigné");
  });
  it("handles invalid dates as missing and uses the business timezone", () => {
    expect(humanDate(null)).toBe("Date non renseignée");
    expect(humanDate("invalid")).toBe("Date non renseignée");
    expect(humanDate("2026-10-25T22:30:00Z")).toContain("26 oct.");
  });
});
