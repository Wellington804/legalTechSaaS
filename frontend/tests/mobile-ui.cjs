// Responsive UI contract checks. API fixtures only: not a DB/provider or physical-device test.
const assert = require("node:assert/strict");
const { mkdirSync } = require("node:fs");
const { join } = require("node:path");
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "C:/Users/maxue/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright");
const { fixtureApi } = require("./workspace-ui.cjs");

const base = process.env.WORKSPACE_UI_URL || "http://127.0.0.1:3109";
const origin = new URL(base).origin;
const apiOrigin = new URL(process.env.WORKSPACE_UI_API_URL || base).origin;
assert.ok(["localhost", "127.0.0.1"].includes(new URL(base).hostname), "Local bundle only");
assert.ok(["localhost", "127.0.0.1"].includes(new URL(apiOrigin).hostname), "Local fixture API only");
const paths = ["/dashboard", "/dashboard/pilot", "/dashboard/crm", "/dashboard/tracker", "/dashboard/tasks", "/dashboard/cases/case-a", "/dashboard/petitions/editor", "/dashboard/templates", "/dashboard/financeiro", "/dashboard/library", "/dashboard/communications", "/dashboard/conflitos", "/dashboard/controladoria", "/dashboard/operacoes", "/dashboard/oab", "/dashboard/jurimetria", "/dashboard/integrations", "/dashboard/analytics/judge-profiling", "/dashboard/admin/users", "/dashboard/audit", "/dashboard/audit/ai-quality", "/dashboard/account", "/account/access", "/portal"];

