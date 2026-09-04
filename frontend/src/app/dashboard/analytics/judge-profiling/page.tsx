"use client";
import Link from "next/link";
import { Page, Panel, State, useResource } from "@/components/workspace/shared";
export default function PageView() {
  const data = useResource<Record<string, Record<string, unknown>>>("/workspace/analytics");
  const labels: Record<string, string> = { clients_by_stage: "Clientes por etapa", cases_by_status: "Processos por situação", tasks: "Agenda", fees: "Financeiro" };
  const itemLabels: Record<string, string> = { lead: "Novos contatos", prospect: "Em atendimento", client: "Clientes", inactive: "Inativos", open: "Em andamento", paused: "Suspensos", closed: "Encerrados", archived: "Arquivados", due_today: "Para hoje", overdue: "Vencidos", upcoming: "Próximos", completed: "Concluídos", posted_amount: "Honorários lançados", pending_amount: "Honorários em rascunho" };
  const links: Record<string, string> = { clients_by_stage: "/dashboard/crm", cases_by_status: "/dashboard/tracker", tasks: "/dashboard/tasks", fees: "/dashboard/financeiro" };
  const valueText = (group: string, key: string, value: unknown) => group === "fees" && key.endsWith("_amount") ? new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number(value || 0)) : String(value ?? "—");
  const groups = data.data ? Object.entries(data.data).filter(([, value]) => value && typeof value === "object") : [];
  return <Page title="Indicadores da carteira" subtitle="Resumo dos seus registros autorizados. Os números mostram a situação cadastrada, sem prever resultado de processo."><State loading={data.loading} error={data.error} />{data.data && !groups.length && <Panel title="Sem indicadores ainda"><p className="text-sm text-zinc-400">Cadastre ou atualize registros para ver o resumo da carteira.</p><Link href="/dashboard" className="text-sm text-blue-300">Ir para a Central</Link></Panel>}<div className="grid sm:grid-cols-2 gap-4">{groups.map(([key, value]) => <Panel key={key} title={labels[key] || "Resumo"}>{Object.entries(value).filter(([name]) => name !== "currency").map(([name, total]) => <div key={name} className="flex justify-between text-sm gap-3"><span className="min-w-0 text-zinc-400">{itemLabels[name] || "Outro"}</span><span>{valueText(key, name, total)}</span></div>)}<Link className="inline-flex min-h-11 items-center text-sm text-blue-300" href={links[key] || "/dashboard"}>Abrir registros</Link></Panel>)}</div></Page>;
}
