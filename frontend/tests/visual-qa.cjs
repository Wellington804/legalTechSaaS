const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const path = require("node:path");
const { chromium } = require(
  process.env.PLAYWRIGHT_MODULE ||
    "C:/Users/maxue/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright"
);
const { fixtureApi } = require("./workspace-ui.cjs");

const baseUrl = process.env.WORKSPACE_UI_URL || "http://localhost:3000";
const apiOrigin = new URL(process.env.WORKSPACE_UI_API_URL || "http://localhost:8000").origin;
const baseOrigin = new URL(baseUrl).origin;
const output = path.resolve(__dirname, "../test-results/visual-qa");
const screens = [
  ["central", "/dashboard"],
  ["agenda", "/dashboard/tasks"],
  ["copiloto", "/dashboard/assistant"],
  ["conhecimento", "/dashboard/library"],
  ["controladoria", "/dashboard/controladoria"],
  ["processos", "/dashboard/tracker"],
  ["comunicacoes", "/dashboard/communications"],
  ["atendimento", "/dashboard/operacoes"],
  ["servicos", "/dashboard/integrations"],
  ["conta", "/dashboard/account"],
  ["auditoria", "/dashboard/audit"],
];

(async () => {
  assert.ok(["localhost", "127.0.0.1"].includes(new URL(baseUrl).hostname), "visual QA is local-only");
  await fs.mkdir(output, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const errors = [];
  try {
    for (const [theme, colorScheme] of [["claro", "light"], ["escuro", "dark"]]) for (const [device, viewport] of [["desktop", { width: 1440, height: 960 }], ["mobile", { width: 375, height: 812 }]]) {
      const api = fixtureApi();
      const context = await browser.newContext({ viewport, colorScheme });
      await context.route("**/*", route => [baseOrigin, apiOrigin].includes(new URL(route.request().url()).origin) ? route.fallback() : route.abort("blockedbyclient"));
      await context.route(`${apiOrigin}/api/v1/**`, api.handler);
      const page = await context.newPage();
      page.setDefaultTimeout(8000);
      page.on("pageerror", error => errors.push(`${device}: ${error.message}`));
      for (const [name, pathname] of screens) {
        await page.goto(new URL(pathname, baseUrl).href);
        await page.locator("main h1").first().waitFor();
        await page.screenshot({ path: path.join(output, `${theme}-${device}-${name}.png`), fullPage: true });
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), `${device}-${name} has horizontal overflow`);
      }
      await page.goto(new URL("/dashboard/assistant", baseUrl).href);
      const composer = await page.getByLabel("Mensagem para o Copiloto", { exact: true }).boundingBox();
      assert.ok(composer && composer.y >= 0 && composer.y + composer.height <= viewport.height, `${theme}-${device} Copiloto composer is visible`);
      if (device === "mobile") {
        const navigation = await page.getByRole("navigation", { name: "Navegação principal" }).boundingBox();
        assert.ok(navigation && composer.y + composer.height <= navigation.y, `${theme}-${device} Copiloto composer stays above navigation`);
      }
      await page.goto(new URL("/dashboard/communications", baseUrl).href);
      await page.getByRole("button", { name: "Conectar WhatsApp", exact: true }).click();
      await page.getByRole("img", { name: "QR Code para conectar o WhatsApp do escritório", exact: true }).waitFor();
      await page.screenshot({ path: path.join(output, `${theme}-${device}-comunicacoes-qr.png`), fullPage: true });
      await page.goto(new URL("/dashboard/controladoria", baseUrl).href);
      await page.getByRole("button", { name: "Acompanhar processo", exact: true }).click();
      await page.getByRole("button", { name: "Novo número", exact: true }).click();
      await page.getByLabel("Número CNJ", { exact: true }).waitFor();
      await page.screenshot({ path: path.join(output, `${theme}-${device}-controladoria-novo-numero.png`), fullPage: true });
      await page.goto(new URL("/dashboard/tracker", baseUrl).href);
      await page.getByRole("button", { name: "Novo processo", exact: true }).click();
      await page.getByRole("button", { name: "+ Novo cliente", exact: true }).click();
      const dialog = page.getByRole("dialog", { name: "Novo cliente", exact: true });
      await dialog.waitFor();
      const box = await dialog.boundingBox();
      assert.ok(box, `${device} quick-client dialog is visible`);
      if (device === "mobile") assert.ok(box.width >= 360 && box.height >= 760, `mobile quick-client dialog uses nearly the full screen: ${JSON.stringify(box)}`);
      else assert.ok(box.width <= 600 && box.height <= 600, "desktop quick-client dialog remains centered and bounded");
      await page.screenshot({ path: path.join(output, `${theme}-${device}-novo-cliente.png`) });
      assert.deepEqual(api.state.unhandled, [], `${theme}-${device} visual fixtures are incomplete`);
      await context.close();
    }
    assert.deepEqual(errors, [], "visual pages must not throw browser errors");
    console.log(`PASS: responsive light/dark screenshots written to ${output}`);
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error.stack || error.message); process.exitCode = 1; });
