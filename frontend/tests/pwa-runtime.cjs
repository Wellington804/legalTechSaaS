// Real service worker + production bundle. Authentication is an anonymous fixture;
// no PushManager subscription, permission request, provider send or legal data is used.
const assert = require("node:assert/strict");
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "C:/Users/maxue/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright");
const base = process.env.WORKSPACE_UI_URL || "http://localhost:3000";
const origin = new URL(base).origin;
const apiOrigin = new URL(process.env.WORKSPACE_UI_API_URL || base).origin;
assert.ok([origin, apiOrigin].every(url => ["localhost", "127.0.0.1"].includes(new URL(url).hostname)), "Local runtime only");
const assets = ["/offline.html", "/icons/icon-192.png", "/icons/icon-512.png", "/icons/apple-touch-icon.png"];

(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    const context = await browser.newContext({ viewport: { width: 375, height: 812 }, serviceWorkers: "allow" });
    await context.route("**/*", route => [origin, apiOrigin].includes(new URL(route.request().url()).origin) ? route.fallback() : route.abort("blockedbyclient"));
    await context.route(`${apiOrigin}/api/v1/**`, route => route.fulfill({ status: 401, contentType: "application/json", body: '{"detail":"Anonymous runtime fixture"}' }));
    const page = await context.newPage(); page.setDefaultTimeout(20000);
    await page.goto(base + "/dashboard");
    await page.getByRole("button", { name: "Entrar", exact: true }).waitFor();
    const initialPermission = await page.evaluate(() => Notification.permission);
    assert.notEqual(initialPermission, "granted", "Runtime does not grant notification permission");
    await page.waitForFunction(() => navigator.serviceWorker.controller?.scriptURL.endsWith("/sw.js"));
    const worker = await context.request.get(base + "/sw.js");
    assert.equal(worker.status(), 200);
    assert.match(worker.headers()["content-type"], /javascript/);
    assert.match(worker.headers()["cache-control"], /no-store/);
    assert.equal(worker.headers()["service-worker-allowed"], "/");
    const manifestResponse = await context.request.get(base + "/manifest.webmanifest");
    assert.equal(manifestResponse.status(), 200); assert.match(manifestResponse.headers()["content-type"], /manifest\+json|application\/json/);
    const manifest = await manifestResponse.json();
    assert.equal(manifest.start_url, "/dashboard"); assert.equal(manifest.scope, "/"); assert.equal(manifest.display, "standalone");
    for (const asset of assets) {
      const response = await context.request.get(base + asset); assert.equal(response.status(), 200);
      assert.match(response.headers()["content-type"], asset.endsWith(".png") ? /image\/png/ : /text\/html/);
    }
    for (const path of ["/dashboard/account", "/portal", "/dashboard"]) await page.goto(base + path);
    const cacheSnapshot = () => page.evaluate(async () => {
      const names = await caches.keys();
      return Promise.all(names.map(async name => ({ name, paths: (await (await caches.open(name)).keys()).map(request => new URL(request.url).pathname).sort() })));
    });
    assert.deepEqual(await cacheSnapshot(), [{ name: "legalflow-public-v1", paths: [...assets].sort() }]);
    await context.unroute(`${apiOrigin}/api/v1/**`);
    await context.setOffline(true);
    await page.goto(base + "/dashboard/tracker");
    await page.getByRole("heading", { name: "Você está sem conexão", exact: true }).waitFor();
    await page.getByText(/casos, documentos e mensagens não ficam disponíveis offline/).waitFor();
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), "Public offline shell fits mobile");
    const apiResponse = await page.evaluate(async () => {
      try { const response = await fetch("/api/v1/auth/me", { cache: "no-store", credentials: "omit" }); return { status: response.status, type: response.headers.get("content-type") }; }
      catch { return null; }
    });
    assert.equal(apiResponse, null, "Offline API fetch must fail, never return cached private data or HTML fallback");
    assert.deepEqual(await cacheSnapshot(), [{ name: "legalflow-public-v1", paths: [...assets].sort() }]);
    assert.equal(await page.evaluate(() => Notification.permission), initialPermission, "Notification permission was not changed");
    await context.setOffline(false);
    await page.getByRole("link", { name: "Tentar abrir a central", exact: true }).click();
    await page.getByRole("button", { name: "Entrar", exact: true }).waitFor();
    assert.deepEqual(await cacheSnapshot(), [{ name: "legalflow-public-v1", paths: [...assets].sort() }]);
    await context.close();
    console.log("PASS: real /sw.js controls built app, manifest/MIME/headers, exactly four public cached files, offline fallback, no API offline substitution, no permission/provider call, and mobile shell.");
  } finally { await browser.close(); }
})().catch(error => { console.error(error.stack || error.message); process.exitCode = 1; });
