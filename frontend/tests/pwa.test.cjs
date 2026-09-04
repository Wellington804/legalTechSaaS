const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { test } = require("node:test");
const vm = require("node:vm");
const { webcrypto } = require("node:crypto");
const ts = require("typescript");

function worker() {
  const handlers = {}, writes = [], deleted = [], notifications = [], opened = [], fetched = [];
  const cache = { put: async (path, response) => { writes.push(path); }, match: async () => new Response("PUBLIC OFFLINE", { headers: { "Content-Type": "text/html" } }) };
  const state = { handlers, writes, deleted, notifications, opened, fetched, claimed: 0, skipped: 0, offline: false, windows: [] };
  const self = {
    location: new URL("https://app.example.test/sw.js"),
    addEventListener: (event, callback) => { handlers[event] = callback; },
    skipWaiting: async () => { state.skipped++; },
    registration: { showNotification: async (title, options) => notifications.push({ title, options }) },
    clients: { claim: async () => { state.claimed++; }, matchAll: async () => state.windows, openWindow: async url => opened.push(url) },
  };
  vm.runInNewContext(readFileSync(require.resolve("../public/sw.js"), "utf8"), {
    self, URL, Response, caches: { open: async () => cache, keys: async () => ["legalflow-public-v0", "legaltech-old", "legalflow-public-v1", "unrelated-app"], delete: async name => deleted.push(name) },
    fetch: async (request, options) => {
      fetched.push({ request, options });
      if (state.offline) throw new TypeError("offline");
      return new Response("PRIVATE ONLINE RESPONSE");
    },
  });
  state.event = async (name, properties = {}) => {
    let pending; handlers[name]({ ...properties, waitUntil: promise => { pending = promise; }, respondWith: promise => { pending = promise; } });
    return pending ? await pending : null;
  };
  return state;
}
function request(path, mode = "cors", headers = {}) { return { url: `https://app.example.test${path}`, method: "GET", mode, headers: new Headers(headers) }; }

test("PWA installs only fixed public assets and update activation is explicit and same-origin", async () => {
  const sw = worker();
  await sw.event("install");
  assert.deepEqual(sw.writes.sort(), ["/offline.html", "/icons/icon-192.png", "/icons/icon-512.png", "/icons/apple-touch-icon.png"].sort());
  assert.ok(sw.fetched.every(call => call.options.credentials === "omit" && call.options.redirect === "error" && call.options.cache === "no-store"));
  assert.equal(sw.skipped, 0, "updates cannot activate/reload automatically");
  await sw.event("activate");
  assert.deepEqual(sw.deleted, ["legalflow-public-v0", "legaltech-old"]); assert.equal(sw.claimed, 1);
  await sw.event("message", { data: { type: "ACTIVATE_UPDATE" }, source: { url: "https://evil.test/" } });
  assert.equal(sw.skipped, 0);
  await sw.event("message", { data: { type: "ACTIVATE_UPDATE" }, source: { url: "https://app.example.test/dashboard" } });
  assert.equal(sw.skipped, 1);
});

test("PWA never stores private HTML, documents, API/RSC, nor synthesizes HTML for non-navigation", async () => {
  const sw = worker();
  assert.equal(await sw.event("fetch", { request: request("/api/v1/workspace/export", "navigate") }), null);
  assert.equal(await sw.event("fetch", { request: request("/dashboard?_rsc=test", "cors", { RSC: "1" }) }), null);
  assert.equal(await sw.event("fetch", { request: request("/dashboard", "navigate", { RSC: "1" }) }), null);
  assert.equal(await sw.event("fetch", { request: request("/private.pdf") }), null);
  assert.equal(await sw.event("fetch", { request: request("/icons/icon-192.png?private=x") }), null);
  assert.equal(await (await sw.event("fetch", { request: request("/dashboard", "navigate") })).text(), "PRIVATE ONLINE RESPONSE");
  assert.equal(sw.fetched[0].options.cache, "no-store");
  assert.deepEqual(sw.writes, []);
  sw.offline = true;
  assert.equal(await (await sw.event("fetch", { request: request("/portal?secret=never-cache", "navigate") })).text(), "PUBLIC OFFLINE");
  assert.deepEqual(sw.writes, []);
});

test("push strips personal payload and notification clicks cannot navigate off-site or replace a draft", async () => {
  const sw = worker();
  await sw.event("push", { data: { json: () => ({ title: "Private person", body: "Case and credentials", url: "https://evil.test/token", tag: "delivery-123" }) } });
  assert.equal(sw.notifications[0].title, "LexFlow");
  assert.equal(sw.notifications[0].options.body, "Há uma atualização no seu escritório. Entre no LexFlow para consultar.");
  assert.deepEqual(JSON.parse(JSON.stringify(sw.notifications[0].options.data)), { url: "/dashboard" });
  assert.equal(sw.notifications[0].options.tag, "delivery-123");
  await sw.event("push", { data: { json: () => { throw new SyntaxError("malformed"); } } });
  assert.equal(sw.notifications.length, 2);
  let closed = 0, focused = 0;
  sw.windows = [{ url: "https://app.example.test/dashboard/petitions/editor", focus: () => { throw new Error("Cannot touch open draft"); } }];
  await sw.event("notificationclick", { notification: { data: { url: "javascript:alert(1)" }, close: () => closed++ } });
  assert.equal(closed, 1); assert.deepEqual(sw.opened, ["https://app.example.test/dashboard"]);
  sw.windows.push({ url: "https://app.example.test/dashboard", focus: async () => focused++ });
  await sw.event("notificationclick", { notification: { close: () => closed++ } });
  assert.equal(focused, 1); assert.equal(sw.opened.length, 1);
});

