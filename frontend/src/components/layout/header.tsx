"use client";

import React, { useState, useEffect, useRef } from "react";
import { Search, Building2, User, Bell, Command, ShieldCheck, ChevronDown, Check, Shield, LogIn, LogOut, Crown, Lock } from "lucide-react";
import { GlobalSearchModal } from "./global-search-modal";
import { NotificationPopover } from "./notification-popover";
import { LoginModal } from "./login-modal";
import { useUser, UserRole } from "@/context/user-context";

export interface RoleConfig {
  id: UserRole;
  label: string;
  badgeBg: string;
  badgeText: string;
  badgeBorder: string;
  permissions: string;
}

export const roleConfigs: Record<UserRole, RoleConfig> = {
  SUPER_ADMIN: {
    id: "SUPER_ADMIN",
    label: "SUPER_ADMIN (Master)",
    badgeBg: "bg-amber-950/90",
    badgeText: "text-amber-300 font-extrabold",
    badgeBorder: "border-amber-500 shadow-md shadow-amber-950",
    permissions: "Acesso Total Master, Gestão de Todos Usuários e Multitenants",
  },
  SOCIO: {
    id: "SOCIO",
    label: "Sócio / Administrador",
    badgeBg: "bg-amber-950/80",
    badgeText: "text-amber-300",
    badgeBorder: "border-amber-800",
    permissions: "Acesso Total ao Escritório, Aprovação de Minutas e Financeiro",
  },
  ASSOCIADO: {
    id: "ASSOCIADO",
    label: "Advogado Associado",
    badgeBg: "bg-blue-950/80",
    badgeText: "text-blue-300",
    badgeBorder: "border-blue-800",
    permissions: "Edição de Processos, Petições e Agenda",
  },
  ESTAGIARIO: {
    id: "ESTAGIARIO",
    label: "Estagiário de Direito",
    badgeBg: "bg-purple-950/80",
    badgeText: "text-purple-300",
    badgeBorder: "border-purple-800",
    permissions: "Redação de Rascunho (Exige Aprovação do Sócio)",
  },
  SECRETARIA: {
    id: "SECRETARIA",
    label: "Secretaria / Financeiro",
    badgeBg: "bg-emerald-950/80",
    badgeText: "text-emerald-300",
    badgeBorder: "border-emerald-800",
    permissions: "Emissão de Pix, Boletos e Agendamentos",
  },
};

