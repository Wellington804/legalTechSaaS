// Local built-bundle contracts only; PostgreSQL/provider/device checks are separate.
const assert = require("node:assert/strict");
const { mkdirSync } = require("node:fs");
const { join } = require("node:path");
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "C:/Users/maxue/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright");
const { fixtureApi } = require("./workspace-ui.cjs");
const base = process.env.WORKSPACE_UI_URL || "http://127.0.0.1:3111";
const origin = new URL(base).origin;
const apiOrigin = new URL(process.env.WORKSPACE_UI_API_URL || base).origin;
assert.ok([origin, apiOrigin].every(url => ["127.0.0.1", "localhost"].includes(new URL(url).hostname)), "Local fixture endpoints only");

(async () => {
  const browser = await chromium.launch({ headless: true });
  const baseApi = fixtureApi(), calls = [], reports = [], outcomes = [], errors = [];
  const task = { id: "task-a", case_id: "case-a", title: "Conferir diligência", kind: "task", status: "pending", due_at: "2027-01-10T15:00:00Z", manually_reviewed: true, revision: 7, location: "Fórum de teste", contact: "Recepção", notes: "Levar documentos fictícios." };
  let feedbackFailure = true, outcomeFailure = true, documentFailure = 2, reminder = null, expireFeedback = false, logoutExpired = false, documentRevisionConflict = false;
  const committedDocuments = new Map();
  const authProfile = email => ({ user_id: email === "other@example.test" ? "user-other" : "user-a", user_name: email === "other@example.test" ? "Outra Advogada" : "Ana Advogada", tenant_id: email === "other@example.test" ? "tenant-other" : "tenant-a", email, role: "admin", tenant_name: "Escritório Exemplo", email_verified: true, mfa_enabled: true });
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, serviceWorkers: "block" });
    await context.route("**/*", route => [origin, apiOrigin].includes(new URL(route.request().url()).origin) ? route.fallback() : route.abort("blockedbyclient"));
    await context.route(`${apiOrigin}/api/v1/**`, async route => {
      const request = route.request(), method = request.method(), path = new URL(request.url()).pathname;
      const body = request.postData() ? request.postDataJSON() : null;
      calls.push({ method, path, body });
      const json = (value, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(value) });
      if (path === "/api/v1/auth/login") return json(authProfile(body.email));
      if (path === "/api/v1/auth/logout") return logoutExpired ? json({ detail: "Sessão já expirada." }, 401) : route.fulfill({ status: 204 });
      if (path === "/api/v1/workspace/cases/case-b") return json({ case: baseApi.state.cases.find(item => item.id === "case-b") });
      if (["/api/v1/workspace/cases/case-b/parties", "/api/v1/workspace/cases/case-b/access", "/api/v1/routines/cases/case-b/outcomes"].includes(path)) return json({ items: [], limit: 50 });
      if (path === "/api/v1/pilot/feedback") {
        if (method === "GET") return json({ items: reports });
        if (expireFeedback) { expireFeedback = false; return json({ detail: "Sessão expirada." }, 401); }
        if (feedbackFailure) { feedbackFailure = false; return json({ detail: "Falha temporária de teste." }, 503); }
        const report = { id: "report-" + reports.length, ...body, created_at: "2026-08-28T12:00:00Z", release: "fixture" }; reports.push(report); return json(report, 201);
      }
      if (path === "/api/v1/workspace/tasks" && method === "GET") return json({ items: new URL(request.url()).searchParams.get("case_id") === "case-b" ? [] : [task], limit: 50 });
      if (path === "/api/v1/workspace/tasks" && method === "POST") return json({ id: "task-no-date", revision: 1, ...body }, 201);
      if (path === "/api/v1/workspace/tasks/task-a" && method === "PUT") return json({ detail: "Conflito de revisão da tarefa." }, 409);
      if (path === "/api/v1/workspace/documents/doc-a" && method === "PUT" && documentRevisionConflict) return json({ detail: "Conflito de versão do documento." }, 409);
      if (path === "/api/v1/routines/attention") return json({ cases_without_next_action: [{ id: "case-a", title: "Caso Exemplo" }], reminders: [], limit: 50 });
      if (path === "/api/v1/routines/checklists") return json({ items: [{ key: "intake", title: "Primeiro atendimento", items: ["Conferir cadastro", "Definir próxima ação"] }] });
      if (path === "/api/v1/routines/cases/case-a/checklists") return json({ task_ids: ["task-b", "task-c"], created: true }, 201);
      if (path === "/api/v1/routines/cases/case-a/outcomes") {
        if (method === "GET") return json({ items: outcomes, limit: 50 });
        if (outcomeFailure) { outcomeFailure = false; return json({ detail: "Falha de rede simulada." }, 503); }
        const outcome = { id: "outcome-" + outcomes.length, ...body, created_at: "2026-08-28T12:00:00Z" }; outcomes.push(outcome); return json(outcome, 201);
      }
      if (path === "/api/v1/routines/tasks/task-a/reminder") {
        if (method === "GET") return json({ item: reminder });
        if (method === "DELETE") { reminder = null; return route.fulfill({ status: 204 }); }
        reminder = { id: "reminder-a", task_id: task.id, task_title: task.title, case_id: task.case_id, remind_at: body.remind_at, status: "scheduled", push_status: "not_requested", acknowledged_at: null }; return json(reminder);
      }
      if (path === "/api/v1/document-kit/templates") return json({ items: [{ key: "intake", title: "Ficha de atendimento", version: "1", description: "Modelo de teste", review_required: true, fields: [{ key: "purpose", label: "Finalidade do atendimento", required: true }] }] });
      if (path === "/api/v1/document-kit/preview") return json({ title: "Ficha de atendimento — Caso Exemplo", content_text: `RASCUNHO — revisão profissional necessária\n${body.values.purpose || "[Finalidade ausente]"}`, content_format: "plain", missing_fields: body.values.purpose ? [] : [{ key: "purpose", label: "Finalidade do atendimento" }], source: { case_revision: 4, client_revision: 2, template_version: "1", profile_fingerprint: "a".repeat(64) }, review_required: true });
      if (path === "/api/v1/document-kit/documents") {
        if (documentFailure === 2) { documentFailure--; return json({ detail: "Cadastro alterado; gere nova prévia." }, 409); }
        if (!committedDocuments.has(body.request_id)) {
          const document = { id: "kit-doc", title: "Ficha revisada", case_id: "case-a", current_version: 1, revision: 1, content_text: "RASCUNHO — revisão profissional necessária\n" + body.values.purpose, content_format: "plain" }; committedDocuments.set(body.request_id, document); baseApi.state.documents.push(document);
        }
        if (documentFailure === 1) { documentFailure--; return json({ detail: "Resposta perdida após gravar." }, 503); }
        return json({ document: committedDocuments.get(body.request_id) }, 201);
      }
      if (path === "/api/v1/branding/profiles") return json({ items: [] });
      if (path === "/api/v1/branding/capabilities") return json({ pdf_available: true });
      if (path === "/api/v1/branding/documents/kit-doc/exports") return json({ items: [] });
      return baseApi.handler(route);
    });
    const page = await context.newPage(); page.setDefaultTimeout(10000); page.on("pageerror", err => errors.push(err.message));
    const posted = path => calls.filter(call => call.path === "/api/v1" + path && ["POST", "PUT"].includes(call.method));
    async function fits(label) { assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `${label} must fit`); }
    async function moduleLink(name) { if (await page.getByRole("button", { name: "Outros", exact: true }).isVisible()) await page.getByRole("button", { name: "Outros", exact: true }).click(); await page.getByRole("link", { name, exact: true }).click(); }

    for (const width of [1440, 375]) {
      await page.setViewportSize({ width, height: 1000 });
      await page.goto(base + "/dashboard/pilot");
      await page.getByRole("heading", { name: "Seu primeiro atendimento", exact: true }).waitFor();
      await fits(`pilot ${width}`);
      if (width === 375 && process.env.PILOT_SCREENSHOT_DIR) { mkdirSync(process.env.PILOT_SCREENSHOT_DIR, { recursive: true }); await page.screenshot({ path: join(process.env.PILOT_SCREENSHOT_DIR, "mobile-pilot.png"), fullPage: true }); }
    }
    await page.goto(base + "/dashboard/pilot");
    const message = page.getByLabel("O que aconteceu ou precisa melhorar?", { exact: true });
    await message.fill("Dificuldade fictícia para revisar a agenda.");
    await page.getByText("Autorizo registrar este relato para acompanhamento do piloto.", { exact: true }).click();
    await page.getByRole("button", { name: "Registrar relato", exact: true }).click();
    await page.getByText("Falha temporária de teste.", { exact: true }).waitFor();
    assert.equal(await message.inputValue(), "Dificuldade fictícia para revisar a agenda.");
    page.once("dialog", dialog => dialog.accept());
    await page.getByRole("link", { name: "Central", exact: true }).click(); await page.waitForURL("**/dashboard");
    await page.goBack(); await page.waitForURL("**/dashboard/pilot");
    await page.waitForFunction(() => document.querySelector('textarea[name="message"]')?.value === "Dificuldade fictícia para revisar a agenda.");
    await page.getByRole("button", { name: "Registrar relato", exact: true }).click();
    await page.getByText("Relato registrado. Nenhum atendimento externo foi presumido.", { exact: true }).waitFor();
    assert.equal(posted("/pilot/feedback")[0].body.request_id, posted("/pilot/feedback")[1].body.request_id, "retry preserves idempotency");
    assert.deepEqual(Object.keys(posted("/pilot/feedback")[0].body).sort(), ["request_id", "kind", "area", "message", "completed_steps", "help_steps", "consent"].sort(), "feedback sends no URL, client identifiers or screenshot");
    await page.getByLabel("Tipo de relato", { exact: true }).selectOption("weekly");
    await page.locator('input[name="completed"][value="client"]').check();
    await message.fill("Consegui cadastrar o cliente fictício.");
    await page.getByText("Autorizo registrar este relato para acompanhamento do piloto.", { exact: true }).click();
    await page.getByRole("button", { name: "Registrar relato", exact: true }).click();
    await page.waitForFunction(() => document.querySelector('textarea[name="message"]').value === "");
    assert.deepEqual(posted("/pilot/feedback").at(-1).body.completed_steps, ["client"]);

    await moduleLink("Casos e processos");
    await page.getByRole("link", { name: "Abrir caso", exact: true }).click();
    await page.getByText("Mais", { exact: true }).click();
    await page.getByRole("button", { name: "Diligências e rotina", exact: true }).click();
    await page.getByText("Fórum de teste · Recepção", { exact: false }).waitFor();
    await page.getByLabel("Checklist operacional", { exact: true }).selectOption("intake");
    await page.getByRole("button", { name: "Adicionar checklist ao caso", exact: true }).click();
    await page.getByText("2 tarefas vinculadas ao caso. Confira e defina as datas na Agenda.", { exact: true }).waitFor();
    await page.getByText("Registrar resultado da diligência", { exact: true }).click();
    await page.getByLabel("Título do resultado", { exact: true }).fill("Visita fictícia concluída");
    await page.getByLabel("Resultado e próxima providência", { exact: true }).fill("Retornar com a documentação de teste.");
    await page.getByRole("button", { name: "Salvar resultado no caso", exact: true }).click();
    await page.getByText("Falha de rede simulada.", { exact: true }).first().waitFor();
    assert.equal(await page.getByLabel("Resultado e próxima providência", { exact: true }).inputValue(), "Retornar com a documentação de teste.");
    await page.goBack(); await page.waitForURL("**/dashboard/tracker"); await page.goForward(); await page.waitForURL("**/dashboard/cases/case-a");
    await page.getByText("Mais", { exact: true }).click();
    await page.getByRole("button", { name: "Diligências e rotina", exact: true }).click();
    await page.getByText("Registrar resultado da diligência", { exact: true }).click();
    await page.waitForFunction(() => document.querySelector('textarea[name="content_text"]')?.value === "Retornar com a documentação de teste.");
    page.once("dialog", dialog => dialog.dismiss());
    await page.getByRole("button", { name: "Agenda", exact: true }).click();
    assert.equal(await page.getByLabel("Título do resultado", { exact: true }).inputValue(), "Visita fictícia concluída", "cancelled tab navigation preserves draft");
    await page.getByRole("button", { name: "Salvar resultado no caso", exact: true }).click();
    await page.getByText("Resultados registrados", { exact: true }).click();
    await page.getByText("Visita fictícia concluída", { exact: true }).waitFor();
    assert.equal(posted("/routines/cases/case-a/outcomes")[0].body.request_id, posted("/routines/cases/case-a/outcomes")[1].body.request_id);
    await fits("routine 375");
    await page.getByRole("button", { name: "Agenda", exact: true }).click();
    await page.getByText("Mais ações", { exact: true }).first().click();
    await page.getByRole("button", { name: "Meu lembrete", exact: true }).click();
    await page.getByLabel("Lembrar em (horário local)", { exact: true }).fill("2027-01-09T09:00");
    await page.getByRole("button", { name: "Salvar meu lembrete", exact: true }).click();
    await page.getByText("Lembrete salvo para você. O push depende da ativação deste dispositivo e do provedor.", { exact: true }).waitFor();
    assert.equal(posted("/routines/tasks/task-a/reminder")[0].body.expected_revision, 7);
    await page.getByRole("button", { name: "Editar compromisso", exact: true }).click();
    assert.equal(await page.getByLabel("Data e origem conferidas por mim", { exact: true }).isChecked(), true);
    await page.getByLabel("Data e horário local", { exact: true }).fill("2027-01-11T10:00");
    assert.equal(await page.getByLabel("Data e origem conferidas por mim", { exact: true }).isChecked(), false, "changing date requires a new manual confirmation");
    task.revision = 8;
    await page.goBack(); await page.waitForURL("**/dashboard/tracker"); await page.goForward(); await page.waitForURL("**/dashboard/cases/case-a");
    await page.getByRole("button", { name: "Agenda", exact: true }).click();
    await page.getByRole("button", { name: "Editar compromisso", exact: true }).click();
    await page.getByRole("button", { name: "Salvar alterações", exact: true }).click();
    await page.getByText("Conflito de revisão da tarefa.", { exact: true }).waitFor();
    assert.equal(posted("/workspace/tasks/task-a").at(-1).body.expected_revision, 7, "restored task draft cannot adopt a newer server revision silently");
    page.once("dialog", dialog => dialog.accept());
    await page.getByRole("button", { name: "Cancelar edição", exact: true }).click();

    await page.getByRole("button", { name: "Criar compromisso", exact: true }).click();
    await page.getByLabel("Título", { exact: true }).fill("Checklist concluído sem data inventada");
    await page.getByLabel("Situação", { exact: true }).selectOption("completed");
    assert.equal(await page.getByLabel("Data e horário local", { exact: true }).getAttribute("required"), null);
    await page.getByRole("button", { name: "Criar compromisso", exact: true }).last().click();
    await page.waitForFunction(() => !document.querySelector('input[name="title"]'));
    assert.equal(posted("/workspace/tasks").at(-1).body.due_at, null);
    assert.equal(posted("/workspace/tasks").at(-1).body.status, "completed");

    await moduleLink("Documentos");
    await page.getByRole("button", { name: "Editar documento", exact: true }).first().click();
    await page.getByLabel("Texto do documento", { exact: true }).fill("Rascunho original antes da edição concorrente.");
    Object.assign(baseApi.state.documents[0], { current_version: 4, revision: 8, content_text: "Texto atualizado por outra sessão." }); documentRevisionConflict = true;
    await page.goBack(); await page.waitForURL("**/dashboard/cases/case-a"); await page.goForward(); await page.waitForURL("**/dashboard/petitions/editor");
    await page.getByRole("button", { name: "Editar documento", exact: true }).first().click();
    assert.equal(await page.getByLabel("Texto do documento", { exact: true }).inputValue(), "Rascunho original antes da edição concorrente.");
    await page.getByRole("button", { name: "Salvar nova versão", exact: true }).click();
    await page.getByText("Conflito de versão do documento.", { exact: true }).waitFor();
    assert.equal(posted("/workspace/documents/doc-a").at(-1).body.expected_revision, 7);
    assert.equal(posted("/workspace/documents/doc-a").at(-1).body.expected_version, 3, "restored document keeps its original optimistic concurrency tokens");
    page.once("dialog", dialog => dialog.accept()); await page.getByRole("button", { name: "Cancelar edição", exact: true }).click();
    await page.getByRole("button", { name: "Usar modelo guiado", exact: true }).click();
    await page.getByLabel("Tipo de documento", { exact: true }).selectOption("intake");
    await page.getByLabel("Caso relacionado", { exact: true }).selectOption("case-a");
    await page.getByRole("button", { name: "Gerar prévia para revisão", exact: true }).click();
    await page.getByText("Preencha os dados antes de salvar:", { exact: true }).waitFor();
    assert.equal(await page.getByRole("button", { name: "Salvar documento revisado", exact: true }).isEnabled(), false);
    await page.getByLabel("Finalidade do atendimento (necessário para salvar)", { exact: true }).fill("Conferir o caso fictício.");
    await context.setOffline(true);
    await page.getByText("Sem conexão.", { exact: false }).waitFor();
    assert.equal(await page.getByLabel("Finalidade do atendimento (necessário para salvar)", { exact: true }).inputValue(), "Conferir o caso fictício.");
    assert.equal(await page.evaluate(() => JSON.stringify({ ...localStorage, ...sessionStorage }).includes("Conferir o caso fictício")), false, "legal draft is memory-only");
    await context.setOffline(false);
    await page.getByRole("button", { name: "Gerar prévia para revisão", exact: true }).click();
    await page.getByText("Revisei todo o texto e confirmo sua adequação ao caso.", { exact: true }).click();
    await page.getByRole("button", { name: "Salvar documento revisado", exact: true }).click();
    await page.getByText("Cadastro alterado; gere nova prévia.", { exact: false }).waitFor();
    assert.equal(await page.getByLabel("Finalidade do atendimento (necessário para salvar)", { exact: true }).inputValue(), "Conferir o caso fictício.");
    await page.getByRole("button", { name: "Gerar prévia para revisão", exact: true }).click();
    await page.getByText("Revisei todo o texto e confirmo sua adequação ao caso.", { exact: true }).click();
    await page.getByRole("button", { name: "Salvar documento revisado", exact: true }).click();
    await page.getByText("Resposta perdida após gravar.", { exact: false }).waitFor();
    await page.goBack(); await page.waitForURL("**/dashboard/cases/case-a"); await page.goForward(); await page.waitForURL("**/dashboard/petitions/editor");
    await page.getByRole("button", { name: "Usar modelo guiado", exact: true }).click();
    assert.equal(await page.getByLabel("Finalidade do atendimento (necessário para salvar)", { exact: true }).inputValue(), "Conferir o caso fictício.");
    await page.getByRole("button", { name: "Gerar prévia para revisão", exact: true }).click();
    await page.getByText("Revisei todo o texto e confirmo sua adequação ao caso.", { exact: true }).click();
    await page.getByRole("button", { name: "Salvar documento revisado", exact: true }).click();
    await page.getByRole("heading", { name: "Exportar documento: Ficha revisada", exact: true }).waitFor();
    assert.equal(committedDocuments.size, 1, "lost response + back/return + repeated preview cannot duplicate a committed document");
    assert.equal(posted("/document-kit/documents").at(-2).body.request_id, posted("/document-kit/documents").at(-1).body.request_id);
    assert.equal(posted("/document-kit/documents").at(-1).body.reviewed, true);
    assert.equal(posted("/document-kit/documents").at(-1).body.source.profile_fingerprint, "a".repeat(64));
    for (const width of [375, 1440]) { await page.setViewportSize({ width, height: 1000 }); await fits(`kit ${width}`); }

    baseApi.state.cases.push({ ...baseApi.state.cases[0], id: "case-b", title: "Outro caso fictício" });
    await moduleLink("Casos e processos"); await page.getByRole("link", { name: "Abrir caso", exact: true }).first().click();
    await page.getByText("Mais", { exact: true }).click();
    await page.getByRole("button", { name: "Diligências e rotina", exact: true }).click();
    await page.getByLabel("Título do resultado", { exact: true }).fill("Rascunho exclusivo do caso A");
    await page.getByLabel("Resultado e próxima providência", { exact: true }).fill("Conteúdo exclusivo do caso A.");
    page.once("dialog", dialog => dialog.accept()); await moduleLink("Casos e processos");
    await page.getByRole("link", { name: "Abrir caso", exact: true }).nth(1).click();
    await page.getByText("Mais", { exact: true }).click();
    await page.getByRole("button", { name: "Diligências e rotina", exact: true }).click();
    assert.equal(await page.getByLabel("Título do resultado", { exact: true }).inputValue(), "", "case B never receives case A draft");
    assert.equal(await page.getByLabel("Resultado e próxima providência", { exact: true }).inputValue(), "");
    await moduleLink("Casos e processos"); await page.getByRole("link", { name: "Abrir caso", exact: true }).first().click();
    await page.getByText("Mais", { exact: true }).click();
    await page.getByRole("button", { name: "Diligências e rotina", exact: true }).click();
    assert.equal(await page.getByLabel("Título do resultado", { exact: true }).inputValue(), "Rascunho exclusivo do caso A");
    await page.getByRole("button", { name: "Salvar resultado no caso", exact: true }).click();
    await page.waitForFunction(() => document.querySelector('input[name="title"]').value === "");

    await page.goto(base + "/dashboard/pilot");
    await message.fill("Rascunho preservado durante renovação de sessão.");
    await page.getByText("Autorizo registrar este relato para acompanhamento do piloto.", { exact: true }).click();
    expireFeedback = true;
    await page.getByRole("button", { name: "Registrar relato", exact: true }).click();
    const login = page.getByRole("dialog", { name: "Renovar sessão", exact: true }); await login.waitFor();
    assert.equal(await message.isVisible(), false, "expired-session private form is hidden, not destroyed");
    assert.equal(await login.getByLabel("E-mail", { exact: true }).inputValue(), "ana@example.test");
    await login.getByLabel("Senha", { exact: true }).fill("NotARealPassword123");
    await login.getByRole("button", { name: "Entrar", exact: true }).click();
    await login.waitFor({ state: "hidden" });
    assert.equal(await message.inputValue(), "Rascunho preservado durante renovação de sessão.");
    assert.equal(posted("/pilot/feedback").at(-1).body.message, "Rascunho preservado durante renovação de sessão.", "no automatic mutation retry");
    const countBefore = posted("/pilot/feedback").length;
    await page.getByRole("button", { name: "Registrar relato", exact: true }).click();
    await page.waitForFunction(() => document.querySelector('textarea[name="message"]').value === "");
    assert.equal(posted("/pilot/feedback").length, countBefore + 1);
    assert.equal(posted("/pilot/feedback").at(-2).body.request_id, posted("/pilot/feedback").at(-1).body.request_id);

    await message.fill("Nunca mostrar este rascunho para outra identidade.");
    await page.getByText("Autorizo registrar este relato para acompanhamento do piloto.", { exact: true }).click();
    expireFeedback = true; await page.getByRole("button", { name: "Registrar relato", exact: true }).click(); await login.waitFor();
    page.once("dialog", dialog => dialog.accept());
    await login.getByRole("button", { name: "Descartar rascunhos e trocar de conta", exact: true }).click();
    const otherLogin = page.getByRole("dialog", { name: "Entrar no escritório", exact: true }); await otherLogin.waitFor();
    await otherLogin.getByLabel("E-mail", { exact: true }).fill("other@example.test"); await otherLogin.getByLabel("Senha", { exact: true }).fill("NotARealPassword123"); await otherLogin.getByRole("button", { name: "Entrar", exact: true }).click();
    await message.waitFor(); assert.equal(await message.inputValue(), "", "account switch clears memory and mounted form state");
    logoutExpired = true; await page.getByRole("button", { name: "Sair da conta", exact: true }).click();
    await page.getByRole("dialog", { name: "Entrar no escritório", exact: true }).waitFor();
    assert.deepEqual(baseApi.state.unhandled, []); assert.deepEqual(errors, []);
    console.log("PASS: pilot 375/desktop, feedback privacy/idempotency, checklists/outcomes, memory-only back/return/offline drafts, 401 reauth/account isolation, no-date tasks, reminders/date review, kit missing fields/stale preview/lost-response dedupe and exports. UI fixtures only.");
  } finally { await browser.close(); }
})().catch(error => { console.error(error.stack || error.message); process.exitCode = 1; });
