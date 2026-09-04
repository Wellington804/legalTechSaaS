import { api } from "./api-client";

export interface PushDevice {
  id: string;
  label: string;
  endpoint_hash: string;
  created_at: string;
  last_seen_at: string;
  expires_at: string;
}
export interface PushCapabilities { enabled: boolean; public_key: string | null }
let registrationPromise: Promise<ServiceWorkerRegistration> | null = null;
let subscriptionEpoch = 0;

export function pwaRegistration(): Promise<ServiceWorkerRegistration> {
  if (!registrationPromise) registrationPromise = navigator.serviceWorker.register("/sw.js", { scope: "/", updateViaCache: "none" }).catch(error => {
    registrationPromise = null;
    throw error;
  });
  return registrationPromise;
}

export function applicationServerKey(value: string): Uint8Array<ArrayBuffer> {
  const raw = atob(value.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat((4 - value.length % 4) % 4));
  const key = Uint8Array.from(raw, character => character.charCodeAt(0));
  if (key.length !== 65 || key[0] !== 4) throw new Error("A chave pública de notificações está inválida. Contate o suporte.");
  return key;
}

export async function endpointFingerprint(endpoint: string): Promise<string> {
  const hash = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(endpoint));
  return Array.from(new Uint8Array(hash), byte => byte.toString(16).padStart(2, "0")).join("");
}

export function pushSubscriptionBody(subscription: PushSubscription, label: string) {
  const { endpoint, keys } = subscription.toJSON();
  if (!endpoint || !keys?.p256dh || !keys?.auth) throw new Error("O navegador não forneceu uma inscrição válida.");
  return { endpoint, keys: { p256dh: keys.p256dh, auth: keys.auth }, label, consent: true };
}

export async function clearBrowserPush(): Promise<void> {
  subscriptionEpoch++;
  if (!("serviceWorker" in navigator)) return;
  const registration = await navigator.serviceWorker.getRegistration("/");
  const script = registration?.active?.scriptURL || registration?.waiting?.scriptURL;
  if (!registration || !script || new URL(script).pathname !== "/sw.js") return;
  await Promise.allSettled([
    registration.getNotifications().then(notifications => notifications.forEach(notification => notification.close())),
    registration.pushManager?.getSubscription().then(subscription => subscription?.unsubscribe()),
  ]);
}

/** Renew only an already active subscription belonging to the authenticated account.
 * No local user map, permission prompt, endpoint transfer, or resurrection after logout. */
export async function reconcileBrowserPush(registration: ServiceWorkerRegistration): Promise<void> {
  const epoch = subscriptionEpoch;
  if (!("PushManager" in window) || !("Notification" in window) || Notification.permission !== "granted") return;
  const subscription = await registration.pushManager.getSubscription();
  if (!subscription) return;
  const [{ items }, capabilities, hash] = await Promise.all([
    api.get<{ items: PushDevice[] }>("/push/subscriptions"),
    api.get<PushCapabilities>("/push/capabilities"),
    endpointFingerprint(subscription.endpoint),
  ]);
  if (epoch !== subscriptionEpoch) return;
  const current = items.find(device => device.endpoint_hash === hash);
  if (!current) {
    await clearBrowserPush();
    return;
  }
  if (capabilities.enabled && capabilities.public_key) {
    const activeKey = subscription.options.applicationServerKey;
    const configured = applicationServerKey(capabilities.public_key);
    if (activeKey && (activeKey.byteLength !== configured.length || new Uint8Array(activeKey).some((byte, index) => byte !== configured[index]))) return;
    if (epoch === subscriptionEpoch) await api.post("/push/subscriptions", pushSubscriptionBody(subscription, current.label));
  }
}
