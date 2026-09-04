"use client";
import { MessageSquareText } from "lucide-react";
import { useState } from "react";
import { Records } from "@/components/workspace/records";
import { Page, button } from "@/components/workspace/shared";
export default function LibraryPage() {
  const [tab, setTab] = useState<"publications" | "library">("publications");
  const tabStyle = (active: boolean) => `${active ? "border-blue-500 text-blue-300" : "border-transparent text-zinc-400 hover:text-zinc-200"} min-h-11 border-b-2 px-1 text-sm font-medium`;
  return <Page title="Conhecimento do escritório" subtitle="Reúna andamentos e referências com a fonte e a data para conferência.">
    <div className="flex flex-col gap-3 border-b border-zinc-800 pb-4 sm:flex-row sm:items-end sm:justify-between">
      <nav aria-label="Áreas de conhecimento" className="flex gap-5 overflow-x-auto"><button type="button" className={tabStyle(tab === "publications")} aria-current={tab === "publications" ? "page" : undefined} onClick={() => setTab("publications")}>Andamentos dos casos</button><button type="button" className={tabStyle(tab === "library")} aria-current={tab === "library" ? "page" : undefined} onClick={() => setTab("library")}>Referências do escritório</button></nav>
      <button type="button" className={`${button} shrink-0`} onClick={() => window.dispatchEvent(new CustomEvent("lexflow:open-ai", { detail: { contextKind: "library" } }))}><MessageSquareText aria-hidden="true" size={17} /> Perguntar à IA</button>
    </div>
    <section aria-label={tab === "publications" ? "Andamentos dos casos" : "Referências do escritório"}><Records kind={tab} embedded /></section>
  </Page>;
}
