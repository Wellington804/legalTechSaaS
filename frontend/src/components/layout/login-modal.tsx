"use client";

import React, { useEffect, useState } from "react";
import { Eye, EyeOff, Loader2, Lock, LogIn, LogOut, X } from "lucide-react";
import { useUser } from "@/context/user-context";
import Link from "next/link";

export function LoginModal() {
  const { user, isLoggedIn, isLoading, requiresReauth, discardSessionDrafts, authError, login, logout, isLoginModalOpen, setIsLoginModalOpen } = useUser();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [otpCode, setOtpCode] = useState("");
  const [rememberMe, setRememberMe] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  useEffect(() => { if (requiresReauth) { setEmail(user.email); setPassword(""); setOtpCode(""); } }, [requiresReauth, user.email]);

  if (isLoading) return <div className="fixed inset-0 z-50 bg-zinc-950 flex items-center justify-center"><Loader2 className="w-6 h-6 animate-spin text-blue-400" aria-label="Verificando sessão" /></div>;
  if (isLoggedIn && !isLoginModalOpen) return null;

  const handleLogin = async (event: React.FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    try { if (await login(email, password, otpCode, rememberMe)) { setPassword(""); setOtpCode(""); setRememberMe(false); } } finally { setSubmitting(false); }
  };

  if (isLoggedIn && !requiresReauth) {
    return (
      <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md overflow-y-auto p-4">
        <div className="mx-auto my-4 bg-zinc-950 border border-zinc-800 rounded-2xl max-w-md w-full p-6 space-y-5 shadow-2xl [overflow-wrap:anywhere]">
          <div className="flex items-center justify-between">
            <div><p className="font-bold text-zinc-100">{user.name}</p><p className="text-xs text-zinc-400">{user.email}</p></div>
            <button type="button" onClick={() => setIsLoginModalOpen(false)} className="min-h-11 min-w-11 flex items-center justify-center text-zinc-400 hover:text-white" aria-label="Fechar"><X className="w-5 h-5" /></button>
          </div>
          {authError && <p role="alert" className="text-xs text-rose-300 bg-rose-950/60 border border-rose-900 rounded-lg p-3">{authError}</p>}
          <button type="button" onClick={() => void logout()} className="w-full py-2.5 bg-rose-950 text-rose-200 border border-rose-800 rounded-xl text-xs font-bold flex items-center justify-center gap-2"><LogOut className="w-4 h-4" /> Sair com segurança</button>
        </div>
      </div>
    );
  }

  return (
    <div role="dialog" aria-modal="true" aria-label={requiresReauth ? "Renovar sessão" : "Entrar no escritório"} className="fixed inset-0 z-50 bg-zinc-950/95 backdrop-blur-xl overflow-y-auto p-4">
      <div className="mx-auto my-4 md:my-12 bg-zinc-900 border border-zinc-800 rounded-3xl max-w-md w-full p-5 sm:p-8 space-y-6 shadow-2xl">
        <div className="text-center space-y-2">
          <div className="w-12 h-12 rounded-2xl bg-blue-600 flex items-center justify-center text-white mx-auto"><Lock className="w-5 h-5" /></div>
          <h1 className="text-2xl font-semibold tracking-[-0.02em] text-zinc-100">LexFlow</h1>
          <p className="text-sm leading-relaxed text-zinc-400">{requiresReauth ? "Seu rascunho continua protegido nesta aba. Renove a sessão e tente salvar novamente." : "Entre para acessar o seu escritório."}</p>
        </div>
        <form onSubmit={handleLogin} className="space-y-4">
          <div>
            <label htmlFor="login-email" className="block text-sm text-zinc-300 mb-1.5">E-mail</label>
            <input id="login-email" type="email" value={email} readOnly={requiresReauth} onChange={(event) => setEmail(event.target.value)} autoComplete="username" required className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-3.5 py-2.5 text-zinc-100 focus:outline-none focus:border-blue-500" />
          </div>
          <div>
            <label htmlFor="login-password" className="block text-sm text-zinc-300 mb-1.5">Senha</label>
            <div className="relative">
              <input id="login-password" type={showPassword ? "text" : "password"} value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" required className="w-full bg-zinc-950 border border-zinc-800 rounded-xl pl-3.5 pr-11 py-2.5 text-zinc-100 focus:outline-none focus:border-blue-500" />
              <button type="button" onClick={() => setShowPassword((value) => !value)} className="absolute right-0 top-1/2 -translate-y-1/2 min-h-11 min-w-11 flex items-center justify-center text-zinc-400" aria-label={showPassword ? "Ocultar senha" : "Mostrar senha"}>{showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}</button>
            </div>
          </div>
          <label className="flex min-h-11 items-center gap-2 text-sm text-zinc-300">
            <input type="checkbox" checked={rememberMe} onChange={(event) => setRememberMe(event.target.checked)} className="size-4 rounded border-zinc-700 bg-zinc-950 accent-blue-600" />
            Manter conectado
          </label>
          {authError && <p role="alert" className="text-xs text-rose-300 bg-rose-950/60 border border-rose-900 rounded-lg p-3">{authError}</p>}
          <div><label htmlFor="login-otp" className="block text-sm text-zinc-300 mb-1.5">Código do autenticador, se solicitado</label><input id="login-otp" value={otpCode} onChange={e => setOtpCode(e.target.value)} autoComplete="one-time-code" inputMode="numeric" maxLength={64} className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-3 py-2" /></div>
          <button type="submit" disabled={submitting} className="w-full min-h-11 py-3 bg-blue-600 hover:bg-blue-500 disabled:opacity-60 text-white font-semibold rounded-xl text-sm flex items-center justify-center gap-2">
            {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <LogIn className="w-4 h-4" />}{submitting ? "Autenticando..." : "Entrar"}
          </button>
        </form>
        {requiresReauth && <button type="button" disabled={submitting} className="min-h-11 w-full text-sm text-amber-300" onClick={async () => { if (!window.confirm("Descartar os rascunhos desta conta e entrar com outra identidade?")) return; setSubmitting(true); try { await discardSessionDrafts(); setEmail(""); setPassword(""); setOtpCode(""); } finally { setSubmitting(false); } }}>Descartar rascunhos e trocar de conta</button>}
        <Link href="/account/access" className="flex min-h-11 items-center justify-center text-center text-sm text-blue-300">Criar escritório, aceitar convite ou recuperar acesso</Link>
      </div>
    </div>
  );
}
