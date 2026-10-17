import { describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { GET } from "./app/api/[...path]/route";
import { getValueKindInfo, formatNumber, formatPrice } from "./lib/formatters";

describe("Observatoire Economique & Marches (R2.10, ADR-070, ADR-072)", () => {
  it("forwards /v1/economic/* requests through same-origin proxy", async () => {
    vi.stubEnv("API_INTERNAL_URL", "http://api:8000");
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ as_of_date: "2026-05-01", dimensions: {} }), {
        headers: { "content-type": "application/json" },
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    const request = new NextRequest("http://web:3000/api/v1/economic/dashboard", {
      headers: { cookie: "session_token=test", accept: "application/json" },
    });
    const response = await GET(request, { params: { path: ["v1", "economic", "dashboard"] } });

    expect(fetchMock).toHaveBeenCalled();
    const [target, options] = fetchMock.mock.calls[0];
    expect(target.toString()).toBe("http://api:8000/v1/economic/dashboard");
    expect(options.headers.get("cookie")).toBe("session_token=test");
    expect(response.status).toBe(200);

    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("forwards /v1/market/coverage/gaps with query parameters", async () => {
    vi.stubEnv("API_INTERNAL_URL", "http://api:8000");
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ coverage_ratio: 0.95, missing_months: 2 }), {
        headers: { "content-type": "application/json" },
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    const request = new NextRequest(
      "http://web:3000/api/v1/market/coverage/gaps?product=RICE_WHITE_LOCAL&location=MDG11&actor_level=retail"
    );
    const response = await GET(request, { params: { path: ["v1", "market", "coverage", "gaps"] } });

    expect(fetchMock).toHaveBeenCalled();
    const [target] = fetchMock.mock.calls[0];
    expect(target.toString()).toContain("product=RICE_WHITE_LOCAL");
    expect(target.toString()).toContain("location=MDG11");
    expect(response.status).toBe(200);

    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("formats prices and economic units with French locale conventions (SPECS §22)", () => {
    // 2 850 Ar/kg with non-breaking space
    const formatted = formatPrice(2850, "kg");
    expect(formatted).toContain("Ar/kg");
    expect(formatted.replace(/\s/g, " ")).toContain("2 850");

    // Percentage variation format
    const num = formatNumber(12.5, 1);
    expect(num.replace(/\s/g, " ")).toBe("12,5");
  });

  it("handles ValueKind metadata according to non-negotiable principle 9", () => {
    const observed = getValueKindInfo("observed");
    expect(observed.label).toBe("Observé");

    const imputed = getValueKindInfo("imputed");
    expect(imputed.label).toBe("Imputé");

    const forecast = getValueKindInfo("forecast");
    expect(forecast.label).toBe("Prévision");

    const composite = getValueKindInfo("composite");
    expect(composite.label).toBe("Composite");
  });
});
