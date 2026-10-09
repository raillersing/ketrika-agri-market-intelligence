import { describe, expect, it } from "vitest";
import { spawnSync } from "node:child_process";
import { commandOutcome, commandTimeout, validateReport } from "../scripts/qa-check.mjs";

const valid = () => ({
  success: true, numTotalTests: 1, numPassedTests: 1, numFailedTests: 0,
  numPendingTests: 0, numFailedTestSuites: 0, numPendingTestSuites: 0,
  testResults: [{ assertionResults: [{ status: "passed" }] }],
});

describe("measured frontend qualification", () => {
  it("keeps every command bounded, with the documented build allowance", () => {
    expect(commandTimeout(["build"])).toBe(1800000);
    for (const args of [["lint"], ["typecheck"], ["run", "test"]]) {
      expect(commandTimeout(args)).toBe(900000);
    }
  });
  it("refuses an error even if a subprocess reports status zero", () => {
    expect(commandOutcome({ status: 0, error: { code: "ETIMEDOUT" }, signal: "SIGTERM" }))
      .toEqual({ exit_code: 0, error_code: "ETIMEDOUT", signal: "SIGTERM", timed_out: true, successful: false });
  });
  it("reports a real subprocess timeout as failure", () => {
    const result = spawnSync(process.execPath, ["-e", "setInterval(() => {}, 1000)"], { timeout: 100 });
    expect(commandOutcome(result)).toMatchObject({ error_code: "ETIMEDOUT", timed_out: true, successful: false });
  });
  it("recounts current cases", () => {
    expect(validateReport(valid())).toEqual({ tests: 1, suites: 1 });
  });
  it.each([
    { success: false }, { numTotalTests: 0 }, { numFailedTests: 1 },
    { numPendingTests: 1 }, { numFailedTestSuites: 1 }, { numPendingTestSuites: 1 },
    { testResults: [] }, { numPassedTests: 0 },
    { testResults: [{ assertionResults: [{ status: "skipped" }] }] },
    { testResults: [{ assertionResults: [] }] },
  ])("refuses empty, skipped, failed or inconsistent outcomes: %j", (change) => {
    expect(() => validateReport({ ...valid(), ...change })).toThrow();
  });
  it("refuses a missing report", () => expect(() => validateReport(null)).toThrow());
});
