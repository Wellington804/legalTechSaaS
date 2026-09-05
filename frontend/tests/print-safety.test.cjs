const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const root = path.resolve(__dirname, "..");

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
