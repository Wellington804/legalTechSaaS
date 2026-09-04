// Contract UI smoke: runs the built Next bundle against local, in-browser
// /api/v1 fixtures only. It is deliberately not an API/DB/provider E2E test.
const assert = require("node:assert/strict");
const { chromium } = require(
  process.env.PLAYWRIGHT_MODULE ||
    "C:/Users/maxue/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright"
);

const baseUrl = process.env.WORKSPACE_UI_URL || "http://127.0.0.1:3109";
const baseOrigin = new URL(baseUrl).origin;
const apiOrigin = new URL(process.env.WORKSPACE_UI_API_URL || baseUrl).origin;
assert.ok(["127.0.0.1", "localhost"].includes(new URL(apiOrigin).hostname), "local fixture API only");
assert.ok(
  ["127.0.0.1", "localhost"].includes(new URL(baseUrl).hostname),
  "workspace-ui.cjs is restricted to a local Next bundle"
);

const profile = (needsSecuritySetup = false, role = "admin") => ({
  user_id: "user-a",
  user_name: "Ana Advogada",
  email: "ana@example.test",
  role,
  tenant_id: "tenant-a",
  tenant_name: "Escritório Exemplo",
  tenant_cnpj: "12.345.678/0001-99",
  oab_number: "123456",
  oab_uf: "SP",
  email_verified: !needsSecuritySetup,
  email_verification_required: needsSecuritySetup,
  mfa_enabled: !needsSecuritySetup,
  mfa_required: false,
  subscription_status: "trial",
  trial_ends_at: "2026-09-10T00:00:00Z",
});

