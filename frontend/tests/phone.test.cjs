const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { test } = require('node:test');
const ts = require('typescript');

require.extensions['.ts'] = (module, filename) => {
  module._compile(ts.transpileModule(readFileSync(filename, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText, filename);
};

test('formats Brazilian phone input, including pasted E.164 values', () => {
  const { formatBrazilianPhone } = require('../src/lib/phone.ts');
  assert.equal(formatBrazilianPhone('11999999999'), '(11) 99999-9999');
  assert.equal(formatBrazilianPhone('+55 (11) 99999-9999'), '(11) 99999-9999');
  assert.equal(formatBrazilianPhone('5511999999999'), '(11) 99999-9999');
  assert.equal(formatBrazilianPhone('011999999999'), '(11) 99999-9999');
  assert.equal(formatBrazilianPhone('+14155552671'), '+14155552671');
});
