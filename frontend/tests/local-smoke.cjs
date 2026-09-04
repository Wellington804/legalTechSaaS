// Opt-in, real local application. Creates uniquely named local verification records.
// External providers are never invoked; no emails, WhatsApp messages or signatures.
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

function totp(secret, offsetSeconds = 0) {
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567'; let bits = '';
  for (const character of secret.replace(/=+$/, '').toUpperCase()) bits += alphabet.indexOf(character).toString(2).padStart(5, '0');
  const key = Buffer.from((bits.match(/.{8}/g) || []).map(byte => parseInt(byte, 2)));
  const counter = Buffer.alloc(8); counter.writeBigUInt64BE(BigInt(Math.floor((Date.now() + offsetSeconds * 1000) / 30000)));
  const digest = crypto.createHmac('sha1', key).update(counter).digest(); const offset = digest[19] & 15;
  return ((digest.readUInt32BE(offset) & 0x7fffffff) % 1000000).toString().padStart(6, '0');
}

(async () => {
  const base = process.env.AUDIT_FRONTEND_URL || 'http://localhost:3000';
  const api = process.env.AUDIT_API_URL || 'http://localhost:8000/api/v1';
  assert.equal(new URL(base).hostname, 'localhost', 'Local smoke only');
  assert.equal(new URL(api).hostname, 'localhost', 'Local smoke only');
  let email = process.env.AUDIT_LOGIN_EMAIL; let password = process.env.AUDIT_LOGIN_PASSWORD; let totpSecret = process.env.AUDIT_TOTP_SECRET;
  if (process.env.AUDIT_REGISTER === 'true') { const stamp = Date.now(); email = `e2e+${stamp}@example.com`; password = `E2e!${stamp}SafePassword`; }
  assert.ok(email && password, 'Provide local test credentials or AUDIT_REGISTER=true');
  const browser = await chromium.launch({ headless: true });
  try {
    const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    const origin = { Origin: new URL(base).origin };
    if (process.env.AUDIT_REGISTER === 'true') {
      const registered = await context.request.post(`${api}/auth/register`, { headers: origin, data: { full_name: 'Advogada E2E', email, password, tenant_name: `Escritório E2E ${Date.now()}`, oab_number: 'TESTE', oab_uf: 'SP' } });
      assert.equal(registered.status(), 201, await registered.text());
      const setup = await context.request.post(`${api}/account/mfa/setup`, { headers: origin, data: {} });
      assert.equal(setup.status(), 200, await setup.text()); totpSecret = (await setup.json()).secret;
      const confirmed = await context.request.post(`${api}/account/mfa/confirm`, { headers: origin, data: { code: totp(totpSecret, -30) } });
      assert.equal(confirmed.status(), 200, await confirmed.text());
      assert.equal((await context.request.post(`${api}/auth/logout`, { headers: origin })).status(), 204);
    }
    const login = await context.request.post(`${api}/auth/login`, { headers: origin, data: { email, password, ...(totpSecret ? { otp_code: totp(totpSecret) } : {}) } });
    assert.equal(login.status(), 200, await login.text());
    const profile = await login.json(); assert.ok(!('access_token' in profile));
    assert.equal((await context.cookies()).find(cookie => cookie.name === 'lexflow_session').httpOnly, true);
    const privacy = await context.request.patch(`${api}/account/privacy`, { headers: origin, data: { privacy_notice_url: 'https://example.com/privacy', privacy_notice_version: 'e2e-v1', privacy_contact: 'privacy@example.com', data_retention_days: 365 } });
    assert.equal(privacy.status(), 200, await privacy.text()); assert.equal((await privacy.json()).configured, true);
    const privacyRequest = await context.request.post(`${api}/account/privacy/requests`, { headers: origin, data: { request_type: 'export', scope: 'self', reason: 'Validação E2E' } });
    assert.equal(privacyRequest.status(), 202, await privacyRequest.text());
    const privacyRecord = await privacyRequest.json(); const listedPrivacy = await (await context.request.get(`${api}/account/privacy/requests`)).json();
    assert.ok(listedPrivacy.some(item => item.id === privacyRecord.id));
    const page = await context.newPage(); const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(`${base}/dashboard`);
    await page.getByRole('heading', { name: 'Painel Diário', exact: true }).waitFor();
    await page.getByText('Carregando registros…').first().waitFor({ state: 'hidden' });
    await page.keyboard.press('Control+k');
    await page.getByRole('dialog').waitFor();
    assert.equal(await page.getByRole('dialog').count(), 1);
    await page.keyboard.press('Escape');

    const label = `Verificação local ${Date.now()}`;
    await page.goto(`${base}/dashboard/crm`);
    await page.getByRole('button', { name: 'Cadastrar cliente', exact: true }).click();
    await page.getByLabel('Nome / razão social').fill(label);
    await page.getByLabel('Etapa').selectOption('client');
    const clientSaved = page.waitForResponse(response => response.url().endsWith('/workspace/clients') && response.request().method() === 'POST');
    await page.getByRole('button', { name: 'Cadastrar cliente', exact: true }).last().click();
    const clientResponse = await clientSaved;
    assert.equal(clientResponse.status(), 201, await clientResponse.text());
    const client = await clientResponse.json();
    await page.reload(); await page.getByText(label, { exact: true }).waitFor();

    await page.goto(`${base}/dashboard/tracker`);
    await page.getByRole('button', { name: 'Novo processo', exact: true }).click();
    await page.getByLabel('Cliente', { exact: true }).selectOption(client.id);
    await page.getByLabel('Assunto do processo').fill(`${label} — caso`);
    const caseSaved = page.waitForResponse(response => response.url().endsWith('/workspace/cases') && response.request().method() === 'POST');
    await page.getByRole('button', { name: 'Salvar processo', exact: true }).click();
    const caseResponse = await caseSaved;
    assert.equal(caseResponse.status(), 201, await caseResponse.text());
    const caseRecord = await caseResponse.json();
    await page.goto(`${base}/dashboard/cases/${caseRecord.id}`);
    await page.getByRole('heading', { name: `${label} — caso`, exact: true }).waitFor();

    await page.goto(`${base}/dashboard/petitions/editor`);
    await page.getByRole('button', { name: 'Criar documento', exact: true }).click();
    await page.getByRole('button', { name: 'Começar em branco', exact: true }).click();
    await page.getByLabel('Processo', { exact: true }).selectOption(caseRecord.id);
    await page.getByLabel('Título', { exact: true }).fill(`${label} — documento`);
    await page.getByRole('textbox', { name: 'Texto do documento' }).fill('Texto de verificação persistido no banco.');
    const documentSaved = page.waitForResponse(response => response.url().endsWith('/workspace/documents') && response.request().method() === 'POST');
    await page.getByRole('button', { name: 'Salvar documento', exact: true }).click();
    const documentResponse = await documentSaved; assert.equal(documentResponse.status(), 201); const document = await documentResponse.json();
    await page.reload();
    await page.getByRole('button', { name: 'Criar documento', exact: true }).click();
    await page.getByText(`${label} — documento`, { exact: false }).waitFor();

    const task = await context.request.post(`${api}/workspace/tasks`, { headers: origin, data: { case_id: caseRecord.id, title: `${label} — prazo`, kind: 'deadline', due_at: new Date(Date.now() + 86400000).toISOString(), assigned_user_id: profile.user_id, status: 'pending', manually_reviewed: true } });
    assert.equal(task.status(), 201, await task.text());
    const fees = await context.request.post(`${api}/operations/fee-contracts`, { headers: origin, data: { client_id: client.id, case_id: caseRecord.id, document_id: document.id, title: `${label} — honorários`, currency: 'BRL', terms_version: 'e2e-v1' } });
    assert.equal(fees.status(), 201, await fees.text());

    for (const path of ['/dashboard', '/dashboard/tasks', '/dashboard/crm', '/dashboard/account']) {
      await page.setViewportSize({ width: 375, height: 812 });
      await page.goto(base + path);
      await page.getByRole('heading', { level: 1 }).waitFor();
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `${path} overflows 375px`);
    }
    await page.goto(`${base}/dashboard/assinaturas`);
    await page.waitForURL('**/dashboard/operacoes');
    await page.getByRole('heading', { name: 'Atendimento e honorários', exact: true }).waitFor();
    assert.deepEqual(errors, []);
    const logout = await context.request.post(`${api}/auth/logout`, { headers: origin });
    assert.equal(logout.status(), 204);
    assert.equal((await context.request.get(`${api}/auth/me`)).status(), 401);
    console.log('PASS: cadastro, MFA, privacidade, cliente, caso, documento, prazo, honorários, responsividade, gate de protótipo e logout em PostgreSQL real.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error.message); process.exitCode = 1; });
