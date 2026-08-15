"use client";

import React, { useState } from "react";
import { useUser, defaultUsers, UserRole, UserProfile } from "@/context/user-context";
import { UserCheck, ShieldCheck, X, KeyRound, Building2, User, Award, LogIn, Lock, Sparkles, LogOut, Eye, EyeOff, Check } from "lucide-react";

export function LoginModal() {
  const { user, usersList, setUser, isLoggedIn, login, logout, isLoginModalOpen, setIsLoginModalOpen } = useUser();
  const [selectedUser, setSelectedUser] = useState(user);
  const [inputEmail, setInputEmail] = useState("");
  const [inputPassword, setInputPassword] = useState("••••••••");
  const [showPassword, setShowPassword] = useState(false);

  // Form edit states
  const [name, setName] = useState(user.name);
  const [oabNumber, setOabNumber] = useState(user.oabNumber);
  const [role, setRole] = useState<UserRole>(user.role);
  const [officeName, setOfficeName] = useState(user.officeName);
  const [email, setEmail] = useState(user.email);

  if (!isLoginModalOpen && isLoggedIn) return null;

  // Alternar instantaneamente de usuário ao clicar no botão da conta
  const handleSelectPreset = (u: UserProfile) => {
    setSelectedUser(u);
    setName(u.name);
    setOabNumber(u.oabNumber);
    setRole(u.role);
    setOfficeName(u.officeName);
    setEmail(u.email);
    setInputEmail(u.email);
    setUser(u);
    setIsLoginModalOpen(false);
  };

  const handleDirectLogin = (e: React.FormEvent) => {
    e.preventDefault();
    const success = login(inputEmail || selectedUser.email);
    if (success) {
      setIsLoginModalOpen(false);
    }
  };

  const handleSaveProfile = (e: React.FormEvent) => {
    e.preventDefault();
    const initials = name
      .split(" ")
      .filter(Boolean)
      .slice(0, 2)
      .map((n) => n[0].toUpperCase())
      .join("");

    const updatedUser: UserProfile = {
      ...selectedUser,
      name,
      oabNumber,
      role,
      officeName,
      email,
      avatarInitials: initials || "ADV",
    };

    setUser(updatedUser);
    setIsLoginModalOpen(false);
  };

  // TELA DE AUTENTICAÇÃO FULLSCREEN QUANDO LOGOUT É EFETUADO
  if (!isLoggedIn) {
    return (
      <div className="fixed inset-0 z-50 bg-zinc-950/95 backdrop-blur-xl flex items-center justify-center p-4">
        <div className="bg-zinc-900 border border-zinc-800 rounded-3xl max-w-lg w-full p-8 space-y-6 shadow-2xl">
          {/* Logo Brand */}
          <div className="text-center space-y-2">
            <div className="w-12 h-12 rounded-2xl bg-blue-600 flex items-center justify-center font-bold text-xl text-white shadow-xl shadow-blue-900/50 mx-auto">
              L
            </div>
            <h1 className="text-2xl font-extrabold text-zinc-100 tracking-tight">LexFlow Enterprise</h1>
            <p className="text-xs text-zinc-400 font-mono">SaaS LegalTech Tier 1 • Autenticação de Advogados</p>
          </div>

          {/* Quick User Selector */}
          <div>
            <label className="block text-[11px] font-mono text-zinc-400 uppercase tracking-wider mb-2">
              Clique em uma Conta para Conectar Instantaneamente:
            </label>
            <div className="grid grid-cols-2 gap-2">
              {usersList.map((u) => (
                <button
                  key={u.id}
                  type="button"
                  onClick={() => handleSelectPreset(u)}
                  className={`p-2.5 rounded-xl border text-left transition-all cursor-pointer ${
                    selectedUser.id === u.id
                      ? "bg-blue-600/20 border-blue-500 text-blue-200 font-bold shadow-sm"
                      : "bg-zinc-950 border-zinc-800 text-zinc-400 hover:bg-zinc-800/60"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <p className="text-xs truncate font-semibold">{u.name}</p>
                    {selectedUser.id === u.id && <Check className="w-3.5 h-3.5 text-blue-400 shrink-0" />}
                  </div>
                  <p className="text-[10px] font-mono text-zinc-500 truncate">{u.oabNumber} • {u.role}</p>
                </button>
              ))}
            </div>
          </div>

          {/* Login Form */}
          <form onSubmit={handleDirectLogin} className="space-y-3 text-xs pt-2 border-t border-zinc-800">
            <div>
              <label className="block text-zinc-300 mb-1 font-medium">E-mail Cadastrado</label>
              <input
                type="email"
                value={inputEmail || selectedUser.email}
                onChange={(e) => setInputEmail(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-3.5 py-2.5 text-zinc-100 focus:outline-none focus:border-blue-500 font-mono"
                required
              />
            </div>

            <div>
              <label className="block text-zinc-300 mb-1 font-medium">Senha de Acesso</label>
              <div className="relative">
                <input
                  type={showPassword ? "text" : "password"}
                  value={inputPassword}
                  onChange={(e) => setInputPassword(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-xl pl-3.5 pr-10 py-2.5 text-zinc-100 focus:outline-none focus:border-blue-500 font-mono"
                  required
                />
                <button
                  type="button"
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    setShowPassword((prev) => !prev);
                  }}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-400 hover:text-zinc-200 cursor-pointer p-1"
                  title={showPassword ? "Ocultar Senha" : "Exibir Senha"}
                >
                  {showPassword ? <EyeOff className="w-4 h-4 text-blue-400" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              className="w-full py-3 bg-blue-600 hover:bg-blue-500 text-white font-bold rounded-xl text-xs flex items-center justify-center space-x-2 shadow-lg shadow-blue-950 cursor-pointer transition-all mt-2"
            >
              <LogIn className="w-4 h-4" />
              <span>Entrar no LexFlow Enterprise</span>
            </button>
          </form>
        </div>
      </div>
    );
  }

  // TELA DE EDIÇÃO DE PERFIL QUANDO LOGADO
  return (
    <div
      onClick={() => setIsLoginModalOpen(false)}
      className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="bg-zinc-950 border border-zinc-800 rounded-2xl max-w-lg w-full p-6 space-y-5 shadow-2xl"
      >
        <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
          <div className="flex items-center space-x-2 text-xs font-bold text-zinc-100 uppercase tracking-wider">
            <KeyRound className="w-4 h-4 text-blue-400" />
            <span>Perfil da Conta Ativa & Autenticação</span>
          </div>
          <button
            onClick={() => setIsLoginModalOpen(false)}
            className="text-zinc-400 hover:text-zinc-200 p-1 cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* User Presets Selection */}
        <div>
          <label className="block text-[11px] font-mono text-zinc-400 uppercase tracking-wider mb-2">
            Clique em um Usuário para Alternar Login Instantaneamente:
          </label>
          <div className="grid grid-cols-2 gap-2">
            {usersList.map((u) => (
              <button
                key={u.id}
                type="button"
                onClick={() => handleSelectPreset(u)}
                className={`p-2.5 rounded-xl border text-left transition-all cursor-pointer ${
                  user.id === u.id
                    ? "bg-blue-600/20 border-blue-500 text-blue-200 font-bold shadow-sm"
                    : "bg-zinc-900 border-zinc-800 text-zinc-400 hover:bg-zinc-800"
                }`}
              >
                <div className="flex items-center justify-between">
                  <p className="text-xs truncate font-semibold">{u.name}</p>
                  {user.id === u.id && <Check className="w-3.5 h-3.5 text-blue-400 shrink-0" />}
                </div>
                <p className="text-[10px] font-mono text-zinc-500 truncate">{u.oabNumber} • {u.role}</p>
              </button>
            ))}
          </div>
        </div>

        {/* Custom Edit Form */}
        <form onSubmit={handleSaveProfile} className="space-y-3 text-xs pt-1 border-t border-zinc-800">
          <div>
            <label className="block text-zinc-300 mb-1 font-medium">Nome do Advogado / Usuário</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full bg-zinc-900 border border-zinc-800 rounded-xl px-3 py-2 text-zinc-100 focus:outline-none focus:border-blue-500"
              required
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-zinc-300 mb-1 font-medium">Inscrição OAB</label>
              <input
                type="text"
                value={oabNumber}
                onChange={(e) => setOabNumber(e.target.value)}
                className="w-full bg-zinc-900 border border-zinc-800 rounded-xl px-3 py-2 text-zinc-100 font-mono focus:outline-none focus:border-blue-500"
                required
              />
            </div>
            <div>
              <label className="block text-zinc-300 mb-1 font-medium">Papel de Acesso (RBAC)</label>
              <select
                value={role}
                onChange={(e) => setRole(e.target.value as UserRole)}
                disabled={user.role !== "SUPER_ADMIN" && user.role !== "SOCIO"}
                className={`w-full border rounded-xl px-3 py-2 text-zinc-100 focus:outline-none ${
                  user.role !== "SUPER_ADMIN" && user.role !== "SOCIO"
                    ? "bg-zinc-950/60 border-zinc-800 text-zinc-500 cursor-not-allowed"
                    : "bg-zinc-900 border-zinc-800 focus:border-blue-500"
                }`}
              >
                <option value="SUPER_ADMIN">SUPER_ADMIN (Master)</option>
                <option value="SOCIO">Sócio / Administrador</option>
                <option value="ASSOCIADO">Advogado Associado</option>
                <option value="ESTAGIARIO">Estagiário de Direito</option>
                <option value="SECRETARIA">Secretaria / Financeiro</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-zinc-300 mb-1 font-medium">Razão Social do Escritório</label>
            <input
              type="text"
              value={officeName}
              onChange={(e) => setOfficeName(e.target.value)}
              className="w-full bg-zinc-900 border border-zinc-800 rounded-xl px-3 py-2 text-zinc-100 focus:outline-none focus:border-blue-500"
              required
            />
          </div>

          <div>
            <label className="block text-zinc-300 mb-1 font-medium font-sans">Senha de Acesso da Conta</label>
            <div className="relative">
              <input
                type={showPassword ? "text" : "password"}
                value={inputPassword}
                onChange={(e) => setInputPassword(e.target.value)}
                className="w-full bg-zinc-900 border border-zinc-800 rounded-xl pl-3 py-2 text-zinc-100 font-mono focus:outline-none focus:border-blue-500 pr-10"
                required
              />
              <button
                type="button"
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  setShowPassword((prev) => !prev);
                }}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-400 hover:text-zinc-200 cursor-pointer p-1"
                title={showPassword ? "Ocultar Senha" : "Exibir Senha"}
              >
                {showPassword ? <EyeOff className="w-4 h-4 text-blue-400" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          <div className="pt-3 flex justify-between items-center">
            {/* Logout Action Button */}
            <button
              type="button"
              onClick={logout}
              className="px-3.5 py-2 bg-rose-950/80 hover:bg-rose-900 text-rose-300 border border-rose-800 rounded-xl text-xs font-semibold flex items-center space-x-1.5 cursor-pointer transition-colors"
            >
              <LogOut className="w-4 h-4" />
              <span>Sair do Sistema</span>
            </button>

            <div className="flex space-x-2">
              <button
                type="button"
                onClick={() => setIsLoginModalOpen(false)}
                className="px-4 py-2 bg-zinc-900 hover:bg-zinc-800 text-zinc-300 rounded-xl text-xs font-semibold border border-zinc-800 cursor-pointer"
              >
                Cancelar
              </button>
              <button
                type="submit"
                className="px-5 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-semibold flex items-center space-x-1.5 shadow-lg shadow-blue-950 cursor-pointer"
              >
                <UserCheck className="w-4 h-4" />
                <span>Salvar & Conectar</span>
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
