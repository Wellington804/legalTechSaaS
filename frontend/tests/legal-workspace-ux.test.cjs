const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const root = path.resolve(__dirname, "..");
const source = relative => readFileSync(path.join(root, relative), "utf8");

test("legal workspaces keep technical setup out of the main flow", () => {
  const controladoria = source("src/components/workspace/controladoria.tsx");
  const library = source("src/app/dashboard/library/page.tsx");

  assert.match(controladoria, /subscriptions\/from-number/);
  assert.match(controladoria, /Novo número/);
  assert.doesNotMatch(controladoria, /Fontes judiciais e homologação/);
  assert.doesNotMatch(controladoria, /JSON\.stringify/);
  assert.match(library, /detail: \{ contextKind: "library" \}/);
  assert.doesNotMatch(library, /prompt:/);
});
