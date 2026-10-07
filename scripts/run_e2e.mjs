import { spawn } from "node:child_process";
import fs from "node:fs";

// E2E Test Suite for Ketrika Agri Market Intelligence Web Frontend (T7.3)
const BASE_URL = process.env.WEB_BASE_URL || "http://localhost:3005";
const API_URL = process.env.API_BASE_URL || "http://localhost:8090";

const CHROME_PATH =
  process.env.CHROME_PATH || "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";

let testFailures = 0;
let testSuccesses = 0;

function assert(condition, message) {
  if (!condition) {
    console.error(`  FAIL: ${message}`);
    testFailures++;
    throw new Error(message);
  }
  console.log(`  PASS: ${message}`);
  testSuccesses++;
}

async function runTests() {
  console.log("==================================================");
  console.log("  Ketrika Agri Market Intelligence - Web E2E Suite");
  console.log(`  Target Web: ${BASE_URL}`);
  console.log(`  Target API: ${API_URL}`);
  console.log("==================================================\n");

  // Step 1: Launch Chrome headless with CDP
  const chrome = spawn(CHROME_PATH, [
    "--headless=new",
    "--remote-debugging-port=9222",
    "--disable-gpu",
    "--window-size=1440,900",
  ]);

  await new Promise((r) => setTimeout(r, 2000));

  let ws;
  let msgId = 1;
  const callbacks = new Map();
  const consoleErrors = [];

  try {
    const listRes = await fetch("http://127.0.0.1:9222/json/list");
    const targets = await listRes.json();
    const pageTarget = targets.find((t) => t.type === "page") || targets[0];
    const wsUrl = pageTarget.webSocketDebuggerUrl;

    ws = new WebSocket(wsUrl);
    await new Promise((resolve, reject) => {
      ws.onopen = resolve;
      ws.onerror = reject;
    });

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.method === "Runtime.consoleAPICalled" && data.params.type === "error") {
        consoleErrors.push(data.params.args.map((a) => a.value || a.description).join(" "));
      }
      if (data.method === "Runtime.exceptionThrown") {
        consoleErrors.push(data.params.exceptionDetails.text);
      }
      if (data.id && callbacks.has(data.id)) {
        const { resolve, reject } = callbacks.get(data.id);
        callbacks.delete(data.id);
        if (data.error) reject(data.error);
        else resolve(data.result);
      }
    };

    function send(method, params = {}) {
      const id = msgId++;
      return new Promise((resolve, reject) => {
        callbacks.set(id, { resolve, reject });
        ws.send(JSON.stringify({ id, method, params }));
      });
    }

    await send("Network.enable");
    await send("Page.enable");
    await send("Runtime.enable");

    // ==============================================================
    // Test 1: Authentication API Login Flow
    // ==============================================================
    console.log("[Test 1] Authentication flow (admin login & JWT)...");
    const loginRes = await fetch(`${API_URL}/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: "admin@ketrika.local", password: "change-me" }),
    });
    assert(loginRes.status === 200, `POST /v1/auth/login returns 200 (got ${loginRes.status})`);
    const loginData = await loginRes.json();
    assert(Boolean(loginData.token), "JWT token received in login response");
    const token = loginData.token;

    // ==============================================================
    // Test 2: Unauthenticated Access & Redirection
    // ==============================================================
    console.log("\n[Test 2] Middleware protection on private route without cookie...");
    await send("Page.navigate", { url: `${BASE_URL}/prices` });
    await new Promise((r) => setTimeout(r, 1500));
    const evalUrlRes = await send("Runtime.evaluate", { expression: "window.location.pathname" });
    assert(
      evalUrlRes.result.value === "/login",
      `Unauthenticated visit to /prices redirects to /login (got ${evalUrlRes.result.value})`
    );

    // Set auth cookie
    await send("Network.setCookie", {
      name: "ketrika_token",
      value: token,
      domain: "localhost",
      path: "/",
    });
    console.log("  Set ketrika_token cookie in browser session.");

    // ==============================================================
    // Test 3: Authenticated Navigation to Overview (/)
    // ==============================================================
    console.log("\n[Test 3] Overview page (/) rendering with KPI cards...");
    await send("Page.navigate", { url: `${BASE_URL}/` });
    await new Promise((r) => setTimeout(r, 2000));
    const evalHome = await send("Runtime.evaluate", { expression: "document.title" });
    assert(evalHome.result.value.includes("Ketrika"), "Page title contains 'Ketrika'");

    const hasKpiRes = await send("Runtime.evaluate", {
      expression: "document.body.innerText.includes('PRIX MÉDIAN NATIONAL')",
    });
    assert(hasKpiRes.result.value === true, "Overview displays 'PRIX MÉDIAN NATIONAL' KPI card");

    // ==============================================================
    // Test 4: Price Explorer & Global Filters (/prices)
    // ==============================================================
    console.log("\n[Test 4] Price explorer (/prices) with search params...");
    await send("Page.navigate", {
      url: `${BASE_URL}/prices?product=rice_milled&region=MG11`,
    });
    await new Promise((r) => setTimeout(r, 2000));
    const pricesTitle = await send("Runtime.evaluate", {
      expression: "document.body.innerText.includes('Explorateur des prix vivriers')",
    });
    assert(pricesTitle.result.value === true, "Prices page renders header");

    const tableLoaded = await send("Runtime.evaluate", {
      expression: "document.body.innerText.includes('Tableau des observations mensuelles')",
    });
    assert(tableLoaded.result.value === true, "Monthly observations table is rendered");

    // ==============================================================
    // Test 5: CSV Streaming Export
    // ==============================================================
    console.log("\n[Test 5] CSV streaming export endpoint...");
    const csvRes = await fetch(`${API_URL}/v1/prices?format=csv&limit=5`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    assert(csvRes.status === 200, `CSV export status is 200 (got ${csvRes.status})`);
    const csvContent = await csvRes.text();
    assert(csvContent.includes("product_code"), "CSV content contains header 'product_code'");
    assert(csvContent.includes("median_price"), "CSV content contains header 'median_price'");

    // ==============================================================
    // Test 6: Observation Total Provenance Certificate
    // ==============================================================
    console.log("\n[Test 6] Observation total provenance certificate (/observations/[id])...");
    const obsLatestRes = await fetch(`${API_URL}/v1/prices?limit=1`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    // Obtain an observation id from database via API
    const targetObsId = "a70c0f38-407b-4b62-8fec-29c8928f3327";
    const singleObsRes = await fetch(
      `${API_URL}/v1/observations/${targetObsId}`
    );
    assert(
      singleObsRes.status === 200,
      `API /v1/observations/{id} returns 200 (got ${singleObsRes.status})`
    );
    const obsJson = await singleObsRes.json();
    assert(Boolean(obsJson.bronze_presigned_url), "Presigned Bronze S3/MinIO URL is generated");
    assert(Boolean(obsJson.evidence), "Mechanical evidence extraction is present");

    await send("Page.navigate", {
      url: `${BASE_URL}/observations/${targetObsId}`,
    });
    await new Promise((r) => setTimeout(r, 4000));
    const certText = await send("Runtime.evaluate", {
      expression: "document.body.innerText.includes('CERTIFICAT DE PROVENANCE TOTALE')",
    });
    assert(certText.result.value === true, "Page displays 'CERTIFICAT DE PROVENANCE TOTALE'");

    // ==============================================================
    // Test 7: Navigation across all remaining pages
    // ==============================================================
    console.log("\n[Test 7] Full route navigation smoke checks...");
    const pagesToCheck = [
      { path: "/map", titleSnippet: "Carte des marchés" },
      { path: "/trade", titleSnippet: "Commerce extérieur" },
      { path: "/climate", titleSnippet: "Climat" },
      { path: "/alerts", titleSnippet: "Alertes" },
      { path: "/bulletins", titleSnippet: "Bulletins" },
      { path: "/copilot", titleSnippet: "Copilote" },
      { path: "/sources", titleSnippet: "DataOps" },
      { path: "/admin/review", titleSnippet: "File de revue" },
    ];

    for (const page of pagesToCheck) {
      await send("Page.navigate", { url: `${BASE_URL}${page.path}` });
      await new Promise((r) => setTimeout(r, 1500));
      const hasSnippet = await send("Runtime.evaluate", {
        expression: `document.body.innerText.includes('${page.titleSnippet}')`,
      });
      assert(hasSnippet.result.value === true, `Route ${page.path} renders '${page.titleSnippet}'`);
    }

    // ==============================================================
    // Test 8: Admin Review Workflow & RBAC
    // ==============================================================
    console.log("\n[Test 8] Admin review item resolution & RBAC security...");
    const listReviewRes = await fetch(`${API_URL}/v1/admin/review`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    assert(listReviewRes.status === 200, "GET /v1/admin/review as admin returns 200");
    const reviewList = await listReviewRes.json();
    assert(Array.isArray(reviewList), "Review list is an array");

    if (reviewList.length > 0) {
      const firstId = reviewList[0].review_id;
      const resolveRes = await fetch(`${API_URL}/v1/admin/review/${firstId}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ status: "approved" }),
      });
      assert(
        resolveRes.status === 200,
        `POST /v1/admin/review/{id} approval returns 200 (got ${resolveRes.status})`
      );
    }

    // RBAC: Client / unauthenticated request to /v1/admin/review must be 401 or 403
    const unauthReviewRes = await fetch(`${API_URL}/v1/admin/review`);
    assert(
      unauthReviewRes.status === 401 || unauthReviewRes.status === 403,
      `Unauthenticated access to /v1/admin/review returns 401/403 (got ${unauthReviewRes.status})`
    );

    // ==============================================================
    // Test 9: Zero Unhandled Console Errors
    // ==============================================================
    console.log("\n[Test 9] Browser console error check...");
    assert(consoleErrors.length === 0, `0 unhandled browser console errors (${consoleErrors.length} found)`);

    console.log("\n==================================================");
    console.log(`  E2E Test Results: ${testSuccesses} passed, ${testFailures} failed`);
    console.log("==================================================\n");

    ws.close();
  } finally {
    chrome.kill();
  }

  if (testFailures > 0) {
    process.exit(1);
  } else {
    process.exit(0);
  }
}

runTests().catch((err) => {
  console.error("Fatal E2E suite error:", err);
  process.exit(1);
});
