const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { test } = require('node:test');
const ts = require('typescript');

// Exercise the actual TypeScript helpers with Node's built-in test runner.
require.extensions['.ts'] = (module, filename) => {
  module._compile(ts.transpileModule(readFileSync(filename, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText, filename);
};

test('API origin, credentials, safe retries and empty responses', async () => {
  const originalFetch = global.fetch;
  const previousUrl = process.env.NEXT_PUBLIC_API_URL;
  process.env.NEXT_PUBLIC_API_URL = 'http://localhost:8000/api/v1/';
  const modulePath = require.resolve('../src/lib/api-client.ts');
  delete require.cache[modulePath];
  const { api, API_BASE_URL, API_ORIGIN } = require(modulePath);
  try {
    assert.equal(API_BASE_URL, 'http://localhost:8000/api/v1');
    assert.equal(`${API_ORIGIN}/readyz`, 'http://localhost:8000/readyz');
    let calls = 0;
    global.fetch = async (url, options) => {
      calls++;
      assert.equal(url, `${API_BASE_URL}/example`);
      assert.equal(options.credentials, 'include');
      assert.equal(options.cache, 'no-store');
      assert.equal(options.headers.get('X-Test'), 'yes');
      return calls === 1 ? new Response('{}', { status: 503 }) : Response.json({ ok: true });
    };
    assert.deepEqual(await api.get('/example', { backoffMs: 0, headers: new Headers({ 'X-Test': 'yes' }) }), { ok: true });
    assert.equal(calls, 2);

    for (const method of ['post', 'put', 'delete']) {
      calls = 0;
      global.fetch = async () => { calls++; throw new TypeError('Response lost after commit'); };
      await assert.rejects(() => method === 'delete'
        ? api.delete('/example', { retries: 3, backoffMs: 0 })
        : api[method]('/example', {}, { retries: 3, backoffMs: 0 }));
      assert.equal(calls, 1, `${method} must not repeat a potentially committed write`);
    }
    calls = 0;
    global.fetch = async () => { calls++; return Response.json({ detail: 'unauthorized' }, { status: 401 }); };
    await assert.rejects(() => api.get('/example', { backoffMs: 0 }), { status: 401 });
    assert.equal(calls, 1);
    global.fetch = async () => new Response(null, { status: 204 });
    assert.equal(await api.post('/auth/logout', {}), undefined);

    delete process.env.NEXT_PUBLIC_API_URL;
    delete require.cache[modulePath];
    const sameOrigin = require(modulePath);
    assert.equal(sameOrigin.API_BASE_URL, '/api/v1');
    assert.equal(`${sameOrigin.API_ORIGIN}/readyz`, '/readyz');
  } finally {
    global.fetch = originalFetch;
    if (previousUrl === undefined) delete process.env.NEXT_PUBLIC_API_URL;
    else process.env.NEXT_PUBLIC_API_URL = previousUrl;
    delete require.cache[modulePath];
  }
});

test('Sentry removes sensitive request and metadata from real helper', () => {
  const { scrubSentryEvent } = require('../src/lib/sentry-config.ts');
  const event = scrubSentryEvent({
    request: { url: 'https://username:password@example.test/path?token=SECRET#SECRET', headers: { authorization: 'SECRET' }, data: { body: 'SECRET' } },
    extra: { instanceToken: 'SECRET' }, breadcrumbs: [{ message: 'SECRET' }],
    user: { id: 'internal-id', email: 'client@example.test' },
  });
  assert.ok(!JSON.stringify(event).includes('SECRET'));
  assert.equal(event.request.url, 'https://example.test/path');
  assert.deepEqual(event.user, { id: 'internal-id' });
});

test('removed prototype routes fail closed permanently', () => {
  const { NextRequest } = require('next/server');
  const { proxy } = require('../src/proxy.ts');
  for (const path of ['/sign/test', '/verify/test', '/dashboard/simulator', '/oab-hub']) {
    const response = proxy(new NextRequest(`http://localhost:3000${path}`));
    assert.equal(response.status, 307);
    assert.equal(response.headers.get('location'), 'http://localhost:3000/dashboard');
  }
  for (const path of ['/portal', '/dashboard/crm', '/dashboard/tasks', '/dashboard/cases/test', '/dashboard/account']) {
    assert.equal(proxy(new NextRequest(`http://localhost:3000${path}`)).status, 200);
  }
  assert.equal(proxy(new NextRequest('http://localhost:3000/api/ai/generate')).status, 404);
});
