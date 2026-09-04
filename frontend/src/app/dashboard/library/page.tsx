"use client";
import { useState } from "react";
import { Records } from "@/components/workspace/records";
import { Page, button, primary } from "@/components/workspace/shared";
export default function LibraryPage() {
  const [tab, setTab] = useState<"publications" | "library">("publications");
  return <Page title="Conhecimento do escritório" subtitle="Consulte andamentos e referências em uma única área. Fontes e datas permanecem visíveis para conferência.">
    <nav aria-label="Áreas de conhecimento" className="flex flex-wrap gap-2"><button type="button" className={tab === "publications" ? primary : button} aria-current={tab === "publications" ? "page" : undefined} onClick={() => setTab("publications")}>Andamentos dos casos</button><button type="button" className={tab === "library" ? primary : button} aria-current={tab === "library" ? "page" : undefined} onClick={() => setTab("library")}>Minha biblioteca</button></nav>
    <button type="button" className={button} onClick={() => window.dispatchEvent(new CustomEvent("lexflow:open-ai", { detail: { contextKind: "library", prompt: "Resuma as referências autorizadas relevantes para minha pergunta e identifique claramente a fonte e a data de cada uma. Não presuma vigência." } }))}>Consultar biblioteca com IA</button>
    <Records kind={tab} embedded />
  </Page>;
}
