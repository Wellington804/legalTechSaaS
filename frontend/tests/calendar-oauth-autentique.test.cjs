const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const root = path.resolve(__dirname, "..");

test("calendar UI offers revocable Google and Microsoft OAuth plus explicit task selection", () => {
  const source = readFileSync(path.join(root, "src/components/workspace/calendar-connections.tsx"), "utf8");
  assert.match(source, /Google Agenda/);
  assert.match(source, /Microsoft Outlook/);
  assert.match(source, /task_ids: selectedTasks/);
  assert.match(source, /calendar-oauth\/\$\{provider\}\/sync/);
  assert.match(source, /api\.delete\(`\/integrations\/calendar-oauth\/\$\{provider\}`\)/);
  assert.match(source, /iPhone ou iPad/);
  assert.match(source, /expected_local_revision: conflict\.local\.revision/);
  assert.match(source, /expected_remote_hash: conflict\.remote_hash/);
  assert.match(source, /Dados enviados ao provedor/);
  assert.match(source, /Versão no LexFlow/);
  assert.match(source, /Versão na agenda externa/);
  assert.doesNotMatch(source, /client_secret|icloud_password|caldav_password/i);
});

test("signature UI exposes Autentique without collecting PFX or PIN", () => {
  const source = readFileSync(path.join(root, "src/components/workspace/operations.tsx"), "utf8");
  assert.match(source, /<option value="autentique">Autentique<\/option>/);
  assert.match(source, /certificado A1\/A3 e PIN.*nunca passam pelo LexFlow/i);
  assert.doesNotMatch(source, /name=["'](?:pin|pfx|certificate_password|private_key)["']/i);
});
