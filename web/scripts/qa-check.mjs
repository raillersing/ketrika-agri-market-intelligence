import { spawnSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";

export function validateReport(report) {
  if (!report || report.success !== true ||
      !Number.isInteger(report.numTotalTests) || report.numTotalTests < 1 ||
      report.numPassedTests !== report.numTotalTests ||
      report.numFailedTests !== 0 || report.numPendingTests !== 0 ||
      report.numFailedTestSuites !== 0 || report.numPendingTestSuites !== 0 ||
      !Array.isArray(report.testResults) || report.testResults.length < 1) {
    throw new Error("Frontend test report is empty, failed, skipped or incomplete");
  }
  const cases = report.testResults.flatMap((suite) => suite.assertionResults || []);
  if (cases.length !== report.numTotalTests || cases.some((test) => test.status !== "passed")) {
    throw new Error("Frontend case outcomes do not match the measured summary");
  }
  return { tests: cases.length, suites: report.testResults.length };
}

export function commandTimeout(args) {
  return args[0] === "build" ? 1800000 : 900000;
}

export function commandOutcome(result) {
  return {
    exit_code: result.status,
    error_code: result.error?.code || null,
    signal: result.signal || null,
    timed_out: result.error?.code === "ETIMEDOUT",
    successful: !result.error && result.status === 0,
  };
}

export function runChecks() {
  if (process.env.KETRIKA_QUALIFICATION !== "1") throw new Error("Isolated profile required");
  const executionId = randomUUID();
  const directory = resolve("node_modules/.qa-results", executionId);
  mkdirSync(directory, { recursive: true });
  const reportFile = resolve(directory, "vitest.json");
  const receipt = { execution_id: executionId, scope: "frontend software only", passed: false, steps: [] };
  if (process.env.KETRIKA_SOURCE_COMMIT) {
    receipt.version = 1;
    receipt.commit = process.env.KETRIKA_SOURCE_COMMIT;
    receipt.source_fingerprint = process.env.KETRIKA_SOURCE_FINGERPRINT;
    receipt.dataset = "mixed";
    receipt.captured_at = new Date().toISOString();
    receipt.environment = {
      project: "ketrika-qualification-main-final", database: "ketrika_qualification",
      bronze_bucket: "ketrika-qa-bronze", network: "ketrika_qualification_main_final_network",
      dataset_mode: "test",
      backend_image_id: process.env.KETRIKA_PROOF_BACKEND_IMAGE_ID,
      web_image_id: process.env.KETRIKA_PROOF_WEB_IMAGE_ID,
      browser_image_id: process.env.KETRIKA_PROOF_BROWSER_IMAGE_ID,
    };
  }
  const commands = [
    ["lint"], ["typecheck"],
    ["run", "test", "--reporter=default", "--reporter=json", `--outputFile=${reportFile}`],
    ["build"],
  ];
  try {
    for (const args of commands) {
      const started = Date.now();
      const result = spawnSync("pnpm", args, { stdio: "inherit", timeout: commandTimeout(args) });
      const outcome = commandOutcome(result);
      receipt.steps.push({ command: ["pnpm", ...args], ...outcome, duration_ms: Date.now() - started });
      if (!outcome.successful) throw new Error(`${args[0]} did not complete successfully`);
      if (args[0] === "run" && args[1] === "test") receipt.counts = validateReport(JSON.parse(readFileSync(reportFile, "utf8")));
    }
    receipt.passed = true;
  } catch (error) {
    receipt.reason = String(error);
  }
  writeFileSync(resolve(directory, "receipt.json"), JSON.stringify(receipt, null, 2) + "\n");
  writeFileSync(resolve("node_modules/.qa-results/latest.json"), JSON.stringify({ execution_id: executionId }) + "\n");
  process.stdout.write(JSON.stringify(receipt) + "\n");
  return receipt.passed ? 0 : 1;
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  process.exitCode = runChecks();
}
