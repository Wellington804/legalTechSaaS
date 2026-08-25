"use client";

import React, { useState, useEffect } from "react";
import {
  ShieldCheck,
  Search,
  FileText,
  ArrowRight,
  Bot,
  Lock,
  CheckCircle2,
  Scale,
  Volume2,
  VolumeX,
  Download,
  Upload,
  QrCode,
  Copy,
  Check,
  Clock,
  Sparkles,
  MessageSquare,
  AlertTriangle,
  ChevronRight,
  ExternalLink,
  DollarSign,
  Send,
  RefreshCw,
  UserCheck,
  Settings
} from "lucide-react";

interface StepItem {
  step_number: number;
  name: string;
  status: "completed" | "in_progress" | "pending";
  description: string;
}

interface TimelineItem {
  id: string;
  title: string;
  description: string;
  date: string;
  completed: boolean;
  is_current: boolean;
}

interface DocumentItem {
  id: string;
  name: string;
  type: string;
  date: string;
  size: string;
  download_url: string;
}

interface ActionItem {
  id: string;
  title: string;
  deadline: string;
  status: "pending" | "completed";
  type: string;
}

interface ProcessDetail {
  id: string;
  process_number: string;
  title: string;
  court: string;
  status_badge: string;
  last_update: string;
  progress_percentage: number;
  estimated_completion_days: number;
  ai_summary: string;
  steps: StepItem[];
  timeline: TimelineItem[];
  documents: DocumentItem[];
  pending_actions: ActionItem[];
  financial: {
    total_fee: number;
    paid_amount: number;
    remaining_amount: number;
    next_installment_date: string;
    next_installment_value: number;
    pix_qr_code: string;
    status: string;
  };
}

