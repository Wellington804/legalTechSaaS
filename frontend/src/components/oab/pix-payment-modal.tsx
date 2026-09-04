"use client";

import React, { useState, useEffect } from "react";
import { X, QrCode, FileText, Copy, Check, ShieldCheck, Download, Clock, ArrowRight, Sparkles } from "lucide-react";
import { OAB_SECCIONAIS, useOabStore } from "@/store/useOabStore";
import { formatCurrency } from "@/lib/utils";

interface PixPaymentModalProps {
  isOpen: boolean;
  onClose: () => void;
  totalCalculated: number;
  taxaRequerimento: number;
  taxaCartao: number;
  anuidadeProporcional: number;
  descontoJovem: number;
  descontoSua: number;
  mesesRestantes: number;
}

export function PixPaymentModal({
  isOpen,
  onClose,
  totalCalculated,
  taxaRequerimento,
  taxaCartao,
  anuidadeProporcional,
  descontoJovem,
  descontoSua,
  mesesRestantes,
}: PixPaymentModalProps) {
  const { feeState } = useOabStore();
  const [activeTab, setActiveTab] = useState<"pix" | "boleto">("pix");
  const [copiedPix, setCopiedPix] = useState(false);
  const [copiedBoleto, setCopiedBoleto] = useState(false);
  const [isPaymentConfirmed, setIsPaymentConfirmed] = useState(false);
  const [timeLeft, setTimeLeft] = useState(900); // 15 minutos em segundos
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const seccionalData = OAB_SECCIONAIS.find((s) => s.code === feeState.seccional) || OAB_SECCIONAIS[24]; // SP default

  // Chave Pix Payload Simula formato Banco Central EMV
  const pixPayload = `00020126580014BR.GOV.BCB.PIX0136123e4567-e89b-12d3-a456-426614174000520400005303986540${totalCalculated.toFixed(
    2
  )}5802BR5925ORDE DOS ADVOGADOS DO BRASIL6009BRASILIA62070503***6304C8A1`;

  // Linha Digitável do Boleto
  const linhaDigitavel = "03399.65432 12345.678901 23456.789012 3 98760000" + Math.round(totalCalculated * 100).toString().padStart(6, "0");

  useEffect(() => {
    if (!isOpen) {
      setIsPaymentConfirmed(false);
      setTimeLeft(900);
      return;
    }

    const timer = setInterval(() => {
      setTimeLeft((prev) => (prev > 0 ? prev - 1 : 0));
    }, 1000);

    return () => clearInterval(timer);
  }, [isOpen]);

  if (!isOpen) return null;

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3000);
  };

  const copyToClipboard = (text: string, type: "pix" | "boleto") => {
    navigator.clipboard.writeText(text);
    if (type === "pix") {
      setCopiedPix(true);
      showToast("Chave Pix Copia e Cola copiada com sucesso!");
      setTimeout(() => setCopiedPix(false), 2500);
    } else {
      setCopiedBoleto(true);
      showToast("Linha digitável do Boleto copiada com sucesso!");
      setTimeout(() => setCopiedBoleto(false), 2500);
    }
  };

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  };

  const handleSimulatePayment = () => {
    setIsPaymentConfirmed(true);
    showToast("Pagamento reconhecido via Pix! Inscrição liberada.");
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-in fade-in duration-200">
      {/* Toast Floating Alert */}
      {toastMessage && (
        <div className="fixed top-6 right-6 z-50 bg-emerald-500 text-zinc-950 font-bold px-4 py-3 rounded-xl shadow-2xl flex items-center space-x-2 text-xs animate-in slide-in-from-top duration-300">
          <Check className="w-4 h-4 stroke-[3]" />
          <span>{toastMessage}</span>
        </div>
      )}

      <div 
        className="bg-zinc-900 border border-zinc-800 rounded-2xl max-w-xl w-full max-h-[90vh] flex flex-col shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="p-5 border-b border-zinc-800 flex items-center justify-between bg-zinc-900/90 backdrop-blur">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
              <QrCode className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-zinc-100 flex items-center gap-2">
                Guia de Pagamento - {seccionalData.code}
              </h2>
              <p className="text-xs text-zinc-400">
                Ordem dos Advogados do Brasil - Seccional {seccionalData.name}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 rounded-xl transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {isPaymentConfirmed ? (
          /* Recibo / Status de Sucesso */
          <div className="p-8 text-center space-y-5 my-auto">
            <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full border border-emerald-500/40 bg-emerald-500/20 text-emerald-400">
              <Check className="w-8 h-8 stroke-[3]" />
            </div>
            <div>
              <span className="text-xs font-semibold uppercase tracking-widest text-emerald-400 bg-emerald-950/60 px-3 py-1 rounded-full border border-emerald-800/50">
                Pagamento Confirmado
              </span>
              <h3 className="text-xl font-bold text-zinc-100 mt-3">Taxas de Inscrição Liquidadas</h3>
              <p className="text-xs text-zinc-400 mt-1 max-w-sm mx-auto">
                O pagamento de <strong>{formatCurrency(totalCalculated)}</strong> para a <strong>{seccionalData.code}</strong> foi identificado e registrado com sucesso.
              </p>
            </div>

            <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-4 text-xs space-y-2 text-left max-w-sm mx-auto font-mono">
              <div className="flex justify-between text-zinc-400">
                <span>Comprovante:</span>
                <span className="text-zinc-200">#PAY-OAB-{Math.floor(100000 + Math.random() * 900000)}</span>
              </div>
              <div className="flex justify-between text-zinc-400">
                <span>Data/Hora:</span>
                <span className="text-zinc-200">{new Date().toLocaleString("pt-BR")}</span>
              </div>
              <div className="flex justify-between text-zinc-400">
                <span>Seccional:</span>
                <span className="text-zinc-200">{seccionalData.code} ({seccionalData.name})</span>
              </div>
            </div>

            <button
              onClick={onClose}
              className="px-6 py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-semibold shadow-lg shadow-blue-950 transition-all"
            >
              Concluir e Voltar
            </button>
          </div>
        ) : (
          /* Fluxo normal de Pagamento */
          <div className="p-6 overflow-y-auto space-y-5">
            {/* Tabs */}
            <div className="flex bg-zinc-950 p-1 rounded-xl border border-zinc-800">
              <button
                onClick={() => setActiveTab("pix")}
                className={`flex-1 py-2 rounded-lg text-xs font-semibold transition-all flex items-center justify-center space-x-2 ${
                  activeTab === "pix"
                    ? "bg-blue-600 text-white shadow-md"
                    : "text-zinc-400 hover:text-zinc-200"
                }`}
              >
                <QrCode className="w-4 h-4" />
                <span>Pix Instantâneo (QR Code)</span>
              </button>
              <button
                onClick={() => setActiveTab("boleto")}
                className={`flex-1 py-2 rounded-lg text-xs font-semibold transition-all flex items-center justify-center space-x-2 ${
                  activeTab === "boleto"
                    ? "bg-blue-600 text-white shadow-md"
                    : "text-zinc-400 hover:text-zinc-200"
                }`}
              >
                <FileText className="w-4 h-4" />
                <span>Boleto Bancário (Guia)</span>
              </button>
            </div>

            {/* Pix Content */}
            {activeTab === "pix" && (
              <div className="space-y-4 text-center">
                {/* Timer Header */}
                <div className="flex items-center justify-center space-x-2 text-xs text-amber-400 bg-amber-950/40 border border-amber-900/50 py-1.5 px-3 rounded-lg w-fit mx-auto">
                  <Clock className="w-3.5 h-3.5" />
                  <span>QR Code expira em: <strong>{formatTime(timeLeft)}</strong></span>
                </div>

                {/* Simulated QR Code Visual */}
                <div className="bg-white p-4 rounded-2xl w-44 h-44 mx-auto flex flex-col items-center justify-center shadow-lg border-4 border-blue-600/30 relative group">
                  <div className="grid grid-cols-6 gap-1 w-full h-full p-1 bg-zinc-900 rounded-lg">
                    {Array.from({ length: 36 }).map((_, i) => (
                      <div
                        key={i}
                        className={`rounded-xs ${
                          (i * 7 + 3) % 5 === 0 || (i * 3 + 2) % 4 === 0
                            ? "bg-emerald-400"
                            : (i * 2 + 1) % 3 === 0
                            ? "bg-blue-500"
                            : "bg-zinc-100"
                        }`}
                      />
                    ))}
                  </div>
                  <div className="absolute inset-0 flex items-center justify-center">
                    <span className="px-2 py-1 bg-blue-600 text-white text-[10px] font-black rounded border border-white shadow">
                      PIX OAB
                    </span>
                  </div>
                </div>

                <p className="text-xs text-zinc-400">
                  Abra o app do seu banco, escolha <strong>Pix &gt; Ler QR Code</strong> ou use a chave abaixo:
                </p>

                {/* Copia e Cola Box */}
                <div className="space-y-2">
                  <label className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider block text-left">
                    Chave Pix Copia e Cola
                  </label>
                  <div className="flex items-center space-x-2">
                    <input
                      type="text"
                      readOnly
                      value={pixPayload}
                      className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-3 py-2 text-xs font-mono text-zinc-400 truncate focus:outline-none"
                    />
                    <button
                      onClick={() => copyToClipboard(pixPayload, "pix")}
                      className={`px-4 py-2 rounded-xl text-xs font-semibold transition-all flex items-center space-x-1.5 whitespace-nowrap ${
                        copiedPix
                          ? "bg-emerald-600 text-white"
                          : "bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-950"
                      }`}
                    >
                      {copiedPix ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                      <span>{copiedPix ? "Copiado!" : "Copiar Chave"}</span>
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* Boleto Content */}
            {activeTab === "boleto" && (
              <div className="space-y-4">
                <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-4 space-y-3">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-zinc-400">Banco Emissor:</span>
                    <span className="font-semibold text-zinc-200">033 - Banco Santander / OAB</span>
                  </div>
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-zinc-400">Vencimento:</span>
                    <span className="font-semibold text-emerald-400">Hoje + 3 dias úteis</span>
                  </div>

                  {/* Simulated Barcode */}
                  <div className="py-2 px-3 bg-zinc-900 rounded-lg flex items-center justify-between">
                    <div className="flex space-x-1 h-8 items-center w-full justify-around opacity-80">
                      {Array.from({ length: 32 }).map((_, i) => (
                        <div
                          key={i}
                          className={`h-full ${i % 3 === 0 ? "w-1 bg-zinc-200" : i % 2 === 0 ? "w-0.5 bg-zinc-400" : "w-1.5 bg-zinc-100"}`}
                        />
                      ))}
                    </div>
                  </div>

                  <div>
                    <label className="text-[11px] font-semibold text-zinc-400 block mb-1">Linha Digitável:</label>
                    <div className="flex items-center space-x-2">
                      <input
                        type="text"
                        readOnly
                        value={linhaDigitavel}
                        className="w-full bg-zinc-900 border border-zinc-800 rounded-xl px-3 py-2 text-xs font-mono text-zinc-300 focus:outline-none"
                      />
                      <button
                        onClick={() => copyToClipboard(linhaDigitavel, "boleto")}
                        className={`px-3 py-2 rounded-xl text-xs font-semibold transition-all flex items-center space-x-1 whitespace-nowrap ${
                          copiedBoleto
                            ? "bg-emerald-600 text-white"
                            : "bg-zinc-800 hover:bg-zinc-700 text-zinc-200"
                        }`}
                      >
                        {copiedBoleto ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                        <span>{copiedBoleto ? "Copiado" : "Copiar"}</span>
                      </button>
                    </div>
                  </div>
                </div>

                <button
                  onClick={() => showToast("Download da Guia PDF iniciado...")}
                  className="w-full py-2.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 rounded-xl text-xs font-semibold transition-colors flex items-center justify-center space-x-2"
                >
                  <Download className="w-4 h-4" />
                  <span>Baixar Guia PDF da OAB ({seccionalData.code})</span>
                </button>
              </div>
            )}

            {/* Financial Summary Breakdown */}
            <div className="bg-zinc-950/80 border border-zinc-800 rounded-xl p-4 space-y-2 text-xs">
              <span className="text-[10px] font-mono text-blue-400 uppercase tracking-widest block mb-1">
                Discriminativo de Taxas - {seccionalData.code}
              </span>
              <div className="flex justify-between text-zinc-400">
                <span>Taxa de Requerimento:</span>
                <span className="font-mono text-zinc-200">{formatCurrency(taxaRequerimento)}</span>
              </div>
              <div className="flex justify-between text-zinc-400">
                <span>Carteira Vermelha & Chip:</span>
                <span className="font-mono text-zinc-200">{formatCurrency(taxaCartao)}</span>
              </div>
              <div className="flex justify-between text-zinc-400">
                <span>Anuidade Proporcional ({mesesRestantes} meses):</span>
                <span className="font-mono text-zinc-200">{formatCurrency(anuidadeProporcional)}</span>
              </div>
              {descontoJovem > 0 && (
                <div className="flex justify-between text-emerald-400">
                  <span>Desconto Jovem Advogado (50%):</span>
                  <span className="font-mono">-{formatCurrency(descontoJovem)}</span>
                </div>
              )}
              {descontoSua > 0 && (
                <div className="flex justify-between text-emerald-400">
                  <span>Desconto Sociedade Unipessoal (25%):</span>
                  <span className="font-mono">-{formatCurrency(descontoSua)}</span>
                </div>
              )}

              <div className="pt-2 border-t border-zinc-800 flex justify-between items-baseline font-bold">
                <span className="text-zinc-200">Total da Guia:</span>
                <span className="text-lg font-mono text-blue-400">{formatCurrency(totalCalculated)}</span>
              </div>
            </div>

            {/* Action simulation */}
            <div className="pt-2">
              <button
                onClick={handleSimulatePayment}
                className="w-full py-3 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-bold shadow-lg shadow-emerald-950 transition-all flex items-center justify-center space-x-2 group"
              >
                <ShieldCheck className="w-4 h-4" />
                <span>Simular Pagamento Confirmado no Pix</span>
                <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
