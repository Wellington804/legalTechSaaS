"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { useUser, defaultUsers } from "@/context/user-context";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { 
  Eye, 
  EyeOff, 
  LogIn, 
  UserPlus, 
  CheckCircle2, 
  AlertCircle, 
  ShieldCheck, 
  Scale, 
  Building2, 
  ArrowRight,
  Sparkles
} from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const { login, registerUser, switchUserById, usersList } = useUser();

  const [mode, setMode] = useState<"login" | "register">("login");
  const [selectedAccountId, setSelectedAccountId] = useState<string>("user-super");

  // Form State (Login)
  const [email, setEmail] = useState("super.admin@lexflow.law");
  const [password, setPassword] = useState("lawyer123");
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");

  // Form State (Register)
  const [regName, setRegName] = useState("");
  const [regEmail, setRegEmail] = useState("");
  const [regPassword, setRegPassword] = useState("");
  const [regRole, setRegRole] = useState("associado");
  const [regOabNumber, setRegOabNumber] = useState("");
  const [regOfficeName, setRegOfficeName] = useState("");

  const handleSelectAccount = (userItem: typeof defaultUsers[0]) => {
    setSelectedAccountId(userItem.id);
    setEmail(userItem.email);
    setPassword(userItem.password || "lawyer123");
    switchUserById(userItem.id);
    setErrorMessage("");
  };

  const handleLoginSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage("");
    setSuccessMessage("");
    setIsLoading(true);

    try {
      const res = await login(email, password);
      if (res.success) {
        setSuccessMessage("Autenticação realizada com sucesso! Redirecionando...");
        setTimeout(() => {
          router.push("/dashboard");
        }, 600);
      } else {
        setErrorMessage(res.message || "Erro ao efetuar login.");
      }
    } catch (err) {
      setErrorMessage("Erro ao conectar com servidor de autenticação.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleRegisterSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage("");
    setSuccessMessage("");

    if (!regName || !regEmail || !regPassword) {
      setErrorMessage("Por favor, preencha todos os campos obrigatórios.");
      return;
    }

    setIsLoading(true);

    try {
      const res = await registerUser({
        name: regName,
        email: regEmail,
        password: regPassword,
        role: regRole,
        oabNumber: regOabNumber,
        officeName: regOfficeName,
      });

      if (res.success) {
        setSuccessMessage("Conta criada com sucesso! Redirecionando para o sistema...");
        setTimeout(() => {
          router.push("/dashboard");
        }, 800);
      } else {
        setErrorMessage(res.message || "Erro ao registrar usuário.");
      }
    } catch (err) {
      setErrorMessage("Falha na criação da conta. Tente novamente.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-100 dark:bg-zinc-950 text-slate-900 dark:text-zinc-100 flex flex-col items-center justify-center p-4 sm:p-6 relative overflow-hidden font-sans transition-colors duration-200">
      
      {/* Fixed Top-Right Theme Toggle Switcher */}
      <ThemeToggle className="fixed top-4 right-4 sm:top-6 sm:right-6 z-50 shadow-xl" />

      {/* Dynamic Background Glow Effects */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-blue-600/10 dark:bg-blue-600/10 rounded-full blur-[140px] pointer-events-none" />
      <div className="absolute bottom-10 right-10 w-[400px] h-[400px] bg-indigo-600/10 dark:bg-indigo-600/10 rounded-full blur-[120px] pointer-events-none" />

      {/* Main Container */}
      <div className="w-full max-w-xl bg-white/95 dark:bg-zinc-900/80 border border-slate-200 dark:border-zinc-800/80 backdrop-blur-2xl rounded-3xl p-6 sm:p-8 shadow-2xl dark:shadow-black/80 relative z-10 transition-colors duration-200">
        
        {/* Header Branding */}
        <div className="flex flex-col items-center text-center mb-6 sm:mb-8">
          <div className="w-14 h-14 bg-gradient-to-tr from-blue-600 to-indigo-500 rounded-2xl flex items-center justify-center shadow-lg shadow-blue-500/30 mb-4 border border-blue-400/30">
            <span className="text-2xl font-black text-white tracking-wider">L</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900 dark:text-white mb-1.5 font-outfit">
            LexFlow Enterprise
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 dark:text-zinc-400 font-mono flex items-center gap-1.5">
            <ShieldCheck className="w-3.5 h-3.5 text-blue-500 dark:text-blue-400 inline" />
            SaaS LegalTech Tier 1 • Autenticação de Advogados
          </p>
        </div>

        {/* Feedback Alerts */}
        {errorMessage && (
          <div className="mb-5 p-3.5 bg-red-50 dark:bg-red-950/60 border border-red-200 dark:border-red-800/60 rounded-xl text-red-700 dark:text-red-300 text-xs sm:text-sm flex items-center gap-2.5 animate-in fade-in slide-in-from-top-2">
            <AlertCircle className="w-4 h-4 shrink-0 text-red-500 dark:text-red-400" />
            <span>{errorMessage}</span>
          </div>
        )}

        {successMessage && (
          <div className="mb-5 p-3.5 bg-emerald-50 dark:bg-emerald-950/60 border border-emerald-200 dark:border-emerald-800/60 rounded-xl text-emerald-700 dark:text-emerald-300 text-xs sm:text-sm flex items-center gap-2.5 animate-in fade-in slide-in-from-top-2">
            <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-500 dark:text-emerald-400" />
            <span>{successMessage}</span>
          </div>
        )}

        {/* Mode Toggle Switcher (Login / Register) */}
        <div className="grid grid-cols-2 p-1 bg-slate-100 dark:bg-zinc-950/80 rounded-xl border border-slate-200 dark:border-zinc-800/60 mb-6">
          <button
            type="button"
            onClick={() => setMode("login")}
            className={`py-2 px-4 rounded-lg text-xs font-semibold tracking-wide transition-all flex items-center justify-center gap-2 ${
              mode === "login"
                ? "bg-blue-600 text-white shadow-md shadow-blue-600/30 font-bold"
                : "text-slate-600 dark:text-zinc-400 hover:text-slate-900 dark:hover:text-white"
            }`}
          >
            <LogIn className="w-3.5 h-3.5" />
            Entrar no Sistema
          </button>
          <button
            type="button"
            onClick={() => setMode("register")}
            className={`py-2 px-4 rounded-lg text-xs font-semibold tracking-wide transition-all flex items-center justify-center gap-2 ${
              mode === "register"
                ? "bg-blue-600 text-white shadow-md shadow-blue-600/30 font-bold"
                : "text-slate-600 dark:text-zinc-400 hover:text-slate-900 dark:hover:text-white"
            }`}
          >
            <UserPlus className="w-3.5 h-3.5" />
            Criar Novo Usuário
          </button>
        </div>

        {/* MODE LOGIN */}
        {mode === "login" ? (
          <div>
            {/* Quick Account Switcher Section */}
            <div className="mb-6">
              <div className="flex items-center justify-between mb-3">
                <span className="text-[10px] sm:text-xs font-mono font-semibold text-slate-500 dark:text-zinc-400 tracking-wider uppercase flex items-center gap-1.5">
                  <Sparkles className="w-3 h-3 text-blue-500 dark:text-blue-400" />
                  Clique em uma conta para conectar instantaneamente:
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                {usersList.slice(0, 5).map((u) => {
                  const isSelected = selectedAccountId === u.id || email === u.email;
                  return (
                    <button
                      key={u.id}
                      type="button"
                      onClick={() => handleSelectAccount(u)}
                      className={`text-left p-3 rounded-xl border transition-all relative overflow-hidden group ${
                        isSelected
                          ? "bg-blue-50 dark:bg-blue-950/40 border-blue-500 shadow-md shadow-blue-500/10 ring-1 ring-blue-500/50"
                          : "bg-slate-50 dark:bg-zinc-950/60 border-slate-200 dark:border-zinc-800/80 hover:border-blue-400 dark:hover:border-zinc-700 hover:bg-slate-100 dark:hover:bg-zinc-950"
                      }`}
                    >
                      <div className="flex items-start justify-between">
                        <div className="pr-2">
                          <p className="text-xs font-bold text-slate-900 dark:text-zinc-100 group-hover:text-blue-600 dark:group-hover:text-blue-300 transition-colors line-clamp-1">
                            {u.name}
                          </p>
                          <p className="text-[10px] text-slate-500 dark:text-zinc-400 font-mono mt-0.5 tracking-tight flex items-center gap-1">
                            <span>{u.oabNumber}</span>
                            <span className="text-slate-400 dark:text-zinc-600">•</span>
                            <span className="text-blue-600 dark:text-blue-400 font-semibold uppercase">{u.role}</span>
                          </p>
                        </div>
                        {isSelected && (
                          <CheckCircle2 className="w-4 h-4 text-blue-600 dark:text-blue-400 shrink-0 mt-0.5" />
                        )}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="relative flex py-2 items-center mb-6">
              <div className="flex-grow border-t border-slate-200 dark:border-zinc-800"></div>
              <span className="flex-shrink mx-4 text-[11px] font-mono text-slate-400 dark:text-zinc-500 uppercase tracking-widest">
                Credenciais de Acesso
              </span>
              <div className="flex-grow border-t border-slate-200 dark:border-zinc-800"></div>
            </div>

            {/* Form Fields */}
            <form onSubmit={handleLoginSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-zinc-300 mb-1.5">
                  E-mail Cadastrado
                </label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="usuario@lexflow.law"
                  required
                  className="w-full bg-slate-50 dark:bg-zinc-950 border border-slate-300 dark:border-zinc-800 rounded-xl px-4 py-2.5 text-sm text-slate-900 dark:text-zinc-100 font-mono placeholder-slate-400 dark:placeholder-zinc-600 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-zinc-300 mb-1.5">
                  Senha de Acesso
                </label>
                <div className="relative">
                  <input
                    type={showPassword ? "text" : "password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    required
                    className="w-full bg-slate-50 dark:bg-zinc-950 border border-slate-300 dark:border-zinc-800 rounded-xl px-4 py-2.5 pr-10 text-sm text-slate-900 dark:text-zinc-100 font-mono placeholder-slate-400 dark:placeholder-zinc-600 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 dark:text-zinc-400 hover:text-slate-600 dark:hover:text-zinc-200 transition-colors p-1"
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <button
                type="submit"
                disabled={isLoading}
                className="w-full bg-blue-600 hover:bg-blue-500 text-white font-bold py-3 px-4 rounded-xl shadow-lg shadow-blue-600/30 transition-all duration-200 flex items-center justify-center gap-2 group mt-2 text-sm disabled:opacity-50"
              >
                {isLoading ? (
                  <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                ) : (
                  <>
                    <span>Entrar no LegalFlow Enterprise</span>
                    <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                  </>
                )}
              </button>
            </form>
          </div>
        ) : (
          /* MODE REGISTER */
          <div>
            <form onSubmit={handleRegisterSubmit} className="space-y-3.5">
              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-zinc-300 mb-1">
                  Nome Completo do Advogado/Profissional *
                </label>
                <input
                  type="text"
                  value={regName}
                  onChange={(e) => setRegName(e.target.value)}
                  placeholder="Dr. Eduardo Martins"
                  required
                  className="w-full bg-slate-50 dark:bg-zinc-950 border border-slate-300 dark:border-zinc-800 rounded-xl px-4 py-2.5 text-sm text-slate-900 dark:text-zinc-100 placeholder-slate-400 dark:placeholder-zinc-600 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 dark:text-zinc-300 mb-1">
                    E-mail Corporativo *
                  </label>
                  <input
                    type="email"
                    value={regEmail}
                    onChange={(e) => setRegEmail(e.target.value)}
                    placeholder="eduardo@escritorio.adv.br"
                    required
                    className="w-full bg-slate-50 dark:bg-zinc-950 border border-slate-300 dark:border-zinc-800 rounded-xl px-4 py-2.5 text-sm text-slate-900 dark:text-zinc-100 placeholder-slate-400 dark:placeholder-zinc-600 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 dark:text-zinc-300 mb-1">
                    Senha de Acesso *
                  </label>
                  <input
                    type="password"
                    value={regPassword}
                    onChange={(e) => setRegPassword(e.target.value)}
                    placeholder="••••••••"
                    required
                    className="w-full bg-slate-50 dark:bg-zinc-950 border border-slate-300 dark:border-zinc-800 rounded-xl px-4 py-2.5 text-sm text-slate-900 dark:text-zinc-100 placeholder-slate-400 dark:placeholder-zinc-600 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 dark:text-zinc-300 mb-1">
                    Nº Inscrição OAB (Opcional)
                  </label>
                  <input
                    type="text"
                    value={regOabNumber}
                    onChange={(e) => setRegOabNumber(e.target.value)}
                    placeholder="Ex: 345.890"
                    className="w-full bg-slate-50 dark:bg-zinc-950 border border-slate-300 dark:border-zinc-800 rounded-xl px-4 py-2.5 text-sm text-slate-900 dark:text-zinc-100 placeholder-slate-400 dark:placeholder-zinc-600 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 dark:text-zinc-300 mb-1">
                    Cargo / Nível de Permissão
                  </label>
                  <select
                    value={regRole}
                    onChange={(e) => setRegRole(e.target.value)}
                    className="w-full bg-slate-50 dark:bg-zinc-950 border border-slate-300 dark:border-zinc-800 rounded-xl px-4 py-2.5 text-sm text-slate-900 dark:text-zinc-100 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all"
                  >
                    <option value="socio">Sócio Proprietário</option>
                    <option value="associado">Advogado Associado</option>
                    <option value="estagiario">Estagiário de Direito</option>
                    <option value="secretaria">Secretaria / Paralegal</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-zinc-300 mb-1">
                  Nome do Escritório / Razão Social
                </label>
                <input
                  type="text"
                  value={regOfficeName}
                  onChange={(e) => setRegOfficeName(e.target.value)}
                  placeholder="Ex: Martins & Associados Advocacia"
                  className="w-full bg-slate-50 dark:bg-zinc-950 border border-slate-300 dark:border-zinc-800 rounded-xl px-4 py-2.5 text-sm text-slate-900 dark:text-zinc-100 placeholder-slate-400 dark:placeholder-zinc-600 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all"
                />
              </div>

              <button
                type="submit"
                disabled={isLoading}
                className="w-full bg-blue-600 hover:bg-blue-500 text-white font-bold py-3 px-4 rounded-xl shadow-lg shadow-blue-600/30 transition-all duration-200 flex items-center justify-center gap-2 group mt-4 text-sm disabled:opacity-50"
              >
                {isLoading ? (
                  <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                ) : (
                  <>
                    <UserPlus className="w-4 h-4" />
                    <span>Cadastrar Usuário no Supabase</span>
                  </>
                )}
              </button>
            </form>
          </div>
        )}

        {/* Footer info */}
        <div className="mt-6 pt-4 border-t border-slate-200 dark:border-zinc-800/60 text-center">
          <p className="text-[11px] text-slate-500 dark:text-zinc-500 font-mono">
            Conectado ao Supabase Enterprise Database • Criptografia SSL 256-bit
          </p>
        </div>
      </div>
    </div>
  );
}
