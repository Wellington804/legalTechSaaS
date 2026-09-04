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
  assert.match(source, /Arquivo assinado conferido/);
  assert.match(source, /confirme a validade do certificado antes de usar/);
  assert.match(source, /não passou na conferência e não foi liberado como assinado/);
  assert.doesNotMatch(source, /name=["'](?:pin|pfx|certificate_password)["']/i);
});

test("calendar UI exposes a native Apple webcal subscription", () => {
  const source = readFileSync(path.join(root, "src/components/workspace/calendar.tsx"), "utf8");
  assert.match(source, /replace\(\/\^https\?:\/i, "webcal:"\)/);
  assert.match(source, /Assinar no Calendário Apple/);
  assert.match(source, /somente leitura/);
});

test("communications preserves WhatsApp state and keeps setup details out of lawyer-facing pages", () => {
  const communications = readFileSync(path.join(root, "src/components/workspace/communications.tsx"), "utf8");
  const operations = readFileSync(path.join(root, "src/components/workspace/operations.tsx"), "utf8");
  const integrations = readFileSync(path.join(root, "src/app/dashboard/integrations/page.tsx"), "utf8");
  const navigation = readFileSync(path.join(root, "src/lib/navigation.ts"), "utf8");

  assert.doesNotMatch(communications, /channels\.reload\(\)/);
  assert.doesNotMatch(communications, /VPS|Resend|credenciais/i);
  assert.match(communications, /Temporariamente indisponível/);
  assert.match(communications, /max-h-\[28rem\].*overflow-y-auto/);
  assert.match(operations, /export function OperationsSettings/);
  assert.match(integrations, /<OperationsSettings \/>/);
  assert.match(navigation, /Configurações de serviços.*admin: true/);
});
