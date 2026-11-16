import { describe, expect, it } from "vitest";
import { apiHealthLabel, classifyApiHealth } from "./lib/system-health";

describe("system health is measured, never fabricated", () => {
  it("accepts a real successful health response only", () => {
    expect(classifyApiHealth(true, { status: "ok" })).toBe("reachable");
    expect(classifyApiHealth(true, { status: "ok", version: "0.1.0" })).toBe("reachable");
  });

  it("refuses success badges for failures or unknown payloads", () => {
    expect(classifyApiHealth(false, { status: "ok" })).toBe("unverified");
    expect(classifyApiHealth(true, { status: "failed" })).toBe("unverified");
    expect(classifyApiHealth(true, null)).toBe("unverified");
    expect(classifyApiHealth(true, "ok")).toBe("unverified");
  });

  it("limits the health claim to the API service", () => {
    expect(apiHealthLabel("reachable")).toContain("autres services non vérifiés");
    expect(apiHealthLabel("unverified")).toContain("non vérifié");
    expect(apiHealthLabel("checking")).toContain("en cours");
  });
});
