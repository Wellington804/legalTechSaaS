const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const root = path.resolve(__dirname, "..");

test("signature UI requests ICP-Brasil through Clicksign without collecting certificate secrets", () => {
  const source = readFileSync(path.join(root, "src/components/workspace/operations.tsx"), "utf8");
  assert.match(source, /Certificado ICP-Brasil A1\/A3/);
  assert.match(source, /request_key: requestKey/);
  assert.match(source, /setRequestKey\(crypto\.randomUUID\(\)\)/);
  assert.match(source, /signature-envelopes\/\$\{item\.id\}\/download/);
  assert.match(source, /window\.location\.origin}\/api\/v1\/operations\/webhooks\/signatures/);
  assert.doesNotMatch(source, /name=["'](?:pin|pfx|certificate_password)["']/i);
});

test("calendar UI exposes a native Apple webcal subscription", () => {
  const source = readFileSync(path.join(root, "src/components/workspace/calendar.tsx"), "utf8");
  assert.match(source, /replace\(\/\^https\?:\/i, "webcal:"\)/);
  assert.match(source, /Assinar no Calendário Apple/);
  assert.match(source, /somente leitura/);
});
