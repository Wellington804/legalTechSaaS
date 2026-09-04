const assert = require("node:assert/strict");
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "C:/Users/maxue/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright");
const { fixtureApi } = require("./workspace-ui.cjs");

const baseUrl = process.env.WORKSPACE_UI_URL || "http://127.0.0.1:3109";
const baseOrigin = new URL(baseUrl).origin;
const apiOrigin = new URL(process.env.WORKSPACE_UI_API_URL || baseUrl).origin;

async function waitForCount(requests, count) {
  for (let attempt = 0; attempt < 40; attempt += 1) {
    if (requests.length >= count) return;
    await new Promise(resolve => setTimeout(resolve, 25));
  }
  assert.fail(`Expected ${count} audit requests, received ${requests.length}`);
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const api = fixtureApi();
  const auditRequests = [];
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 960 } });
    await context.route("**/*", route => [baseOrigin, apiOrigin].includes(new URL(route.request().url()).origin) ? route.fallback() : route.abort("blockedbyclient"));
    await context.route(`${apiOrigin}/api/v1/**`, api.handler);
    await context.route(`${apiOrigin}/api/v1/audit/logs**`, route => {
      auditRequests.push(new URL(route.request().url()).search);
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([{
        id: "audit-a", action: "CASE_UPDATED", resource_type: "workspace_cases", actor_name: "Ana Advogada", created_at: "2026-09-04T12:00:00Z", details: {},
      }]) });
    });
    const page = await context.newPage();
    await page.goto(`${baseUrl}/dashboard/audit`);
    await page.getByText("Ana Advogada realizou uma alteração.", { exact: true }).waitFor();
    await page.waitForTimeout(150);
    assert.equal(auditRequests.length, 1, "initial audit load must settle after one request");

    await page.getByLabel("Período", { exact: true }).selectOption("7");
    await waitForCount(auditRequests, 2);
    await page.waitForTimeout(150);
    assert.equal(auditRequests.length, 2, "changing period must make one replacement request");

    await page.evaluate(() => window.dispatchEvent(new Event("legalflow:session-restored")));
    await waitForCount(auditRequests, 3);
    await page.waitForTimeout(150);
    assert.equal(auditRequests.length, 3, "session restoration must revalidate once");
    assert.match(auditRequests[0], /date_from=/);
    assert.match(auditRequests[1], /date_from=/);
    console.log("PASS: audit loading settles and revalidates once per intentional filter/session change.");
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error.stack || error.message); process.exitCode = 1; });
