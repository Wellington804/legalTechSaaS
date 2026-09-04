// Focused browser contract. Local bundle + intercepted API; no provider or production data.
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const ts = require("typescript");
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const { fixtureApi } = require("./workspace-ui.cjs");
require.extensions[".ts"] = (module, filename) => module._compile(ts.transpileModule(readFileSync(filename, "utf8"), { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText, filename);
const { BRAND_FONT_FAMILIES, defaultBrandSettings } = require("../src/lib/branding.ts");

const base = process.env.WORKSPACE_UI_URL || "http://127.0.0.1:3000";
const origin = new URL(base).origin;
const apiOrigin = new URL(process.env.WORKSPACE_UI_API_URL || "http://localhost:8000").origin;
assert.ok([origin, apiOrigin].every(url => ["localhost", "127.0.0.1"].includes(new URL(url).hostname)), "Local fixtures only");

function pdfBytes() {
  return Buffer.from("%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Count 0/Kids[]>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF");
}
async function overflow(page) {
  return page.evaluate(() => [...document.querySelectorAll("main *")].filter(element => {
    if (!element.checkVisibility() || element.classList.contains("sr-only") || element.closest(".overflow-x-auto")) return false;
    const rect = element.getBoundingClientRect();
    return rect.width > 1 && (rect.right > document.documentElement.clientWidth + 1 || rect.left < -1);
  }).slice(0, 5).map(element => element.outerHTML.slice(0, 140)));
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const workspace = fixtureApi(); const calls = []; const unhandled = []; const pageErrors = [];
  const professional = { fields: [
    { key: "professional_name", label: "Nome profissional", value: "Ana Silva", source: "Perfil profissional", complete: true },
    { key: "oab", label: "OAB", value: "OAB/SP 123456", source: "Perfil profissional", complete: true },
    { key: "professional_email", label: "E-mail profissional", value: "ana@example.com", source: "Perfil profissional", complete: true },
    { key: "professional_phone", label: "Telefone profissional", value: "(11) 99999-9999", source: "Perfil profissional", complete: true },
    { key: "professional_address", label: "Endereço profissional", value: "Rua Um, 10", source: "Perfil profissional", complete: true },
    { key: "office_name", label: "Nome do escritório", value: "Silva Advocacia", source: "Cadastro do escritório", complete: true },
  ] };
  const band = { id: "top-band", kind: "rectangle", role: "decoration", label: "Faixa superior", x_percent: 8, y_percent: 1, width_percent: 84, height_percent: 14,
    rotation_deg: 0, opacity: 1, visible: true, locked: false, image_contrast: 1, z_index: 0, page_scope: "all", color: "#17324D", asset_id: null, text: "", binding: null,
    icon: "none", font_family: "Liberation Sans", font_size_pt: 8, font_weight: "normal", alignment: "left", letter_spacing_pt: 0, uppercase: false, line_thickness_pt: 1 };
  const brand = { id: "brand-a", name: "Identidade Ana", scope: "personal", owner_user_id: "user-a", revision: 1,
    settings: { ...defaultBrandSettings, layout_mode: "composed", layout_layers: [band] }, variants: {}, archived_at: null, published_version: 1, can_edit: true };
  const assets = [{ id: "reference-a", filename: "manual-identidade.pdf", kind: "reference", content_type: "application/pdf", analysis: { identified: { pages: 2 }, estimated: {}, warnings: [] } }]; const versions = [{ id: "v1", version: 1, settings: { ...brand.settings }, variants: {}, created_at: "2026-09-02T12:00:00Z" }];
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
    await context.route("**/*", route => [origin, apiOrigin].includes(new URL(route.request().url()).origin) ? route.fallback() : route.abort("blockedbyclient"));
    await context.route(`${apiOrigin}/api/v1/**`, async route => {
      const request = route.request(); const url = new URL(request.url()); const path = url.pathname; const method = request.method();
      if (!path.startsWith("/api/v1/branding")) return workspace.handler(route);
      let body = null; try { body = request.postDataJSON(); } catch {}
      calls.push({ path, method, body });
      const json = (payload, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(payload) });
      if (method === "GET" && path.endsWith("/capabilities")) return json({ fonts: BRAND_FONT_FAMILIES, pdf_available: true, ai_available: true, image_ai_available: false });
      if (method === "GET" && path === "/api/v1/branding/profiles") return json({ items: [brand] });
      if (method === "GET" && path.endsWith("/professional-data")) return json(professional);
      if (method === "GET" && path.endsWith("/assets")) return json({ items: assets });
      if (method === "GET" && path.endsWith("/assets/reference-a/pages/1")) return route.fulfill({ status: 200, contentType: "image/png", body: Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=", "base64") });
      if (method === "GET" && path.endsWith("/assets/background-a/download")) return route.fulfill({ status: 200, contentType: "image/png", body: Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=", "base64") });
      if (method === "POST" && path.endsWith("/assets/reference-a/extract")) { const extracted = { id: "background-a", filename: "papel-timbrado-pagina-1.png", kind: body.kind, content_type: "image/png", analysis: { identified: {}, estimated: {}, warnings: [] } }; assets.unshift(extracted); return json(extracted, 201); }
      if (method === "GET" && path.endsWith("/versions")) return json({ items: versions });
      if (method === "PUT" && path.endsWith("/profiles/brand-a")) {
        assert.equal(body.expected_revision, brand.revision); Object.assign(brand, body, { revision: brand.revision + 1 }); return json(brand);
      }
      if (method === "POST" && path.endsWith("/suggest")) return json({ settings: { ...brand.settings, primary_color: "#294A70" }, observations: ["Contraste mais sóbrio."], warnings: [] });
      if (method === "POST" && path.endsWith("/preview")) return route.fulfill({ status: 200, contentType: "application/pdf", body: pdfBytes() });
      if (method === "POST" && path.endsWith("/publish")) { brand.revision++; brand.published_version++; versions.unshift({ id: `v${brand.published_version}`, version: brand.published_version, settings: brand.settings, variants: brand.variants, created_at: "2026-09-02T13:00:00Z" }); return json(brand); }
      unhandled.push(`${method} ${path}`); return json({ detail: "Unhandled branding fixture" }, 404);
    });
    const page = await context.newPage(); page.setDefaultTimeout(12000); page.on("pageerror", error => pageErrors.push(error.message));
    await page.goto(`${base}/dashboard/brand`);
    await page.getByRole("heading", { name: "Identidade documental", exact: true }).waitFor();
    await page.getByRole("button", { name: /Identidade Ana/ }).click();
    await page.getByRole("heading", { name: "Estúdio de identidade documental" }).waitFor();
    assert.equal(await page.getByRole("heading", { name: "Assistente de design" }).count(), 1);
    assert.deepEqual(await overflow(page), []);

    await page.getByRole("button", { name: /Camadas visuais/ }).click();
    assert.equal(await page.getByText("23 fontes disponíveis", { exact: false }).count(), 0, "font help belongs to visual direction, not layers");
    const paper = page.locator("[data-brand-paper]"); const initialPaper = await paper.boundingBox();
    await page.getByRole("button", { name: "Aumentar zoom" }).click();
    const zoomedPaper = await paper.boundingBox();
    assert.ok(zoomedPaper.width > initialPaper.width * 1.2, "zoom enlarges the actual paper");
    await page.getByRole("button", { name: "Ajustar pré-visualização à tela" }).click();
    await page.locator('[data-brand-layer="top-band"]').click();
    assert.equal(await page.getByRole("button", { name: "Excluir elemento" }).isVisible(), true);
    await page.locator('[data-brand-layer="top-band"]').press("Delete");
    await page.locator('[role="status"]', { hasText: "Salvo" }).waitFor();
    assert.equal(brand.settings.layout_layers.length, 0);
    const undoSaved = page.waitForResponse(response => response.request().method() === "PUT" && new URL(response.url()).pathname.endsWith("/branding/profiles/brand-a"));
    await page.getByRole("button", { name: "Desfazer" }).click();
    await undoSaved;
    assert.equal(brand.settings.layout_layers.length, 1);
    await page.locator('[data-brand-layer="top-band"]').click();
    const positionSaved = page.waitForResponse(response => response.request().method() === "PUT" && new URL(response.url()).pathname.endsWith("/branding/profiles/brand-a"));
    await page.getByRole("button", { name: "Direita", exact: true }).click();
    await positionSaved;
    assert.equal(brand.settings.layout_layers[0].x_percent, 16);
    const layerName = page.getByLabel("Nome da camada");
    await layerName.fill("Faixa superior X"); await layerName.press("Backspace");
    assert.equal(brand.settings.layout_layers.length, 1, "Backspace in an input never deletes the layer");
    await layerName.fill("Faixa superior");
    await page.getByRole("button", { name: "Ocultar Faixa superior" }).click();
    await page.locator('[role="status"]', { hasText: "Salvo" }).waitFor();
    assert.equal(brand.settings.layout_layers[0].visible, false);
    await page.getByRole("button", { name: "Mostrar Faixa superior" }).click();
    await page.locator('[role="status"]', { hasText: "Salvo" }).waitFor();
    await page.getByRole("button", { name: /Papel e margens/ }).click();
    await page.getByRole("button", { name: "Aplicar área segura" }).click();
    await page.locator('[role="status"]', { hasText: "Salvo" }).waitFor();
    assert.equal(brand.settings.margin_top_mm, 49);

    await page.getByRole("button", { name: /Direção visual/ }).click();
    await page.getByText("23 fontes disponíveis", { exact: false }).waitFor();

    await page.getByLabel("Nome da identidade").fill("Identidade Ana revisada");
    await page.locator('[role="status"]', { hasText: "Salvo" }).waitFor();
    assert.equal(brand.name, "Identidade Ana revisada");

    await page.getByRole("button", { name: /Referências/ }).click();
    await page.getByAltText("Página 1 de manual-identidade.pdf").waitFor();
    await page.getByRole("button", { name: "Usar página inteira como timbrado fiel" }).click();
    await page.getByText(/Página aplicada como fundo fiel/).waitFor();
    await page.locator('[role="status"]', { hasText: "Salvo" }).waitFor();
    assert.equal(brand.settings.layout_mode, "exact");
    assert.equal(brand.settings.background_asset_id, "background-a");

    await page.getByRole("button", { name: "Petição", exact: true }).click();
    await page.getByRole("button", { name: /Papel e margens/ }).click();
    await page.getByLabel("Margem esquerda (mm)").fill("36");
    await page.locator('[role="status"]', { hasText: "Salvo" }).waitFor();
    assert.equal(brand.variants.petition.margin_left_mm, 36);

    await page.getByRole("button", { name: /Direção visual/ }).click();
    await page.getByLabel("Mensagem para a IA").fill("Deixe a cor principal mais sóbria para documentos impressos.");
    await page.getByRole("button", { name: "Enviar e comparar" }).click();
    await page.getByText("Contraste mais sóbrio.").waitFor();
    const suggestion = calls.find(call => call.path.endsWith("/suggest"));
    assert.equal(suggestion.body.consent, true); assert.equal(suggestion.body.document_type, "petition");
    await page.getByRole("button", { name: "Aplicar selecionados" }).click();
    await page.locator('[role="status"]', { hasText: "Salvo" }).waitFor();
    assert.equal(brand.settings.primary_color, "#294A70");

    await page.setViewportSize({ width: 375, height: 900 });
    await page.getByRole("button", { name: "Visualizar", exact: true }).click();
    await page.getByRole("region", { name: /Pré-visualização da identidade para Petição/ }).waitFor();
    assert.deepEqual(await overflow(page), []);
    await page.getByRole("button", { name: "Editar", exact: true }).click();
    await page.getByRole("button", { name: /Revisar e publicar/ }).click();
    await page.getByRole("button", { name: "Gerar PDF real desta variação" }).click();
    await page.getByRole("region", { name: "PDF real · Petição" }).waitFor();
    await page.getByRole("button", { name: "Fechar prévia" }).click();
    await page.getByRole("checkbox", { name: /Conferi dados profissionais/ }).check();
    await page.getByRole("button", { name: "Publicar nova versão" }).click();
    await page.getByText(/Versão 2 publicada/).waitFor();

    assert.deepEqual(unhandled, []); assert.deepEqual(workspace.state.unhandled, []); assert.deepEqual(pageErrors, []);
    console.log("PASS: galeria, estúdio responsivo, autosave, variação, comparação da IA, PDF e publicação.");
    await context.close();
  } finally { await browser.close(); }
})().catch(error => { console.error(error.stack || error.message); process.exitCode = 1; });
