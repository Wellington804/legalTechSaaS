"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";
import { Field, Page, Panel, State, button, control, errorText, primary } from "@/components/workspace/shared";
export default function AccessPage() {
  const [action, setAction] = useState("register"); const [token, setToken] = useState(""); const [message, setMessage] = useState(""); const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  useEffect(() => { const params = new URLSearchParams(window.location.hash.slice(1)); if (params.has("token")) { setToken(params.get("token") || ""); setAction(params.get("action") || "invite"); history.replaceState(null, "", location.pathname); } }, []);
  return <main className="p-4 md:p-10"><Page title="Acesso ao LexFlow"><Panel title="Conta do escritório">
    {!token && <div className="flex flex-wrap gap-2"><button className={button} onClick={() => setAction("register")}>Criar escritório</button><button className={button} onClick={() => setAction("request-reset")}>Recuperar senha</button></div>}
    <form className="space-y-3" onSubmit={async e => {
      e.preventDefault(); const data = new FormData(e.currentTarget); setError(""); setMessage(""); setBusy(true);
      try {
        if (action === "register") { await api.post("/auth/register", { full_name: data.get("name"), tenant_name: data.get("office"), email: data.get("email"), password: data.get("password") }); window.location.assign("/dashboard/account"); }
        else if (action === "request-reset") { await api.post("/account/password-resets/request", { email: data.get("email") }); setMessage("Se a conta estiver habilitada para recuperação, você receberá as instruções por e-mail."); }
        else if (action === "invite") { await api.post("/account/team/invites/accept", { token, full_name: data.get("name"), password: data.get("password") }); setMessage("Convite aceito. Entre com seu e-mail e a senha cadastrada."); setToken(""); }
        else if (action === "reset") { await api.post("/account/password-resets/confirm", { token, new_password: data.get("password") }); setMessage("Senha alterada. Faça login novamente."); setToken(""); }
        else if (action === "verify") { await api.post("/account/email-verifications/confirm", { token }); setMessage("E-mail verificado."); setToken(""); }
      } catch (err) { setError(errorText(err)); } finally { setBusy(false); }
    }}>
      {["register", "invite"].includes(action) && <Field label="Nome completo"><input className={control} name="name" minLength={2} maxLength={120} required /></Field>}
      {action === "register" && <Field label="Nome do escritório"><input className={control} name="office" minLength={2} maxLength={120} required /></Field>}
      {["register", "request-reset"].includes(action) && <Field label="E-mail"><input className={control} name="email" type="email" required autoComplete="email" /></Field>}
      {["register", "invite", "reset"].includes(action) && <Field label="Senha (mínimo 12 caracteres, letras e números)"><input className={control} type="password" name="password" minLength={12} maxLength={72} required autoComplete="new-password" /></Field>}
      <State error={error} />{message && <p role="status" className="text-sm text-green-300">{message}</p>}
      <button className={primary} disabled={busy}>{busy ? "Processando…" : action === "verify" ? "Confirmar verificação de e-mail" : "Continuar"}</button>
    </form><Link className="text-xs text-blue-300 inline-block" href="/dashboard">Voltar ao login →</Link>
  </Panel></Page></main>;
}
