"use client";

import { useMemo, useState } from "react";
import { Field, Page, Panel, State, control, dateText, useResource } from "@/components/workspace/shared";
import type { List, Row } from "@/components/workspace/records";

const actions: Record<string, string> = {
  BRAND_PROFILE_CREATED: "criou uma identidade documental", BRAND_DRAFT_UPDATED: "salvou alterações em uma identidade documental", BRAND_PUBLISHED: "publicou uma nova versão da identidade documental",
  BRAND_PROFILE_DUPLICATED: "duplicou uma identidade documental", BRAND_PROFILE_ARCHIVED: "arquivou uma identidade documental",
  BRAND_ASSET_IMPORTED: "adicionou uma referência visual à identidade", BRAND_AI_REQUESTED: "pediu uma sugestão visual à IA", BRAND_AI_PROPOSED: "recebeu uma sugestão visual da IA",
  BRAND_DOCUMENT_EXPORTED: "exportou um documento com identidade visual",
  OFFICE_UPDATED: "atualizou as informações do escritório", ACCOUNT_PROFILE_UPDATED: "atualizou seus dados profissionais", WORKSPACE_TASK_CREATED: "criou um compromisso",
  WORKSPACE_CASE_CREATED: "criou um processo", WORKSPACE_CLIENT_CREATED: "cadastrou um cliente", WORKSPACE_DOCUMENT_CREATED: "criou um documento",
  WORKSPACE_CASE_ACCESS_REVOKED: "revogou um acesso ao processo", WHATSAPP_CONNECTION_STARTED: "iniciou a conexão do WhatsApp",
  WHATSAPP_CONNECTED: "conectou o WhatsApp do escritório", WHATSAPP_RECONNECTED: "reiniciou a conexão do WhatsApp", WHATSAPP_DISCONNECTED: "desconectou o WhatsApp do escritório",
  SUPPORT_PILOT_EMAIL_APPROVED: "confirmou o e-mail de acesso ao piloto",
};
const areas: Record<string, string> = { branding: "Identidade documental", tenant: "Escritório", user: "Perfil", workspace_tasks: "Agenda", workspace_cases: "Processos", workspace_clients: "Clientes", workspace_documents: "Documentos", case_communication: "Comunicações" };

export default function PageView() {
  const [person, setPerson] = useState(""); const [area, setArea] = useState(""); const [period, setPeriod] = useState("30");
  const logsPath = useMemo(() => {
    const params = new URLSearchParams(); if (person) params.set("user_id", person); if (area) params.set("area", area); if (period) { const from = new Date(); from.setDate(from.getDate() - Number(period)); params.set("date_from", from.toISOString()); }
    return `/audit/logs?${params}`;
  }, [area, period, person]);
  const logs = useResource<Row[]>(logsPath); const members = useResource<List>("/workspace/members");
  return <Page title="Histórico do escritório" subtitle="Veja quem alterou informações e quando. Códigos técnicos ficam reservados para suporte.">
    <Panel title="Filtrar alterações"><div className="grid gap-3 sm:grid-cols-3"><Field label="Pessoa"><select className={control} value={person} onChange={event => setPerson(event.target.value)}><option value="">Todas</option>{members.data?.items.map(item => <option key={item.id} value={item.id}>{item.full_name}</option>)}</select></Field><Field label="Área"><select className={control} value={area} onChange={event => setArea(event.target.value)}><option value="">Todas</option>{Object.entries(areas).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></Field><Field label="Período"><select className={control} value={period} onChange={event => setPeriod(event.target.value)}><option value="7">Últimos 7 dias</option><option value="30">Últimos 30 dias</option><option value="90">Últimos 90 dias</option><option value="">Todo o histórico carregado</option></select></Field></div></Panel>
    <Panel title="Alterações recentes"><State loading={logs.loading} error={logs.error || members.error} />{logs.data && !logs.data.length && <p className="text-sm text-zinc-400">Nenhuma alteração corresponde aos filtros.</p>}<div className="space-y-2">{logs.data?.map(log => <article key={log.id} className="rounded-lg border border-zinc-800 bg-zinc-950/30 p-4"><p className="text-sm font-medium">{log.actor_name} {actions[log.action] || "realizou uma alteração"}.</p><p className="mt-1 text-xs text-zinc-400">{dateText(log.created_at)} · {areas[log.resource_type] || "Administração"}</p><details className="group mt-2 text-xs"><summary className="min-h-11 cursor-pointer list-none content-center text-zinc-500">Detalhes técnicos para suporte</summary><pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-all rounded-lg bg-zinc-950 p-3">{JSON.stringify({ código: log.action, recurso: log.resource_type, identificador: log.resource_id, dados: log.details || {}, hash: log.current_hash }, null, 2)}</pre></details></article>)}</div></Panel>
  </Page>;
}
