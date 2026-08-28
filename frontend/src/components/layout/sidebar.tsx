"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Award,
  ShieldCheck,
  Scale,
  FileText,
  FileSignature,
  DollarSign,
  Users,
  Search,
  Bot,
  ShieldAlert,
  Palette,
  CheckSquare,
  Calculator,
  BookOpen,
  Split,
  TrendingUp,
  QrCode,
  Sparkles,
  UserCog,
  Lock,
  MessageSquare
} from "lucide-react";
import { TenantSwitcher } from "./tenant-switcher";
import { useUser, UserRole } from "@/context/user-context";
import { cn } from "@/lib/utils";

interface NavItem {
  name: string;
  href: string;
  icon: any;
  allowedRoles?: UserRole[];
  subItems?: { name: string; href: string; icon: any }[];
}

const navigationItems: NavItem[] = [
  { name: "Visão Geral", href: "/dashboard", icon: LayoutDashboard },
  { name: "Gestão de Usuários & RBAC", href: "/dashboard/admin/users", icon: UserCog, allowedRoles: ["SUPER_ADMIN", "SOCIO"] },
  {
    name: "Hub OAB & Novo Advogado",
    href: "/oab-hub",
    icon: Award,
    subItems: [
      { name: "Checklist de Inscrição", href: "/oab-hub/checklist", icon: CheckSquare },
      { name: "Gerador de Declarações", href: "/oab-hub/declaracoes", icon: FileText },
      { name: "Calculadora de Anuidade", href: "/oab-hub/calculadora", icon: Calculator },
      { name: "Guia SUA (Sociedade)", href: "/oab-hub/sua-guide", icon: BookOpen },
    ],
  },
  { name: "Omnichannel CRM", href: "/dashboard/crm", icon: Users },
  { name: "Radar de Conflitos", href: "/dashboard/conflitos", icon: ShieldAlert },
  {
    name: "Central de Petições",
    href: "/dashboard/petitions/editor",
    icon: Scale,
    subItems: [
      { name: "Editor Split-View", href: "/dashboard/petitions/editor", icon: Split },
    ]
  },
  {
    name: "Legal Tracker & Jurimetria",
    href: "/dashboard/analytics/judge-profiling",
    icon: Search,
    subItems: [
      { name: "Perfil de Magistrados", href: "/dashboard/analytics/judge-profiling", icon: TrendingUp },
    ]
  },
  { name: "Simulador de Audiências", href: "/dashboard/simulator", icon: Sparkles },
  { name: "Calculadora Judicial", href: "/dashboard/calculadora", icon: Calculator },
  { name: "Minutas & Contratos IA", href: "/dashboard/templates", icon: FileText },
  { name: "Assinatura Eletrônica", href: "/dashboard/assinaturas", icon: FileSignature },
  { name: "Financeiro & Pix", href: "/dashboard/financial", icon: DollarSign },
  { name: "Governança & Audit Logs", href: "/dashboard/audit", icon: ShieldCheck, allowedRoles: ["SUPER_ADMIN", "SOCIO", "ASSOCIADO"] },
  {
    name: "AI Brand & WhatsApp Escritório",
    href: "/dashboard/brand",
    icon: Palette,
    subItems: [
      { name: "Identidade & Timbrado", href: "/dashboard/brand?tab=TIMBRADO", icon: Palette },
      { name: "WhatsApp do Escritório", href: "/dashboard/brand?tab=whatsapp", icon: MessageSquare },
    ]
  },
  { name: "Portal do Cliente (White-Label)", href: "/portal", icon: Bot },
];

import { LogOut } from "lucide-react";