function fixtureApi() {
  const state = {
    needsSecuritySetup: false,
    role: "admin",
    calls: [],
    unhandled: [],
    clients: [{ id: "client-a", name: "Cliente Exemplo", email: "cliente@example.test", stage: "client" }],
    cases: [{
      id: "case-a", client_id: "client-a", title: "Caso Exemplo", number: "00000000000000000000",
      court: "TJSP", status: "open", responsible_user_id: "user-a", restricted: true, revision: 4,
    }],
    documents: [{
      id: "doc-a", case_id: "case-a", title: "Petição inicial", content_text: "Texto original.",
      kind: "document", current_version: 3, revision: 7, created_at: "2026-08-26T10:00:00Z", updated_at: "2026-08-26T10:00:00Z",
    }],
    messages: [],
    whatsapp: { status: "disconnected", connected: false, number: null, last_checked_at: null },
    dailyTaskCompleted: false,
    dailyNextActionCreated: false,
  };
  const list = (items) => ({ items, limit: 50 });
  const json = (route, status, payload) => route.fulfill({
    status, contentType: "application/json", body: JSON.stringify(payload),
  });
  const requestBody = (request) => {
    const raw = request.postData();
    if (!raw) return null;
    try { return JSON.parse(raw); } catch { return raw; }
  };

  async function handler(route) {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();
    const body = requestBody(request);
    state.calls.push({ method, path, body });

    if (method === "GET" && path === "/api/v1/auth/me") return json(route, 200, profile(state.needsSecuritySetup, state.role));
    if (method === "GET" && path === "/api/v1/push/capabilities") return json(route, 200, { enabled: false, public_key: null });
    if (method === "GET" && path === "/api/v1/push/subscriptions") return json(route, 200, { items: [] });
    if (method === "GET" && path === "/api/v1/routines/attention") return json(route, 200, { cases_without_next_action: [], reminders: [], limit: 50 });
    if (method === "GET" && path === "/api/v1/document-kit/templates") return json(route, 200, { items: [] });
    if (method === "GET" && path === "/api/v1/pilot/feedback") return json(route, 200, { items: [] });
    if (method === "GET" && path === "/api/v1/pilot/overview") return json(route, 200, {
      steps: [{ id: "client", title: "Cadastrar cliente", description: "Cadastro de teste", href: "/dashboard/crm", status: "done" }],
      subscription: { status: "trial", ends_at: "2026-09-10T00:00:00Z", days_remaining: 13, write_allowed: true },
      security: { email_verified: true, mfa_enabled: true, environment: "test", sentry_configured: false, account_email_configured: false, https_configured: false },
      support_url: null, release: "fixture", weekly: { last_report_at: null, next_review_at: "2026-09-04T00:00:00Z" }, data_policy: "fictitious_until_validated",
    });
    if (method === "GET" && path === "/api/v1/workspace/summary") {
      const priorities = [];
      if (!state.dailyTaskCompleted) priorities.push({
        id: "task-a", source: "task", severity: "today", title: "Revisar processo", case_id: "case-a",
        case_title: "Caso Exemplo", task_kind: "task", status: "pending", relevant_at: new Date(Date.now() + 60 * 60 * 1000).toISOString(),
        revision: 1, manually_reviewed: true, detail: null, href: "/dashboard/cases/case-a", actions: ["complete", "reschedule"],
      });
      if (!state.dailyNextActionCreated) priorities.push({
        id: "case-a", source: "case_without_action", severity: "planning", title: "Cadastrar proxima acao", case_id: "case-a",
        case_title: "Caso Exemplo", task_kind: null, status: "open", relevant_at: "2026-08-30T10:00:00Z",
        revision: 4, manually_reviewed: null, detail: null, href: "/dashboard/cases/case-a", actions: ["create_next_action"],
      });
      return json(route, 200, {
        generated_at: new Date().toISOString(), timezone: "America/Sao_Paulo",
        clients: { total: state.clients.length }, cases: { active: 1, waiting_action: state.dailyNextActionCreated ? 0 : 1 },
        tasks: { due_today: state.dailyTaskCompleted ? 0 : 1, overdue: 0, upcoming: 0, hearings_upcoming: 0 },
        priorities, attention: { communication_failures: 0, document_failures: 0, financial_drafts: 0 }, financial: null,
      });
    }
    if (method === "GET" && path === "/api/v1/workspace/analytics") return json(route, 200, {
      cases_by_status: { open: 1, paused: 0, closed: 0, archived: 0 }, workload_next_7_days: { [new Date().toISOString().slice(0, 10)]: 1 }, tasks: {}, clients_by_stage: {}, fees: null,
    });
    if (method === "GET" && path === "/api/v1/workspace/activity") return json(route, 200, list([{ id: "case-a", area: "Processo", message: "O processo Caso Exemplo foi atualizado.", href: "/dashboard/cases/case-a", created_at: "2026-08-30T10:00:00Z" }]));
    if (method === "GET" && path === "/api/v1/workspace/tasks") return json(route, 200, list([{
      id: "task-a", case_id: "case-a", title: "Revisar processo", kind: "task", status: "pending",
      due_at: new Date(Date.now() + 60 * 60 * 1000).toISOString(), manually_reviewed: true,
    }]));
    if (method === "GET" && path === "/api/v1/workspace/publications") return json(route, 200, list([]));
    if (method === "PUT" && path === "/api/v1/workspace/tasks/task-a") {
      state.dailyTaskCompleted = body.status === "completed";
      return json(route, 200, { id: "task-a", revision: 2, ...body });
    }
    if (method === "POST" && path === "/api/v1/workspace/tasks") {
      state.dailyNextActionCreated = true;
      return json(route, 201, { id: "task-created", revision: 1, status: "pending", ...body });
    }
    if (method === "GET" && path === "/api/v1/workspace/clients") return json(route, 200, list(state.clients));
    if (method === "POST" && path === "/api/v1/workspace/clients") return json(route, 201, { id: "client-created", ...body });
    if (method === "GET" && path === "/api/v1/workspace/cases") return json(route, 200, list(state.cases));
    if (method === "POST" && path === "/api/v1/workspace/cases") return json(route, 201, { id: "case-created", ...body });
    if (method === "GET" && path === "/api/v1/workspace/members") return json(route, 200, list([{
      id: "user-a", full_name: "Ana Advogada", email: "ana@example.test", role: "admin",
    }, { id: "user-b", full_name: "Bruno Parceiro", email: "bruno@example.test", role: "partner" }]));
    if (method === "GET" && path === "/api/v1/workspace/cases/case-a") return json(route, 200, { case: state.cases[0] });
    if (method === "GET" && path === "/api/v1/workspace/cases/case-a/parties") return json(route, 200, list([{
      id: "party-a", name: "Cliente Exemplo", side: "client", role: "Autor",
    }]));
    if (method === "POST" && path === "/api/v1/workspace/cases/case-a/parties") return json(route, 201, { id: "party-created", ...body });
    if (method === "GET" && path === "/api/v1/workspace/cases/case-a/access") return json(route, 200, list([{ user_id: "user-b" }]));
    if (method === "POST" && path === "/api/v1/workspace/cases/case-a/access") return json(route, 204, null);
    if (method === "DELETE" && path.startsWith("/api/v1/workspace/cases/case-a/access/")) return json(route, 204, null);
    if (method === "GET" && path === "/api/v1/workspace/documents") return json(route, 200, list(state.documents));
    if (method === "GET" && path === "/api/v1/workspace/document-storage") return json(route, 200, { direct_uploads: false });
    if (method === "GET" && path === "/api/v1/workspace/document-folders") return json(route, 200, list([]));
    if (method === "GET" && path === "/api/v1/workspace/templates") return json(route, 200, list([{
      id: "template-a", title: "Modelo básico", content_text: "Modelo", current_version: 1,
    }]));
    if (method === "POST" && path === "/api/v1/workspace/documents") {
      const created = {
        id: "doc-created", current_version: 1, revision: 1, created_at: "2026-08-27T10:00:00Z",
        updated_at: "2026-08-27T10:00:00Z", ...body,
      };
      state.documents.push(created);
      return json(route, 201, created);
    }
    if (method === "PUT" && path === "/api/v1/workspace/documents/doc-a") {
      Object.assign(state.documents[0], body, { current_version: 4, revision: 8 });
      return json(route, 200, state.documents[0]);
    }
    if (method === "GET" && path === "/api/v1/account/profile") return json(route, 200, profile(state.needsSecuritySetup, state.role));
    if (method === "GET" && path === "/api/v1/account/team") return json(route, 200, [{
      id: "user-a", full_name: "Ana Advogada", email: "ana@example.test", role: "admin", is_active: true,
    }, { id: "user-b", full_name: "Bruno Parceiro", email: "bruno@example.test", role: "partner", is_active: true }]);
    if (method === "GET" && path === "/api/v1/account/team/invites") return json(route, 200, list([{
      id: "invite-a", email: "pendente@example.test", role: "lawyer", expires_at: "2026-09-03T10:00:00Z",
    }]));
    if (method === "GET" && path === "/api/v1/account/subscription") return json(route, 200, {
      plan: "trial", status: "trial", trial_starts_at: "2026-08-27T00:00:00Z", trial_ends_at: "2026-09-10T00:00:00Z",
      subscription_ends_at: null, cancel_at_period_end: false, quota_users: 3, active_users: 1,
      quota_storage_bytes: 1048576, storage_used_bytes: 512, quota_messages: 100, messages_used: 2,
      cancellation_request_pending: false,
    });
    if (method === "GET" && path === "/api/v1/engagement/channels") return json(route, 200, {
      whatsapp: state.whatsapp,
    });
    if (method === "POST" && path === "/api/v1/engagement/whatsapp/connect") {
      state.whatsapp = { status: "pending", connected: false, number: null, last_checked_at: new Date().toISOString() };
      return json(route, 200, { whatsapp: state.whatsapp, qr_code: "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=" });
    }
    if (method === "GET" && path === "/api/v1/engagement/whatsapp/qr") return json(route, 200, { qr_code: "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=" });
    if (method === "POST" && path === "/api/v1/engagement/whatsapp/reconnect") return json(route, 200, { whatsapp: state.whatsapp });
    if (method === "DELETE" && path === "/api/v1/engagement/whatsapp/connection") {
      state.whatsapp = { status: "disconnected", connected: false, number: null, last_checked_at: new Date().toISOString() };
      return route.fulfill({ status: 204, body: "" });
    }
    if (method === "GET" && path === "/api/v1/audit/logs") return json(route, 200, [{
      id: "audit-a", action: "CASE_UPDATED", area: "processos", actor_name: "Ana Advogada",
      message: "Ana Advogada atualizou o processo Caso Exemplo.", created_at: new Date().toISOString(), metadata: { case_id: "case-a" },
    }]);
    if (method === "POST" && path === "/api/v1/engagement/assistant") return json(route, 200, {
      text: "Rascunho contextual para revisão.", sources: [],
      limitations: ["Resposta não salva."], review_required: true, saved: false,
    });
    if (method === "POST" && path === "/api/v1/engagement/assistant/chat") return json(route, 200, {
      text: "Rascunho contextual para revisão.", sources: [], limitations: ["Resposta não salva."],
      review_required: true, saved: false, conversation_id: "conversation-a",
      conversation: { id: "conversation-a", title: "Conversa", context_kind: "global", retention_days: 90, message_count: 2, updated_at: new Date().toISOString() },
    });
    if (method === "POST" && path === "/api/v1/engagement/cases/case-a/evidence-matrix") return json(route, 200, {
      matrix: {
        facts: [{ id: "F1", statement: "O documento registra o inadimplemento.", status: "supported", source_ids: ["D1-N1"], review_note: "Conferir o original.", human_review_required: true }],
        evidence: [], legal_bases: [{ id: "B1", statement: "Fundamento ainda não confirmado.", status: "unverified", source_ids: [], review_note: "Selecionar fonte oficial.", human_review_required: true }],
        requests: [{ id: "P1", statement: "Avaliar o pedido de cobrança.", status: "supported", source_ids: ["D1-N1"], review_note: "Delimitar o pedido.", human_review_required: true }],
        gaps: ["Fonte jurídica oficial."], conflicts: [], limitations: ["Somente os documentos selecionados."], human_review_required: true,
      },
      snapshots: [{ document_id: "doc-a", version: 4, sha256: "a".repeat(64) }],
      sources: [{ id: "D1-N1", kind: "document", document_id: "doc-a", title: "Petição revista", version: 4, page: null, paragraph: 1, locator: "§ 1", excerpt: "Texto revisado." }],
      coverage: { documents: 1, source_characters: 15, total_content_characters: 15, truncated: false },
      source_query: body.instructions, provider: "openrouter", model: "legal-model", review_required: true, saved: false,
    });
    if (method === "POST" && path === "/api/v1/engagement/cases/case-a/guided-draft") return json(route, 200, {
      title: "Minuta de cobrança", content_markdown: "# Minuta de cobrança\n\nTexto para revisão [D1-N1].",
      verification: { verdict: "needs_review", issues: [], checked_source_ids: ["D1-N1"], summary: "Fontes conferidas automaticamente; revisão profissional pendente.", human_review_required: true },
      sources: [], snapshots: body.snapshots, provider: "openrouter", generator_model: "legal-model", verifier_model: "deep-model",
      model_independent: true, review_required: true, saved: false, stale: false,
    });
    if (method === "GET" && path === "/api/v1/engagement/cases/case-a/messages") return json(route, 200, list(state.messages));
    if (method === "POST" && path === "/api/v1/engagement/cases/case-a/messages") {
      const created = { id: `message-${state.messages.length + 1}`, direction: "outbound", status: "recorded", created_at: "2026-08-27T10:00:00Z", ...body };
      state.messages.push(created);
      return json(route, 202, created);
    }
    if (method === "GET" && path === "/api/v1/engagement/cases/case-a/checklist") return json(route, 200, list([]));
    if (method === "GET" && path === "/api/v1/engagement/cases/case-a/portal-invites") return json(route, 200, list([]));
    if (method === "GET" && path === "/api/v1/engagement/cases/case-a/folder-shares") return json(route, 200, list([]));
    if (method === "POST" && path === "/api/v1/engagement/cases/case-a/portal-invites") return json(route, 201, { invite_link: "https://portal.example.test/access" });
    if (method === "POST" && path === "/api/v1/engagement/cases/case-a/checklist") return json(route, 201, { id: "check-a", ...body });
    if (method === "POST" && path === "/api/v1/account/mfa/setup") return json(route, 200, { secret: "TESTSECRET", provisioning_uri: "otpauth://totp/test" });
    if (method === "POST" && path === "/api/v1/account/mfa/confirm") return json(route, 200, { recovery_codes: ["recovery-code"] });
    if (method === "PATCH" && path === "/api/v1/account/profile") return json(route, 200, profile(state.needsSecuritySetup, state.role));
    if (method === "PATCH" && path === "/api/v1/account/office") return json(route, 200, profile(state.needsSecuritySetup, state.role));
    if (method === "POST" && path.startsWith("/api/v1/account/")) return json(route, 202, { status: "received" });
    if (method === "GET" && path === "/api/v1/controladoria/providers") return json(route, 200, [
      { source_kind: "datajud", label: "DataJud", configured: false, homologation_required: false, detail: "Não configurada." },
      { source_kind: "escavador", label: "Escavador", configured: false, homologation_required: true, detail: "Homologação obrigatória." },
      { source_kind: "djen", label: "DJEN", configured: true, homologation_required: false, detail: "API pública oficial." },
      { source_kind: "domicilio", label: "Domicílio Judicial Eletrônico", configured: false, homologation_required: true, detail: "Credencial do CNJ necessária." },
      { source_kind: "tribunal_api", label: "API específica do tribunal", configured: false, homologation_required: true, detail: "Contrato necessário." },
    ]);
    if (method === "GET" && [
      "/api/v1/controladoria/subscriptions", "/api/v1/controladoria/events", "/api/v1/controladoria/deadlines",
      "/api/v1/controladoria/deadline-rules", "/api/v1/controladoria/calendar-exceptions",
      "/api/v1/controladoria/workflow-templates", "/api/v1/controladoria/workflows", "/api/v1/operations/intakes",
      "/api/v1/operations/fee-contracts", "/api/v1/operations/invoices", "/api/v1/operations/time-entries",
      "/api/v1/operations/provider-credentials", "/api/v1/operations/signature-providers",
    ].includes(path)) return json(route, 200, list([]));
    if (method === "GET" && path === "/api/v1/operations/intake-config") return json(route, 404, { detail: "Formulário ainda não configurado." });
    if (method === "GET" && path === "/api/v1/integrations/status") return json(route, 200, {
      calendar_export: { status: "available", format: "ics" }, datajud: { status: "not_configured" },
      email: { status: "not_configured" }, whatsapp: { status: "not_configured" },
      ai: { status: "not_configured", provider: "openrouter" }, sentry: { status: "not_configured" },
    });

    state.unhandled.push(`${method} ${path}`);
    return json(route, 404, { detail: `Unmocked UI-contract request: ${method} ${path}` });
  }
  return { state, handler };
}

