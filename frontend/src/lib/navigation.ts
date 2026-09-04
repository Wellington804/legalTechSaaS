export type NavigationGroup = "daily" | "more" | "office";

export type NavigationItem = {
  name: string;
  shortName: string;
  href: string;
  icon: "home" | "calendar" | "users" | "briefcase" | "file" | "message" | "book" | "shield" | "chart" | "wallet" | "palette" | "team" | "audit" | "settings" | "bot";
  group: NavigationGroup;
  admin?: boolean;
  lawyer?: boolean;
};

export const navigationGroups: { id: NavigationGroup; name: string; primary?: boolean }[] = [
  { id: "daily", name: "Trabalho diário", primary: true },
  { id: "more", name: "Mais áreas" },
  { id: "office", name: "Administração" },
];

export const workspaceNavigation: NavigationItem[] = [
  { name: "Central do Advogado", shortName: "Central", href: "/dashboard", icon: "home", group: "daily" },
  { name: "Copiloto jurídico", shortName: "Copiloto", href: "/dashboard/assistant", icon: "bot", group: "daily" },
  { name: "Agenda e prazos", shortName: "Agenda", href: "/dashboard/tasks", icon: "calendar", group: "daily" },
  { name: "Processos", shortName: "Processos", href: "/dashboard/tracker", icon: "briefcase", group: "daily" },
  { name: "Clientes", shortName: "Clientes", href: "/dashboard/crm", icon: "users", group: "daily" },
  { name: "Central de Arquivos", shortName: "Arquivos", href: "/dashboard/petitions/editor", icon: "file", group: "daily" },
  { name: "Comunicações", shortName: "Mensagens", href: "/dashboard/communications", icon: "message", group: "daily" },
  { name: "Biblioteca e publicações", shortName: "Biblioteca", href: "/dashboard/library", icon: "book", group: "more" },
  { name: "Conflitos de interesse", shortName: "Conflitos", href: "/dashboard/conflitos", icon: "shield", group: "more" },
  { name: "Controladoria judicial", shortName: "Controladoria", href: "/dashboard/controladoria", icon: "calendar", group: "more" },
  { name: "Atendimento e honorários", shortName: "Operação", href: "/dashboard/operacoes", icon: "wallet", group: "more", lawyer: true },
  { name: "Indicadores da carteira", shortName: "Indicadores", href: "/dashboard/analytics/judge-profiling", icon: "chart", group: "more" },
  { name: "Auditoria", shortName: "Auditoria", href: "/dashboard/audit", icon: "audit", group: "office", admin: true },
  { name: "Honorários e despesas", shortName: "Honorários", href: "/dashboard/financeiro", icon: "wallet", group: "office", admin: true },
  { name: "Modelos de documentos", shortName: "Modelos", href: "/dashboard/templates", icon: "file", group: "office" },
  { name: "Identidade documental", shortName: "Identidade", href: "/dashboard/brand", icon: "palette", group: "office" },
  { name: "Equipe e permissões", shortName: "Equipe", href: "/dashboard/admin/users", icon: "team", group: "office", admin: true },
  { name: "Conta e escritório", shortName: "Conta", href: "/dashboard/account", icon: "settings", group: "office" },
];

export function isNavigationActive(path: string, href: string) {
  if (href === "/dashboard") return path === href;
  if (href === "/dashboard/tracker" && /^\/dashboard\/cases\/[^/]+$/.test(path)) return true;
  return path === href;
}

export function navigationItemForPath(path: string) {
  return workspaceNavigation.find(item => isNavigationActive(path, item.href));
}

export function isWorkspacePath(path: string) {
  return Boolean(navigationItemForPath(path))
    || ["/dashboard/pilot", "/dashboard/brand", "/dashboard/financial", "/dashboard/peticoes", "/dashboard/assinaturas", "/portal", "/account/access"].includes(path);
}
