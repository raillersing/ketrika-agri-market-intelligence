import { afterEach, describe, expect, it, vi } from "vitest";
import { freshnessLabel, freshnessSummary, measuredFreshness, recomputeIndicators } from "./lib/sources-state";

afterEach(() => vi.unstubAllGlobals());

describe("truthful sources actions", () => {
  it("never calls unknown or disabled sources fresh", () => {
    expect(measuredFreshness(null, false)).toBeNull();
    expect(measuredFreshness(-1, false)).toBeNull();
    expect(measuredFreshness(0, false)).toBe(false);
    expect(freshnessLabel("active", null)).toBe("Fraîcheur non mesurée");
    expect(freshnessLabel("disabled", false)).toBe("Source indisponible");
    expect(freshnessSummary([{ status: "active" }, { status: "disabled", isStale: false }]).percent).toBeNull();
    expect(freshnessSummary([{ status: "active", isStale: false }, { status: "active", isStale: true }]))
      .toEqual({ measured: 2, fresh: 1, percent: 50 });
  });

  it("confirms a recalculation without claiming collection", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({
      success: true, action: "recompute", collection_performed: false,
      new_records_count: 0, views_refreshed: ["source_health"],
    })));
    await expect(recomputeIndicators("/api/v1/sources/refresh")).resolves.toContain("Aucune nouvelle collecte");
    expect(fetch).toHaveBeenCalledWith("/api/v1/sources/refresh", { method: "POST", credentials: "include" });
  });

  it.each([401, 403, 409, 503])("rejects failed action %s", async (status) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status })));
    await expect(recomputeIndicators("/api/v1/sources/refresh")).rejects.toThrow();
  });

  it("rejects an old misleading success receipt", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({ success: true, records_count: 728 })));
    await expect(recomputeIndicators("/api/v1/sources/refresh")).rejects.toThrow("non confirmée");
  });
});
