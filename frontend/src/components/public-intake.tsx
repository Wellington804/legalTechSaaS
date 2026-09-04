"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { api } from "@/lib/api-client";
import { Field, State, control, errorText, primary } from "@/components/workspace/shared";

type IntakeForm = { form_title: string; notice_version: string; consent_version: string; notice_url: string | null };

export function PublicIntake() {
  const [token, setToken] = useState("");
  const [form, setForm] = useState<IntakeForm | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [received, setReceived] = useState(false);
  const requestId = useRef(crypto.randomUUID());

  useEffect(() => {
    const fragment = new URLSearchParams(window.location.hash.slice(1));
    const value = fragment.get("token") || "";
    // The public access secret lives only in memory; fragments are not sent to the server.
    window.history.replaceState(null, "", window.location.pathname);
    if (value.length < 32 || value.length > 512) { setError("Este link de atendimento é inválido ou está incompleto. Peça um novo link ao escritório."); setLoading(false); return; }
    setToken(value);
    api.get<IntakeForm>("/operations/intake", { headers: { "X-Intake-Token": value } })
      .then(setForm)
      .catch(reason => setError(errorText(reason)))
      .finally(() => setLoading(false));
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!form || !token) return;
    const values = new FormData(event.currentTarget);
    setBusy(true); setError("");
    try {
      await api.post("/operations/intake", {
        name: values.get("name"), email: values.get("email") || null, phone: values.get("phone") || null,
        subject: values.get("subject") || null, message: values.get("message") || null,
        preferred_contact_at: values.get("preferred_contact_at") ? new Date(String(values.get("preferred_contact_at"))).toISOString() : null,
        consent_version: form.consent_version, consent: true,
      }, { headers: { "X-Intake-Token": token, "Idempotency-Key": requestId.current } });
      setReceived(true);
    } catch (reason) { setError(errorText(reason)); }
    finally { setBusy(false); }
  }

  return <main className="min-h-dvh bg-zinc-950 px-4 py-8 text-zinc-100 sm:py-14">
    <div className="mx-auto max-w-xl space-y-6"><header><p className="text-sm font-medium text-blue-300">LexFlow</p><h1 className="mt-2 text-2xl font-semibold tracking-tight">{form?.form_title || "Atendimento do escritório"}</h1><p className="mt-2 text-sm text-zinc-400">Envie seus dados com segurança. O escritório analisará a solicitação; o envio não cria relação advogado-cliente nem garante aceitação do caso.</p></header>
      <State loading={loading} error={error} />
      {received ? <section role="status" className="rounded-lg border border-emerald-800 bg-emerald-950/20 p-5"><h2 className="font-medium text-emerald-200">Solicitação recebida</h2><p className="mt-2 text-sm text-zinc-300">O escritório recebeu seus dados para análise e entrará em contato pelos canais informados.</p></section> : form && <form onSubmit={submit} className="space-y-4 rounded-xl border border-zinc-800 bg-zinc-900/60 p-4 sm:p-6"><fieldset disabled={busy} className="space-y-4">
        <Field label="Nome completo"><input className={control} name="name" autoComplete="name" required minLength={2} maxLength={200} /></Field>
        <div className="grid gap-4 sm:grid-cols-2"><Field label="E-mail (opcional)"><input className={control} name="email" type="email" autoComplete="email" maxLength={320} /></Field><Field label="Telefone (opcional)"><input className={control} name="phone" type="tel" inputMode="tel" autoComplete="tel" maxLength={32} placeholder="(11) 99999-9999" /></Field></div>
        <Field label="Assunto"><input className={control} name="subject" maxLength={160} placeholder="Como o escritório pode ajudar?" /></Field>
        <Field label="Melhor data e horário para contato (opcional)"><input className={control} name="preferred_contact_at" type="datetime-local" /></Field>
        <Field label="Conte brevemente sua necessidade"><textarea className={control} name="message" rows={6} maxLength={4000} /></Field>
        <label className="flex min-h-11 items-start gap-3 text-sm text-zinc-300"><input className="mt-1 h-4 w-4 shrink-0" type="checkbox" required /> <span>Li as informações de privacidade e autorizo o uso destes dados para o escritório analisar e responder esta solicitação.{form.notice_url && <> <a className="text-blue-300 underline" href={form.notice_url} target="_blank" rel="noopener noreferrer">Ler aviso de privacidade</a>.</>}</span></label>
        <button className={primary} disabled={busy}>{busy ? "Enviando…" : "Enviar solicitação"}</button>
      </fieldset></form>}
    </div>
  </main>;
}
