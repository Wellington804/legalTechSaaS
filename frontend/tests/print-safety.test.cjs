const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");
const ts = require("typescript");

const root = path.resolve(__dirname, "..");
function compile(source) {
  return ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
}
const helperContext = { exports: {} };
vm.runInNewContext(compile(readFileSync(path.join(root, "src/lib/print-safety.ts"), "utf8")), helperContext);

test("escapeHtml treats all markup delimiters as text", () => {
  const { escapeHtml } = helperContext.exports;
  assert.equal(escapeHtml(`<>&\"'`), "&lt;&gt;&amp;&quot;&#39;");
  assert.equal(escapeHtml(null), "");
  assert.equal(escapeHtml(123), "123");
});

test("removed signature prototypes cannot render or export simulated evidence", () => {
  const legacy = [
    readFileSync(path.join(root, "src/app/dashboard/assinaturas/page.tsx"), "utf8"),
    readFileSync(path.join(root, "src/app/sign/[id]/page.tsx"), "utf8"),
    readFileSync(path.join(root, "src/app/verify/[id]/page.tsx"), "utf8"),
  ].join("\n");
  assert.match(legacy, /redirect\("\/dashboard\/operacoes"\)/);
  assert.equal((legacy.match(/notFound\(\)/g) || []).length, 2);
  assert.ok(!/jsPDF|hashSha256|auditTrail|CERTIFICADO|simulad/i.test(legacy));
});