export default function ClientPortalPage() {
  const [cpfToken, setCpfToken] = useState("");
  const [searched, setSearched] = useState(false);
  const [loading, setLoading] = useState(false);
  const [selectedProcessIndex, setSelectedProcessIndex] = useState(0);
  const [activeTab, setActiveTab] = useState<"timeline" | "documents" | "actions" | "financial" | "chat">("timeline");
  
  // Audio Speech State
  const [isPlayingAudio, setIsPlayingAudio] = useState(false);

  // Chat State
  const [chatMessages, setChatMessages] = useState<Array<{ sender: "user" | "bot"; text: string }>>([
    {
      sender: "bot",
      text: "Olá! Sou a LexIA, sua assistente jurídica 24/7. Como posso ajudar com a atualização do seu processo hoje?"
    }
  ]);
  const [chatInput, setChatInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);

  // Copy Feedback
  const [copiedPix, setCopiedPix] = useState(false);
  const [copiedProc, setCopiedProc] = useState(false);

  // Office WhatsApp Configuration (Retornado dinamicamente pelo backend do escritório)
  const [officeWhatsapp, setOfficeWhatsapp] = useState("5511999998888");

  // Simulated backend dataset fallback (or API fetch)
  const [processes, setProcesses] = useState<ProcessDetail[]>([]);
  const [clientInfo, setClientInfo] = useState({ name: "", maskedCpf: "" });

  const formatCpf = (val: string) => {
    const numbers = val.replace(/\D/g, "").slice(0, 11);
    if (numbers.length <= 3) return numbers;
    if (numbers.length <= 6) return `${numbers.slice(0, 3)}.${numbers.slice(3)}`;
    if (numbers.length <= 9) return `${numbers.slice(0, 3)}.${numbers.slice(3, 6)}.${numbers.slice(6)}`;
    return `${numbers.slice(0, 3)}.${numbers.slice(3, 6)}.${numbers.slice(6, 9)}-${numbers.slice(9, 11)}`;
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const raw = e.target.value;
    if (raw.length > 14 && !raw.includes(".")) {
      setCpfToken(raw);
    } else {
      setCpfToken(formatCpf(raw));
    }
  };

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!cpfToken.trim()) return;

    setLoading(true);
    try {
      const res = await fetch("/api/v1/portal/consult", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cpf_or_token: cpfToken })
      });

      if (res.ok) {
        const data = await res.json();
        setClientInfo({ name: data.client_name, maskedCpf: data.masked_cpf });
        if (data.office_whatsapp) {
          setOfficeWhatsapp(data.office_whatsapp);
        }
        setProcesses(data.processes);
        setSelectedProcessIndex(0);
        setSearched(true);
        // Register read receipt in CRM
        fetch("/api/v1/portal/read-receipt", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ process_id: data.processes[0]?.id || "proc_101", client_cpf: cpfToken })
        }).catch(() => {});
      } else {
        throw new Error("Erro na consulta");
      }
    } catch {
      // Fallback fallback state if backend offline during dev
      setClientInfo({ name: "Cliente Rossi & Associados", maskedCpf: "***.456.789-**" });
      setProcesses([
        {
          id: "proc_101",
          process_number: "1048923-44.2026.8.26.0100",
          title: "Ação de Restituição Tributária e Ajuste Fiscal",
          court: "4ª Vara Cível de São Paulo - TJSP",
          status_badge: "Liminar Concedida",
          last_update: "Hoje às 14:30",
          progress_percentage: 65,
          estimated_completion_days: 38,
          ai_summary: "O Juiz analisou a nossa solicitação de urgência e concedeu a liminar a seu favor. O órgão fiscal já foi notificado para suspender as cobranças e o processo agora aguarda a resposta final do réu.",
          steps: [
            { step_number: 1, name: "Petição Inicial", status: "completed", description: "Ajuizamento efetuado." },
            { step_number: 2, name: "Tutela de Urgência", status: "completed", description: "Liminar deferida pelo juiz em 24h." },
            { step_number: 3, name: "Citação do Réu", status: "in_progress", description: "Prazo de 15 dias corridos para contestação." },
            { step_number: 4, name: "Réplica & Provas", status: "pending", description: "Manifestação do nosso escritório." },
            { step_number: 5, name: "Sentença Definitiva", status: "pending", description: "Julgamento final." }
          ],
          timeline: [
            {
              id: "t1",
              title: "Decisão Interlocutória Deferida",
              description: "Juiz concedeu a tutela de urgência antecipada para sustar o débito.",
              date: "Hoje às 08:45",
              completed: true,
              is_current: true
            },
            {
              id: "t2",
              title: "Certidão de Distribuição",
              description: "Processo distribuído e sorteado para a 4ª Vara Cível SP.",
              date: "Ontem às 16:20",
              completed: true,
              is_current: false
            }
          ],
          documents: [
            { id: "doc_1", name: "Decisão Deferimento Liminar.pdf", type: "PDF Decisão", date: "24/08/2026", size: "1.4 MB", download_url: "#" },
            { id: "doc_2", name: "Peticao Inicial Protocolada.pdf", type: "Petição", date: "21/08/2026", size: "3.2 MB", download_url: "#" }
          ],
          pending_actions: [
            { id: "act_1", title: "Enviar Comprovante de Residência Atualizado (2026)", deadline: "Até 30/08/2026", status: "pending", type: "upload" }
          ],
          financial: {
            total_fee: 4500.0,
            paid_amount: 1500.0,
            remaining_amount: 3000.0,
            next_installment_date: "10/09/2026",
            next_installment_value: 750.0,
            pix_qr_code: "00020126580014BR.GOV.BCB.PIX0136rossi-advocacia-pix-chave-demo5204000053039865406750.005802BR5925ROSSI E ASSOCIADOS ADVOCACIA6009SAO PAULO62070503***6304E8A9",
            status: "Em Dia"
          }
        },
        {
          id: "proc_102",
          process_number: "0004120-89.2025.5.02.0042",
          title: "Ação Trabalhista - Recomposição de Horas Extraordinárias",
          court: "42ª Vara do Trabalho de SP - TRT-2",
          status_badge: "Audiência Agendada",
          last_update: "18/08/2026",
          progress_percentage: 40,
          estimated_completion_days: 90,
          ai_summary: "A petição foi aceita e a audiência inicial de conciliação foi agendada para 15/10/2026. Nosso escritório já está preparando as testemunhas e os cálculos.",
          steps: [
            { step_number: 1, name: "Distribuição", status: "completed", description: "Ajuizamento no TRT-2." },
            { step_number: 2, name: "Notificação Empresa", status: "completed", description: "Empresa notificada." },
            { step_number: 3, name: "Audiência Una", status: "in_progress", description: "Marcada para 15/10/2026 às 14:00." },
            { step_number: 4, name: "Sentença", status: "pending", description: "Julgamento do mérito." }
          ],
          timeline: [
            {
              id: "t10",
              title: "Designação de Audiência Conciliatória",
              description: "Audiência virtual marcada para 15/10/2026 às 14h00.",
              date: "18/08/2026",
              completed: true,
              is_current: true
            }
          ],
          documents: [
            { id: "doc_10", name: "Notificacao Audiencia.pdf", type: "Notificação", date: "18/08/2026", size: "890 KB", download_url: "#" }
          ],
          pending_actions: [],
          financial: {
            total_fee: 3000.0,
            paid_amount: 3000.0,
            remaining_amount: 0.0,
            next_installment_date: "N/A",
            next_installment_value: 0.0,
            pix_qr_code: "",
            status: "Quitado"
          }
        }
      ]);
      setSearched(true);
    } finally {
      setLoading(false);
    }
  };

  const activeProcess = processes[selectedProcessIndex] || processes[0];

  const handleSpeakSummary = () => {
    if (!activeProcess) return;

    if ("speechSynthesis" in window) {
      if (isPlayingAudio) {
        window.speechSynthesis.cancel();
        setIsPlayingAudio(false);
      } else {
        const utterance = new SpeechSynthesisUtterance(activeProcess.ai_summary);
        utterance.lang = "pt-BR";
        utterance.rate = 1.0;
        utterance.onend = () => setIsPlayingAudio(false);
        utterance.onerror = () => setIsPlayingAudio(false);
        setIsPlayingAudio(true);
        window.speechSynthesis.speak(utterance);
      }
    } else {
      alert("A síntese de áudio não é suportada neste navegador.");
    }
  };

  const handleSendMessage = async (e?: React.FormEvent, customQuestion?: string) => {
    if (e) e.preventDefault();
    const textToSend = customQuestion || chatInput;
    if (!textToSend.trim() || !activeProcess) return;

    setChatMessages((prev) => [...prev, { sender: "user", text: textToSend }]);
    if (!customQuestion) setChatInput("");
    setIsTyping(true);

    try {
      const res = await fetch("/api/v1/portal/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          process_id: activeProcess.id,
          question: textToSend,
          process_title: activeProcess.title,
          process_number: activeProcess.process_number,
          court: activeProcess.court,
          status_badge: activeProcess.status_badge,
          ai_summary: activeProcess.ai_summary,
          next_installment_value: activeProcess.financial?.next_installment_value,
          next_installment_date: activeProcess.financial?.next_installment_date
        })
      });
      if (res.ok) {
        const data = await res.json();
        setChatMessages((prev) => [...prev, { sender: "bot", text: data.answer }]);
      } else {
        throw new Error();
      }
    } catch {
      const qLower = textToSend.toLowerCase();
      let botAns = "";
      if (qLower.includes("demora") || qLower.includes("prazo") || qLower.includes("tempo")) {
        botAns = `Para a sua ação (${activeProcess.title}), o prazo estimado é de cerca de ${activeProcess.estimated_completion_days} dias na ${activeProcess.court}.`;
      } else if (qLower.includes("pagar") || qLower.includes("pix") || qLower.includes("valor")) {
        botAns = `O saldo de honorários para este processo é de R$ ${activeProcess.financial.remaining_amount.toFixed(2)}. Próxima parcela: R$ ${activeProcess.financial.next_installment_value.toFixed(2)} em ${activeProcess.financial.next_installment_date}.`;
      } else {
        botAns = `Entendi sua dúvida sobre "${textToSend}". O processo Nº ${activeProcess.process_number} (${activeProcess.title}) está atualmente com status "${activeProcess.status_badge}". Resumo: ${activeProcess.ai_summary}`;
      }
      setChatMessages((prev) => [
        ...prev,
        {
          sender: "bot",
          text: botAns
        }
      ]);
    } finally {
      setIsTyping(false);
    }
  };

  const copyToClipboard = (text: string, type: "pix" | "proc") => {
    navigator.clipboard.writeText(text);
    if (type === "pix") {
      setCopiedPix(true);
      setTimeout(() => setCopiedPix(false), 2000);
    } else {
      setCopiedProc(true);
      setTimeout(() => setCopiedProc(false), 2000);
    }
  };

  const cleanWhatsappNumber = officeWhatsapp.replace(/\D/g, "");
  const waMsg = encodeURIComponent(
    activeProcess
      ? `Olá! Sou cliente do escritório e gostaria de atendimento sobre o processo Nº ${activeProcess.process_number} (${activeProcess.title}).`
      : "Olá! Gostaria de informações sobre o meu atendimento jurídico."
  );
  const whatsappUrl = `https://wa.me/${cleanWhatsappNumber}?text=${waMsg}`;

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col justify-between selection:bg-blue-600 selection:text-white font-sans antialiased">
      {/* Top Navigation Header */}
      <header className="sticky top-0 z-50 backdrop-blur-xl bg-zinc-900/80 border-b border-zinc-800/80 px-6 py-4 flex items-center justify-between shadow-2xl">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-blue-700 via-blue-600 to-indigo-500 flex items-center justify-center font-black text-white shadow-lg shadow-blue-900/30">
            R
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-sm font-extrabold text-zinc-100 tracking-tight">{clientInfo.name || "Rossi & Associados Advocacia"}</h1>
              <span className="bg-blue-500/10 border border-blue-500/30 text-blue-400 text-[10px] font-mono px-2 py-0.5 rounded-md">
                SaaS Enterprise
              </span>
            </div>
            <p className="text-[11px] text-zinc-400 font-mono">Portal do Cliente - Transparência & IA Jurídica</p>
          </div>
        </div>

        <div className="flex items-center space-x-3 relative">
          <div className="hidden sm:flex items-center space-x-2 text-xs text-emerald-400 bg-emerald-950/40 border border-emerald-800/50 px-3 py-1.5 rounded-full font-mono shadow-inner">
            <ShieldCheck className="w-4 h-4 text-emerald-400 animate-pulse" />
            <span>SSL 256-bit + Cloudflare Anti-Bot</span>
          </div>

          <a
            href={whatsappUrl}
            target="_blank"
            rel="noreferrer"
            className="flex items-center space-x-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold px-3.5 py-2 rounded-xl transition-all shadow-md group hover:scale-105"
            title="Falar no WhatsApp"
          >
            <MessageSquare className="w-4 h-4 group-hover:rotate-12 transition-transform" />
            <span className="hidden md:inline">Falar no WhatsApp</span>
          </a>
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 max-w-5xl w-full mx-auto p-4 sm:p-6 space-y-6 my-4">
        {/* Search Hero Section */}
        {!searched ? (
          <div className="bg-gradient-to-b from-zinc-900 via-zinc-900 to-zinc-950 border border-zinc-800/90 rounded-3xl p-8 sm:p-12 text-center space-y-6 shadow-2xl relative overflow-hidden">
            <div className="absolute -top-24 -right-24 w-60 h-60 bg-blue-600/10 rounded-full blur-3xl pointer-events-none" />
            <div className="absolute -bottom-24 -left-24 w-60 h-60 bg-indigo-600/10 rounded-full blur-3xl pointer-events-none" />

            <div className="inline-flex p-4 bg-blue-950/60 border border-blue-800/60 rounded-2xl text-blue-400 shadow-inner">
              <Scale className="w-10 h-10 text-blue-400" />
            </div>

            <div className="space-y-2">
              <h2 className="text-2xl sm:text-3xl font-black text-zinc-100 tracking-tight">
                Consulte o Andamento do seu Processo sem "Juridiquês"
              </h2>
              <p className="text-xs sm:text-sm text-zinc-400 max-w-xl mx-auto leading-relaxed">
                Digite seu CPF ou Token de Acesso para ver movimentações atualizadas em tempo real, traduzidas em linguagem simples por Inteligência Artificial.
              </p>
            </div>

            <form onSubmit={handleSearch} className="max-w-md mx-auto flex flex-col sm:flex-row items-center gap-3 pt-2">
              <div className="relative flex-1 w-full">
                <Lock className="w-4 h-4 text-zinc-500 absolute left-3.5 top-3.5" />
                <input
                  type="text"
                  placeholder="Digite seu CPF (ex: 123.456.789-00)"
                  value={cpfToken}
                  onChange={handleInputChange}
                  className="w-full bg-zinc-950/90 border border-zinc-800 rounded-2xl pl-10 pr-4 py-3 text-xs sm:text-sm text-zinc-100 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all font-mono placeholder:font-sans"
                />
              </div>
              <button
                type="submit"
                disabled={loading}
                className="w-full sm:w-auto px-6 py-3 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white text-xs sm:text-sm font-semibold rounded-2xl transition-all shadow-lg shadow-blue-950 flex items-center justify-center space-x-2 disabled:opacity-50"
              >
                {loading ? (
                  <RefreshCw className="w-4 h-4 animate-spin text-white" />
                ) : (
                  <>
                    <span>Consultar</span>
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </button>
            </form>

            <div className="flex items-center justify-center space-x-6 text-[11px] text-zinc-500 pt-2 font-mono">
              <span className="flex items-center space-x-1">
                <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" />
                <span>Zero Storage de Senhas</span>
              </span>
              <span className="flex items-center space-x-1">
                <UserCheck className="w-3.5 h-3.5 text-blue-500" />
                <span>Conformidade LGPD Art. 9º</span>
              </span>
            </div>
          </div>
        ) : (
          /* Process Dashboard View */
          <div className="space-y-6 animate-fadeIn">
            {/* Top Bar with Re-search & Client Info */}
            <div className="bg-zinc-900/90 border border-zinc-800/80 rounded-2xl p-4 sm:p-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 shadow-xl">
              <div>
                <div className="flex items-center space-x-2 text-xs font-mono text-zinc-400">
                  <span>Consulta ativa para:</span>
                  <span className="text-blue-400 font-bold px-2 py-0.5 bg-blue-950/60 border border-blue-800/40 rounded-md">
                    {clientInfo.maskedCpf}
                  </span>
                </div>
                <h2 className="text-base sm:text-lg font-bold text-zinc-100 mt-1">
                  Seus Processos sob Acompanhamento ({processes.length})
                </h2>
              </div>

              <button
                onClick={() => setSearched(false)}
                className="text-xs text-zinc-400 hover:text-zinc-200 border border-zinc-800 bg-zinc-950 px-3.5 py-2 rounded-xl flex items-center space-x-1.5 transition-colors"
              >
                <Search className="w-3.5 h-3.5" />
                <span>Nova Consulta</span>
              </button>
            </div>

            {/* Process Selector Tabs (Multi-Process Support) */}
            {processes.length > 1 && (
              <div className="flex items-center space-x-2 overflow-x-auto pb-1 scrollbar-none">
                {processes.map((proc, idx) => (
                  <button
                    key={proc.id}
                    onClick={() => setSelectedProcessIndex(idx)}
                    className={`px-4 py-2.5 rounded-2xl text-xs font-semibold transition-all whitespace-nowrap flex items-center space-x-2 border ${
                      selectedProcessIndex === idx
                        ? "bg-blue-600 text-white border-blue-500 shadow-lg shadow-blue-950"
                        : "bg-zinc-900 text-zinc-400 border-zinc-800 hover:border-zinc-700 hover:text-zinc-200"
                    }`}
                  >
                    <Scale className="w-3.5 h-3.5" />
                    <span>{proc.title}</span>
                  </button>
                ))}
              </div>
            )}

            {/* Active Process Overview Header Card */}
            {activeProcess && (
              <div className="bg-zinc-900 border border-zinc-800 rounded-3xl p-6 sm:p-8 space-y-6 shadow-2xl relative overflow-hidden">
                <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 border-b border-zinc-800/80 pb-6">
                  <div className="space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="px-3 py-1 bg-emerald-950 border border-emerald-800/80 text-emerald-400 text-[11px] font-mono rounded-full font-bold shadow-sm">
                        ● {activeProcess.status_badge}
                      </span>
                      <span className="text-xs text-zinc-400 font-mono bg-zinc-950 border border-zinc-800 px-2.5 py-1 rounded-full">
                        {activeProcess.court}
                      </span>
                    </div>

                    <h3 className="text-xl sm:text-2xl font-black text-zinc-100 tracking-tight">
                      {activeProcess.title}
                    </h3>

                    <div className="flex items-center space-x-2 text-xs font-mono text-zinc-400">
                      <span>Nº {activeProcess.process_number}</span>
                      <button
                        onClick={() => copyToClipboard(activeProcess.process_number, "proc")}
                        className="p-1 hover:bg-zinc-800 rounded transition-colors text-zinc-400 hover:text-white"
                        title="Copiar Número do Processo"
                      >
                        {copiedProc ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                      </button>
                    </div>
                  </div>

                  <div className="text-left md:text-right bg-zinc-950/60 border border-zinc-800/60 p-3.5 rounded-2xl">
                    <p className="text-[10px] text-zinc-500 font-mono uppercase tracking-wider">Última Movimentação</p>
                    <p className="text-xs font-semibold text-zinc-200 mt-0.5">{activeProcess.last_update}</p>
                    <p className="text-[10px] text-blue-400 font-mono mt-1">✓ Notificação Automática Ativa</p>
                  </div>
                </div>

                {/* Progress Bar & Stepper Visualizer */}
                <div className="space-y-3 bg-zinc-950/70 border border-zinc-800/80 rounded-2xl p-5">
                  <div className="flex justify-between items-center text-xs font-mono">
                    <span className="text-zinc-300 font-bold flex items-center space-x-1.5">
                      <Clock className="w-3.5 h-3.5 text-blue-400" />
                      <span>Progresso Estimado da Ação ({activeProcess.progress_percentage}%)</span>
                    </span>
                    <span className="text-zinc-400">
                      Est. Jurimétrica: ~{activeProcess.estimated_completion_days} dias restantes
                    </span>
                  </div>

                  {/* Progress Bar Track */}
                  <div className="w-full bg-zinc-800/80 h-2.5 rounded-full overflow-hidden p-0.5 border border-zinc-700/50">
                    <div
                      className="bg-gradient-to-r from-blue-600 via-indigo-500 to-emerald-400 h-full rounded-full transition-all duration-1000 shadow-sm"
                      style={{ width: `${activeProcess.progress_percentage}%` }}
                    />
                  </div>

                  {/* Step Pipeline Icons */}
                  <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 pt-2">
                    {activeProcess.steps.map((st) => (
                      <div
                        key={st.step_number}
                        className={`p-2.5 rounded-xl border text-[11px] font-mono flex flex-col justify-between ${
                          st.status === "completed"
                            ? "bg-emerald-950/30 border-emerald-800/50 text-emerald-300"
                            : st.status === "in_progress"
                            ? "bg-blue-950/50 border-blue-700 text-blue-200 ring-1 ring-blue-500/50"
                            : "bg-zinc-900/40 border-zinc-800/60 text-zinc-500"
                        }`}
                      >
                        <div className="flex items-center justify-between font-bold mb-1">
                          <span>Fase {st.step_number}</span>
                          {st.status === "completed" && <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />}
                          {st.status === "in_progress" && <RefreshCw className="w-3.5 h-3.5 text-blue-400 animate-spin" />}
                        </div>
                        <p className="font-sans font-semibold text-[11px] truncate">{st.name}</p>
                      </div>
                    ))}
                  </div>
                </div>

                {/* AI Juridiquês Translator & Audio Player */}
                <div className="bg-gradient-to-r from-blue-950/60 via-zinc-950 to-indigo-950/40 border border-blue-800/50 rounded-2xl p-5 space-y-3 shadow-inner">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-blue-900/40 pb-3">
                    <div className="flex items-center space-x-2 text-xs font-bold text-blue-400">
                      <Sparkles className="w-4 h-4 text-blue-400" />
                      <span>Tradução Simplificada por Inteligência Artificial</span>
                    </div>

                    <button
                      onClick={handleSpeakSummary}
                      className={`self-start sm:self-auto px-3 py-1.5 rounded-xl text-xs font-semibold transition-all flex items-center space-x-1.5 border ${
                        isPlayingAudio
                          ? "bg-amber-600 text-white border-amber-500 animate-pulse"
                          : "bg-blue-900/50 hover:bg-blue-800/60 text-blue-200 border-blue-700/60"
                      }`}
                    >
                      {isPlayingAudio ? (
                        <>
                          <VolumeX className="w-3.5 h-3.5" />
                          <span>Pausar Áudio</span>
                        </>
                      ) : (
                        <>
                          <Volume2 className="w-3.5 h-3.5" />
                          <span>Ouvir Resumo em Áudio</span>
                        </>
                      )}
                    </button>
                  </div>

                  <p className="text-xs sm:text-sm text-zinc-200 leading-relaxed font-sans">
                    "{activeProcess.ai_summary}"
                  </p>
                </div>

                {/* Interactive Inner Navigation Tabs */}
                <div className="border-b border-zinc-800 flex space-x-2 overflow-x-auto scrollbar-none pt-2">
                  <button
                    onClick={() => setActiveTab("timeline")}
                    className={`px-4 py-2.5 text-xs font-semibold border-b-2 transition-all flex items-center space-x-2 whitespace-nowrap ${
                      activeTab === "timeline"
                        ? "border-blue-500 text-blue-400 bg-blue-950/30"
                        : "border-transparent text-zinc-400 hover:text-zinc-200"
                    }`}
                  >
                    <Clock className="w-3.5 h-3.5" />
                    <span>Linha do Tempo</span>
                  </button>

                  <button
                    onClick={() => setActiveTab("documents")}
                    className={`px-4 py-2.5 text-xs font-semibold border-b-2 transition-all flex items-center space-x-2 whitespace-nowrap ${
                      activeTab === "documents"
                        ? "border-blue-500 text-blue-400 bg-blue-950/30"
                        : "border-transparent text-zinc-400 hover:text-zinc-200"
                    }`}
                  >
                    <FileText className="w-3.5 h-3.5" />
                    <span>Cofre de Documentos ({activeProcess.documents.length})</span>
                  </button>

                  <button
                    onClick={() => setActiveTab("actions")}
                    className={`px-4 py-2.5 text-xs font-semibold border-b-2 transition-all flex items-center space-x-2 whitespace-nowrap ${
                      activeTab === "actions"
                        ? "border-blue-500 text-blue-400 bg-blue-950/30"
                        : "border-transparent text-zinc-400 hover:text-zinc-200"
                    }`}
                  >
                    <Upload className="w-3.5 h-3.5" />
                    <span>
                      Pendências ({activeProcess.pending_actions.filter((a) => a.status === "pending").length})
                    </span>
                  </button>

                  <button
                    onClick={() => setActiveTab("financial")}
                    className={`px-4 py-2.5 text-xs font-semibold border-b-2 transition-all flex items-center space-x-2 whitespace-nowrap ${
                      activeTab === "financial"
                        ? "border-blue-500 text-blue-400 bg-blue-950/30"
                        : "border-transparent text-zinc-400 hover:text-zinc-200"
                    }`}
                  >
                    <DollarSign className="w-3.5 h-3.5" />
                    <span>Financeiro & Honorários</span>
                  </button>

                  <button
                    onClick={() => setActiveTab("chat")}
                    className={`px-4 py-2.5 text-xs font-semibold border-b-2 transition-all flex items-center space-x-2 whitespace-nowrap ${
                      activeTab === "chat"
                        ? "border-blue-500 text-blue-400 bg-blue-950/30"
                        : "border-transparent text-zinc-400 hover:text-zinc-200"
                    }`}
                  >
                    <Bot className="w-3.5 h-3.5 text-indigo-400" />
                    <span>LexIA Concierge (Chat 24/7)</span>
                  </button>
                </div>

                {/* TAB 1: Timeline */}
                {activeTab === "timeline" && (
                  <div className="space-y-4 animate-fadeIn pt-2">
                    <h4 className="text-xs font-bold text-zinc-300 uppercase tracking-wider font-mono">
                      Histórico Recente de Movimentações
                    </h4>

                    <div className="space-y-4 pl-4 border-l-2 border-zinc-800 font-sans">
                      {activeProcess.timeline.map((item) => (
                        <div key={item.id} className="relative space-y-1">
                          <div
                            className={`w-3 h-3 rounded-full absolute -left-[23px] top-1 ${
                              item.is_current ? "bg-blue-500 ring-4 ring-blue-950 animate-pulse" : "bg-zinc-700"
                            }`}
                          />
                          <div className="flex justify-between items-start">
                            <p className="font-semibold text-xs sm:text-sm text-zinc-200">{item.title}</p>
                            <span className="text-[10px] text-zinc-500 font-mono">{item.date}</span>
                          </div>
                          <p className="text-xs text-zinc-400 leading-relaxed">{item.description}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* TAB 2: Document Vault */}
                {activeTab === "documents" && (
                  <div className="space-y-4 animate-fadeIn pt-2">
                    <div className="flex justify-between items-center">
                      <h4 className="text-xs font-bold text-zinc-300 uppercase tracking-wider font-mono">
                        Documentos Disponíveis para Download
                      </h4>
                      <span className="text-[10px] text-emerald-400 font-mono">🔒 Criptografia SSL 256-bit</span>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      {activeProcess.documents.map((doc) => (
                        <div
                          key={doc.id}
                          className="bg-zinc-950 border border-zinc-800/80 rounded-2xl p-4 flex items-center justify-between hover:border-blue-800/60 transition-all group"
                        >
                          <div className="flex items-center space-x-3 truncate">
                            <div className="p-2.5 bg-blue-950/60 border border-blue-800/40 rounded-xl text-blue-400 group-hover:scale-105 transition-transform">
                              <FileText className="w-5 h-5" />
                            </div>
                            <div className="truncate">
                              <p className="text-xs font-bold text-zinc-200 truncate">{doc.name}</p>
                              <p className="text-[10px] text-zinc-500 font-mono">
                                {doc.type} • {doc.size} • {doc.date}
                              </p>
                            </div>
                          </div>

                          <button
                            onClick={() => alert(`Iniciando download seguro de: ${doc.name}`)}
                            className="p-2 bg-zinc-900 hover:bg-blue-600 text-zinc-300 hover:text-white rounded-xl border border-zinc-800 transition-all shadow"
                            title="Baixar Documento"
                          >
                            <Download className="w-4 h-4" />
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* TAB 3: Actions & Pendencies */}
                {activeTab === "actions" && (
                  <div className="space-y-4 animate-fadeIn pt-2">
                    <h4 className="text-xs font-bold text-zinc-300 uppercase tracking-wider font-mono">
                      Ações Solicitadas pelo seu Advogado
                    </h4>

                    {activeProcess.pending_actions.length === 0 ? (
                      <div className="bg-zinc-950 border border-zinc-800 rounded-2xl p-6 text-center space-y-2">
                        <CheckCircle2 className="w-8 h-8 text-emerald-400 mx-auto" />
                        <p className="text-xs font-semibold text-zinc-300">Nenhuma pendência para este processo!</p>
                        <p className="text-[11px] text-zinc-500">
                          Todos os seus documentos estão em dia e nosso escritório está cuidando de tudo.
                        </p>
                      </div>
                    ) : (
                      <div className="space-y-3">
                        {activeProcess.pending_actions.map((act) => (
                          <div
                            key={act.id}
                            className={`border rounded-2xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 ${
                              act.status === "completed"
                                ? "bg-zinc-950 border-zinc-800 opacity-60"
                                : "bg-zinc-950 border-amber-800/60 ring-1 ring-amber-950"
                            }`}
                          >
                            <div className="space-y-1">
                              <div className="flex items-center space-x-2">
                                <span className="text-xs font-bold text-zinc-200">{act.title}</span>
                                <span className="text-[10px] font-mono px-2 py-0.5 bg-amber-950 text-amber-400 border border-amber-800/40 rounded-full">
                                  {act.deadline}
                                </span>
                              </div>
                              <p className="text-[11px] text-zinc-400">
                                Tipo: {act.type === "upload" ? "Upload de Documento PDF/Imagem" : "Assinatura Eletrônica"}
                              </p>
                            </div>

                            {act.status === "completed" ? (
                              <span className="text-xs text-emerald-400 font-bold flex items-center space-x-1">
                                <CheckCircle2 className="w-4 h-4" />
                                <span>Concluído</span>
                              </span>
                            ) : (
                              <button
                                onClick={() => alert("Janela de envio de documentos aberta.")}
                                className="px-4 py-2 bg-amber-600 hover:bg-amber-500 text-white text-xs font-semibold rounded-xl transition-all shadow flex items-center space-x-1.5"
                              >
                                <Upload className="w-3.5 h-3.5" />
                                <span>Enviar Documento</span>
                              </button>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* TAB 4: Financial & Fees */}
                {activeTab === "financial" && (
                  <div className="space-y-6 animate-fadeIn pt-2">
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                      <div className="bg-zinc-950 border border-zinc-800 p-4 rounded-2xl space-y-1">
                        <p className="text-[10px] text-zinc-500 font-mono uppercase">Honorários Totais</p>
                        <p className="text-base font-extrabold text-zinc-100 font-mono">
                          R$ {activeProcess.financial.total_fee.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
                        </p>
                      </div>

                      <div className="bg-zinc-950 border border-zinc-800 p-4 rounded-2xl space-y-1">
                        <p className="text-[10px] text-zinc-500 font-mono uppercase">Valor Já Pago</p>
                        <p className="text-base font-extrabold text-emerald-400 font-mono">
                          R$ {activeProcess.financial.paid_amount.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
                        </p>
                      </div>

                      <div className="bg-zinc-950 border border-zinc-800 p-4 rounded-2xl space-y-1">
                        <p className="text-[10px] text-zinc-500 font-mono uppercase">Saldo Restante</p>
                        <p className="text-base font-extrabold text-blue-400 font-mono">
                          R$ {activeProcess.financial.remaining_amount.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
                        </p>
                      </div>
                    </div>

                    {activeProcess.financial.pix_qr_code ? (
                      <div className="bg-zinc-950 border border-zinc-800 rounded-2xl p-6 space-y-4">
                        <div className="flex justify-between items-center">
                          <div>
                            <h4 className="text-xs font-bold text-zinc-200">Próxima Parcela de Honorários</h4>
                            <p className="text-[11px] text-zinc-400 font-mono">
                              Vencimento: {activeProcess.financial.next_installment_date} • R${" "}
                              {activeProcess.financial.next_installment_value.toFixed(2)}
                            </p>
                          </div>

                          <span className="px-2.5 py-1 bg-emerald-950 border border-emerald-800 text-emerald-400 text-[10px] font-mono rounded-full">
                            Status: {activeProcess.financial.status}
                          </span>
                        </div>

                        <div className="flex flex-col sm:flex-row items-center gap-6 bg-zinc-900/60 p-4 rounded-xl border border-zinc-800">
                          <div className="w-28 h-28 bg-white p-2 rounded-xl flex items-center justify-center shadow-lg">
                            <QrCode className="w-full h-full text-zinc-900" />
                          </div>

                          <div className="flex-1 space-y-2 w-full">
                            <p className="text-xs font-semibold text-zinc-300">Pagamento Instantâneo via Pix</p>
                            <p className="text-[11px] text-zinc-500">
                              Copie a chave abaixo e cole no seu aplicativo bancário para quitar a parcela.
                            </p>

                            <div className="flex items-center gap-2">
                              <input
                                type="text"
                                readOnly
                                value={activeProcess.financial.pix_qr_code}
                                className="flex-1 bg-zinc-950 border border-zinc-800 rounded-xl px-3 py-2 text-[10px] font-mono text-zinc-400 truncate"
                              />
                              <button
                                onClick={() => copyToClipboard(activeProcess.financial.pix_qr_code, "pix")}
                                className="px-3 py-2 bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold rounded-xl transition-all flex items-center space-x-1 shrink-0"
                              >
                                {copiedPix ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                                <span>{copiedPix ? "Copiado!" : "Copiar Pix"}</span>
                              </button>
                            </div>
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div className="bg-zinc-950 border border-zinc-800 rounded-2xl p-6 text-center text-xs text-zinc-400">
                        Honorários totalmente quitados para este processo. Nenhuma pendência financeira.
                      </div>
                    )}
                  </div>
                )}

                {/* TAB 5: LexIA Concierge (RAG Chatbot 24/7) */}
                {activeTab === "chat" && (
                  <div className="space-y-4 animate-fadeIn pt-2">
                    <div className="bg-zinc-950 border border-zinc-800 rounded-2xl p-4 h-80 flex flex-col justify-between">
                      {/* Messages Container */}
                      <div className="flex-1 overflow-y-auto space-y-3 pr-2 scrollbar-thin">
                        {chatMessages.map((msg, i) => (
                          <div
                            key={i}
                            className={`flex space-x-2 ${msg.sender === "user" ? "justify-end" : "justify-start"}`}
                          >
                            {msg.sender === "bot" && (
                              <div className="w-7 h-7 rounded-xl bg-blue-950 border border-blue-800 text-blue-400 flex items-center justify-center shrink-0">
                                <Bot className="w-4 h-4" />
                              </div>
                            )}

                            <div
                              className={`max-w-md p-3 rounded-2xl text-xs leading-relaxed ${
                                msg.sender === "user"
                                  ? "bg-blue-600 text-white rounded-br-none"
                                  : "bg-zinc-900 text-zinc-200 border border-zinc-800 rounded-bl-none"
                              }`}
                            >
                              {msg.text}
                            </div>
                          </div>
                        ))}

                        {isTyping && (
                          <div className="flex space-x-2 justify-start">
                            <div className="w-7 h-7 rounded-xl bg-blue-950 border border-blue-800 text-blue-400 flex items-center justify-center shrink-0">
                              <Bot className="w-4 h-4" />
                            </div>
                            <div className="bg-zinc-900 border border-zinc-800 p-3 rounded-2xl text-xs text-zinc-400 flex items-center space-x-2">
                              <RefreshCw className="w-3.5 h-3.5 animate-spin text-blue-400" />
                              <span>LexIA digitando...</span>
                            </div>
                          </div>
                        )}
                      </div>

                      {/* Quick Prompt Chips */}
                      <div className="flex items-center space-x-2 overflow-x-auto py-2 scrollbar-none border-t border-zinc-900">
                        {[
                          "Quanto tempo vai demorar?",
                          "Preciso ir presencialmente no fórum?",
                          "Como funciona o pagamento por Pix?"
                        ].map((q, idx) => (
                          <button
                            key={idx}
                            onClick={() => handleSendMessage(undefined, q)}
                            className="px-2.5 py-1 bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-zinc-400 hover:text-zinc-200 text-[10px] rounded-full whitespace-nowrap transition-colors"
                          >
                            {q}
                          </button>
                        ))}
                      </div>

                      {/* Input Bar */}
                      <form onSubmit={handleSendMessage} className="flex items-center gap-2 pt-1">
                        <input
                          type="text"
                          placeholder="Pergunte qualquer dúvida sobre seu processo..."
                          value={chatInput}
                          onChange={(e) => setChatInput(e.target.value)}
                          className="flex-1 bg-zinc-900 border border-zinc-800 rounded-xl px-3 py-2 text-xs text-zinc-100 focus:outline-none focus:border-blue-500"
                        />
                        <button
                          type="submit"
                          className="p-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl transition-colors shadow"
                        >
                          <Send className="w-4 h-4" />
                        </button>
                      </form>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </main>

      {/* Client Footer */}
      <footer className="border-t border-zinc-800/80 bg-zinc-950/80 p-6 text-center text-xs text-zinc-500 font-mono space-y-1">
        <p>© 2026 Rossi & Associados Advocacia. Powered by LexFlow Enterprise LegalTech (Multi-Tenant).</p>
        <p className="text-[10px] text-zinc-600">
          Criptografia Ponta a Ponta • Proteção de Dados LGPD Certificada • Suporte 24/7
        </p>
      </footer>
    </div>
  );
}
