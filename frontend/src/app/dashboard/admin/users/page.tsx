"use client";
import { useState } from "react";
import { api } from "@/lib/api-client";
import { Action, Field, Page, Panel, State, control, dateText, errorText, primary, useResource } from "@/components/workspace/shared";
import type { Row } from "@/components/workspace/records";
const roles: Record<string, string> = { admin: "Administrador", partner: "Sócio", lawyer: "Advogado", paralegal: "Assistente" };
export default function TeamPage() {
  const team = useResource<Row[]>("/account/team"); const [link, setLink] = useState(""); const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  const profile = useResource<Row>("/account/profile"); const canManage = profile.data?.role === "admin";
  const invites = useResource<{ items: Row[] }>(canManage ? "/account/team/invites" : null);
  return <Page title="Equipe e permissões" subtitle="Convites de uso único e acessos do escritório, sem apagar o histórico.">
    {canManage && <Panel title="Convidar membro"><form className="grid sm:grid-cols-3 gap-3 items-end" onSubmit={async e => {
      e.preventDefault(); const d = new FormData(e.currentTarget); setBusy(true); setError(""); setLink("");
      try { const result = await api.post<{ invite_link: string }>("/account/team/invites", { email: d.get("email"), role: d.get("role") }); setLink(result.invite_link); invites.reload(); } catch (err) { setError(errorText(err)); } finally { setBusy(false); }
    }}><Field label="E-mail"><input className={control} name="email" type="email" required /></Field><Field label="Permissão"><select className={control} name="role" defaultValue="lawyer">{Object.entries(roles).map(([key,label]) => <option key={key} value={key}>{label}</option>)}</select></Field><button className={primary} disabled={busy}>{busy ? "Criando…" : "Criar convite"}</button></form><State error={error} />
      {link && <Field label="Link exibido uma vez. Compartilhe por canal seguro; ele não foi enviado automaticamente."><input className={control} readOnly value={link} onFocus={e => e.target.select()} /></Field>}
    </Panel>}
    <State error={profile.error || error} />
    {canManage && <Panel title="Convites pendentes"><State loading={invites.loading} error={invites.error} empty={!invites.data?.items.length} />{invites.data?.items.map(invite => <div key={invite.id} className="flex flex-wrap gap-3 text-xs items-center"><span className="min-w-0">{invite.email} · {roles[invite.role]} · expira {dateText(invite.expires_at)}</span><Action run={() => api.post(`/account/team/invites/${invite.id}/cancel`, {})} onDone={invites.reload}>Cancelar convite</Action></div>)}</Panel>}
    <Panel title="Membros do escritório"><State loading={team.loading} error={team.error} empty={!team.data?.length} />{team.data?.map(member => <article key={member.id} className="border-b border-zinc-800 pb-4 flex flex-wrap gap-3 justify-between"><div className="min-w-0"><p className="text-sm">{member.full_name}</p><p className="text-xs text-zinc-400 break-all">{member.email} · {member.is_active ? "Ativo" : "Inativo"} · {roles[member.role]}</p></div>{canManage && <div className="flex flex-wrap gap-2"><select className={`${control} w-auto`} aria-label={`Permissão de ${member.full_name}`} value={member.role} onChange={async e => { try { await api.patch(`/account/team/${member.id}`, { role: e.target.value }); team.reload(); } catch (err) { setError(errorText(err)); } }}>{Object.entries(roles).map(([key,label]) => <option key={key} value={key}>{label}</option>)}</select><Action run={() => api.post(`/account/team/${member.id}/${member.is_active ? "deactivate" : "reactivate"}`, {})} onDone={team.reload}>{member.is_active ? "Desativar" : "Reativar"}</Action></div>}</article>)}</Panel>
  </Page>;
}
