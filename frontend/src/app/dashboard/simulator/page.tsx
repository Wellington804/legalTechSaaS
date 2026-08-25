"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  Bot,
  Sparkles,
  Send,
  Scale,
  ShieldAlert,
  CheckCircle2,
  BookOpen,
  RotateCcw,
  Volume2,
  VolumeX,
  Play,
  Pause,
  Clock,
  Download,
  Zap,
  Award,
  Users,
  Mic,
  MicOff,
  MessageSquare,
  FileCheck,
  Radio,
  Building2,
  Plus,
  X,
} from "lucide-react";

type ForenseRole = "JUIZ" | "PARTE_CONTRARIA" | "TESTEMUNHA" | "TURMA_RECURSAL";

interface ChatMessage {
  sender: "AI" | "LAWYER";
  name: string;
  roleTitle: string;
  message: string;
  timestamp: string;
}

export default function CourtroomSimulatorPage() {
  const [role, setRole] = useState<ForenseRole>("JUIZ");
  const [selectedCourt, setSelectedCourt] = useState("TJSP");
  const [userArgument, setUserArgument] = useState("");
  const [isSimulating, setIsSimulating] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [speakingIndex, setSpeakingIndex] = useState<number | null>(null);

  // Court Options List State
  const [courtOptions, setCourtOptions] = useState([
    { id: "TJSP", name: "TJSP — Tribunal de Justiça de SP (Cível/Empresarial)" },
    { id: "TJRJ", name: "TJRJ — Tribunal de Justiça do RJ (Consumidor/Cível)" },
    { id: "TJMG", name: "TJMG — Tribunal de Justiça de MG (Cível/Família)" },
    { id: "TRF3", name: "TRF3 — Tribunal Regional Federal 3ª Região (Tributário)" },
    { id: "TST", name: "TST — Tribunal Superior do Trabalho (Trabalhista)" },
    { id: "STJ", name: "STJ — Superior Tribunal de Justiça (Recursos Especiais)" },
    { id: "STF", name: "STF — Supremo Tribunal Federal (Constitucional)" },
  ]);

  // Add Court Modal State
  const [isAddCourtModalOpen, setIsAddCourtModalOpen] = useState(false);
  const [newCourtSigla, setNewCourtSigla] = useState("");
  const [newCourtNome, setNewCourtNome] = useState("");
  const [newCourtRamo, setNewCourtRamo] = useState("");

  const handleAddCourt = (e: React.FormEvent) => {
    e.preventDefault();
    const sigla = newCourtSigla.trim().toUpperCase();
    if (!sigla) return;

    const fullName = newCourtNome.trim()
      ? `${sigla} — ${newCourtNome.trim()}${newCourtRamo.trim() ? ` (${newCourtRamo.trim()})` : ""}`
      : sigla;

    if (courtOptions.some((c) => c.id === sigla)) {
      showToast(`O tribunal ${sigla} já consta na lista!`);
      setSelectedCourt(sigla);
      setIsAddCourtModalOpen(false);
      return;
    }

    const newOption = { id: sigla, name: fullName };
    setCourtOptions((prev) => [...prev, newOption]);
    setNewCourtSigla("");
    setNewCourtNome("");
    setNewCourtRamo("");
    setIsAddCourtModalOpen(false);

    handleCourtChange(sigla);
  };

  // Microphone STT State
  const [isListening, setIsListening] = useState(false);
  const recognitionRef = useRef<any>(null);

  // Timer State (15 minutes countdown = 900 seconds)
  const [timerSeconds, setTimerSeconds] = useState(900);
  const [isTimerRunning, setIsTimerRunning] = useState(false);

  // Scorecard State
  const [scores, setScores] = useState({
    clarity: 94,
    legalBasis: 89,
    timeControl: 96,
  });

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500);
  };

  // Court Selector Handler
  const handleCourtChange = (courtId: string) => {
    setSelectedCourt(courtId);
    const courtObj = courtOptions.find((c) => c.id === courtId);
    showToast(`Jurisdição alterada para: ${courtObj?.name || courtId}`);

    let initialSpeaker = "MM. Juiz de Direito";
    if (courtId === "STF" || courtId === "STJ") initialSpeaker = `Min. Relator (${courtId})`;
    else if (courtId.startsWith("TRF") || courtId.startsWith("TJ")) initialSpeaker = `Des. Relator (${courtId})`;

    const updatedPrompt: ChatMessage = {
      sender: "AI",
      name: initialSpeaker,
      roleTitle: `Jurisdição: ${courtId}`,
      message: `Com a palavra o emérito patrono perante o Egrégio ${courtId} para sustentação oral pelo prazo regimental.`,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };
    setChatHistory([updatedPrompt]);
  };

  // Timer countdown effect
  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (isTimerRunning && timerSeconds > 0) {
      interval = setInterval(() => {
        setTimerSeconds((prev) => prev - 1);
      }, 1000);
    }
    return () => clearInterval(interval);
  }, [isTimerRunning, timerSeconds]);

  const formatTimer = (totalSec: number) => {
    const min = Math.floor(totalSec / 60);
    const sec = totalSec % 60;
    return `${min.toString().padStart(2, "0")}:${sec.toString().padStart(2, "0")}`;
  };

  const initialPrompts: Record<ForenseRole, ChatMessage> = {
    JUIZ: {
      sender: "AI",
      name: "MM. Juiz de Direito",
      roleTitle: "Magistrado Presidente",
      message: "Dada a palavra à defesa: formule suas razões para a concessão da tutela de urgência antecipada.",
      timestamp: "14:30",
    },
    PARTE_CONTRARIA: {
      sender: "AI",
      name: "Dr. Roberto Guimarães",
      roleTitle: "Advogado Ex-Adverso",
      message: "Excelência, impugno veementemente o pedido autoral! O requerente carece de interesse processual e pretende burlar a ordem cronológica de pagamentos.",
      timestamp: "14:31",
    },
    TESTEMUNHA: {
      sender: "AI",
      name: "Sra. Carla Mendonça",
      roleTitle: "Testemunha Arrolada",
      message: "Confirmou que estava presente na reunião do dia 15/03, mas afirma não ter visto o réu assinar o aditivo contratual.",
      timestamp: "14:32",
    },
    TURMA_RECURSAL: {
      sender: "AI",
      name: "Des. Relator Carlos Eduardo",
      roleTitle: "2ª Turma Cível (TJSP)",
      message: "Com a palavra o emérito patrono do recorrente para sustentação oral pelo prazo regimental de 15 minutos.",
      timestamp: "14:33",
    },
  };

  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([initialPrompts.JUIZ]);

  // Role Switcher Handler
  // Microphone Speech-to-Text Handler
  const handleToggleMicrophone = () => {
    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (!SpeechRecognition) {
      if (isListening) {
        setIsListening(false);
        showToast("Gravação de voz encerrada.");
      } else {
        setIsListening(true);
        showToast("🔴 Gravando Sustentação Oral por Voz... (Fale no microfone)");
        setTimeout(() => {
          setIsListening(false);
          setUserArgument("Excelência, reiteramos a imprescindibilidade da concessão da liminar postulada, em consonância com a jurisprudência pacífica do STJ.");
          showToast("Sustentação por voz convertida em texto com sucesso!");
        }, 3500);
      }
      return;
    }

    if (isListening) {
      if (recognitionRef.current) {
        recognitionRef.current.stop();
      }
      setIsListening(false);
      showToast("Gravação de voz encerrada.");
    } else {
      try {
        const recognition = new SpeechRecognition();
        recognition.lang = "pt-BR";
        recognition.continuous = true;
        recognition.interimResults = true;

        recognition.onstart = () => {
          setIsListening(true);
          showToast("🔴 Microfone Ativado! Fale sua Sustentação Oral...");
        };

        recognition.onresult = (event: any) => {
          let transcript = "";
          for (let i = event.resultIndex; i < event.results.length; i++) {
            transcript += event.results[i][0].transcript;
          }
          if (transcript.trim()) {
            setUserArgument(transcript);
          }
        };

        recognition.onerror = () => {
          setIsListening(false);
          showToast("Erro na captação do áudio. Tente novamente.");
        };

        recognition.onend = () => {
          setIsListening(false);
        };

        recognitionRef.current = recognition;
        recognition.start();
      } catch (e) {
        setIsListening(false);
      }
    }
  };

  const handleRoleChange = (newRole: ForenseRole) => {
    setRole(newRole);
    setChatHistory([initialPrompts[newRole]]);
    showToast(`Modo alterado para: ${initialPrompts[newRole].roleTitle}`);
  };

  const handleSendArgument = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!userArgument.trim()) return;

    if (isListening) {
      handleToggleMicrophone();
    }

    const userMsg: ChatMessage = {
      sender: "LAWYER",
      name: "Dr. Alexandre Rossi",
      roleTitle: "Patrono da Causa",
      message: userArgument,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    setChatHistory((prev) => [...prev, userMsg]);
    setUserArgument("");
    setIsSimulating(true);

    if (!isTimerRunning && timerSeconds === 900) {
      setIsTimerRunning(true);
    }

    setTimeout(() => {
      setIsSimulating(false);

      let aiResponseText = "";
      let aiName = "MM. Juiz de Direito";
      let aiTitle = `Magistrado Presidente (${selectedCourt})`;

      if (role === "JUIZ") {
        aiResponseText = `Analisando a alegação trazida pela defesa perante o ${selectedCourt}: o perigo de mora resta fundamentado. Defiro parcialmente a liminar para determinar a suspensão da exigibilidade no prazo de 48h.`;
      } else if (role === "PARTE_CONTRARIA") {
        aiName = "Dr. Roberto Guimarães";
        aiTitle = "Advogado Ex-Adverso";
        aiResponseText = "Pela ordem, Excelência! O patrono confunde a matéria fática com o direito alegado. Requeiro o indeferimento imediato e a aplicação de multa por litigância de má-fé!";
      } else if (role === "TESTEMUNHA") {
        aiName = "Sra. Carla Mendonça";
        aiTitle = "Testemunha Arrolada";
        aiResponseText = "Respondendo ao Doutor: Sim, o e-mail de notificação foi recebido, porém o serviço não foi prestado conforme as especificações descritas na cláusula 4ª.";
      } else {
        aiName = selectedCourt === "STF" || selectedCourt === "STJ" ? `Min. Relator (${selectedCourt})` : `Des. Relator (${selectedCourt})`;
        aiTitle = `${selectedCourt} — Turma Recursal`;
        aiResponseText = `O Colegiado do ${selectedCourt} ouviu com atenção a sustentação de Vossa Excelência. Passo à leitura do voto, conhecendo do recurso e dando-lhe provimento nos termos da Súmula.`;
      }

      const aiReply: ChatMessage = {
        sender: "AI",
        name: aiName,
        roleTitle: aiTitle,
        message: aiResponseText,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };

      setChatHistory((prev) => [...prev, aiReply]);

      // Dynamic Score Adjustment
      setScores((prev) => ({
        clarity: Math.min(100, prev.clarity + Math.floor(Math.random() * 3)),
        legalBasis: Math.min(100, prev.legalBasis + Math.floor(Math.random() * 2)),
        timeControl: Math.max(80, prev.timeControl - 1),
      }));
    }, 750);
  };

  // Sudden Objection Trigger
  const handleTriggerObjection = () => {
    setIsSimulating(true);
    setTimeout(() => {
      setIsSimulating(false);
      const objectionMsg: ChatMessage = {
        sender: "AI",
        name: "Dr. Roberto Guimarães",
        roleTitle: "Advogado Ex-Adverso",
        message: "⚡ PELA ORDEM, EXCELÊNCIA! O patrono da parte contrária está formulando pergunta indutiva e impertinente! Requeiro o indeferimento com base no Art. 459 do CPC!",
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };
      setChatHistory((prev) => [...prev, objectionMsg]);
      showToast("Objeção surpresa lançada pelo Ex-Adverso!");
    }, 500);
  };

  // Copilot Rebuttal Suggestion
  const handleCopilotSuggest = () => {
    setUserArgument("Excelência, nos termos do Art. 373, II do CPC, cumpre à parte ré comprovar os fatos impeditivos do direito autoral, razão pela qual a objeção ex-adversa resta totalmente descabida.");
    showToast("Sugestão de tréplica preenchida pelo Copilot via IA!");
  };

  // Speech Synthesis (Text-to-Speech)
  const handleSpeakText = (text: string, index: number) => {
    if (!("speechSynthesis" in window)) {
      showToast("Navegador não suporta síntese de voz.");
      return;
    }

    if (speakingIndex === index) {
      window.speechSynthesis.cancel();
      setSpeakingIndex(null);
      return;
    }

    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "pt-BR";
    utterance.rate = 1.0;

    utterance.onend = () => setSpeakingIndex(null);
    utterance.onerror = () => setSpeakingIndex(null);

    setSpeakingIndex(index);
    window.speechSynthesis.speak(utterance);
  };

  // Export Hearing Minutes (Ata de Audiência)
  const handleExportMinutes = () => {
    const transcript = chatHistory
      .map((m) => `[${m.timestamp}] ${m.name} (${m.roleTitle}):\n${m.message}\n`)
      .join("\n--------------------------------------------------\n\n");

    const minutesContent = `====================================================================
LEXFLOW ENTERPRISE - ATA OFICIAL DE AUDIÊNCIA SIMULADA
DATA/HORA: ${new Date().toLocaleString("pt-BR")}
JURISDIÇÃO / TRIBUNAL: ${selectedCourt}
MODO DE SIMULAÇÃO: ${initialPrompts[role].roleTitle}
DESEMPENHO FORENSE DA SUSTENTAÇÃO:
 - Oratória & Clareza: ${scores.clarity}/100
 - Fundamentação Jurídica: ${scores.legalBasis}/100
 - Domínio do Tempo: ${scores.timeControl}/100
====================================================================

REGISTRO COMPLETO DA ATA:

${transcript}
====================================================================
documento gerado eletronicamente por LexFlow Roleplay AI
`;

    const blob = new Blob([minutesContent], { type: "text/plain;charset=utf-8" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `Ata_Audiencia_${selectedCourt}_${new Date().toISOString().slice(0, 10)}.txt`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    showToast("Ata da Audiência Simulado exportada com sucesso!");
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 bg-purple-600 border border-purple-500 text-white px-4 py-3 rounded-xl shadow-xl flex items-center space-x-2 text-xs font-semibold animate-in slide-in-from-bottom-5 duration-200">
          <Sparkles className="w-4 h-4 text-purple-200" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Top Header */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-4 shadow-xl">
        <div>
          <div className="flex items-center space-x-2 text-xs text-purple-400 font-mono uppercase tracking-wider mb-1">
            <Scale className="w-4 h-4 text-purple-400" />
            <span>Módulo 10: Simulador de Audiências & Sustentação Oral via IA</span>
          </div>
          <h1 className="text-2xl font-extrabold text-zinc-100 tracking-tight">
            Roleplay Interativo de Audiências e Inquirição de Testemunhas
          </h1>
          <p className="text-xs text-zinc-400 mt-1 max-w-3xl leading-relaxed">
            Treinamento imersivo de sustentações orais por voz, oposição de objeções, cross-examination e simulação decisória.
          </p>
        </div>

        {/* Action Controls & Tribunal Dropdown */}
        <div className="flex flex-wrap items-center gap-2.5 w-full md:w-auto">
          {/* Tribunal Dropdown Selector + Add Button */}
          <div className="flex items-center space-x-1 bg-zinc-950 border border-zinc-800 rounded-xl p-1 shadow-sm">
            <div className="flex items-center space-x-2 px-2 py-1">
              <Building2 className="w-4 h-4 text-purple-400 shrink-0" />
              <select
                value={selectedCourt}
                onChange={(e) => handleCourtChange(e.target.value)}
                className="bg-transparent text-xs font-bold text-zinc-100 focus:outline-none cursor-pointer"
              >
                {courtOptions.map((c) => (
                  <option key={c.id} value={c.id} className="bg-zinc-900 text-zinc-200">
                    {c.name}
                  </option>
                ))}
              </select>
            </div>
            <button
              onClick={() => setIsAddCourtModalOpen(true)}
              className="p-1.5 bg-purple-950/70 hover:bg-purple-900/90 text-purple-300 hover:text-purple-100 rounded-lg border border-purple-800/50 transition-colors cursor-pointer flex items-center space-x-1 text-xs font-semibold px-2.5"
              title="Adicionar Novo Tribunal"
            >
              <Plus className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Adicionar</span>
            </button>
          </div>

          <button
            onClick={handleExportMinutes}
            className="px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white rounded-xl text-xs font-bold flex items-center space-x-1.5 shadow-md shadow-purple-950 cursor-pointer transition-colors"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Exportar Ata em PDF/TXT</span>
          </button>
        </div>
      </div>

      {/* Mode Selectors & Official Courtroom Timer Bar */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-5 flex flex-col md:flex-row items-center justify-between gap-4 shadow-lg">
        {/* Forense Role Buttons */}
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-bold text-zinc-400 uppercase tracking-wider mr-1 hidden sm:inline">
            Modo:
          </span>
          {[
            { id: "JUIZ", label: "🏛️ Simular Juiz" },
            { id: "PARTE_CONTRARIA", label: "⚔️ Simular Ex-Adverso" },
            { id: "TESTEMUNHA", label: "🗣️ Inquirição Testemunha" },
            { id: "TURMA_RECURSAL", label: "⚖️ Turma Recursal (STJ)" },
          ].map((m) => (
            <button
              key={m.id}
              onClick={() => handleRoleChange(m.id as ForenseRole)}
              className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                role === m.id
                  ? "bg-purple-600 text-white shadow-md shadow-purple-950"
                  : "bg-zinc-950 hover:bg-zinc-800 text-zinc-400 border border-zinc-800"
              }`}
            >
              {m.label}
            </button>
          ))}
        </div>

        {/* Official Courtroom Timer */}
        <div className="flex items-center space-x-3 bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-2">
          <Clock className="w-4 h-4 text-purple-400" />
          <div className="flex flex-col">
            <span className="text-[9px] text-zinc-500 font-mono uppercase font-bold">Tempo de Sustentação</span>
            <span className="text-base font-extrabold font-mono text-zinc-100">{formatTimer(timerSeconds)}</span>
          </div>

          <div className="flex items-center space-x-1 pl-2 border-l border-zinc-800">
            <button
              onClick={() => setIsTimerRunning(!isTimerRunning)}
              className="p-1.5 text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 rounded-lg transition-colors"
              title={isTimerRunning ? "Pausar Cronômetro" : "Iniciar Cronômetro"}
            >
              {isTimerRunning ? <Pause className="w-4 h-4 text-amber-400" /> : <Play className="w-4 h-4 text-emerald-400" />}
            </button>
            <button
              onClick={() => {
                setIsTimerRunning(false);
                setTimerSeconds(900);
              }}
              className="p-1.5 text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 rounded-lg transition-colors"
              title="Zerar Cronômetro (15 min)"
            >
              <RotateCcw className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Main Grid: Simulator Chat & Live Scorecard */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* LEFT: Simulator Chat Box */}
        <div className="lg:col-span-8 bg-zinc-900 border border-zinc-800 rounded-2xl p-6 flex flex-col justify-between min-h-[540px] space-y-4 shadow-lg">
          {/* Chat History */}
          <div className="space-y-4 max-h-[420px] overflow-y-auto pr-2 text-xs">
            {chatHistory.map((msg, idx) => (
              <div
                key={idx}
                className={`flex flex-col ${msg.sender === "LAWYER" ? "items-end" : "items-start"}`}
              >
                <div className="flex items-center space-x-2 mb-1">
                  <span className="font-bold text-zinc-200">{msg.name}</span>
                  <span className="px-1.5 py-0.5 bg-zinc-800 text-purple-300 text-[9px] font-mono rounded">
                    {msg.roleTitle}
                  </span>
                  <span className="text-[10px] text-zinc-500 font-mono">{msg.timestamp}</span>

                  {/* Speech Synthesis Button */}
                  {msg.sender === "AI" && (
                    <button
                      onClick={() => handleSpeakText(msg.message, idx)}
                      className="p-1 text-zinc-400 hover:text-purple-400 transition-colors cursor-pointer ml-1"
                      title="Ouvir fala por voz (Text-to-Speech)"
                    >
                      {speakingIndex === idx ? (
                        <VolumeX className="w-3.5 h-3.5 text-purple-400 animate-pulse" />
                      ) : (
                        <Volume2 className="w-3.5 h-3.5" />
                      )}
                    </button>
                  )}
                </div>

                <div
                  className={`p-4 rounded-2xl max-w-2xl leading-relaxed font-serif text-xs ${
                    msg.sender === "LAWYER"
                      ? "bg-purple-600 text-white font-medium shadow-md shadow-purple-950"
                      : "bg-zinc-950 border border-zinc-800 text-zinc-200"
                  }`}
                >
                  {msg.message}
                </div>
              </div>
            ))}

            {isSimulating && (
              <div className="flex items-center space-x-2 text-purple-400 text-xs font-mono p-2 bg-purple-950/40 rounded-xl border border-purple-900/50">
                <Bot className="w-4 h-4 animate-bounce" />
                <span>IA ponderando alegações e jurisprudência dos Tribunais...</span>
              </div>
            )}
          </div>

          {/* Tactical Buttons & Input Form */}
          <div className="space-y-3 pt-3 border-t border-zinc-800">
            {/* Live Microphone Recording Indicator */}
            {isListening && (
              <div className="flex items-center space-x-2 px-3 py-1.5 bg-rose-950/70 border border-rose-800 text-rose-300 rounded-xl text-xs font-mono animate-pulse">
                <Radio className="w-4 h-4 text-rose-400 animate-spin" />
                <span>🔴 MICROFONE ATIVADO — Fale sua sustentação oral agora (Sua voz está sendo transcrita em tempo real)</span>
              </div>
            )}

            {/* Tactical AI Helpers */}
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <button
                  type="button"
                  onClick={handleTriggerObjection}
                  className="px-2.5 py-1 bg-amber-950 hover:bg-amber-900 text-amber-400 border border-amber-800/80 rounded-lg text-[11px] font-semibold transition-all cursor-pointer flex items-center space-x-1"
                >
                  <Zap className="w-3 h-3" />
                  <span>Objeção Surpresa</span>
                </button>

                <button
                  type="button"
                  onClick={handleCopilotSuggest}
                  className="px-2.5 py-1 bg-purple-950 hover:bg-purple-900 text-purple-400 border border-purple-800/80 rounded-lg text-[11px] font-semibold transition-all cursor-pointer flex items-center space-x-1"
                >
                  <Sparkles className="w-3 h-3" />
                  <span>Sugerir Tréplica via IA</span>
                </button>
              </div>

              <span className="text-[10px] text-zinc-500 font-mono hidden sm:inline">
                Fale pelo microfone 🎙️ ou digite sua sustentação
              </span>
            </div>

            <form onSubmit={handleSendArgument} className="flex space-x-2">
              <div className="relative flex-1">
                <input
                  type="text"
                  placeholder={
                    isListening
                      ? "Escutando sua voz... fale sua sustentação oral..."
                      : "Formule sua sustentação oral por voz ou digite aqui..."
                  }
                  value={userArgument}
                  onChange={(e) => setUserArgument(e.target.value)}
                  className={`w-full bg-zinc-950 border rounded-xl pl-4 pr-10 py-2.5 text-zinc-100 text-xs focus:outline-none transition-all ${
                    isListening
                      ? "border-rose-500 ring-1 ring-rose-500 text-rose-200"
                      : "border-zinc-800 focus:border-purple-500"
                  }`}
                />

                {/* Microphone Toggle Button Inside Input */}
                <button
                  type="button"
                  onClick={handleToggleMicrophone}
                  className={`absolute right-2 top-2 p-1.5 rounded-lg transition-colors cursor-pointer ${
                    isListening
                      ? "bg-rose-600 text-white animate-pulse"
                      : "text-zinc-400 hover:text-purple-400 hover:bg-zinc-800"
                  }`}
                  title={isListening ? "Desativar Microfone" : "Falar Sustentação Oral por Voz (Microfone STT)"}
                >
                  {isListening ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
                </button>
              </div>

              <button
                type="submit"
                disabled={isSimulating || !userArgument.trim()}
                className="px-5 py-2.5 bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white font-bold rounded-xl text-xs flex items-center space-x-2 shadow-md shadow-purple-950 cursor-pointer transition-colors"
              >
                <Send className="w-4 h-4" />
                <span>Sustentar</span>
              </button>
            </form>
          </div>
        </div>

        {/* RIGHT: Live Oratory Scorecard & Performance Audit */}
        <div className="lg:col-span-4 space-y-4">
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-5 space-y-4 shadow-lg">
            <h3 className="text-xs font-bold text-zinc-100 uppercase tracking-wider flex items-center space-x-2 border-b border-zinc-800 pb-3">
              <Award className="w-4 h-4 text-purple-400" />
              <span>Scorecard de Oratória Forense</span>
            </h3>

            <div className="space-y-4 text-xs">
              <div>
                <div className="flex justify-between font-semibold mb-1">
                  <span className="text-zinc-300">Clareza & Oratória</span>
                  <span className="text-purple-400 font-mono font-bold">{scores.clarity}/100</span>
                </div>
                <div className="w-full bg-zinc-950 rounded-full h-2 border border-zinc-800">
                  <div className="bg-purple-500 h-full rounded-full transition-all" style={{ width: `${scores.clarity}%` }} />
                </div>
              </div>

              <div>
                <div className="flex justify-between font-semibold mb-1">
                  <span className="text-zinc-300">Fundamentação Jurídica</span>
                  <span className="text-emerald-400 font-mono font-bold">{scores.legalBasis}/100</span>
                </div>
                <div className="w-full bg-zinc-950 rounded-full h-2 border border-zinc-800">
                  <div className="bg-emerald-500 h-full rounded-full transition-all" style={{ width: `${scores.legalBasis}%` }} />
                </div>
              </div>

              <div>
                <div className="flex justify-between font-semibold mb-1">
                  <span className="text-zinc-300">Gestão do Tempo</span>
                  <span className="text-blue-400 font-mono font-bold">{scores.timeControl}/100</span>
                </div>
                <div className="w-full bg-zinc-950 rounded-full h-2 border border-zinc-800">
                  <div className="bg-blue-500 h-full rounded-full transition-all" style={{ width: `${scores.timeControl}%` }} />
                </div>
              </div>
            </div>
          </div>

          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-5 space-y-3 shadow-lg">
            <h4 className="text-xs font-bold text-zinc-200 uppercase tracking-wider flex items-center space-x-2">
              <FileCheck className="w-4 h-4 text-emerald-400" />
              <span>Dicas de Atuação Judicial</span>
            </h4>
            <ul className="text-xs text-zinc-400 space-y-2 leading-relaxed font-serif">
              <li className="flex items-start space-x-2">
                <span className="text-purple-400 font-bold">•</span>
                <span>Mantenha tom sereno e refira-se ao Magistrado com o vocativo oficial "Excelência".</span>
              </li>
              <li className="flex items-start space-x-2">
                <span className="text-purple-400 font-bold">•</span>
                <span>Cite expressamente Súmulas do STJ/STF ao impugnar preliminares do ex-adverso.</span>
              </li>
            </ul>
          </div>
        </div>
      </div>

      {/* Modal Adicionar Tribunal */}
      {isAddCourtModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in duration-200">
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl w-full max-w-md p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <div className="flex items-center space-x-2 text-purple-400 font-bold text-sm">
                <Building2 className="w-5 h-5" />
                <span>Adicionar Novo Tribunal</span>
              </div>
              <button
                onClick={() => setIsAddCourtModalOpen(false)}
                className="text-zinc-400 hover:text-zinc-200 p-1 rounded-lg hover:bg-zinc-800 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleAddCourt} className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-zinc-300 uppercase tracking-wider mb-1.5">
                  Sigla do Tribunal *
                </label>
                <input
                  type="text"
                  required
                  placeholder="Ex: TJPR, TRT2, TRF1, TRE-SP"
                  value={newCourtSigla}
                  onChange={(e) => setNewCourtSigla(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-3.5 py-2.5 text-xs text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-purple-500"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-zinc-300 uppercase tracking-wider mb-1.5">
                  Nome do Tribunal
                </label>
                <input
                  type="text"
                  placeholder="Ex: Tribunal de Justiça do Paraná"
                  value={newCourtNome}
                  onChange={(e) => setNewCourtNome(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-3.5 py-2.5 text-xs text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-purple-500"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-zinc-300 uppercase tracking-wider mb-1.5">
                  Vara ou Ramo / Especialidade
                </label>
                <input
                  type="text"
                  placeholder="Ex: Cível/Empresarial, Trabalhista, Fazenda Pública"
                  value={newCourtRamo}
                  onChange={(e) => setNewCourtRamo(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-3.5 py-2.5 text-xs text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-purple-500"
                />
              </div>

              <div className="flex items-center justify-end space-x-2 pt-2 border-t border-zinc-800">
                <button
                  type="button"
                  onClick={() => setIsAddCourtModalOpen(false)}
                  className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-xl text-xs font-semibold transition-colors cursor-pointer"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white rounded-xl text-xs font-bold flex items-center space-x-1.5 shadow-md transition-colors cursor-pointer"
                >
                  <Plus className="w-4 h-4" />
                  <span>Salvar Tribunal</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