async function assertNoHorizontalOverflow(page, path) {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto(new URL(path, baseUrl).href);
  await page.getByRole("heading", { level: 1 }).waitFor();
  assert.ok(
    await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1),
    `${path} overflows at 375px`
  );
}

async function recordedCall(state, predicate, description) {
  for (let attempt = 0; attempt < 40; attempt += 1) {
    const match = [...state.calls].reverse().find(predicate);
    if (match) return match;
    await new Promise((resolve) => setTimeout(resolve, 25));
  }
  assert.fail(`Missing UI-contract request: ${description}`);
}

if (require.main === module) (async () => {
  const browser = await chromium.launch({ headless: true });
  const api = fixtureApi();
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 960 } });
    await context.route("**/*", async (route) => {
      if (![baseOrigin, apiOrigin].includes(new URL(route.request().url()).origin)) return route.abort("blockedbyclient");
      return route.fallback();
    });
    await context.route(`${apiOrigin}/api/v1/**`, api.handler);
    const page = await context.newPage();
    page.setDefaultTimeout(7000);
    page.setDefaultNavigationTimeout(10000);
    const pageErrors = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));

    await page.goto(`${baseUrl}/dashboard`);
    await page.getByRole("heading", { name: "Painel Diário", exact: true }).waitFor();
    await page.getByText("Revisar processo", { exact: true }).waitFor();
    await page.getByRole("button", { name: "Concluir", exact: true }).click();
    await page.getByText("Ação concluída e registrada no histórico.", { exact: true }).waitFor();
    assert.deepEqual((await recordedCall(api.state, call => call.method === "PUT" && call.path === "/api/v1/workspace/tasks/task-a", "complete daily task")).body, {
      status: "completed", expected_revision: 1,
    });
    await page.getByRole("button", { name: "Cadastrar próxima ação", exact: true }).click();
    await page.getByLabel("Próxima ação", { exact: true }).fill("Enviar manifestação");
    await page.getByLabel("Data e horário local", { exact: true }).fill("2026-09-02T09:30");
    await page.getByRole("button", { name: "Salvar", exact: true }).click();
    await page.getByText("Próxima ação cadastrada e vinculada ao processo.", { exact: true }).waitFor();
    const dailyCreate = await recordedCall(api.state, call => call.method === "POST" && call.path === "/api/v1/workspace/tasks", "create next daily action");
    assert.equal(dailyCreate.body.case_id, "case-a");
    assert.equal(dailyCreate.body.title, "Enviar manifestação");
    assert.equal(dailyCreate.body.assigned_user_id, "user-a");
    assert.match(dailyCreate.body.request_id, /^[0-9a-f-]{36}$/i);
    await page.getByRole("button", { name: "Abrir Assistente LexFlow", exact: true }).click();
    await page.getByRole("dialog", { name: "Assistente LexFlow" }).waitFor();
    const prepare = page.getByRole("button", { name: "Enviar mensagem", exact: true });
    assert.equal(await prepare.isDisabled(), true, "IA contextual exige um pedido explícito");
    await page.getByLabel("Mensagem para o assistente", { exact: true }).fill("Organize os próximos passos informados.");
    await prepare.click();
    await page.getByText("Rascunho contextual para revisão.", { exact: true }).waitFor();
    await page.getByRole("button", { name: "Fechar assistente", exact: true }).click();

    await page.goto(`${baseUrl}/dashboard/crm`);
    await page.getByRole("heading", { name: "Clientes e oportunidades", exact: true }).waitFor();
    await page.getByText("Cliente Exemplo", { exact: true }).waitFor();

    await page.goto(`${baseUrl}/dashboard/tracker`);
    await page.getByRole("heading", { name: "Processos", exact: true }).waitFor();
    await page.getByRole("link", { name: "Abrir processo", exact: true }).waitFor();
    await page.getByRole("button", { name: "Novo processo", exact: true }).click();
    await page.locator('select[name="responsible_user_id"]').waitFor();
    assert.equal(
      await page.locator('select[name="responsible_user_id"]').inputValue(),
      "user-a",
      "the asynchronously loaded eligible-member selector preserves the current user default"
    );
    const subject = page.getByLabel("Assunto do processo", { exact: true });
    await subject.fill("Consultoria societária preservada");
    await page.getByRole("button", { name: "+ Novo cliente", exact: true }).click();
    let clientDialog = page.getByRole("dialog", { name: "Novo cliente", exact: true });
    await clientDialog.waitFor();
    assert.equal(await clientDialog.getByLabel("Nome / razão social", { exact: true }).count(), 1);
    assert.equal(await clientDialog.getByLabel("CPF/CNPJ", { exact: true }).count(), 1);
    assert.equal(await clientDialog.getByLabel("E-mail", { exact: true }).count(), 1);
    assert.equal(await clientDialog.getByLabel("WhatsApp", { exact: true }).count(), 1);
    assert.equal(await clientDialog.getByLabel("Etapa", { exact: true }).count(), 1);
    await clientDialog.getByRole("button", { name: "Cancelar", exact: true }).click();
    assert.equal(await subject.inputValue(), "Consultoria societária preservada");
    await page.getByRole("button", { name: "+ Novo cliente", exact: true }).click();
    clientDialog = page.getByRole("dialog", { name: "Novo cliente", exact: true });
    await clientDialog.getByLabel("Nome / razão social", { exact: true }).fill("Cliente criado no processo");
    await clientDialog.getByLabel("CPF/CNPJ", { exact: true }).fill("12345678901");
    await clientDialog.getByLabel("E-mail", { exact: true }).fill("novo@example.test");
    await clientDialog.getByLabel("WhatsApp", { exact: true }).fill("11988887777");
    await clientDialog.getByLabel("Etapa", { exact: true }).selectOption("client");
    await clientDialog.getByRole("button", { name: "Cadastrar e selecionar", exact: true }).click();
    await clientDialog.waitFor({ state: "detached" });
    await page.waitForFunction(() => document.querySelector('select[name="client_id"]')?.value === "client-created");
    assert.equal(await page.locator('select[name="client_id"]').inputValue(), "client-created");
    assert.equal(await subject.inputValue(), "Consultoria societária preservada");
    const quickClient = await recordedCall(api.state, call => call.method === "POST" && call.path === "/api/v1/workspace/clients", "quick-create client from process");
    assert.deepEqual({ name: quickClient.body.name, tax_id: quickClient.body.tax_id, email: quickClient.body.email, stage: quickClient.body.stage }, {
      name: "Cliente criado no processo", tax_id: "12345678901", email: "novo@example.test", stage: "client",
    });

    const existingClients = api.state.clients;
    api.state.clients = [];
    await page.goto(`${baseUrl}/dashboard/tracker`);
    await page.getByRole("button", { name: "Novo processo", exact: true }).click();
    await page.getByText("Nenhum cliente cadastrado.", { exact: true }).waitFor();
    await page.getByText("Cadastre o cliente para continuar com o processo.", { exact: true }).waitFor();
    await page.getByRole("button", { name: "Cadastrar primeiro cliente", exact: true }).waitFor();
    api.state.clients = existingClients;

    await page.goto(`${baseUrl}/dashboard/cases/case-a`);
    await page.getByRole("heading", { name: "Caso Exemplo", exact: true }).waitFor();
    await page.getByRole("navigation", { name: "O que deseja consultar neste processo" }).waitFor();
    await page.getByRole("heading", { name: "Acesso ao processo restrito", exact: true }).waitFor();
    await page.getByRole("button", { name: "Gerenciar partes", exact: true }).click();
    await page.getByLabel("Nome", { exact: true }).fill("Parte de teste");
    await page.getByRole("button", { name: "Salvar parte", exact: true }).click();
    assert.deepEqual((await recordedCall(api.state, (call) => (
      call.method === "POST" && call.path === "/api/v1/workspace/cases/case-a/parties"
    ), "create case party")).body, {
      name: "Parte de teste", tax_id: null, side: "client", role: null,
    });
    await page.getByRole("button", { name: "Arquivos", exact: true }).click();
    await page.getByRole("region", { name: "Central de arquivos", exact: true }).waitFor();
    assert.equal(await page.locator("main h1").count(), 1, "Processo 360 não deve aninhar uma segunda página");

    await page.goto(`${baseUrl}/dashboard/petitions/editor`);
    await page.getByRole("heading", { name: "Central de Arquivos", exact: true }).waitFor();
    await page.getByRole("button", { name: "Criar documento", exact: true }).click();
    await page.getByRole("button", { name: "Começar em branco", exact: true }).click();
    await page.getByLabel("Título", { exact: true }).fill("Documento novo");
    await page.locator('select[name="case_id"]').selectOption("case-a");
    await page.locator('textarea[name="content_text"]').fill("Conteúdo novo.");
    await page.getByRole("button", { name: "Salvar documento", exact: true }).click();
    assert.deepEqual((await recordedCall(api.state, (call) => (
      call.method === "POST" && call.path === "/api/v1/workspace/documents"
    ), "create document")).body, {
      title: "Documento novo", case_id: "case-a", kind: "document", document_type: "general", content_text: "Conteúdo novo.", content_format: "plain",
    });
    await page.getByRole("button", { name: "Editar documento", exact: true }).first().click();
    await page.getByLabel("Título", { exact: true }).fill("Petição revista");
    await page.locator('textarea[name="content_text"]').fill("Texto revisado.");
    await page.getByRole("button", { name: "Salvar nova versão", exact: true }).click();
    assert.deepEqual((await recordedCall(api.state, (call) => (
      call.method === "PUT" && call.path === "/api/v1/workspace/documents/doc-a"
    ), "update document")).body, {
      title: "Petição revista", content_text: "Texto revisado.", content_format: "plain", expected_version: 3, expected_revision: 7,
    });
    await page.getByRole("button", { name: "Analisar e preparar com IA", exact: true }).click();
    await page.getByLabel("Processo", { exact: true }).selectOption("case-a");
    await page.getByRole("checkbox", { name: /Petição revista/ }).check();
    await page.getByLabel(/Autorizo o envio destes documentos/).check();
    await page.getByRole("button", { name: "Gerar matriz para revisão", exact: true }).click();
    await page.getByText("F1 · Com fonte", { exact: true }).waitFor();
    await page.getByLabel("Aprovar F1", { exact: true }).check();
    await page.getByLabel("Aprovar P1", { exact: true }).check();
    await page.getByLabel(/Revisei os fatos e pedidos marcados/).check();
    await page.getByRole("button", { name: "Gerar minuta e verificar", exact: true }).click();
    await page.getByText("Verificação concluída — revisão humana pendente", { exact: true }).waitFor();
    await page.getByRole("button", { name: "Salvar como rascunho", exact: true }).click();
    await page.getByText("Minuta salva como rascunho. Ela ainda precisa passar por edição, revisão e aprovação humana.", { exact: true }).waitFor();
    const guidedDraft = await recordedCall(api.state, call => call.method === "POST" && call.path === "/api/v1/engagement/cases/case-a/guided-draft", "generate verified draft");
    assert.deepEqual(guidedDraft.body.approved_item_ids.sort(), ["F1", "P1"]);
    const savedDraft = [...api.state.calls].reverse().find(call => call.method === "POST" && call.path === "/api/v1/workspace/documents");
    assert.equal(savedDraft.body.document_type, "petition");
    assert.equal(savedDraft.body.content_format, "markdown");

    await page.goto(`${baseUrl}/dashboard/account`);
    await page.getByRole("heading", { name: "Conta e escritório", exact: true }).waitFor();
    await page.getByRole("button", { name: "Escritório", exact: true }).click();
    assert.equal(await page.getByLabel("CNPJ", { exact: true }).inputValue(), "12.345.678/0001-99");
    await page.getByRole("button", { name: "Aplicativo", exact: true }).click();
    await page.getByRole("radio", { name: "Claro", exact: true }).focus();
    await page.keyboard.press("Space");
    assert.equal(await page.evaluate(() => localStorage.getItem("lexflow-theme")), "light");
    assert.equal(await page.evaluate(() => document.documentElement.classList.contains("light")), true);
    assert.equal(await page.evaluate(() => getComputedStyle(document.body).backgroundColor), "rgb(250, 250, 250)");
    await page.getByRole("radio", { name: "Escuro", exact: true }).focus();
    await page.keyboard.press("Space");
    assert.equal(await page.evaluate(() => document.documentElement.classList.contains("dark")), true);
    assert.equal(await page.evaluate(() => getComputedStyle(document.body).backgroundColor), "rgb(9, 9, 11)");
    await page.emulateMedia({ colorScheme: "light" });
    await page.getByRole("radio", { name: "Sistema", exact: true }).focus();
    await page.keyboard.press("Space");
    assert.equal(await page.evaluate(() => document.documentElement.dataset.theme), "system");
    assert.equal(await page.evaluate(() => document.documentElement.classList.contains("light")), true);
    await page.emulateMedia({ colorScheme: "dark" });
    await page.waitForFunction(() => document.documentElement.classList.contains("dark"));
    await page.getByRole("button", { name: "Aparência: Sistema. Alterar para Claro", exact: true }).click();
    assert.equal(await page.evaluate(() => document.documentElement.dataset.theme), "light");
    await page.getByRole("button", { name: "Aparência: Claro. Alterar para Escuro", exact: true }).click();
    assert.equal(await page.evaluate(() => document.documentElement.dataset.theme), "dark");
    await page.getByRole("button", { name: "Aparência: Escuro. Alterar para Sistema", exact: true }).click();
    assert.equal(await page.evaluate(() => document.documentElement.dataset.theme), "system");

    await page.goto(`${baseUrl}/dashboard/communications`);
    await page.getByRole("heading", { name: "Comunicações e portal", exact: true }).waitFor();
    await page.getByText("Status: Desconectado", { exact: true }).waitFor();
    assert.equal(await page.getByText(/Chave da API|Token de webhook|ID da instância/i).count(), 0);
    await page.getByRole("button", { name: "Conectar WhatsApp", exact: true }).click();
    await page.getByRole("img", { name: "QR Code para conectar o WhatsApp do escritório", exact: true }).waitFor();
    await recordedCall(api.state, call => call.method === "POST" && call.path === "/api/v1/engagement/whatsapp/connect", "connect office WhatsApp");
    api.state.whatsapp = {
      status: "connected", connected: true, number: "+5511999999999", last_checked_at: new Date().toISOString(),
    };
    await page.reload();
    await page.getByText("Status: Conectado", { exact: true }).waitFor();
    await page.getByText("(11) 99999-9999", { exact: true }).waitFor();
    await page.getByRole("button", { name: "Reconectar", exact: true }).waitFor();
    await page.getByRole("button", { name: "Desconectar", exact: true }).waitFor();
    await page.locator("select").first().selectOption("case-a");
    await page.getByLabel("Mensagem", { exact: true }).fill("Mensagem contratual de teste.");
    await page.getByRole("button", { name: "Registrar ou enviar mensagem", exact: true }).click();
    const messageBody = (await recordedCall(api.state, (call) => (
      call.method === "POST" && call.path === "/api/v1/engagement/cases/case-a/messages"
    ), "send case message")).body;
    assert.equal(messageBody.body, "Mensagem contratual de teste.");
    assert.equal(messageBody.channel, "portal");
    assert.match(messageBody.request_id, /^[0-9a-f-]{36}$/i);
    await page.getByText("Mensagem registrada. Situação: Registrada.", { exact: true }).waitFor();

    await page.goto(`${baseUrl}/dashboard/admin/users`);
    await page.getByRole("heading", { name: "Equipe e permissões", exact: true }).waitFor();
    await page.getByRole("heading", { name: "Convidar membro", exact: true }).waitFor();
    await page.getByRole("button", { name: "Criar convite", exact: true }).waitFor();
    api.state.role = "SUPER_ADMIN";
    const superAdminPage = await context.newPage();
    superAdminPage.setDefaultTimeout(7000);
    await superAdminPage.goto(`${baseUrl}/dashboard`);
    await superAdminPage.locator("aside summary").click();
    await superAdminPage.getByRole("link", { name: "Auditoria", exact: true }).waitFor();
    await superAdminPage.getByRole("link", { name: "Honorários e despesas", exact: true }).waitFor();
    await superAdminPage.getByRole("link", { name: "Equipe e permissões", exact: true }).waitFor();
    await superAdminPage.close();
    api.state.role = "partner";
    const partnerPage = await context.newPage();
    partnerPage.setDefaultTimeout(7000);
    await partnerPage.goto(`${baseUrl}/dashboard/admin/users`);
    await partnerPage.getByRole("heading", { name: "Equipe e permissões", exact: true }).waitFor();
    assert.equal(await partnerPage.getByRole("heading", { name: "Convidar membro", exact: true }).count(), 0);
    assert.equal(await partnerPage.getByRole("button", { name: "Criar convite", exact: true }).count(), 0);
    assert.equal(await partnerPage.locator('select[aria-label^="Papel de"]').count(), 0);
    await partnerPage.close();
    api.state.role = "admin";

    for (const path of [
      "/dashboard", "/dashboard/crm", "/dashboard/tracker", "/dashboard/cases/case-a",
      "/dashboard/petitions/editor", "/dashboard/account", "/dashboard/communications",
    ]) await assertNoHorizontalOverflow(page, path);

    api.state.needsSecuritySetup = true;
    const securityPage = await context.newPage();
    securityPage.setDefaultTimeout(7000);
    securityPage.setDefaultNavigationTimeout(10000);
    await securityPage.goto(`${baseUrl}/dashboard/crm`);
    await securityPage.waitForURL(`${baseUrl}/dashboard/account`);
    await securityPage.getByRole("heading", { name: "Conta e escritório", exact: true }).waitFor();
    await securityPage.close();

    assert.deepEqual(api.state.unhandled, [], "all UI API contracts must be explicitly mocked");
    assert.deepEqual(pageErrors, [], "the built workspace UI must not throw browser errors");
    await context.close();
    console.log("PASS: built UI contract fixtures across dashboard, CRM, Case 360, documents, account, communications, responsive layouts, and security onboarding redirect. No backend/DB/provider was called.");
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error.stack || error.message);
  process.exitCode = 1;
});

module.exports = { fixtureApi };
