"use client";

import Link from "next/link";
import { useState } from "react";
import { api } from "@/lib/api-client";
import { clearBrowserPush } from "@/lib/pwa";
import { isOfficeAdminRole, useUser } from "@/context/user-context";
import { Action, Field, JsonExport, Page, Panel, State, button, control, dateText, errorText, primary, useResource } from "./shared";
import { display, type Row } from "./records";
import { PwaSettings } from "./pwa-settings";
import { ThemeSettings } from "./theme-settings";

type Section = "profile" | "security" | "office" | "privacy" | "app" | "subscription";

function readAddress(data: FormData, prefix: string) {
  const value = (name: string) => String(data.get(`${prefix}_${name}`) || "").trim();
  const address = { street: value("street"), number: value("number"), complement: value("complement") || null, district: value("district") || null, city: value("city"), state: value("state"), postal_code: value("postal_code") };
  if (!Object.values(address).some(Boolean)) return null;
  if (!address.street || !address.number || !address.city || address.state.length !== 2 || address.postal_code.length < 8) throw new Error("Complete rua, número, cidade, UF e CEP do endereço.");
  return address;
}

function AddressFields({ prefix, address }: { prefix: string; address?: Row | null }) {
  return <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3"><Field label="Rua / avenida"><input className={control} name={`${prefix}_street`} defaultValue={address?.street || ""} /></Field><Field label="Número"><input className={control} name={`${prefix}_number`} defaultValue={address?.number || ""} /></Field><Field label="Complemento"><input className={control} name={`${prefix}_complement`} defaultValue={address?.complement || ""} /></Field><Field label="Bairro"><input className={control} name={`${prefix}_district`} defaultValue={address?.district || ""} /></Field><Field label="Cidade"><input className={control} name={`${prefix}_city`} defaultValue={address?.city || ""} /></Field><Field label="UF"><input className={control} name={`${prefix}_state`} minLength={2} maxLength={2} defaultValue={address?.state || ""} /></Field><Field label="CEP"><input className={control} name={`${prefix}_postal_code`} inputMode="numeric" defaultValue={address?.postal_code || ""} /></Field></div>;
}

