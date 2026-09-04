"use client";

import { useState } from "react";
import { apiClient } from "@/lib/api-client";
import { button, control, errorText, Field, Panel, State } from "./shared";
import type { Row } from "./records";

type Preview = { columns: string[]; rows: Record<string, string>[]; row_count: number; suggested_mapping: Record<string, string> };
type ImportField = { key: "name" | "email" | "phone" | "tax_id" | "stage"; label: string; required?: boolean };
const fields: ImportField[] = [
  { key: "name", label: "Nome ou razão social", required: true },
  { key: "email", label: "E-mail" }, { key: "phone", label: "Telefone ou WhatsApp" },
  { key: "tax_id", label: "CPF ou CNPJ" }, { key: "stage", label: "Etapa do relacionamento" },
];

export function ClientImport({ onImported }: { onImported: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [stage, setStage] = useState("lead");
  const [source, setSource] = useState("planilha");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");

  function downloadExample() {
    const csv = "Nome;E-mail;Telefone;CPF ou CNPJ;Etapa\nCliente Exemplo;cliente@exemplo.com.br;+5511999999999;12345678901;Cliente\n";
    const url = URL.createObjectURL(new Blob(["\ufeff" + csv], { type: "text/csv;charset=utf-8" }));
    const link = document.createElement("a"); link.href = url; link.download = "modelo-clientes-lexflow.csv"; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  async function analyze(selected: File) {
    setBusy(true); setError(""); setStatus(""); setPreview(null); setFile(selected);
    try {
      if (selected.size > 2 * 1024 * 1024) throw new Error("Use uma planilha de até 2 MB.");
      const body = new FormData(); body.set("file", selected);
      const result = await apiClient<Preview>("/workspace/clients/import-preview", { method: "POST", body });
      setPreview(result); setMapping(result.suggested_mapping);
    } catch (err) { setError(errorText(err)); } finally { setBusy(false); }
  }
  async function confirmImport() {
    if (!file || !preview || !mapping.name) return;
    setBusy(true); setError(""); setStatus("");
    try {
      const body = new FormData(); body.set("file", file); body.set("mapping", JSON.stringify(mapping)); body.set("default_stage", stage);
      const result = await apiClient<{ created: Row[]; skipped: unknown[] }>("/workspace/clients/import-file", { method: "POST", body });
      setStatus(`${result.created.length} cliente${result.created.length === 1 ? "" : "s"} importado${result.created.length === 1 ? "" : "s"}; ${result.skipped.length} duplicado${result.skipped.length === 1 ? "" : "s"} ignorado${result.skipped.length === 1 ? "" : "s"}.`);
      setPreview(null); setFile(null); setMapping({}); onImported();
    } catch (err) { setError(errorText(err)); } finally { setBusy(false); }
  }
  return <Panel title="Importar clientes de planilha" collapsibleOnMobile>
    <p className="text-sm text-zinc-400">Use uma planilha CSV ou XLSX com até 200 clientes. Você verá uma prévia e poderá indicar o significado de cada coluna antes de importar.</p>
    <div className="flex flex-wrap gap-2"><button type="button" className={button} onClick={downloadExample}>Baixar planilha de exemplo</button>
      <label className={`${button} cursor-pointer`}>{busy ? "Analisando…" : "Selecionar planilha"}<input className="sr-only" type="file" accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" disabled={busy} onChange={e => { const selected = e.target.files?.[0]; if (selected) void analyze(selected); e.currentTarget.value = ""; }} /></label></div>
    <Field label="Origem da planilha"><select className={control} value={source} onChange={e => setSource(e.target.value)}><option value="planilha">Planilha própria</option><option value="astrea">Exportação do Astrea</option><option value="projuris">Exportação do ProJuris</option><option value="advbox">Exportação do ADVBOX</option><option value="other">Outro sistema</option></select></Field>
    {source !== "planilha" && <p className="text-xs text-zinc-400">Este fluxo importa o arquivo exportado. Não acessa nem altera o sistema de origem.</p>}
    <State error={error} />{status && <p role="status" className="text-sm text-green-300">{status}</p>}
    {preview && <section className="space-y-4 border-t border-zinc-800 pt-4">
      <p className="text-sm font-medium">{file?.name} · {preview.row_count} linha{preview.row_count === 1 ? "" : "s"} encontrada{preview.row_count === 1 ? "" : "s"}</p>
      <div className="grid gap-3 sm:grid-cols-2">{fields.map(field => <Field key={field.key} label={`${field.label}${field.required ? " (obrigatório)" : ""}`}><select className={control} value={mapping[field.key] || ""} onChange={e => setMapping(current => { const next = { ...current }; if (e.target.value) next[field.key] = e.target.value; else delete next[field.key]; return next; })}><option value="">{field.required ? "Selecione uma coluna…" : "Não importar"}</option>{preview.columns.map(column => <option key={column} value={column}>{column}</option>)}</select></Field>)}</div>
      {!mapping.stage && <Field label="Etapa para linhas sem coluna correspondente"><select className={control} value={stage} onChange={e => setStage(e.target.value)}><option value="lead">Novo contato</option><option value="prospect">Em atendimento</option><option value="client">Cliente</option></select></Field>}
      <div className="max-w-full overflow-x-auto"><table className="min-w-full text-left text-xs"><caption className="pb-2 text-left text-zinc-400">Prévia das primeiras cinco linhas</caption><thead><tr>{fields.slice(0, 4).map(field => <th className="border-b border-zinc-800 p-2" key={field.key}>{field.label}</th>)}</tr></thead><tbody>{preview.rows.slice(0, 5).map((row, index) => <tr key={index}>{fields.slice(0, 4).map(field => <td className="max-w-48 border-b border-zinc-800 p-2 break-words" key={field.key}>{row[mapping[field.key]] || "—"}</td>)}</tr>)}</tbody></table></div>
      <div className="flex flex-wrap gap-2"><button type="button" className="min-h-11 rounded-lg bg-blue-600 px-4 py-2 text-sm text-white disabled:opacity-50" disabled={busy || !mapping.name} onClick={confirmImport}>{busy ? "Importando…" : `Confirmar importação de ${preview.row_count} clientes`}</button><button type="button" className={button} disabled={busy} onClick={() => { setPreview(null); setFile(null); setMapping({}); }}>Cancelar</button></div>
    </section>}
  </Panel>;
}
