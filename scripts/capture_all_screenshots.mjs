import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

async function main() {
  // 1. Get auth token
  const loginRes = await fetch("http://localhost:8090/v1/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: "admin@ketrika.local", password: "change-me" }),
  });
  const { token } = await loginRes.json();
  console.log("Token obtained:", token ? "yes" : "no");

  const chromePath = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
  const chrome = spawn(chromePath, [
    "--headless=new",
    "--remote-debugging-port=9222",
    "--disable-gpu",
    "--window-size=1440,900",
  ]);

  try {
    await new Promise((r) => setTimeout(r, 2000));

    const listRes = await fetch("http://127.0.0.1:9222/json/list");
    const targets = await listRes.json();
    const pageTarget = targets.find((t) => t.type === "page") || targets[0];
    const wsUrl = pageTarget.webSocketDebuggerUrl;

    const ws = new WebSocket(wsUrl);
    await new Promise((resolve, reject) => {
      ws.onopen = resolve;
      ws.onerror = reject;
    });
    console.log("WebSocket connected to CDP");

    let msgId = 1;
    const callbacks = new Map();
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.method === "Runtime.consoleAPICalled") {
        console.log("Browser console:", data.params.args.map((a) => a.value || a.description));
      }
      if (data.method === "Runtime.exceptionThrown") {
        console.error("Browser exception:", data.params.exceptionDetails);
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

    fs.mkdirSync("docs/screenshots", { recursive: true });

    // Capture /login without cookie first
    console.log("Capturing 01_login...");
    await send("Page.navigate", { url: "http://localhost:3005/login" });
    await new Promise((r) => setTimeout(r, 1500));
    let res = await send("Page.captureScreenshot", { format: "png" });
    fs.writeFileSync("docs/screenshots/01_login.png", Buffer.from(res.data, "base64"));
    console.log("Saved docs/screenshots/01_login.png");

    // Set cookie for protected pages
    await send("Network.setCookie", {
      name: "ketrika_token",
      value: token,
      domain: "localhost",
      path: "/",
    });
    console.log("Auth cookie set for authenticated routes");

    const obsRes = await fetch("http://127.0.0.1:8090/v1/prices/latest?limit=1");
    let sampleObsId = "be3fdaaf-19e6-4d43-a883-70e8b017fa23";
    try {
      const obsData = await obsRes.json();
      if (Array.isArray(obsData) && obsData.length > 0 && obsData[0].observation_id) {
        sampleObsId = obsData[0].observation_id;
      }
    } catch (e) {}

    const routes = [
      { name: "02_overview", path: "/" },
      { name: "03_prices", path: "/prices" },
      { name: "04_map", path: "/map" },
      { name: "05_trade", path: "/trade" },
      { name: "06_climate", path: "/climate" },
      { name: "07_alerts", path: "/alerts" },
      { name: "08_bulletins", path: "/bulletins" },
      { name: "09_copilot", path: "/copilot" },
      { name: "10_sources", path: "/sources" },
      { name: "11_admin_review", path: "/admin/review" },
      {
        name: "12_observation_provenance",
        path: `/observations/${sampleObsId}`,
      },
    ];

    for (const route of routes) {
      console.log(`Capturing ${route.name} (${route.path})...`);
      await send("Page.navigate", { url: `http://localhost:3005${route.path}` });
      const delay = route.name.includes("observation") ? 5000 : 3000;
      await new Promise((r) => setTimeout(r, delay));
      res = await send("Page.captureScreenshot", { format: "png" });
      const buffer = Buffer.from(res.data, "base64");
      fs.writeFileSync(`docs/screenshots/${route.name}.png`, buffer);
      console.log(`Saved docs/screenshots/${route.name}.png (${buffer.length} bytes)`);
    }

    ws.close();
    console.log("All screenshots captured successfully!");
  } finally {
    chrome.kill();
  }
}

main().catch(console.error);