export function Header() {
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [isRoleDropdownOpen, setIsRoleDropdownOpen] = useState(false);
  const roleDropdownRef = useRef<HTMLDivElement>(null);
  const { user, updateUser, logout, setIsLoginModalOpen } = useUser();

  const canSwitchRoles = user.role === "SUPER_ADMIN" || user.role === "SOCIO";

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setIsSearchOpen((prev) => !prev);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  // Fechar o dropdown de papéis ao clicar fora
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (roleDropdownRef.current && !roleDropdownRef.current.contains(event.target as Node)) {
        setIsRoleDropdownOpen(false);
      }
    };

    if (isRoleDropdownOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isRoleDropdownOpen]);

  const handleSelectRole = (rKey: UserRole) => {
    if (!canSwitchRoles) return;
    updateUser({ role: rKey });
    setIsRoleDropdownOpen(false);
  };

  const currentConfig = roleConfigs[user.role] || roleConfigs.SOCIO;

  return (
    <>
      <header className="h-16 border-b border-zinc-800 bg-zinc-900/80 backdrop-blur-md sticky top-0 z-30 px-6 flex items-center justify-between">
        {/* Universal Vector Search Trigger */}
        <div className="flex items-center space-x-4 flex-1 max-w-md">
          <button
            onClick={() => setIsSearchOpen(true)}
            className="w-full flex items-center justify-between px-3 py-2 bg-zinc-950 border border-zinc-800 rounded-xl text-xs text-zinc-400 hover:border-zinc-700 hover:text-zinc-200 transition-all shadow-inner group cursor-pointer"
          >
            <div className="flex items-center space-x-2">
              <Search className="w-4 h-4 text-zinc-500 group-hover:text-blue-400 transition-colors" />
              <span>Busca Vetorial GED, Processos e OAB...</span>
            </div>
            <kbd className="hidden sm:inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-mono bg-zinc-900 border border-zinc-800 text-zinc-400 rounded-md">
              <Command className="w-3 h-3" /> K
            </kbd>
          </button>
        </div>

        {/* Right Action Icons, RBAC Switcher & Active User Login Profile */}
        <div className="flex items-center space-x-3">
          {/* RBAC ROLE DISPLAY / SWITCHER */}
          <div ref={roleDropdownRef} className="relative">
            {canSwitchRoles ? (
              <button
                onClick={() => setIsRoleDropdownOpen(!isRoleDropdownOpen)}
                className={`hidden sm:flex items-center space-x-2 px-3 py-1.5 rounded-xl border text-xs font-semibold transition-all shadow-sm cursor-pointer ${currentConfig.badgeBg} ${currentConfig.badgeBorder} ${currentConfig.badgeText}`}
                title={currentConfig.permissions}
              >
                {user.role === "SUPER_ADMIN" ? <Crown className="w-3.5 h-3.5 text-amber-400 shrink-0" /> : <Shield className="w-3.5 h-3.5 shrink-0" />}
                <span>Papel: {currentConfig.label}</span>
                <ChevronDown className="w-3 h-3 opacity-70" />
              </button>
            ) : (
              <div
                className={`hidden sm:flex items-center space-x-2 px-3 py-1.5 rounded-xl border text-xs font-semibold shadow-sm ${currentConfig.badgeBg} ${currentConfig.badgeBorder} ${currentConfig.badgeText}`}
                title={`Perfil Fixo (LGPD): ${currentConfig.permissions}`}
              >
                <Lock className="w-3.5 h-3.5 text-zinc-400 shrink-0" />
                <span>Papel: {currentConfig.label}</span>
              </div>
            )}

            {canSwitchRoles && isRoleDropdownOpen && (
              <div className="absolute right-0 top-full mt-1.5 w-64 z-50 bg-zinc-950 border border-zinc-800 rounded-xl shadow-2xl py-1 space-y-0.5">
                <div className="px-3 py-1.5 border-b border-zinc-800 text-[10px] font-mono text-zinc-500 uppercase tracking-wider flex items-center justify-between">
                  <span>Controle de Acesso (RBAC LGPD)</span>
                  <ShieldCheck className="w-3.5 h-3.5 text-blue-400" />
                </div>
                {(Object.keys(roleConfigs) as UserRole[]).map((rKey) => {
                  const cfg = roleConfigs[rKey];
                  return (
                    <button
                      key={rKey}
                      onClick={() => handleSelectRole(rKey)}
                      className={`flex items-center justify-between w-full px-3 py-2 text-xs text-left transition-all cursor-pointer ${
                        user.role === rKey
                          ? "bg-blue-600/20 text-blue-300 font-bold"
                          : "text-zinc-300 hover:bg-zinc-900"
                      }`}
                    >
                      <div>
                        <p className="font-semibold">{cfg.label}</p>
                        <p className="text-[9px] text-zinc-500 font-mono leading-tight">{cfg.permissions}</p>
                      </div>
                      {user.role === rKey && <Check className="w-3.5 h-3.5 text-blue-400 shrink-0 ml-2" />}
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* Central de Notificações */}
          <NotificationPopover />

          {/* User Profile / Login Modal Trigger */}
          <button
            onClick={() => setIsLoginModalOpen(true)}
            className="flex items-center space-x-2 pl-2 border-l border-zinc-800 cursor-pointer hover:opacity-85 transition-opacity"
            title="Clique para Alternar Login ou Editar Perfil do Advogado"
          >
            <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-blue-600 to-indigo-700 flex items-center justify-center text-white text-xs font-bold font-mono shadow-md border border-blue-400/30">
              {user.avatarInitials}
            </div>
            <div className="hidden lg:block text-left">
              <p className="text-xs font-bold text-zinc-200 leading-none">
                <span>{user.name}</span>
              </p>
              <p className="text-[10px] font-mono text-zinc-400">{user.oabNumber}</p>
            </div>
          </button>

          {/* Explicit Logout Button */}
          <button
            onClick={logout}
            className="p-2 text-zinc-400 hover:text-rose-400 bg-zinc-950 border border-zinc-800 rounded-xl transition-all cursor-pointer shadow-sm"
            title="Sair do Sistema (Logout)"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </header>

      <GlobalSearchModal isOpen={isSearchOpen} onClose={() => setIsSearchOpen(false)} />
      <LoginModal />
    </>
  );
}