async function fits(page, label) {
  const overflow = await page.evaluate(() => {
    const width = document.documentElement.clientWidth;
    return [...document.querySelectorAll("body *")].filter(el => {
      if (!el.checkVisibility() || el.closest("dialog:not([open])") || el.classList.contains("sr-only")) return false;
      const rect = el.getBoundingClientRect();
      return rect.width > 1 && (rect.right > width + 1 || rect.left < -1);
    }).slice(0, 5).map(el => `${el.tagName}.${el.className}`);
  });
  assert.deepEqual(overflow, [], `${label}: visible content must fit, not be hidden by overflow-x`);
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    const context = await browser.newContext({ viewport: { width: 375, height: 812 }, isMobile: true, hasTouch: true });
    const api = fixtureApi();
    // Long tokens expose clipping that the original short fixtures did not cover.
    api.state.documents[0].filename = `${"documento_".repeat(25)}.pdf`;
    api.state.clients[0].email = `${"contato".repeat(25)}@example.test`;
    const errors = [];
    let searchRequests = 0;
    await context.route("**/*", route => [origin, apiOrigin].includes(new URL(route.request().url()).origin) ? route.fallback() : route.abort("blockedbyclient"));
    await context.route(`${apiOrigin}/api/v1/**`, async route => {
      const url = new URL(route.request().url());
      const path = url.pathname;
      const json = payload => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(payload) });
      if (path === "/api/v1/workspace/search") {
        searchRequests++;
        const query = url.searchParams.get("q");
        if (query === "diligência") return json({ results: [{
          kind: "document", id: "doc-outside-first-page", title: "Documento encontrado na diligência",
          subtitle: "Petição", snippet: "Conteúdo consultado sem abrir o editor.",
          href: "/dashboard/petitions/editor?document=doc-outside-first-page", updated_at: "2026-09-05T00:00:00Z",
        }] });
        if (query === "Cliente Exemplo") return json({ results: [{
          kind: "client", id: "client-a", title: "Cliente Exemplo", subtitle: api.state.clients[0].email,
          snippet: null, href: "/dashboard/crm", updated_at: "2026-09-05T00:00:00Z",
        }] });
        return json({ results: [] });
      }
      if (["/api/v1/workspace/ledger", "/api/v1/workspace/publications", "/api/v1/workspace/library"].includes(path)) return json({ items: [], limit: 50 });
      if (path === "/api/v1/workspace/analytics") return json({ cases_by_status: { open: 1 } });
      if (path === "/api/v1/audit/logs") return json([{ id: "audit-a", action: "document.updated", resource_type: "document", details: {} }]);
      if (path.endsWith("/versions")) return json({ items: [{ id: "version-a", version: 3, content_text: "Versão preservada." }] });
      if (path === "/api/v1/client-portal") return json({ case: api.state.cases[0], checklist: [], messages: [] });
      return api.handler(route);
    });
    const page = await context.newPage();
    page.setDefaultTimeout(20000);
    page.on("pageerror", error => errors.push(error.message));
    for (const width of [320, 375, 390, 768, 1440]) {
      await page.setViewportSize({ width, height: 900 });
      for (const path of paths) {
        await page.goto(base + path);
        await page.getByRole("heading", { level: 1 }).first().waitFor();
        await page.waitForFunction(() => ![...document.querySelectorAll('[role="status"]')].some(el => el.textContent.includes("Carregando")))
          .catch(error => { throw new Error(`${width}px ${path}: ${error.message}`); });
        await fits(page, `${width}px ${path}`);
      }
    }

    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto(base + "/dashboard/audit/ai-quality");
    assert.equal(await page.getByRole("button", { name: "Aprovar caso conferido", exact: true }).count(), 0, "approval stays unavailable before opening the complete content");
    await page.getByRole("button", { name: "Abrir revisão completa", exact: true }).click();
    await page.getByText("Texto de referência suficientemente completo para que outro advogado confira o conteúdo antes de decidir se o caso pode ser usado na avaliação da inteligência artificial.", { exact: true }).waitFor();
    await page.getByRole("button", { name: "Aprovar caso conferido", exact: true }).waitFor();
    await fits(page, "mobile AI quality complete review");

    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto(base + "/dashboard/crm");
    await page.getByRole("button", { name: "Clientes", exact: true }).click();
    const client = page.getByText("Cliente Exemplo", { exact: true });
    await client.waitFor();
    assert.ok((await client.boundingBox()).y < 812, "client lookup visible before lengthy create/import forms");
    assert.equal(await page.getByLabel("Nome / razão social").isVisible(), false);
    await page.getByRole("button", { name: "Cadastrar cliente", exact: true }).click();
    await page.getByLabel("Nome / razão social").fill("Cliente pelo celular");
    assert.equal(await page.getByLabel("Nome / razão social").evaluate(el => getComputedStyle(el).fontSize), "16px");
    assert.deepEqual(await page.locator("main input:not([type='checkbox']):not([type='file']), main select, main button").evaluateAll(elements => elements.filter(el => el.checkVisibility() && el.getBoundingClientRect().height < 44).map(el => el.outerHTML)), [], "visible form controls have at least 44px touch height");
    await page.getByRole("button", { name: "Cadastrar cliente", exact: true }).last().click();
    await page.waitForFunction(() => [...document.querySelectorAll("button")].filter(button => button.textContent?.trim() === "Cadastrar cliente").every(button => !button.disabled));
    assert.ok(api.state.calls.some(call => call.method === "POST" && call.path.endsWith("/clients") && call.body.name === "Cliente pelo celular"));

    await page.getByRole("button", { name: "Outros", exact: true }).click();
    const menu = page.getByRole("dialog", { name: "Todas as áreas" });
    await menu.waitFor();
    await fits(page, "mobile menu");
    for (let i = 0; i < 18; i++) {
      await page.keyboard.press("Tab");
      // Native dialogs may hand focus to browser chrome, but never to background page controls.
      assert.ok(await page.evaluate(() => !document.hasFocus() || Boolean(document.activeElement.closest("dialog[open]"))), "menu keeps background controls inert");
    }
    await menu.getByRole("link", { name: "Agenda e prazos", exact: true }).click();
    await page.waitForURL("**/dashboard/tasks");
    assert.equal(await menu.isVisible(), false, "menu closes after navigation");
    await page.getByRole("button", { name: "Outros", exact: true }).click();
    await page.keyboard.press("Escape");
    assert.equal(await page.getByRole("button", { name: "Outros", exact: true }).evaluate(el => document.activeElement === el), true);

    const searchTrigger = page.getByRole("button", { name: "Buscar", exact: true });
    await searchTrigger.click();
    const search = page.getByRole("dialog", { name: "Buscar no escritório" });
    await search.getByRole("searchbox").fill("diligência");
    await search.getByRole("link", { name: /Documento encontrado na diligência/ }).waitFor();
    await search.getByText("Conteúdo consultado sem abrir o editor.", { exact: true }).waitFor();
    assert.ok(searchRequests > 0, "lookup uses existing server search, not loaded first page");
    await fits(page, "search document preview and long filename");
    await search.getByRole("searchbox").fill("Cliente Exemplo");
    await search.getByRole("link", { name: /Cliente Exemplo/ }).waitFor();
    await search.getByText(api.state.clients[0].email, { exact: true }).waitFor();
    await fits(page, "search client contact");
    await search.getByRole("searchbox").fill("nenhum resultado");
    await search.getByText("Nada foi encontrado com esses termos.").waitFor();
    await page.setViewportSize({ width: 375, height: 360 });
    await fits(page, "search with reduced keyboard-height viewport");
    await search.getByRole("button", { name: "Fechar busca" }).click();

    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto(base + "/dashboard/petitions/editor");
    await page.getByRole("button", { name: "Criar documento", exact: true }).click();
    await page.getByText("Ler documento", { exact: true }).first().click();
    await page.getByText("Texto original.", { exact: true }).waitFor();
    await page.getByRole("button", { name: "Editar documento", exact: true }).first().click();
    await page.getByLabel("Título", { exact: true }).waitFor();
    assert.equal(await page.getByLabel("Título", { exact: true }).inputValue(), "Petição inicial");
    await page.getByRole("button", { name: "Cancelar edição", exact: true }).click();
    if (process.env.MOBILE_SCREENSHOT_DIR) {
      mkdirSync(process.env.MOBILE_SCREENSHOT_DIR, { recursive: true });
      await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
      await page.screenshot({ path: join(process.env.MOBILE_SCREENSHOT_DIR, "mobile-documents.png"), fullPage: true });
      await page.goto(base + "/dashboard");
      await page.getByText("Revisar caso", { exact: true }).waitFor();
      await page.screenshot({ path: join(process.env.MOBILE_SCREENSHOT_DIR, "mobile-dashboard.png"), fullPage: true });
    }
    assert.deepEqual(api.state.unhandled, []);
    assert.deepEqual(errors, []);

    // Unauthenticated login remains scrollable with a small landscape/keyboard viewport.
    await context.route(`${apiOrigin}/api/v1/auth/me`, route => route.fulfill({ status: 401, contentType: "application/json", body: '{"detail":"Login required"}' }));
    await page.setViewportSize({ width: 320, height: 320 });
    await page.goto(base + "/dashboard");
    await page.getByRole("button", { name: "Entrar", exact: true }).scrollIntoViewIfNeeded();
    await page.getByLabel("E-mail", { exact: true }).fill("mobile@example.test");
    await page.getByLabel("Senha", { exact: true }).fill("NotARealPassword123");
    await page.getByRole("button", { name: "Mostrar senha" }).click();
    assert.equal(await page.getByLabel("Senha", { exact: true }).getAttribute("type"), "text");
    await fits(page, "login 320x320");
    await context.close();
    console.log(`PASS: ${paths.length} routes × 5 widths; mobile create/read/search/menu/focus, long content and reduced-height login. UI fixtures only; no DB/providers or physical devices.`);
  } finally { await browser.close(); }
})().catch(error => { console.error(error.stack || error.message); process.exitCode = 1; });
