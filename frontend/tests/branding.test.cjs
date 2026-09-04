const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { test } = require("node:test");
const ts = require("typescript");

require.extensions[".ts"] = (module, filename) => module._compile(ts.transpileModule(readFileSync(filename, "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText, filename);

test("reference analysis only proposes known typed settings, never asset IDs or arbitrary keys", () => {
  const { BRAND_FONT_FAMILIES, identifiedBrandSettings, defaultBrandSettings, brandSettingLabels, exportFilename, moveBrandLayerToEdge, reorderBrandLayer, requiredBrandMargins } = require("../src/lib/branding.ts");
  assert.ok(BRAND_FONT_FAMILIES.length > 3);
  assert.ok(BRAND_FONT_FAMILIES.includes("Noto Serif"));
  assert.deepEqual(Object.keys(defaultBrandSettings).sort(), Object.keys(brandSettingLabels).sort());
  assert.deepEqual(identifiedBrandSettings(JSON.parse('{"body_size_pt":12,"header_text":"Escritório","page_numbers":true,"logo_asset_id":"foreign-profile","watermark_asset_id":"https://remote.test","constructor":{},"__proto__":{},"font_family":42,"script":"alert(1)"}')), {
    body_size_pt: 12, header_text: "Escritório", page_numbers: true,
  });
  assert.equal(exportFilename('Peça: ação/cliente "A"\n', "pdf"), "Peça_ ação_cliente _A__.pdf");
  assert.equal(exportFilename(" ", "docx"), "documento.docx");
  assert.equal(exportFilename("a".repeat(300), "pdf").length, 144);
  assert.deepEqual(identifiedBrandSettings({ format: "DOCX", fonts: ["Liberation Serif"], font_sizes_pt: [10, 12, 18], colors: ["#123456"], margins_mm: { top: 30.25, bottom: 25, left: 15, right: 20 }, header_text: ["Ana — OAB 123456"], footer_text: ["Contato confirmado"] }), {
    font_family: "Liberation Serif", margin_top_mm: 30.25, margin_bottom_mm: 25, margin_left_mm: 15, margin_right_mm: 20, header_text: "Ana — OAB 123456", footer_text: "Contato confirmado",
  });
  assert.deepEqual(identifiedBrandSettings({ fonts: ["Unknown Font"], margins_mm: { top: 5, left: Infinity }, header_text: ["Primeira página", "Outras páginas"], font_sizes_pt: [12] }), {}, "ambiguous or unsupported metadata is shown for review, not silently guessed");
  assert.deepEqual(identifiedBrandSettings({ fonts: ["Noto Serif"] }), { font_family: "Noto Serif" });
  const layers = [{ id: "band", z_index: 8 }, { id: "watermark", z_index: 2 }, { id: "logo", z_index: 8 }];
  assert.deepEqual(moveBrandLayerToEdge(layers, "band", "back").map(layer => [layer.id, layer.z_index]), [["band", 0], ["watermark", 1], ["logo", 2]]);
  assert.deepEqual(moveBrandLayerToEdge(layers, "logo", "front").map(layer => [layer.id, layer.z_index]), [["watermark", 0], ["band", 1], ["logo", 2]]);
  assert.deepEqual(reorderBrandLayer(layers, "band", "watermark").map(layer => [layer.id, layer.z_index]), [["band", 0], ["watermark", 1], ["logo", 2]]);
  assert.deepEqual(requiredBrandMargins({ ...defaultBrandSettings, layout_mode: "composed", layout_layers: [
    { y_percent: 1, height_percent: 14, role: "decoration", visible: true },
    { y_percent: 91, height_percent: 4, role: "contact", visible: true },
    { y_percent: 30, height_percent: 30, role: "watermark", visible: true },
  ] }), { top: 49, bottom: 31 });
});

test("private binary preview uses cookies/no-store and never retries a rendering write", async () => {
  const { apiBlob } = require("../src/lib/api-client.ts");
  const originalFetch = global.fetch;
  let calls = 0;
  try {
    global.fetch = async (url, options) => {
      calls++;
      assert.ok(url.endsWith("/branding/profiles/a/preview"));
      assert.equal(options.credentials, "include");
      assert.equal(options.cache, "no-store");
      assert.equal(options.method, "POST");
      assert.equal(options.body, '{"expected_revision":2}');
      return new Response("%PDF-1.4 private", { headers: { "Content-Type": "application/pdf" } });
    };
    const blob = await apiBlob("/branding/profiles/a/preview", { method: "POST", body: '{"expected_revision":2}' });
    assert.equal(blob.type, "application/pdf");
    assert.equal(await blob.text(), "%PDF-1.4 private");
    assert.equal(calls, 1);
    calls = 0;
    global.fetch = async () => { calls++; throw new TypeError("Response lost after render commit"); };
    await assert.rejects(apiBlob("/branding/profiles/a/preview", { method: "POST" }));
    assert.equal(calls, 1);
    global.fetch = async () => Response.json({ detail: "Acesso negado" }, { status: 403 });
    await assert.rejects(apiBlob("/branding/exports/a/download?format=pdf"), { status: 403, message: "Acesso negado" });
  } finally { global.fetch = originalFetch; }
});
