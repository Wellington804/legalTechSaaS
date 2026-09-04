"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";
import { BarChart3, BookOpen, Bot, BriefcaseBusiness, CalendarDays, FileText, Gavel, Home, Menu, MessageSquare, Palette, Settings, ShieldCheck, Users, UserRoundCog, WalletCards, X } from "lucide-react";
import { isOfficeAdminRole, useUser } from "@/context/user-context";
import { isNavigationActive, navigationGroups, workspaceNavigation, type NavigationItem } from "@/lib/navigation";

const icons: Record<NavigationItem["icon"], typeof Home> = {
  home: Home, calendar: CalendarDays, users: Users, briefcase: BriefcaseBusiness,
  file: FileText, message: MessageSquare, book: BookOpen, shield: ShieldCheck,
  chart: BarChart3, wallet: WalletCards, palette: Palette, team: UserRoundCog,
  audit: Gavel, settings: Settings, bot: Bot,
};

export function Sidebar() {
  const pathname = usePathname();
  const { user } = useUser();
  const dialog = useRef<HTMLDialogElement>(null);
  const allowed = workspaceNavigation.filter(item => (!item.admin || isOfficeAdminRole(user.role)) && (!item.lawyer || user.role === "ASSOCIADO" || isOfficeAdminRole(user.role)));
  const primaryGroup = navigationGroups.find(group => group.primary)!;
  const secondaryGroups = navigationGroups.filter(group => !group.primary);
  useEffect(() => { dialog.current?.close(); }, [pathname]);

  const groupLinks = (groups = navigationGroups, mobile = false) => <nav aria-label={mobile ? "Áreas do LexFlow" : "Trabalho diário"} className="space-y-5 px-3 py-4" onClick={event => { if ((event.target as HTMLElement).closest("a")) dialog.current?.close(); }}>
    {groups.map(group => {
      const items = allowed.filter(item => item.group === group.id);
      if (!items.length) return null;
      return <section key={group.id} aria-labelledby={`nav-${group.id}`}>
        <h2 id={`nav-${group.id}`} className={`px-3 pb-1.5 text-xs font-medium text-zinc-400 ${!mobile && group.id === "more" ? "sr-only" : ""}`}>{group.name}</h2>
        <div className="space-y-0.5">{items.map(item => {
          const Icon = icons[item.icon]; const active = isNavigationActive(pathname, item.href);
          return <Link key={item.href} href={item.href} aria-current={active ? "page" : undefined}
            className={`flex min-h-11 items-center gap-3 rounded-xl px-3 py-2 text-sm transition-colors ${active ? "bg-blue-500/15 text-blue-200" : "text-zinc-300 hover:bg-zinc-900 hover:text-white"}`}>
            <Icon aria-hidden="true" size={18} className={active ? "text-blue-400" : "text-zinc-500"} /><span>{item.name}</span>
          </Link>;
        })}</div>
      </section>;
    })}
  </nav>;

  return <>
    <aside className="hidden md:flex w-64 border-r border-zinc-800/80 bg-zinc-950 flex-col h-screen sticky top-0 shrink-0">
      <Link href="/dashboard" className="block px-5 py-5 border-b border-zinc-800/80 hover:bg-zinc-900/60">
        <span className="block text-lg font-semibold tracking-[-0.02em]">LexFlow</span><span className="block text-sm text-zinc-400 mt-1 truncate">{user.officeName}</span>
      </Link>
      <div className="overflow-y-auto flex-1">
        {groupLinks([primaryGroup])}
        <div className="border-t border-zinc-800/80 px-3 py-3">
          <details>
            <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between rounded-xl px-3 text-sm text-zinc-400 hover:bg-zinc-900 hover:text-zinc-100">Mais áreas <span aria-hidden="true">⌄</span></summary>
            {groupLinks(secondaryGroups)}
          </details>
        </div>
      </div>
    </aside>

    <nav aria-label="Navegação principal" className="order-2 z-40 grid shrink-0 grid-cols-5 border-t border-zinc-800 bg-zinc-950 px-1 pb-[env(safe-area-inset-bottom)] md:hidden">
      {[["/dashboard", "Central", Home], ["/dashboard/tasks", "Agenda", CalendarDays], ["/dashboard/tracker", "Processos", BriefcaseBusiness], ["/dashboard/petitions/editor", "Documento", FileText]].map(([href, label, Icon]) => {
        const active = isNavigationActive(pathname, String(href)); const Component = Icon as typeof Home;
        return <Link key={String(href)} href={String(href)} aria-current={active ? "page" : undefined} className={`flex min-h-14 flex-col items-center justify-center gap-1 text-[11px] ${active ? "text-blue-300" : "text-zinc-400"}`}><Component aria-hidden="true" size={19} />{String(label)}</Link>;
      })}
      <button type="button" onClick={() => dialog.current?.showModal()} aria-haspopup="dialog" aria-controls="mobile-modules" className="flex min-h-14 flex-col items-center justify-center gap-1 text-[11px] text-zinc-400"><Menu aria-hidden="true" size={19} />Outros</button>
    </nav>

    <dialog ref={dialog} id="mobile-modules" aria-labelledby="mobile-modules-title" className="m-0 ml-auto h-dvh w-[min(90vw,24rem)] max-h-none overflow-y-auto overscroll-contain border-l border-zinc-700 bg-zinc-950 text-zinc-100 p-0 backdrop:bg-black/70">
      <div className="sticky top-0 z-10 flex items-center justify-between gap-3 border-b border-zinc-800 bg-zinc-950 px-4 py-2"><h2 id="mobile-modules-title" className="text-lg font-semibold">Todas as áreas</h2><button type="button" aria-label="Fechar navegação" className="min-h-11 min-w-11 grid place-items-center" onClick={() => dialog.current?.close()}><X aria-hidden="true" size={20} /></button></div>
      {groupLinks(navigationGroups, true)}
    </dialog>
  </>;
}