require.extensions[".ts"] = (module, filename) => module._compile(ts.transpileModule(readFileSync(filename, "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText, filename);

test("subscription reconciliation only renews an active owned endpoint; logout prevents revival", async () => {
  const original = { fetch: global.fetch, window: global.window, navigator: Object.getOwnPropertyDescriptor(global, "navigator"), Notification: global.Notification, crypto: Object.getOwnPropertyDescriptor(global, "crypto") };
  Object.defineProperty(global, "crypto", { configurable: true, value: webcrypto });
  const { applicationServerKey, endpointFingerprint, reconcileBrowserPush, clearBrowserPush } = require("../src/lib/pwa.ts");
  const bytes = Buffer.alloc(65, 1); bytes[0] = 4; const publicKey = bytes.toString("base64url");
  let permission = "granted", unsubscribed = 0, closed = 0, active = true, own = true, writes = 0, fail = false;
  const subscription = { endpoint: "https://fcm.googleapis.com/fcm/send/opaque", options: { applicationServerKey: bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength) },
    toJSON: () => ({ endpoint: subscription.endpoint, keys: { p256dh: "device-key", auth: "device-auth" } }), unsubscribe: async () => { unsubscribed++; active = false; } };
  const registration = { active: { scriptURL: "https://app.example.test/sw.js" }, pushManager: { getSubscription: async () => active ? subscription : null }, getNotifications: async () => [{ close: () => closed++ }] };
  global.window = { PushManager: function () {}, Notification: {} };
  global.Notification = { get permission() { return permission; }, requestPermission: () => { throw new Error("No implicit permission prompt"); } };
  Object.defineProperty(global, "navigator", { configurable: true, value: { serviceWorker: { getRegistration: async () => registration } } });
  const hash = await endpointFingerprint(subscription.endpoint);
  try {
    assert.equal(applicationServerKey(publicKey).length, 65); assert.throws(() => applicationServerKey("bad"));
    global.fetch = async (url, options) => {
      assert.equal(options.credentials, "include"); assert.equal(options.cache, "no-store");
      if (fail) return Response.json({ detail: "Temporary" }, { status: 503 });
      if (options.method === "POST") { writes++; const body = JSON.parse(options.body); assert.equal(body.consent, true); assert.equal(body.endpoint, subscription.endpoint); return Response.json({}); }
      return Response.json(url.endsWith("/capabilities") ? { enabled: true, public_key: publicKey } : { items: own ? [{ id: "own", endpoint_hash: hash, label: "Meu celular" }] : [] });
    };
    await reconcileBrowserPush(registration); assert.equal(writes, 1); assert.equal(unsubscribed, 0);
    permission = "default"; await reconcileBrowserPush(registration); assert.equal(writes, 1);
    permission = "granted"; fail = true; await assert.rejects(reconcileBrowserPush(registration)); assert.equal(unsubscribed, 0); fail = false;
    own = false; await reconcileBrowserPush(registration); assert.equal(writes, 1); assert.equal(unsubscribed, 1); assert.equal(closed, 1);
    await reconcileBrowserPush(registration); assert.equal(writes, 1, "an orphan was never transferred");
    active = true; own = true; await clearBrowserPush(); await reconcileBrowserPush(registration); assert.equal(writes, 1, "logout does not silently enable another subscription");
    active = true;
    let release;
    const gate = new Promise(resolve => { release = resolve; });
    const normalFetch = global.fetch;
    global.fetch = async (...args) => { await gate; return normalFetch(...args); };
    const inFlight = reconcileBrowserPush(registration);
    await new Promise(resolve => setImmediate(resolve));
    await clearBrowserPush(); release(); await inFlight;
    assert.equal(writes, 1, "a reconciliation started before logout cannot register after it");
  } finally {
    global.fetch = original.fetch; global.window = original.window; global.Notification = original.Notification;
    if (original.navigator) Object.defineProperty(global, "navigator", original.navigator); else delete global.navigator;
    if (original.crypto) Object.defineProperty(global, "crypto", original.crypto); else delete global.crypto;
  }
});

test("manifest icons have the declared real PNG dimensions and safe install metadata", () => {
  const manifest = require("../src/app/manifest.ts").default();
  assert.equal(manifest.scope, "/"); assert.equal(manifest.start_url, "/dashboard"); assert.equal(manifest.display, "standalone");
  for (const [name, expected] of [["icon-192.png", 192], ["icon-512.png", 512], ["apple-touch-icon.png", 180]]) {
    const image = readFileSync(require.resolve(`../public/icons/${name}`));
    assert.deepEqual(Array.from(image.subarray(0, 8)), [137, 80, 78, 71, 13, 10, 26, 10]);
    assert.equal(image.readUInt32BE(16), expected); assert.equal(image.readUInt32BE(20), expected);
  }
});
