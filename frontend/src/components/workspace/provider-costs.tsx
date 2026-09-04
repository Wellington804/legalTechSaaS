"use client";

import { useState, type FormEvent } from "react";
import { api } from "@/lib/api-client";
import { Field, Panel, State, button, control, errorText, primary, useResource } from "./shared";

type PriceVersion = {
  id: string;
  provider: string;
  version: number;
  currency: string;
  pricing_model: "commitment_floor" | "base_plus_usage";
  monthly_base_amount: string;
  observed_on: string;
  provenance_url: string;
  quote_required: boolean;
  items: { metric: string; unit_price: string; included_units: number }[];
};
type CostReport = { currency: string; monthly_base_amount: string; usage_amount: string; total_amount: string; quote_required: boolean; provenance_url: string };
const metrics = ["document_created", "signature_request_email", "document_query", "webhook_received"] as const;
const today = () => new Date().toLocaleDateString("en-CA");

export function ProviderCosts() {
  const prices = useResource<{ items: PriceVersion[] }>("/operations/provider-costs/prices");
  const usage = useResource<{ items: { provider: string; metric: string; units: number }[] }>("/operations/provider-costs/usage");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [report, setReport] = useState<CostReport | null>(null);
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(""); setNotice("");
    const data = new FormData(event.currentTarget);
    const items = metrics.flatMap(metric => {
      const value = String(data.get(`price_${metric}`) || "").trim();
      return value ? [{ metric, unit_price: value, included_units: Number(data.get(`included_${metric}`) || 0) }] : [];
    });
    if (!items.length) { setError("Informe ao menos um item de preço confirmado."); return; }
    try {
      await api.post("/operations/provider-costs/prices", {
        provider: data.get("provider"), currency: data.get("currency"), pricing_model: data.get("pricing_model"),
        monthly_base_amount: data.get("monthly_base_amount"), effective_on: data.get("effective_on"), observed_on: data.get("observed_on"),
        provenance_url: data.get("provenance_url"), quote_required: data.get("quote_required") === "on", notes: data.get("notes") || null, items,
      });
      setNotice("Tabela imutável registrada com fonte e data de observação."); prices.reload();
    } catch (reason) { setError(errorText(reason)); }
  }
  async function calculate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError("");
    const data = new FormData(event.currentTarget); const version = prices.data?.items.find(item => item.id === data.get("price_version_id"));
    if (!version) return;
    const volumes = Object.fromEntries(version.items.map(item => [item.metric, Number(data.get(`volume_${item.metric}`) || 0)]));
    try { setReport(await api.post<CostReport>("/operations/provider-costs/report", { provider: version.provider, price_version_id: version.id, volumes })); }
    catch (reason) { setError(errorText(reason)); }
  }
  return <Panel title="Custo dos provedores" description="Simule TCO somente com tabela confirmada, fonte e data. O LexFlow não embute preços comerciais." collapsibleOnMobile>
    <State loading={prices.loading || usage.loading} error={prices.error || usage.error || error} />
    {Boolean(usage.data?.items.length) && <div><p className="text-sm font-medium">Uso observado nos últimos 30 dias</p><div className="mt-1 flex flex-wrap gap-2">{usage.data?.items.map(item => <span key={`${item.provider}:${item.metric}`} className="rounded-full bg-zinc-800 px-3 py-1 text-xs">{item.provider} · {item.metric}: {item.units}</span>)}</div></div>}
    <details><summary className="min-h-11 cursor-pointer content-center font-medium">Cadastrar versão de preço</summary><form onSubmit={save} className="mt-3 grid gap-3 sm:grid-cols-2"><Field label="Provedor"><input className={control} name="provider" required pattern="[a-z][a-z0-9_-]+" placeholder="autentique ou clicksign" /></Field><Field label="Moeda"><input className={control} name="currency" required defaultValue="BRL" pattern="[A-Z]{3}" /></Field><Field label="Modelo"><select className={control} name="pricing_model" defaultValue="commitment_floor"><option value="commitment_floor">Compromisso mínimo</option><option value="base_plus_usage">Mensalidade + consumo</option></select></Field><Field label="Mensalidade ou compromisso"><input className={control} name="monthly_base_amount" type="number" min="0" step="0.000001" defaultValue="0" required /></Field><Field label="Vigência"><input className={control} name="effective_on" type="date" defaultValue={today()} required /></Field><Field label="Data da consulta"><input className={control} name="observed_on" type="date" defaultValue={today()} required /></Field><Field label="Fonte oficial"><input className={control} name="provenance_url" type="url" required placeholder="https://..." /></Field><Field label="Observação"><input className={control} name="notes" maxLength={1000} placeholder="Condições, impostos, SLA…" /></Field>{metrics.map(metric => <div key={metric} className="grid grid-cols-2 gap-2"><Field label={`Preço: ${metric}`}><input className={control} name={`price_${metric}`} type="number" min="0" step="0.000001" placeholder="Não confirmado" /></Field><Field label="Franquia"><input className={control} name={`included_${metric}`} type="number" min="0" step="1" defaultValue="0" /></Field></div>)}<label className="flex min-h-11 items-center gap-2 text-sm"><input name="quote_required" type="checkbox" /> Ainda exige cotação</label><button className={primary}>Registrar tabela imutável</button></form></details>
    {notice && <p role="status" className="text-sm text-emerald-300">{notice}</p>}
    <details><summary className="min-h-11 cursor-pointer content-center font-medium">Simular volume mensal</summary>{prices.data?.items.length ? <form onSubmit={calculate} className="mt-3 space-y-3"><Field label="Tabela"><select className={control} name="price_version_id" required>{prices.data.items.map(item => <option key={item.id} value={item.id}>{item.provider} v{item.version} · observada em {item.observed_on}</option>)}</select></Field>{prices.data.items.flatMap(item => item.items).filter((item, index, all) => all.findIndex(other => other.metric === item.metric) === index).map(item => <Field key={item.metric} label={`Volume: ${item.metric}`}><input className={control} name={`volume_${item.metric}`} type="number" min="0" step="1" defaultValue="0" /></Field>)}<button className={button}>Calcular TCO</button></form> : <p className="mt-2 text-sm text-zinc-400">Cadastre uma tabela confirmada antes de simular.</p>}</details>
    {report && <div className="rounded-lg border border-blue-800 bg-blue-950/15 p-3"><p className="font-medium">Total mensal estimado: {report.currency} {Number(report.total_amount).toFixed(2)}</p><p className="text-sm text-zinc-400">Base {Number(report.monthly_base_amount).toFixed(2)} · consumo {Number(report.usage_amount).toFixed(2)}{report.quote_required ? " · cotação ainda necessária" : ""}</p><a className="mt-2 inline-flex text-sm text-blue-300 underline" href={report.provenance_url} target="_blank" rel="noreferrer">Reabrir fonte oficial</a></div>}
  </Panel>;
}