export function Account() {
  const { user } = useUser();
  const profile = useResource<Row>("/account/profile");
  const [section, setSection] = useState<Section>("profile");
  const subscription = useResource<Row>(profile.data?.role === "admin" && section === "subscription" ? "/account/subscription" : null);
  const privacy = useResource<Row>(section === "privacy" ? "/account/privacy" : null);
  const privacyRequests = useResource<{ items?: Row[] } | Row[]>(section === "privacy" ? "/account/privacy/requests" : null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [mfa, setMfa] = useState<Row | null>(null);
  const [codes, setCodes] = useState<string[]>([]);
  const isAdmin = isOfficeAdminRole(user.role);
  const sections: Array<{ id: Section; label: string; admin?: boolean }> = [
    { id: "profile", label: "Perfil" },
    { id: "security", label: "Segurança" },
    { id: "office", label: "Escritório", admin: true },
    { id: "privacy", label: "Privacidade" },
    { id: "app", label: "Aplicativo" },
    { id: "subscription", label: "Assinatura", admin: true },
  ];

  return <Page title="Conta e escritório" subtitle="Escolha uma área para ajustar. Alterações de pagamento não interferem nos recebimentos dos seus clientes.">
    <Link className={button} href="/dashboard/pilot">Abrir orientações e suporte do piloto</Link>
    <State loading={profile.loading} error={profile.error || error} />
    {message && <p role="status" className="text-sm text-green-300">{message}</p>}
    {profile.data && <>
      <nav aria-label="Configurações da conta" className="flex max-w-full flex-wrap gap-2">
        {sections.filter(item => !item.admin || isAdmin).map(item => <button key={item.id} type="button" className={section === item.id ? primary : button} aria-current={section === item.id ? "page" : undefined} onClick={() => setSection(item.id)}>{item.label}</button>)}
      </nav>

      {section === "profile" && <Panel title="Perfil">
        <form key={profile.data.user_id} className="space-y-3" onSubmit={async event => {
          event.preventDefault(); const data = new FormData(event.currentTarget); setError("");
          try { await api.patch("/account/profile", { full_name: data.get("name"), professional_name: data.get("professional_name") || null, oab_number: data.get("oab") || null, oab_uf: data.get("uf") || null, professional_email: data.get("professional_email") || null, professional_phone: data.get("professional_phone") || null, professional_address: readAddress(data, "professional") }); profile.reload(); setMessage("Dados profissionais salvos e disponíveis nos documentos."); } catch (err) { setError(errorText(err)); }
        }}>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3"><Field label="Nome da conta"><input className={control} name="name" required minLength={2} maxLength={120} defaultValue={profile.data.user_name} /></Field><Field label="Nome profissional nos documentos"><input className={control} name="professional_name" maxLength={120} defaultValue={profile.data.professional_name || ""} /></Field><Field label="OAB"><input className={control} name="oab" maxLength={30} defaultValue={profile.data.oab_number || ""} /></Field><Field label="UF da OAB"><input className={control} name="uf" minLength={2} maxLength={2} defaultValue={profile.data.oab_uf || ""} /></Field><Field label="E-mail profissional"><input className={control} name="professional_email" type="email" defaultValue={profile.data.professional_email || ""} /></Field><Field label="Telefone profissional"><input className={control} name="professional_phone" type="tel" defaultValue={profile.data.professional_phone || ""} /></Field></div>
          <h3 className="text-sm font-semibold">Endereço profissional padrão</h3><AddressFields prefix="professional" address={profile.data.professional_address} />
          <button className={primary}>Salvar dados profissionais</button>
        </form>
        <p className="text-xs text-zinc-400">{profile.data.email} · {profile.data.email_verified ? "E-mail verificado" : "Verificação pendente"}</p>
        {!profile.data.email_verified && <Action run={() => api.post("/account/email-verifications/request", {})} onDone={() => setMessage("Solicitação de verificação enviada ao serviço de e-mail.")}>Solicitar verificação de e-mail</Action>}
        <a className={button} href="/dashboard">Abrir a central de verificações</a>
      </Panel>}

      {section === "security" && <>
        <Panel title="Autenticação em dois fatores">
          <p className="text-sm text-zinc-400">{profile.data.mfa_enabled ? "MFA ativado." : "MFA não ativado."} {profile.data.mfa_required && "Obrigatório para acessar dados do escritório neste ambiente."}</p>
          {!profile.data.mfa_enabled && <Action run={async () => setMfa(await api.post<Row>("/account/mfa/setup", {}))}>Configurar aplicativo autenticador</Action>}
          {mfa && <div className="space-y-3"><p className="text-xs text-amber-300">Cadastre esta chave no autenticador. Não compartilhe nem envie por e-mail.</p><code className="block break-all bg-zinc-950 p-3 text-sm">{mfa.secret}</code>
            <form className="flex flex-wrap gap-2" onSubmit={async event => { event.preventDefault(); const code = new FormData(event.currentTarget).get("code"); try { const result = await api.post<{ recovery_codes?: string[] }>("/account/mfa/confirm", { code }); setCodes(result.recovery_codes || []); setMfa(null); profile.reload(); setMessage("MFA confirmado. Guarde os códigos de recuperação em local seguro."); } catch (err) { setError(errorText(err)); } }}><input className={`${control} max-w-xs`} name="code" aria-label="Código do autenticador" autoComplete="one-time-code" inputMode="numeric" required pattern="[0-9]{6}" /><button className={primary}>Confirmar MFA</button></form>
          </div>}
          {codes.length > 0 && <pre className="whitespace-pre-wrap break-all text-sm">{codes.join("\n")}</pre>}
        </Panel>
        <Panel title="Senha e sessões">
          <form className="space-y-3" onSubmit={async event => { event.preventDefault(); const data = new FormData(event.currentTarget); try { await api.post("/account/password", { current_password: data.get("current"), new_password: data.get("new"), revoke_other_sessions: true }); window.location.assign("/dashboard"); } catch (err) { setError(errorText(err)); } }}><div className="grid gap-3 sm:grid-cols-2"><Field label="Senha atual"><input className={control} type="password" name="current" autoComplete="current-password" required /></Field><Field label="Nova senha (12+ caracteres)"><input className={control} type="password" name="new" autoComplete="new-password" minLength={12} maxLength={72} required /></Field></div><button className={primary}>Alterar senha e revogar outras sessões</button></form>
          <Action run={async () => { await clearBrowserPush().catch(() => {}); await api.post("/account/sessions/revoke-all", {}); window.location.assign("/dashboard"); }}>Encerrar todas as sessões</Action>
        </Panel>
      </>}

      {section === "office" && isAdmin && <Panel title="Escritório"><form className="space-y-3" onSubmit={async event => { event.preventDefault(); const data = new FormData(event.currentTarget); try { await api.patch("/account/office", { name: data.get("name"), legal_name: data.get("legal_name") || null, cnpj: data.get("cnpj") || null, office_email: data.get("office_email") || null, office_phone: data.get("office_phone") || null, website: data.get("website") || null, timezone: data.get("timezone"), signature_city: data.get("signature_city") || null, office_address: readAddress(data, "office") }); profile.reload(); setMessage("Dados do escritório atualizados."); } catch (err) { setError(errorText(err)); } }}><div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3"><Field label="Nome do escritório"><input className={control} name="name" defaultValue={profile.data.tenant_name} minLength={2} maxLength={120} required /></Field><Field label="Razão social"><input className={control} name="legal_name" defaultValue={profile.data.tenant_legal_name || ""} /></Field><Field label="CNPJ"><input className={control} name="cnpj" maxLength={20} defaultValue={profile.data.tenant_cnpj || ""} /></Field><Field label="E-mail"><input className={control} name="office_email" type="email" defaultValue={profile.data.tenant_email || ""} /></Field><Field label="Telefone"><input className={control} name="office_phone" type="tel" defaultValue={profile.data.tenant_phone || ""} /></Field><Field label="Site"><input className={control} name="website" type="url" defaultValue={profile.data.tenant_website || ""} /></Field><Field label="Fuso horário"><select className={control} name="timezone" defaultValue={profile.data.tenant_timezone || "America/Sao_Paulo"}><option value="America/Sao_Paulo">Brasília (São Paulo)</option><option value="America/Manaus">Manaus</option><option value="America/Rio_Branco">Rio Branco</option><option value="America/Noronha">Fernando de Noronha</option></select></Field><Field label="Cidade padrão para assinatura"><input className={control} name="signature_city" defaultValue={profile.data.tenant_signature_city || ""} /></Field></div><h3 className="text-sm font-semibold">Endereço do escritório</h3><AddressFields prefix="office" address={profile.data.tenant_address} /><button className={primary}>Salvar escritório</button></form></Panel>}

      {section === "app" && <><ThemeSettings /><PwaSettings /></>}

      {section === "privacy" && <>
        <Panel title="Privacidade e ciclo dos dados"><State loading={privacy.loading} error={privacy.error} />{privacy.data && <>
          <p className="text-sm text-zinc-300">{privacy.data.configured ? "Política operacional configurada." : "Configuração incompleta: mantenha formulários públicos pausados até publicar o aviso e definir contato, versão e retenção."}</p>
          {isAdmin ? <form key={String(privacy.data.privacy_notice_version)} className="space-y-3" onSubmit={async event => { event.preventDefault(); const data = new FormData(event.currentTarget); setError(""); try { await api.patch("/account/privacy", { privacy_notice_url: data.get("notice_url") || null, privacy_notice_version: data.get("notice_version") || null, privacy_contact: data.get("privacy_contact") || null, data_retention_days: data.get("retention") ? Number(data.get("retention")) : null }); privacy.reload(); setMessage("Política de privacidade atualizada e auditada."); } catch (err) { setError(errorText(err)); } }}><div className="grid gap-3 sm:grid-cols-2"><Field label="URL do aviso publicado"><input className={control} type="url" name="notice_url" placeholder="https://seusite.com/privacidade" defaultValue={privacy.data.privacy_notice_url || ""} /></Field><Field label="Versão do aviso"><input className={control} name="notice_version" maxLength={64} placeholder="privacidade-2026-01" defaultValue={privacy.data.privacy_notice_version || ""} /></Field><Field label="Contato de privacidade"><input className={control} type="email" name="privacy_contact" defaultValue={privacy.data.privacy_contact || ""} /></Field><Field label="Retenção operacional (dias)"><input className={control} type="number" name="retention" min={30} max={3650} defaultValue={privacy.data.data_retention_days || ""} /></Field></div><p className="text-xs text-zinc-400">Defina o prazo com orientação jurídica e obrigações profissionais; o sistema não presume uma regra única.</p><button className={primary}>Salvar política</button></form> : <p className="text-xs text-zinc-400">O administrador do escritório gerencia o aviso e a retenção.</p>}
        </>}</Panel>
        <Panel title="Solicitações sobre dados"><p className="text-sm text-zinc-400">A solicitação abre um protocolo. Exclusão e anonimização só são concluídas após análise de retenção legal e registro da decisão.</p><form className="space-y-3" onSubmit={async event => { event.preventDefault(); const data = new FormData(event.currentTarget); setError(""); try { await api.post("/account/privacy/requests", { request_type: data.get("request_type"), scope: data.get("scope"), reason: data.get("reason") || null }); event.currentTarget.reset(); privacyRequests.reload(); setMessage("Solicitação registrada para análise."); } catch (err) { setError(errorText(err)); } }}><div className="grid gap-3 sm:grid-cols-2"><Field label="Operação"><select className={control} name="request_type" defaultValue="export"><option value="export">Exportar dados</option><option value="anonymization">Anonimizar dados</option><option value="deletion">Excluir dados</option></select></Field><Field label="Abrangência"><select className={control} name="scope" defaultValue="self"><option value="self">Minha conta</option>{isAdmin && <option value="tenant">Todo o escritório</option>}</select></Field></div><Field label="Motivo ou contexto (opcional)"><textarea className={control} name="reason" rows={3} maxLength={2000} /></Field><div className="flex flex-wrap gap-2"><button className={primary}>Registrar solicitação</button>{isAdmin && <JsonExport path="/workspace/export" />}</div></form><State loading={privacyRequests.loading} error={privacyRequests.error} />{(Array.isArray(privacyRequests.data) ? privacyRequests.data : privacyRequests.data?.items || []).map(item => <article key={item.id} className="border-t border-zinc-800 py-3 text-sm"><p>{display(item.request_type)} · {display(item.scope)} · {display(item.status)}</p><p className="text-xs text-zinc-400">{dateText(item.created_at)}{item.resolution_note ? ` · ${item.resolution_note}` : ""}</p></article>)}</Panel>
      </>}

      {section === "subscription" && isAdmin && <Panel title="Assinatura e limites"><State loading={subscription.loading} error={subscription.error} />{subscription.data && <><p className="text-sm">Plano: {display(subscription.data.plan)} · {display(subscription.data.status)}</p><p className="text-xs text-zinc-400">Fim do teste: {dateText(subscription.data.trial_ends_at)}</p><p className="text-xs text-zinc-400">Usuários: {subscription.data.active_users} / {subscription.data.quota_users} · Mensagens no mês: {subscription.data.messages_used} / {subscription.data.quota_messages} · Armazenamento: {Math.ceil(subscription.data.storage_used_bytes / 1024)} KB / {Math.floor(subscription.data.quota_storage_bytes / 1048576)} MB</p></>}
        <p className="text-xs text-zinc-400">A contratação é assistida enquanto não houver provedor de cobrança homologado. Não informe dados de cartão aqui.</p><div className="flex flex-wrap gap-2"><Action run={() => api.post("/account/subscription/request", { message: "Solicito contratação ou revisão dos limites do escritório." })} onDone={() => setMessage("Solicitação registrada para atendimento comercial. Não houve cobrança.")}>Solicitar contratação</Action><Action run={() => api.post("/account/subscription/cancel", {})} onDone={subscription.reload}>Solicitar cancelamento ao fim do período</Action></div>
      </Panel>}
    </>}
  </Page>;
}
