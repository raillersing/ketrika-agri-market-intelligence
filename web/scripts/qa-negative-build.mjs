// A real Next build defect in a disposable copy, never in the mounted repository.
import { spawnSync } from "node:child_process";
import { cpSync, existsSync, mkdtempSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

if (process.env.KETRIKA_QUALIFICATION !== "1") throw new Error("Isolated profile required");
const directory = mkdtempSync(join(tmpdir(), "ketrika-negative-build-"));
for (const name of ["src", "public", "package.json", "pnpm-lock.yaml", "next.config.mjs", "next.config.js", "tsconfig.json", "next-env.d.ts", "postcss.config.mjs", "postcss.config.js", "tailwind.config.ts", ".eslintrc.json"]) {
  if (existsSync(name)) cpSync(name, join(directory, name), { recursive: true });
}
symlinkSync("/app/node_modules", join(directory, "node_modules"), "dir");
writeFileSync(join(directory, "src/app/page.tsx"), "export default function DeliberatelyInvalid( {\n");
const result = spawnSync("pnpm", ["exec", "next", "build"], {
  cwd: directory, encoding: "utf8", timeout: 600000,
  env: { ...process.env, NEXT_TELEMETRY_DISABLED: "1" },
});
const output = (result.stdout || "") + (result.stderr || "");
const passed = result.status === 1 && /Failed to compile|Syntax Error|Unexpected/.test(output);
process.stdout.write(JSON.stringify({ scope: "deliberate build defect only in disposable copy", expected_nonzero: true, actual_exit: result.status, detected_compile_error: passed, passed }) + "\n");
if (!passed) process.stderr.write(output);
process.exitCode = passed ? 0 : 1;
