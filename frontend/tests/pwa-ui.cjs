// Built local bundle + explicit PushManager/API fixtures. Does not prove delivery on a phone/provider.
const assert = require("node:assert/strict");
const { createHash } = require("node:crypto");
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "C:/Users/maxue/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright");
const { fixtureApi } = require("./workspace-ui.cjs");
const base = process.env.WORKSPACE_UI_URL || "http://127.0.0.1:3111";
const origin = new URL(base).origin;
const apiOrigin = new URL(process.env.WORKSPACE_UI_API_URL || base).origin;
assert.ok([origin, apiOrigin].every(url => ["127.0.0.1", "localhost"].includes(new URL(url).hostname)), "Local fixtures only");

function browserPushFixture() {
  const data = { permissionRequests: 0, installs: 0, subscribes: 0, unsubscribes: 0, notificationCloses: 0, registrations: [], messages: [], subscription: null };
  window.pushFixture = data;
  const serverKey = new Uint8Array(65).fill(1); serverKey[0] = 4;
  const worker = { scriptURL: location.origin + "/sw.js", postMessage: message => data.messages.push(message) };
  const registration = Object.assign(new EventTarget(), {
    active: worker, waiting: null, installing: null,
    getNotifications: async () => [{ close: () => data.notificationCloses++ }],
    pushManager: {
      getSubscription: async () => data.subscription,
      subscribe: async options => {
        if (!options.userVisibleOnly) throw new Error("userVisibleOnly required");
        data.subscribes++;
        const endpoint = "https://fcm.googleapis.com/fcm/send/browser-fixture-" + data.subscribes;
        const subscription = {
          endpoint, options: { applicationServerKey: serverKey.buffer },
          toJSON: () => ({ endpoint, keys: { p256dh: "browser-fixture-public-key", auth: "browser-fixture-auth" } }),
          unsubscribe: async () => { data.unsubscribes++; if (data.subscription === subscription) data.subscription = null; return true; },
        };
        data.subscription = subscription; return subscription;
      },
    },
  });
  data.registration = registration;
  const serviceWorker = Object.assign(new EventTarget(), {
    controller: worker,
    ready: Promise.resolve(registration),
    getRegistration: async () => registration,
    register: async (url, options) => { data.registrations.push({ url, options }); return registration; },
  });
  Object.defineProperty(navigator, "serviceWorker", { configurable: true, value: serviceWorker });
  Object.defineProperty(window, "Notification", { configurable: true, value: {
    permission: "default", requestPermission: async () => { data.permissionRequests++; window.Notification.permission = "granted"; return "granted"; },
  } });
  Object.defineProperty(window, "PushManager", { configurable: true, value: function PushManager() {} });
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const api = fixtureApi(), devices = [], calls = [], errors = [], unhandled = [];
  const key = Buffer.alloc(65, 1); key[0] = 4;
  let enabled = true, failNextSubscription = false;
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 960 }, serviceWorkers: "block" });
    await context.addInitScript(browserPushFixture);
    await context.route("**/*", route => [origin, apiOrigin].includes(new URL(route.request().url()).origin) ? route.fallback() : route.abort("blockedbyclient"));
    await context.route(`${apiOrigin}/api/v1/**`, async route => {
      const request = route.request(), path = new URL(request.url()).pathname, method = request.method();
      if (path === "/api/v1/auth/logout" && method === "POST") { devices.splice(0); return route.fulfill({ status: 204 }); }
      if (!path.startsWith("/api/v1/push")) return api.handler(route);
      const body = request.postData() ? request.postDataJSON() : null;
      calls.push({ path, method, body });
      const json = (payload, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(payload) });
      if (path.endsWith("/capabilities")) return json({ enabled, public_key: enabled ? key.toString("base64url") : null });
      if (path === "/api/v1/push/subscriptions" && method === "GET") return json({ items: devices });
      if (path === "/api/v1/push/subscriptions" && method === "POST") {
        if (failNextSubscription) { failNextSubscription = false; return json({ detail: "Inscrição rejeitada para o teste de interface." }, 409); }
        const device = { id: "push-" + (devices.length + 1), label: body.label, endpoint_hash: createHash("sha256").update(body.endpoint).digest("hex"), created_at: "2026-08-28T12:00:00Z", last_seen_at: "2026-08-28T12:00:00Z", expires_at: "2026-11-26T12:00:00Z" };
        devices.push(device); return json(device, 201);
      }
      if (/\/subscriptions\/[^/]+\/test$/.test(path) && method === "POST") return json({ status: "queued" }, 202);
      if (/\/subscriptions\/[^/]+$/.test(path) && method === "DELETE") {
        const index = devices.findIndex(device => path.endsWith("/" + device.id)); if (index !== -1) devices.splice(index, 1);
        return route.fulfill({ status: 204 });
      }
      unhandled.push(`${method} ${path}`); return json({ detail: "Missing fixture" }, 404);
    });
    const page = await context.newPage(); page.setDefaultTimeout(10000); page.on("pageerror", err => errors.push(err.message));
    await page.goto(base + "/dashboard/account");
    await page.getByRole("button", { name: "Aplicativo", exact: true }).click();
    await page.getByRole("heading", { name: "Aplicativo e notificações", exact: true }).waitFor();
    await page.getByText("Nenhum dispositivo autorizado.", { exact: true }).waitFor();
    assert.equal(await page.evaluate(() => window.pushFixture.permissionRequests), 0);
    const enable = page.getByRole("button", { name: "Ativar notificações neste dispositivo", exact: true });
    assert.equal(await enable.isEnabled(), false, "consent is required");
    await page.evaluate(() => {
      const event = new Event("beforeinstallprompt");
      event.prompt = async () => { window.pushFixture.installs++; };
      event.userChoice = Promise.resolve({ outcome: "dismissed" }); window.dispatchEvent(event);
    });
    await page.getByRole("button", { name: "Instalar LexFlow", exact: true }).click();
    assert.equal(await page.evaluate(() => window.pushFixture.installs), 1);
    await page.getByLabel("Nome deste dispositivo", { exact: true }).fill("Celular da Ana");
    await page.getByLabel(/Quero receber notificações neste dispositivo/).check();
    assert.equal(await page.evaluate(() => window.pushFixture.permissionRequests), 0);
    await enable.click();
    await page.getByText(/Notificações ativadas neste dispositivo/).waitFor();
    assert.equal(await page.evaluate(() => window.pushFixture.permissionRequests), 1);
    const post = calls.find(call => call.method === "POST" && call.path.endsWith("/subscriptions"));
    assert.equal(post.body.consent, true); assert.equal(post.body.label, "Celular da Ana");
    assert.ok(post.body.keys.p256dh && post.body.keys.auth);
    await page.getByRole("button", { name: "Testar notificações em Celular da Ana", exact: true }).click();
    await page.getByText(/Teste colocado na fila/).waitFor();
    assert.equal(calls.filter(call => call.path.endsWith("/test")).length, 1);
    for (const width of [320, 375, 1440]) {
      await page.setViewportSize({ width, height: 900 });
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), `Account/PWA overflow at ${width}px`);
    }
    await page.getByRole("button", { name: "Desativar notificações em Celular da Ana", exact: true }).click();
    await page.getByText(/Dispositivo desativado/).waitFor();
    assert.equal(devices.length, 0); assert.equal(await page.evaluate(() => window.pushFixture.unsubscribes), 1);
    assert.equal(await page.evaluate(() => window.pushFixture.notificationCloses), 1);
    failNextSubscription = true;
    await page.getByLabel(/Quero receber notificações neste dispositivo/).check();
    await enable.click();
    await page.getByText("Inscrição rejeitada para o teste de interface.", { exact: true }).waitFor();
    assert.equal(await page.evaluate(() => window.pushFixture.subscription), null, "failed subscribe must not be shown as enabled");
    assert.equal(await page.evaluate(() => window.pushFixture.unsubscribes), 2);
    await enable.click();
    await page.getByText(/Notificações ativadas neste dispositivo/).waitFor();
    await page.getByRole("button", { name: "Sair da conta", exact: true }).click();
    await page.getByRole("button", { name: "Entrar", exact: true }).waitFor();
    assert.equal(await page.evaluate(() => window.pushFixture.subscription), null, "logout removes the browser subscription");
    assert.equal(await page.evaluate(() => window.pushFixture.notificationCloses), 2, "logout closes visible notifications");
    assert.equal(devices.length, 0);
    enabled = false; await page.goto(base + "/dashboard/account");
    await page.getByRole("button", { name: "Aplicativo", exact: true }).click();
    await page.getByText(/Web Push ainda não está habilitado/).waitFor();
    await page.getByLabel(/Quero receber notificações neste dispositivo/).check(); assert.equal(await enable.isEnabled(), false);
    await page.evaluate(() => {
      const fixture = window.pushFixture;
      fixture.registration.waiting = { postMessage: message => fixture.messages.push(message) };
      const worker = new EventTarget(); fixture.registration.installing = worker;
      fixture.registration.dispatchEvent(new Event("updatefound")); worker.dispatchEvent(new Event("statechange"));
    });
    await page.getByRole("button", { name: "Salvei, atualizar agora", exact: true }).waitFor();
    await page.getByRole("button", { name: "Perfil", exact: true }).click();
    await page.getByLabel("Nome", { exact: true }).fill("Rascunho não salvo");
    await page.getByRole("button", { name: "Mais tarde", exact: true }).click();
    assert.equal(await page.getByLabel("Nome", { exact: true }).inputValue(), "Rascunho não salvo");
    assert.deepEqual(await page.evaluate(() => window.pushFixture.messages), []);
    const ios = await context.newPage();
    await ios.addInitScript(() => Object.defineProperty(navigator, "userAgent", { value: "iPhone OS 17 Safari" }));
    await ios.goto(base + "/dashboard/account");
    await ios.getByRole("button", { name: "Aplicativo", exact: true }).click();
    await ios.getByText(/No iPhone ou iPad: abra no Safari/).waitFor();
    assert.equal(await ios.evaluate(() => window.pushFixture.permissionRequests), 0);
    await ios.close();
    assert.deepEqual(errors, []); assert.deepEqual(unhandled, []); assert.deepEqual(api.state.unhandled, []);
    await context.close();
    console.log("PASS: install prompt/iOS guidance, explicit permission/consent, subscribe/test/revoke, rollback on error, disabled provider, non-forced update and 320/375/1440px. PushManager and API fixtures, not phone/provider E2E.");
  } finally { await browser.close(); }
})().catch(error => { console.error(error.stack || error.message); process.exitCode = 1; });
