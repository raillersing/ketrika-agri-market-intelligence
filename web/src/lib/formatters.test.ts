import { describe, expect, it } from "vitest";
import {
  formatMonthYear,
  formatNumber,
  formatPercent,
  formatPrice,
  getValueKindInfo,
} from "./formatters";

describe("formatters fr-FR", () => {
  describe("formatNumber", () => {
    it("formats integers with space separator in fr-FR", () => {
      const res = formatNumber(2850);
      // In fr-FR, space can be thin space (\u202f) or non-breaking space (\u00a0)
      expect(res.replace(/\s|\u202f|\u00a0/g, " ")).toBe("2 850");
    });

    it("formats decimals with comma", () => {
      const res = formatNumber(1234.56, 2);
      expect(res.replace(/\s|\u202f|\u00a0/g, " ")).toBe("1 234,56");
    });

    it("handles null and undefined gracefully", () => {
      expect(formatNumber(null)).toBe("—");
      expect(formatNumber(undefined)).toBe("—");
      expect(formatNumber(NaN)).toBe("—");
    });
  });

  describe("formatPrice", () => {
    it("formats prices in Ariary per kg by default", () => {
      const res = formatPrice(2850);
      expect(res.replace(/\s|\u202f|\u00a0/g, " ")).toBe("2 850 Ar/kg");
    });

    it("formats custom unit or currency", () => {
      const res = formatPrice(15000, "sac", "MGA");
      expect(res.replace(/\s|\u202f|\u00a0/g, " ")).toBe("15 000 MGA/sac");
    });

    it("handles null", () => {
      expect(formatPrice(null)).toBe("—");
    });
  });

  describe("formatPercent", () => {
    it("formats positive variation with + sign", () => {
      const res = formatPercent(0.052);
      expect(res.replace(/\s|\u202f|\u00a0/g, " ")).toBe("+5,2 %");
    });

    it("formats negative variation with - sign", () => {
      const res = formatPercent(-0.031);
      expect(res.replace(/\s|\u202f|\u00a0/g, " ")).toBe("-3,1 %");
    });

    it("formats zero", () => {
      const res = formatPercent(0);
      expect(res.replace(/\s|\u202f|\u00a0/g, " ")).toBe("0,0 %");
    });

    it("handles null", () => {
      expect(formatPercent(null)).toBe("—");
    });
  });

  describe("formatMonthYear", () => {
    it("formats YYYY-MM to French month name and year", () => {
      const res = formatMonthYear("2026-09");
      // sept. 2026 or septembre 2026
      expect(res.toLowerCase()).toContain("2026");
      expect(res.toLowerCase()).toMatch(/sept|sep/);
    });

    it("handles null", () => {
      expect(formatMonthYear(null)).toBe("—");
    });
  });

  describe("getValueKindInfo", () => {
    it("returns correct labels for all four value kinds", () => {
      expect(getValueKindInfo("observed").label).toBe("Observé");
      expect(getValueKindInfo("imputed").label).toBe("Imputé");
      expect(getValueKindInfo("forecast").label).toBe("Prévision");
      expect(getValueKindInfo("composite").label).toBe("Composite");
    });

    it("falls back gracefully for unknown kind", () => {
      expect(getValueKindInfo("unknown").label).toBe("unknown");
    });
  });
});
