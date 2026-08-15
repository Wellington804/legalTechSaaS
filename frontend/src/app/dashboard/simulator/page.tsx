"use client";

import React, { useState } from "react";
import {
  Bot,
  Sparkles,
  Send,
  Scale,
  ShieldAlert,
  CheckCircle2,
  BookOpen,
  RotateCcw,
  Volume2
} from "lucide-react";

export default function CourtroomSimulatorPage() {
  const [role, setRole] = useState<"JUIZ" | "PROMOTOR" | "PARTE_CONTRARIA">("JUIZ");
  const [userArgument, setUserArgument] = useState("");
  const [isSimulating, setIsSimulating] = useState(false);

  const [chatHistory, setChatHistory] = useState([
    {
      sender: "AI_MAGISTRADO",
      name: "MM. Juiz de Direito (Simulador IA)",
      message: "Dada a palavra à defesa: formule suas razões para a concessão da tutela de urgência antecipada.",
      timestamp: "14:30"
    }
  ]);

  const handleSendArgument = (e: React.FormEvent) => {
    e.preventDefault();
    if (!userArgument.trim()) return;

    const userMsg = {
      sender: "LAWYER",
      name: "Dr. Alexandre Rossi",
      message: userArgument,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    setChatHistory((prev) => [...prev, userMsg]);
    setUserArgument("");
    setIsSimulating(true);

    setTimeout(() => {
      setIsSimulating(false);
      const aiReply = {
        sender: "AI_MAGISTRADO",
        name: "MM. Juiz de Direito (Simulador IA)",
        message: "Analisando a alegação trazida pela defesa: o perigo de mora resta fundamentado. Defiro parcialmente a liminar para determinar a suspensão da exigibilidade do crédito no prazo de 48h sob pena de multa diária.",
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };
      setChatHistory((prev) => [...prev, aiReply]);
    }, 800);
  };

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <div className="flex items-center space-x-2 text-xs text-purple-400 font-mono uppercase tracking-wider mb-1">
            <Scale className="w-4 h-4 text-purple-400" />
            <span>Módulo 10: Simulador de Audiências & Sustentação Oral via IA</span>
          </div>
          <h1 className="text-2xl font-extrabold text-zinc-100 tracking-tight">
            Roleplay Interativo de Audiências e Inquirição de Testemunhas
          </h1>
          <p className="text-xs text-zinc-400 mt-1 max-w-3xl leading-relaxed">
            Treinamento imersivo de sustentações orais, oposição de objeções e simulação de postura decisória do magistrado.
          </p>
        </div>

        <div className="flex space-x-1 p-1 bg-zinc-950 border border-zinc-800 rounded-xl">
          <button
            onClick={() => setRole("JUIZ")}
            className={`px-3 py-1.5 text-xs font-semibold rounded-lg ${role === "JUIZ" ? "bg-purple-600 text-white" : "text-zinc-400"}`}
          >
            Simular Juiz
          </button>
          <button
            onClick={() => setRole("PARTE_CONTRARIA")}
            className={`px-3 py-1.5 text-xs font-semibold rounded-lg ${role === "PARTE_CONTRARIA" ? "bg-purple-600 text-white" : "text-zinc-400"}`}
          >
            Simular Ex-Adverso
          </button>
        </div>
      </div>

      {/* Simulator Chat Container */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 flex flex-col justify-between min-h-[500px] space-y-4">
        {/* Chat History */}
        <div className="space-y-4 max-h-[400px] overflow-y-auto pr-2 text-xs">
          {chatHistory.map((msg, idx) => (
            <div
              key={idx}
              className={`flex flex-col ${msg.sender === "LAWYER" ? "items-end" : "items-start"}`}
            >
              <div className="flex items-center space-x-2 mb-1">
                <span className="font-bold text-zinc-300">{msg.name}</span>
                <span className="text-[10px] text-zinc-500 font-mono">{msg.timestamp}</span>
              </div>
              <div
                className={`p-3.5 rounded-xl max-w-2xl leading-relaxed ${
                  msg.sender === "LAWYER"
                    ? "bg-blue-600 text-white font-medium"
                    : "bg-zinc-950 border border-zinc-800 text-zinc-200"
                }`}
              >
                {msg.message}
              </div>
            </div>
          ))}

          {isSimulating && (
            <div className="flex items-center space-x-2 text-purple-400 text-xs font-mono">
              <Bot className="w-4 h-4 animate-bounce" />
              <span>Magistrado avaliando argumentação e precedentes STJ...</span>
            </div>
          )}
        </div>

        {/* Input Form */}
        <form onSubmit={handleSendArgument} className="flex space-x-2 pt-2 border-t border-zinc-800">
          <input
            type="text"
            placeholder="Formule sua sustentação oral ou resposta à objeção..."
            value={userArgument}
            onChange={(e) => setUserArgument(e.target.value)}
            className="flex-1 bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-2.5 text-zinc-200 text-xs focus:outline-none focus:border-purple-500"
          />
          <button
            type="submit"
            disabled={isSimulating || !userArgument.trim()}
            className="px-5 py-2.5 bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white font-semibold rounded-xl text-xs flex items-center space-x-2 shadow-md transition-colors"
          >
            <Send className="w-4 h-4" />
            <span>Sustentar</span>
          </button>
        </form>
      </div>
    </div>
  );
}
