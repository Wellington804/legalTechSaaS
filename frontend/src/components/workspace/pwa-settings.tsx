"use client";

import { useCallback, useEffect, useState } from "react";
import { usePwa } from "@/components/pwa-provider";
import { api } from "@/lib/api-client";
import { applicationServerKey, clearBrowserPush, endpointFingerprint, pushSubscriptionBody, type PushCapabilities, type PushDevice } from "@/lib/pwa";
import { button, control, dateText, errorText, Field, Panel, primary, State } from "./shared";

export function PwaSettings() {
  const pwa = usePwa();
  const [capabilities, setCapabilities] = useState<PushCapabilities | null>(null);
  const [devices, setDevices] = useState<PushDevice[]>([]);
  const [currentHash, setCurrentHash] = useState("");
  const [label, setLabel] = useState("Meu dispositivo");
  const [consent, setConsent] = useState(false);
  const [permission, setPermission] = useState<NotificationPermission | "unsupported">("unsupported");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const supportsPush = pwa.supported && permission !== "unsupported";
  const needsInstall = pwa.ios && !pwa.installed;
  const currentDevice = devices.find(device => device.endpoint_hash === currentHash);

  const reload = useCallback(async () => {
    const [capability, subscriptions] = await Promise.all([
      api.get<PushCapabilities>("/push/capabilities"), api.get<{ items: PushDevice[] }>("/push/subscriptions"),
    ]);
    setCapabilities(capability); setDevices(subscriptions.items);
    if (pwa.registration?.pushManager) {
      const subscription = await pwa.registration.pushManager.getSubscription();
      setCurrentHash(subscription ? await endpointFingerprint(subscription.endpoint) : "");
    }
  }, [pwa.registration]);

  useEffect(() => {
    setPermission("Notification" in window && "PushManager" in window ? Notification.permission : "unsupported");
    let active = true;
    reload().catch(err => { if (active) setError(errorText(err)); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [reload]);

  async function run(action: () => Promise<void>) {
    setBusy(true); setError(""); setMessage("");
    try { await action(); } catch (err) { setError(errorText(err)); }
    finally { setBusy(false); }
  }

  async function subscribe() {
    if (!consent || !capabilities?.enabled || !capabilities.public_key || !pwa.registration || needsInstall) return;
    // This permission request is reached exclusively by the user's button click.
    const granted = await Notification.requestPermission();
    setPermission(granted);
    if (granted !== "granted") throw new Error(granted === "denied" ? "Notificações bloqueadas. Altere a permissão nas configurações deste navegador." : "Permissão não concedida. Você pode tentar novamente quando quiser.");
    const key = applicationServerKey(capabilities.public_key);
    let subscription = await pwa.registration.pushManager.getSubscription();
    let created = false;
    if (subscription) {
      const activeKey = subscription.options.applicationServerKey;
      const matchesKey = activeKey && activeKey.byteLength === key.length && !new Uint8Array(activeKey).some((byte, index) => byte !== key[index]);
      const own = devices.some(device => device.endpoint_hash === currentHash);
      if (!matchesKey || !own) { await subscription.unsubscribe(); subscription = null; }
    }
    if (!subscription) {
      subscription = await pwa.registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: key });
      created = true;
    }
    try { await api.post<PushDevice>("/push/subscriptions", pushSubscriptionBody(subscription, label.trim())); }
    catch (err) {
      // Failed registration is not presented as enabled. No implicit write retry.
      if (created) await subscription.unsubscribe().catch(() => false);
      throw err;
    }
    await reload(); setConsent(false);
    setMessage("Notificações ativadas neste dispositivo. Use o teste para verificar o recebimento.");
  }

  async function revoke(device: PushDevice) {
    await api.delete(`/push/subscriptions/${device.id}`);
    if (device.endpoint_hash === currentHash) await clearBrowserPush();
    await reload();
    setMessage("Dispositivo desativado. Novos alertas não serão enviados para essa inscrição.");
  }

  return <Panel title="Aplicativo e notificações">
    <div className="space-y-3">
      <p className="text-sm">Instale o LexFlow para abrir sua central pela tela inicial. Consultas, documentos e mensagens exigem conexão.</p>
      {pwa.installed ? <p className="text-sm text-green-300">LexFlow aberto como aplicativo instalado.</p>
        : pwa.ios ? <p className="text-sm text-zinc-300">No iPhone ou iPad: abra no Safari, toque em Compartilhar → Adicionar à Tela de Início. Abra pelo ícone para ativar as notificações (iOS/iPadOS 16.4 ou superior).</p>
        : pwa.installPrompt ? <button type="button" className={button} disabled={busy} onClick={() => run(pwa.install)}>Instalar LexFlow</button>
        : <p className="text-sm text-zinc-400">No menu do navegador, procure “Instalar aplicativo” ou “Adicionar à tela inicial”. A disponibilidade depende do navegador.</p>}
      {!pwa.supported && <p className="text-sm text-amber-300">Instalação e notificações precisam de um navegador compatível e de conexão HTTPS. Localhost funciona apenas no computador de desenvolvimento.</p>}
    </div>
    <State loading={loading} error={error || pwa.error} />
    {message && <p role="status" className="text-sm text-green-300">{message}</p>}
    {!loading && capabilities && <div className="space-y-3 border-t border-zinc-800 pt-4">
      <p className="text-sm">Receba alertas genéricos de tarefas atribuídas e atualizações do portal, mesmo com o app fechado. Nomes, processos e conteúdo de mensagens não aparecem na tela bloqueada.</p>
      <p className="text-xs text-zinc-400">O sistema pode pedir login ao abrir um alerta. Sair da conta desativa os alertas desta sessão. Notificações não substituem a conferência de prazos; a entrega depende da conexão e das permissões do aparelho.</p>
      {!capabilities.enabled && <p className="text-sm text-amber-300">Web Push ainda não está habilitado neste ambiente. A equipe precisa configurar as chaves VAPID e o serviço de envio.</p>}
      {!supportsPush && <p className="text-sm text-zinc-400">Este navegador não oferece Web Push. No iPhone/iPad, tente pelo aplicativo adicionado à Tela de Início.</p>}
      {permission === "denied" && <p className="text-sm text-amber-300">Notificações bloqueadas neste navegador. Libere a permissão nas configurações do site e recarregue esta página.</p>}
      {currentDevice ? <p className="text-sm text-green-300">Este dispositivo está ativo: {currentDevice.label}. Válido até {dateText(currentDevice.expires_at)}.</p>
        : <form className="space-y-3" onSubmit={event => { event.preventDefault(); void run(subscribe); }}>
          <Field label="Nome deste dispositivo"><input className={control} value={label} onChange={event => setLabel(event.target.value)} minLength={2} maxLength={80} required autoComplete="off" placeholder="Ex.: Meu celular" /></Field>
          <label className="flex items-start gap-3 text-sm"><input type="checkbox" checked={consent} onChange={event => setConsent(event.target.checked)} className="mt-1 h-5 w-5 shrink-0" /><span>Quero receber notificações neste dispositivo. Sei que alertas podem aparecer na tela bloqueada.</span></label>
          <button className={primary} disabled={busy || !consent || !capabilities.enabled || !capabilities.public_key || !supportsPush || !pwa.ready || needsInstall || permission === "denied" || label.trim().length < 2}>{busy ? "Processando…" : "Ativar notificações neste dispositivo"}</button>
        </form>}
      <h3 className="pt-2 text-sm font-medium">Seus dispositivos autorizados</h3>
      {devices.length === 0 && <p className="text-sm text-zinc-400">Nenhum dispositivo autorizado.</p>}
      <ul className="space-y-3">{devices.map(device => <li key={device.id} className="rounded-lg border border-zinc-800 p-3 space-y-2">
        <p className="text-sm font-medium break-words">{device.label}{device.endpoint_hash === currentHash && " · Este dispositivo"}</p>
        <p className="text-xs text-zinc-400">Última confirmação: {dateText(device.last_seen_at)} · Expira: {dateText(device.expires_at)}</p>
        <div className="flex flex-wrap gap-2">
          <button type="button" className={button} disabled={busy || !capabilities.enabled} aria-label={`Testar notificações em ${device.label}`} onClick={() => run(async () => {
            await api.post(`/push/subscriptions/${device.id}/test`, {});
            setMessage("Teste colocado na fila. Aguarde o aviso no dispositivo; isso ainda não confirma a entrega. Verifique também o modo Não Perturbe.");
          })}>Enviar teste</button>
          <button type="button" className={button} disabled={busy} aria-label={`Desativar notificações em ${device.label}`} onClick={() => run(() => revoke(device))}>Desativar</button>
        </div>
      </li>)}</ul>
    </div>}
  </Panel>;
}
