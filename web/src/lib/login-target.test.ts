import { describe, expect, it } from "vitest";
import { safeLoginTarget } from "./login-target";

describe("safeLoginTarget", () => {
  it.each([
    null, "", "javascript:alert(1)", "data:text/html,attack", "https://example.org",
    "//example.org", "/\\example.org", "/%5cexample.org", "/%2fexample.org",
    "/prices\n", "/%00prices", "/login", "/login?from=/prices", "/log%69n",
    "/login/", "/%invalid", "/prices?foo=%0a", "/%09prices",
  ])("refuses a dangerous or looping destination %s", (value) => {
    expect(safeLoginTarget(value)).toBe("/");
  });

  it.each(["/", "/prices", "/prices?product=RICE_WHITE_LOCAL#series", "/map?region=MG11", "/prices?reference=https%3A%2F%2Fexample.org"]) (
    "preserves a local destination %s", (value) => {
      expect(safeLoginTarget(value)).toBe(value);
    },
  );
});
