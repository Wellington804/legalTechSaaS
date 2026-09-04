"use client";
import Link from "next/link";
import { useState } from "react";
import { Page, Panel, State, Field, control, primary, useResource } from "@/components/workspace/shared";
import type { Row } from "@/components/workspace/records";
export default function PageView() {
  const [query, setQuery] = useState(""); const taxId = query.replace(/\D/g, "");
  const result = useResource<{ clients: Row[]; parties: Row[]; matches?: Row[] }>(query ? `/workspace/conflicts?q=${encodeURIComponent(query)}${[11, 14].includes(taxId.length) ? `&tax_id=${taxId}` : ""}` : null);
  const matches = result.data ? [...(result.data.clients || []), ...(result.data.parties || []), ...(result.data.matches || [])] : [];
  return <Page title="Conflitos de interesse" subtitle="Verifique nomes e documentos nos cadastros internos que você tem autorização para consultar. O resultado exige análise ética profissional.">
    <Panel title="Verificar na base do escritório"><form className="space-y-3" onSubmit={e => { e.preventDefault(); setQuery(String(new FormData(e.currentTarget).get("q") || "").trim()); }}><Field label="Nome, CPF ou CNPJ"><input className={control} name="q" minLength={2} maxLength={200} required /></Field><button className={primary}>Verificar na base do escritório</button></form><details><summary className="min-h-11 cursor-pointer content-center text-sm text-blue-300">O que esta verificação consulta?</summary><div className="space-y-1 text-xs text-zinc-400"><p>Consulta: clientes cadastrados e partes de processos acessíveis ao seu usuário.</p><p>Não consulta: Receita Federal, OAB, tribunais, internet, bases públicas externas ou dados de outros escritórios.</p><p>Uma ausência de correspondência não comprova inexistência de conflito.</p></div></details></Panel>
    {query && <Panel title="Correspondências internas"><State loading={result.loading} error={result.error} />{result.data && !matches.length && <div className="rounded-lg border border-amber-800 p-3 text-sm text-amber-300">Nenhuma correspondência foi encontrada na base interna consultada. Confira grafia, documentos, partes relacionadas e outras fontes aplicáveis antes de decidir.</div>}{matches.map((row, index) => <div key={`${row.id}-${index}`} className="border-b border-zinc-800 pb-3 text-sm"><p>{row.name} · {row.tax_id || "CPF/CNPJ não informado"}</p><p className="text-xs text-zinc-400">Fonte: {row.source === "workspace_clients" ? "cadastro de clientes" : "parte vinculada a caso acessível"}</p>{row.case_id && <Link className="inline-flex min-h-11 items-center text-xs text-blue-300" href={`/dashboard/cases/${row.case_id}`}>Conferir vínculo com o caso</Link>}</div>)}</Panel>}
  </Page>;
}