export function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useUser();

  return (
    <aside className="w-64 border-r border-zinc-800 bg-zinc-950 flex flex-col h-screen sticky top-0 shrink-0">
      {/* Brand Header */}
      <div className="p-4 border-b border-zinc-800">
        <div className="flex items-center space-x-3 mb-3">
          <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center font-bold text-white shadow-lg shadow-blue-900/40">
            L
          </div>
          <div>
            <span className="font-semibold text-sm text-zinc-100 tracking-tight block">LegalFlow Enterprise</span>
            <span className="text-[10px] text-blue-400 font-mono uppercase tracking-wider">Tier 1 LegalTech</span>
          </div>
        </div>
        <TenantSwitcher />
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
        {navigationItems.map((item) => {
          const isRoleAllowed = !item.allowedRoles || item.allowedRoles.includes(user.role);
          const isActive = pathname === item.href || (item.subItems && item.subItems.some(sub => pathname === sub.href));
          const Icon = item.icon;

          if (!isRoleAllowed) {
            return (
              <div
                key={item.name}
                className="flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium text-zinc-600 bg-zinc-950/40 border border-zinc-900 cursor-not-allowed opacity-60"
                title={`Acesso Restrito ao papel ${user.role} (Regra LGPD)`}
              >
                <div className="flex items-center space-x-3 truncate">
                  <Icon className="w-4 h-4 text-zinc-700 shrink-0" />
                  <span className="truncate">{item.name}</span>
                </div>
                <Lock className="w-3.5 h-3.5 text-zinc-700 shrink-0 ml-1" />
              </div>
            );
          }

          return (
            <div key={item.name} className="space-y-1">
              <Link
                href={item.href}
                className={cn(
                  "flex items-center space-x-3 px-3 py-2 rounded-lg text-xs font-medium transition-colors",
                  isActive
                    ? "bg-blue-600/10 text-blue-400 border border-blue-500/20"
                    : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900"
                )}
              >
                <Icon className={cn("w-4 h-4 shrink-0", isActive ? "text-blue-400" : "text-zinc-500")} />
                <span>{item.name}</span>
              </Link>

              {/* Render SubItems */}
              {item.subItems && isActive && (
                <div className="ml-4 pl-3 border-l border-zinc-800 space-y-1 my-1">
                  {item.subItems.map((sub) => {
                    const isSubActive = pathname === sub.href;
                    const SubIcon = sub.icon;
                    return (
                      <Link
                        key={sub.name}
                        href={sub.href}
                        className={cn(
                          "flex items-center space-x-2 px-2.5 py-1.5 rounded-md text-[11px] font-medium transition-colors",
                          isSubActive
                            ? "bg-blue-600/20 text-blue-300 font-semibold"
                            : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900/60"
                        )}
                      >
                        <SubIcon className="w-3.5 h-3.5" />
                        <span>{sub.name}</span>
                      </Link>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </nav>

      {/* Footer User Profile & Logout */}
      <div className="p-3 border-t border-zinc-800 bg-zinc-950/80 space-y-2">
        <div className="flex items-center justify-between p-2 rounded-xl bg-zinc-900/80 border border-zinc-800">
          <div className="flex items-center space-x-2.5 truncate">
            <div className="w-7 h-7 rounded-lg bg-blue-600/30 text-blue-400 border border-blue-500/40 flex items-center justify-center font-bold text-xs shrink-0">
              {user.avatarInitials || "ADV"}
            </div>
            <div className="truncate">
              <p className="text-[11px] font-bold text-zinc-100 truncate">{user.name}</p>
              <p className="text-[9px] text-zinc-400 font-mono truncate">{user.oabNumber}</p>
            </div>
          </div>

          <button
            onClick={logout}
            title="Sair do sistema (Logout)"
            className="p-1.5 hover:bg-red-950/60 hover:text-red-400 text-zinc-400 rounded-lg transition-colors shrink-0 ml-1"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>

        <div className="flex items-center space-x-2 px-2 py-1 rounded-lg bg-emerald-950/30 border border-emerald-800/40">
          <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
          <p className="text-[9px] text-emerald-400 font-mono truncate">Supabase DB Conectado</p>
        </div>
      </div>
    </aside>
  );
}
