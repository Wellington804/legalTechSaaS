"use client";

import React, { useState } from "react";
import {
  DollarSign,
  QrCode,
  Copy,
  Check,
  Clock,
  Plus,
  CreditCard,
  Barcode,
  Users,
  ShieldCheck,
  FileCheck,
  Download,
  Send,
  Sparkles,
  ArrowUpRight,
  TrendingUp,
  AlertCircle,
  FileText,
  Percent,
} from "lucide-react";

export interface BillingRecord {
  id: string;
  client: string;
  amount: number;
  description: string;
  method: "PIX" | "CREDIT_CARD" | "BOLETO" | "SPLIT";
  status: "PAID" | "PENDING" | "OVERDUE";
  dueDate: string;
  createdAt: string;
}

export default function FinancialPage() {
  const [selectedMethod, setSelectedMethod] = useState<"PIX" | "CREDIT_CARD" | "BOLETO" | "SPLIT">("PIX");
  const [clientName, setClientName] = useState("Empresa Alimenta Distribuidora Ltda.");
  const [amount, setAmount] = useState("4500.00");
  const [description, setDescription] = useState("Honorários Pro Labore - Ação Tributária Federal");
  const [installments, setInstallments] = useState("1");
  const [splitPartner, setSplitPartner] = useState("Dr. Marcos Oliveira (Advogado Parceiro)");
  const [splitPercentage, setSplitPercentage] = useState("30");

  const [copiedField, setCopiedField] = useState<string | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500);
  };

  const copyToClipboard = (text: string, fieldName: string) => {
    navigator.clipboard.writeText(text);
    setCopiedField(fieldName);
    showToast(`${fieldName} copiado com sucesso!`);
    setTimeout(() => setCopiedField(null), 2000);
  };

  // Mock Payloads
  const pixPayload = `00020126580014BR.GOV.BCB.PIX0136contato@rossiadvocacia.com.br52040000530398654${parseFloat(amount || "0").toFixed(2)}5802BR5925ROSSI E ASSOCIADOS ADV6009SAO PAULO62070503***6304E2CA`;
  const creditCardCheckoutUrl = `https://pay.legalflow.app/chk-${Math.floor(100000 + Math.random() * 900000)}`;
  const boletoLine = "34191.09008 61234.567890 12345.678901 8 98760000450000";

  // Initial Billing Records
  const [billings, setBillings] = useState<BillingRecord[]>([
    {
      id: "FIN-901",
      client: "Empresa Alimenta Distribuidora Ltda.",
      amount: 4500.0,
      description: "Honorários Pro Labore - Ação Tributária",
      method: "PIX",
      status: "PENDING",
      dueDate: "28/08/2026",
      createdAt: "22/08/2026",
    },
    {
      id: "FIN-902",
      client: "Marcos Paulo Silva",
      amount: 2800.0,
      description: "Contrato de Honorários Quota Litis",
      method: "CREDIT_CARD",
      status: "PAID",
      dueDate: "20/08/2026",
      createdAt: "12/08/2026",
    },
    {
      id: "FIN-903",
      client: "TechCorp Indústria de Softwares S/A",
      amount: 12500.0,
      description: "Assessoria M&A Dissolução Societária",
      method: "SPLIT",
      status: "PAID",
      dueDate: "15/08/2026",
      createdAt: "10/08/2026",
    },
    {
      id: "FIN-904",
      client: "Indústrias Matarazzo S/A",
      amount: 6200.0,
      description: "Boleto Recorrente Consultoria Fiscal",
      method: "BOLETO",
      status: "OVERDUE",
      dueDate: "18/08/2026",
      createdAt: "05/08/2026",
    },
  ]);

  const handleGenerateBilling = (e: React.FormEvent) => {
    e.preventDefault();
    if (!amount || parseFloat(amount) <= 0) {
      showToast("Informe um valor válido para gerar a cobrança.");
      return;
    }

    const newRec: BillingRecord = {
      id: `FIN-${Math.floor(905 + Math.random() * 100)}`,
      client: clientName || "Cliente Geral",
      amount: parseFloat(amount),
      description: description || "Honorários Advocatícios",
      method: selectedMethod,
      status: "PENDING",
      dueDate: new Date(Date.now() + 7 * 86400000).toLocaleDateString("pt-BR"),
      createdAt: new Date().toLocaleDateString("pt-BR"),
    };

    setBillings([newRec, ...billings]);
    showToast(`Cobrança de R$ ${parseFloat(amount).toFixed(2)} gerada via ${selectedMethod}!`);
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12 font-sans">
      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 bg-emerald-600 border border-emerald-500 text-white px-4 py-3 rounded-xl shadow-2xl flex items-center space-x-2 text-xs font-semibold animate-in slide-in-from-bottom-5 duration-200">
          <Sparkles className="w-4 h-4 text-emerald-200" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Header */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-4 shadow-xl">
        <div className="space-y-1">
          <div className="flex items-center space-x-2 text-xs text-emerald-400 font-mono uppercase tracking-wider">
            <DollarSign className="w-4 h-4 text-emerald-400" />
            <span>Módulo 7: Gestão Financeira Multimeios & Faturamento Legal</span>
          </div>
          <h1 className="text-2xl font-extrabold text-zinc-100 tracking-tight">
            Gestão de Honorários & Formas de Pagamento SaaS
          </h1>
          <p className="text-xs text-zinc-400 max-w-3xl leading-relaxed">
            Emissão instantânea de cobranças multimeios: Pix com QR Code, Cartão de Crédito até 12x, Boleto Bancário Registrado e Split Automático de Honorários.
          </p>
        </div>

        <div className="flex items-center space-x-2 font-mono text-xs text-emerald-400 bg-emerald-950/60 border border-emerald-800 px-3 py-2 rounded-xl">
          <ShieldCheck className="w-4 h-4 text-emerald-400" />
          <span>Gateways Integrados: Asaas / Mercado Pago / BACEN</span>
        </div>
      </div>

      {/* KPI Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 space-y-2 shadow-md">
          <div className="flex items-center justify-between text-zinc-400 text-xs font-medium">
            <span>Faturado no Mês</span>
            <TrendingUp className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="flex items-baseline space-x-2">
            <span className="text-2xl font-extrabold font-mono text-emerald-400">R$ 26.000,00</span>
          </div>
          <p className="text-[10px] text-zinc-500 font-mono">+18.4% em relação ao mês anterior</p>
        </div>

        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 space-y-2 shadow-md">
          <div className="flex items-center justify-between text-zinc-400 text-xs font-medium">
            <span>A Receber (Pendentes)</span>
            <Clock className="w-4 h-4 text-amber-400" />
          </div>
          <div className="flex items-baseline space-x-2">
            <span className="text-2xl font-extrabold font-mono text-amber-400">R$ 10.700,00</span>
          </div>
          <p className="text-[10px] text-zinc-500 font-mono">2 cobranças pendentes</p>
        </div>

        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 space-y-2 shadow-md">
          <div className="flex items-center justify-between text-zinc-400 text-xs font-medium">
            <span>Inadimplência (&gt; 15 dias)</span>
            <AlertCircle className="w-4 h-4 text-rose-400" />
          </div>
          <div className="flex items-baseline space-x-2">
            <span className="text-2xl font-extrabold font-mono text-rose-400">R$ 6.200,00</span>
          </div>
          <p className="text-[10px] text-zinc-500 font-mono">1 boleto em atraso (Matarazzo)</p>
        </div>

        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 space-y-2 shadow-md">
          <div className="flex items-center justify-between text-zinc-400 text-xs font-medium">
            <span>Split de Honorários Ativo</span>
            <Users className="w-4 h-4 text-purple-400" />
          </div>
          <div className="flex items-baseline space-x-2">
            <span className="text-2xl font-extrabold font-mono text-purple-400">30% Parceiros</span>
          </div>
          <p className="text-[10px] text-zinc-500 font-mono">Repasse automático pós-recebimento</p>
        </div>
      </div>

      {/* PAYMENT GENERATOR MAIN CARD */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* LEFT FORM */}
        <div className="lg:col-span-5 bg-zinc-900 border border-zinc-800 rounded-2xl p-6 space-y-5 shadow-xl text-xs">
          <div className="space-y-1 border-b border-zinc-800 pb-3">
            <h3 className="text-xs font-bold text-zinc-100 uppercase tracking-wider flex items-center space-x-2">
              <DollarSign className="w-4 h-4 text-emerald-400" />
              <span>Gerador de Cobrança Multimeios</span>
            </h3>
            <p className="text-[11px] text-zinc-400">Selecione o meio de pagamento preferido pelo cliente:</p>
          </div>

          {/* Payment Method Selector Grid */}
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => setSelectedMethod("PIX")}
              className={`p-3 rounded-xl border text-left transition-all cursor-pointer ${
                selectedMethod === "PIX" ? "bg-emerald-950/80 border-emerald-500 text-white" : "bg-zinc-950 border-zinc-800 text-zinc-400 hover:text-zinc-200"
              }`}
            >
              <div className="flex items-center space-x-1.5 font-bold text-xs text-emerald-400 mb-0.5">
                <QrCode className="w-4 h-4" />
                <span>Pix Instantâneo</span>
              </div>
              <p className="text-[10px] text-zinc-400">Payload QR Code Copia & Cola</p>
            </button>

            <button
              type="button"
              onClick={() => setSelectedMethod("CREDIT_CARD")}
              className={`p-3 rounded-xl border text-left transition-all cursor-pointer ${
                selectedMethod === "CREDIT_CARD" ? "bg-blue-950/80 border-blue-500 text-white" : "bg-zinc-950 border-zinc-800 text-zinc-400 hover:text-zinc-200"
              }`}
            >
              <div className="flex items-center space-x-1.5 font-bold text-xs text-blue-400 mb-0.5">
                <CreditCard className="w-4 h-4" />
                <span>Cartão até 12x</span>
              </div>
              <p className="text-[10px] text-zinc-400">Link de Checkout Seguro</p>
            </button>

            <button
              type="button"
              onClick={() => setSelectedMethod("BOLETO")}
              className={`p-3 rounded-xl border text-left transition-all cursor-pointer ${
                selectedMethod === "BOLETO" ? "bg-amber-950/80 border-amber-500 text-white" : "bg-zinc-950 border-zinc-800 text-zinc-400 hover:text-zinc-200"
              }`}
            >
              <div className="flex items-center space-x-1.5 font-bold text-xs text-amber-400 mb-0.5">
                <Barcode className="w-4 h-4" />
                <span>Boleto Registrado</span>
              </div>
              <p className="text-[10px] text-zinc-400">Código de Barras + PDF</p>
            </button>

            <button
              type="button"
              onClick={() => setSelectedMethod("SPLIT")}
              className={`p-3 rounded-xl border text-left transition-all cursor-pointer ${
                selectedMethod === "SPLIT" ? "bg-purple-950/80 border-purple-500 text-white" : "bg-zinc-950 border-zinc-800 text-zinc-400 hover:text-zinc-200"
              }`}
            >
              <div className="flex items-center space-x-1.5 font-bold text-xs text-purple-400 mb-0.5">
                <Users className="w-4 h-4" />
                <span>Split de Honorários</span>
              </div>
              <p className="text-[10px] text-zinc-400">Divisão Automática Escritório/Sócio</p>
            </button>
          </div>

          <form onSubmit={handleGenerateBilling} className="space-y-3 pt-2">
            <div>
              <label className="block text-zinc-300 font-bold uppercase text-[10px] mb-1">Cliente / Razão Social *</label>
              <input
                type="text"
                required
                value={clientName}
                onChange={(e) => setClientName(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-zinc-100 focus:outline-none focus:border-emerald-500"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-zinc-300 font-bold uppercase text-[10px] mb-1">Valor Total (R$) *</label>
                <input
                  type="number"
                  required
                  step="0.01"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-zinc-100 font-mono focus:outline-none focus:border-emerald-500"
                />
              </div>

              {selectedMethod === "CREDIT_CARD" ? (
                <div>
                  <label className="block text-zinc-300 font-bold uppercase text-[10px] mb-1">Parcelas Máximas</label>
                  <select
                    value={installments}
                    onChange={(e) => setInstallments(e.target.value)}
                    className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-zinc-100 focus:outline-none focus:border-blue-500 cursor-pointer"
                  >
                    <option value="1">1x À Vista (Sem Juros)</option>
                    <option value="3">Até 3x Sem Juros</option>
                    <option value="6">Até 6x com Juros do Cliente</option>
                    <option value="12">Até 12x no Cartão</option>
                  </select>
                </div>
              ) : selectedMethod === "SPLIT" ? (
                <div>
                  <label className="block text-zinc-300 font-bold uppercase text-[10px] mb-1">% Repasse Parceiro</label>
                  <input
                    type="number"
                    value={splitPercentage}
                    onChange={(e) => setSplitPercentage(e.target.value)}
                    className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-purple-300 font-mono focus:outline-none focus:border-purple-500"
                  />
                </div>
              ) : (
                <div>
                  <label className="block text-zinc-300 font-bold uppercase text-[10px] mb-1">Vencimento Padrão</label>
                  <input
                    type="text"
                    disabled
                    value="7 dias após emissão"
                    className="w-full bg-zinc-950/60 border border-zinc-800/80 rounded-lg px-3 py-2 text-zinc-500 font-mono text-[10px]"
                  />
                </div>
              )}
            </div>

            {selectedMethod === "SPLIT" && (
              <div>
                <label className="block text-zinc-300 font-bold uppercase text-[10px] mb-1">Advogado / Parceiro de Destino do Split</label>
                <input
                  type="text"
                  value={splitPartner}
                  onChange={(e) => setSplitPartner(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-zinc-200 focus:outline-none focus:border-purple-500"
                />
              </div>
            )}

            <div>
              <label className="block text-zinc-300 font-bold uppercase text-[10px] mb-1">Descrição do Serviço Advocatício</label>
              <input
                type="text"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-zinc-200 focus:outline-none focus:border-emerald-500"
              />
            </div>

            <button
              type="submit"
              className={`w-full py-3 text-white font-bold rounded-xl text-xs flex items-center justify-center space-x-2 transition-all shadow-lg cursor-pointer ${
                selectedMethod === "PIX"
                  ? "bg-emerald-600 hover:bg-emerald-500 shadow-emerald-950"
                  : selectedMethod === "CREDIT_CARD"
                  ? "bg-blue-600 hover:bg-blue-500 shadow-blue-950"
                  : selectedMethod === "BOLETO"
                  ? "bg-amber-600 hover:bg-amber-500 shadow-amber-950"
                  : "bg-purple-600 hover:bg-purple-500 shadow-purple-950"
              }`}
            >
              <Sparkles className="w-4 h-4" />
              <span>Gerar Cobrança Oficial via {selectedMethod}</span>
            </button>
          </form>
        </div>

        {/* RIGHT DISPLAY PANEL */}
        <div className="lg:col-span-7 bg-zinc-900 border border-zinc-800 rounded-2xl p-6 flex flex-col justify-between space-y-4 shadow-xl">
          {/* DISPLAY PIX */}
          {selectedMethod === "PIX" && (
            <div className="space-y-4 animate-in fade-in duration-150">
              <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
                <div className="flex items-center space-x-2">
                  <QrCode className="w-4 h-4 text-emerald-400" />
                  <span className="text-xs font-bold text-zinc-100 uppercase tracking-wider">Payload Pix Autêntico BACEN</span>
                </div>

                <button
                  onClick={() => copyToClipboard(pixPayload, "Payload Pix")}
                  className="px-3.5 py-1.5 bg-emerald-950 border border-emerald-800 text-emerald-300 hover:bg-emerald-900 text-xs font-bold rounded-xl flex items-center space-x-1.5 transition-colors cursor-pointer"
                >
                  {copiedField === "Payload Pix" ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{copiedField === "Payload Pix" ? "Copiado!" : "Copiar Chave Pix"}</span>
                </button>
              </div>

              <div className="flex flex-col sm:flex-row items-center space-y-4 sm:space-y-0 sm:space-x-6 p-4 bg-zinc-950 border border-zinc-800 rounded-2xl">
                <div className="w-36 h-36 bg-white p-2 rounded-xl flex items-center justify-center shrink-0 shadow-lg">
                  <img
                    src={`https://api.qrserver.com/v1/create-qr-code/?size=150x150&data=${encodeURIComponent(pixPayload)}`}
                    alt="QR Code Pix"
                    className="w-full h-full object-contain"
                  />
                </div>

                <div className="space-y-2 text-xs text-zinc-300 flex-1">
                  <p className="font-bold text-zinc-100 text-sm">{clientName}</p>
                  <p className="font-mono text-emerald-400 text-xl font-extrabold">R$ {parseFloat(amount || "0").toFixed(2)}</p>
                  <p className="text-[11px] text-zinc-400">{description}</p>
                  <div className="p-2 bg-zinc-900 border border-zinc-800 rounded font-mono text-[10px] text-zinc-400 break-all">
                    {pixPayload}
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-between pt-2">
                <span className="text-[11px] font-mono text-zinc-500">Chave Pix: contato@rossiadvocacia.com.br</span>
                <button
                  onClick={() => showToast("Link Pix enviado diretamente para o WhatsApp do cliente!")}
                  className="px-4 py-2 bg-emerald-600/20 border border-emerald-800 text-emerald-300 hover:bg-emerald-950 text-xs font-bold rounded-xl flex items-center space-x-1.5 cursor-pointer"
                >
                  <Send className="w-3.5 h-3.5 text-emerald-400" />
                  <span>Enviar Pix via WhatsApp</span>
                </button>
              </div>
            </div>
          )}

          {/* DISPLAY CREDIT CARD */}
          {selectedMethod === "CREDIT_CARD" && (
            <div className="space-y-4 animate-in fade-in duration-150">
              <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
                <div className="flex items-center space-x-2">
                  <CreditCard className="w-4 h-4 text-blue-400" />
                  <span className="text-xs font-bold text-zinc-100 uppercase tracking-wider">Link de Checkout Cartão de Crédito</span>
                </div>

                <button
                  onClick={() => copyToClipboard(creditCardCheckoutUrl, "Link de Checkout")}
                  className="px-3.5 py-1.5 bg-blue-950 border border-blue-800 text-blue-300 hover:bg-blue-900 text-xs font-bold rounded-xl flex items-center space-x-1.5 transition-colors cursor-pointer"
                >
                  {copiedField === "Link de Checkout" ? <Check className="w-3.5 h-3.5 text-blue-400" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{copiedField === "Link de Checkout" ? "Copiado!" : "Copiar Link Checkout"}</span>
                </button>
              </div>

              <div className="bg-zinc-950 border border-blue-900/60 p-5 rounded-2xl space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-blue-300 uppercase">Checkout Criptografado PCI-DSS</span>
                  <span className="text-[10px] font-mono text-emerald-400 bg-emerald-950 border border-emerald-800 px-2 py-0.5 rounded font-bold">
                    ATÉ {installments}X NO CARTÃO
                  </span>
                </div>

                <p className="text-sm font-bold text-white">{clientName}</p>
                <p className="text-2xl font-extrabold font-mono text-blue-400">R$ {parseFloat(amount || "0").toFixed(2)}</p>

                <div className="p-3 bg-zinc-900 border border-zinc-800 rounded-xl space-y-1 font-mono text-xs">
                  <p className="text-zinc-400">Link de Pagamento Seguro:</p>
                  <p className="text-blue-400 underline break-all">{creditCardCheckoutUrl}</p>
                </div>
              </div>

              <div className="flex items-center justify-between pt-2">
                <span className="text-[11px] font-mono text-zinc-500">Aceita Visa, Mastercard, Elo, Amex e Apple Pay</span>
                <button
                  onClick={() => showToast("Link de Checkout enviado via WhatsApp!")}
                  className="px-4 py-2 bg-blue-600/20 border border-blue-800 text-blue-300 hover:bg-blue-950 text-xs font-bold rounded-xl flex items-center space-x-1.5 cursor-pointer"
                >
                  <Send className="w-3.5 h-3.5 text-blue-400" />
                  <span>Enviar Link via WhatsApp</span>
                </button>
              </div>
            </div>
          )}

          {/* DISPLAY BOLETO */}
          {selectedMethod === "BOLETO" && (
            <div className="space-y-4 animate-in fade-in duration-150">
              <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
                <div className="flex items-center space-x-2">
                  <Barcode className="w-4 h-4 text-amber-400" />
                  <span className="text-xs font-bold text-zinc-100 uppercase tracking-wider">Boleto Bancário Registrado CNAB</span>
                </div>

                <button
                  onClick={() => copyToClipboard(boletoLine, "Linha Digitável")}
                  className="px-3.5 py-1.5 bg-amber-950 border border-amber-800 text-amber-300 hover:bg-amber-900 text-xs font-bold rounded-xl flex items-center space-x-1.5 transition-colors cursor-pointer"
                >
                  {copiedField === "Linha Digitável" ? <Check className="w-3.5 h-3.5 text-amber-400" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{copiedField === "Linha Digitável" ? "Copiada!" : "Copiar Código de Barras"}</span>
                </button>
              </div>

              <div className="bg-zinc-950 border border-amber-900/60 p-5 rounded-2xl space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-amber-300 uppercase">Banco Itaú / Registro CIP</span>
                  <span className="text-[10px] font-mono text-amber-400 bg-amber-950 border border-amber-800 px-2 py-0.5 rounded font-bold">
                    VENCIMENTO EM 7 DIAS
                  </span>
                </div>

                <p className="text-sm font-bold text-white">{clientName}</p>
                <p className="text-2xl font-extrabold font-mono text-amber-400">R$ {parseFloat(amount || "0").toFixed(2)}</p>

                <div className="p-3 bg-zinc-900 border border-zinc-800 rounded-xl space-y-1 font-mono text-xs">
                  <p className="text-zinc-400">Linha Digitável de Cobrança:</p>
                  <p className="text-amber-300 font-bold break-all">{boletoLine}</p>
                </div>
              </div>

              <div className="flex items-center justify-between pt-2">
                <button
                  onClick={() => showToast("Baixando PDF do Boleto Registrado...")}
                  className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-bold rounded-xl flex items-center space-x-1.5 cursor-pointer"
                >
                  <Download className="w-3.5 h-3.5 text-amber-400" />
                  <span>Baixar Boleto PDF</span>
                </button>

                <button
                  onClick={() => showToast("Boleto e linha digitável enviados via WhatsApp!")}
                  className="px-4 py-2 bg-amber-600/20 border border-amber-800 text-amber-300 hover:bg-amber-950 text-xs font-bold rounded-xl flex items-center space-x-1.5 cursor-pointer"
                >
                  <Send className="w-3.5 h-3.5 text-amber-400" />
                  <span>Enviar Boleto via WhatsApp</span>
                </button>
              </div>
            </div>
          )}

          {/* DISPLAY SPLIT */}
          {selectedMethod === "SPLIT" && (
            <div className="space-y-4 animate-in fade-in duration-150">
              <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
                <div className="flex items-center space-x-2">
                  <Users className="w-4 h-4 text-purple-400" />
                  <span className="text-xs font-bold text-zinc-100 uppercase tracking-wider">Regra de Split de Honorários Automático</span>
                </div>

                <span className="text-[10px] font-mono text-purple-300 bg-purple-950 border border-purple-800 px-2.5 py-1 rounded-full font-bold">
                  REPASSE AUTOMÁTICO
                </span>
              </div>

              <div className="bg-zinc-950 border border-purple-900/60 p-5 rounded-2xl space-y-4">
                <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
                  <div>
                    <span className="text-[10px] font-mono text-zinc-400 uppercase">Valor Total do Contrato</span>
                    <p className="text-xl font-extrabold font-mono text-white">R$ {parseFloat(amount || "0").toFixed(2)}</p>
                  </div>
                  <Percent className="w-6 h-6 text-purple-400" />
                </div>

                <div className="grid grid-cols-2 gap-3 font-mono text-xs">
                  <div className="p-3 bg-zinc-900 border border-zinc-800 rounded-xl space-y-1">
                    <span className="text-[10px] text-zinc-400 uppercase block">Escritório Principal ({100 - parseInt(splitPercentage || "0")}%)</span>
                    <p className="text-emerald-400 font-bold text-sm">
                      R$ {((parseFloat(amount || "0") * (100 - parseInt(splitPercentage || "0"))) / 100).toFixed(2)}
                    </p>
                  </div>

                  <div className="p-3 bg-zinc-900 border border-zinc-800 rounded-xl space-y-1">
                    <span className="text-[10px] text-purple-400 uppercase block">Parceiro ({splitPercentage}%)</span>
                    <p className="text-purple-300 font-bold text-sm">
                      R$ {((parseFloat(amount || "0") * parseInt(splitPercentage || "0")) / 100).toFixed(2)}
                    </p>
                  </div>
                </div>

                <p className="text-[11px] text-zinc-400 leading-relaxed font-sans">
                  Destinatário do Repasse: <strong className="text-white">{splitPartner}</strong>. Assim que o cliente efetuar o pagamento por Pix ou Cartão, o gateway transfere a fatia do parceiro em tempo real.
                </p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* BILLING HISTORY TABLE */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 space-y-4 shadow-xl">
        <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
          <div>
            <h3 className="text-sm font-extrabold text-zinc-100 uppercase tracking-wider">Histórico de Cobranças & Faturamento</h3>
            <p className="text-xs text-zinc-400">Registros em tempo real das cobranças emitidas para clientes do escritório.</p>
          </div>

          <span className="text-xs font-mono text-zinc-400 bg-zinc-950 border border-zinc-800 px-3 py-1.5 rounded-xl font-bold">
            {billings.length} Cobranças Registradas
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-zinc-800 text-[10px] font-mono text-zinc-400 uppercase tracking-wider">
                <th className="py-3 px-3">Código</th>
                <th className="py-3 px-3">Cliente / Razão Social</th>
                <th className="py-3 px-3">Meio</th>
                <th className="py-3 px-3">Valor (R$)</th>
                <th className="py-3 px-3">Status</th>
                <th className="py-3 px-3">Vencimento</th>
                <th className="py-3 px-3 text-right">Ação</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/60 text-xs">
              {billings.map((b) => (
                <tr key={b.id} className="hover:bg-zinc-950/50 transition-colors">
                  <td className="py-3.5 px-3 font-mono font-bold text-zinc-300">{b.id}</td>
                  <td className="py-3.5 px-3 font-semibold text-white">
                    {b.client}
                    <span className="block text-[10px] font-normal text-zinc-400 font-sans">{b.description}</span>
                  </td>
                  <td className="py-3.5 px-3 font-mono text-[11px]">
                    {b.method === "PIX" && <span className="text-emerald-400 font-bold">⚡ PIX</span>}
                    {b.method === "CREDIT_CARD" && <span className="text-blue-400 font-bold">💳 CARTÃO</span>}
                    {b.method === "BOLETO" && <span className="text-amber-400 font-bold">📄 BOLETO</span>}
                    {b.method === "SPLIT" && <span className="text-purple-400 font-bold">👥 SPLIT</span>}
                  </td>
                  <td className="py-3.5 px-3 font-mono font-bold text-zinc-100">
                    R$ {b.amount.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
                  </td>
                  <td className="py-3.5 px-3">
                    {b.status === "PAID" && (
                      <span className="px-2.5 py-1 bg-emerald-950 text-emerald-400 border border-emerald-800 rounded-full font-mono text-[10px] font-bold inline-flex items-center space-x-1">
                        <Check className="w-3 h-3 text-emerald-400" />
                        <span>PAGO</span>
                      </span>
                    )}
                    {b.status === "PENDING" && (
                      <span className="px-2.5 py-1 bg-amber-950 text-amber-400 border border-amber-800 rounded-full font-mono text-[10px] font-bold inline-flex items-center space-x-1">
                        <Clock className="w-3 h-3 text-amber-400" />
                        <span>PENDENTE</span>
                      </span>
                    )}
                    {b.status === "OVERDUE" && (
                      <span className="px-2.5 py-1 bg-rose-950 text-rose-400 border border-rose-800 rounded-full font-mono text-[10px] font-bold inline-flex items-center space-x-1">
                        <AlertCircle className="w-3 h-3 text-rose-400" />
                        <span>EM ATRASO</span>
                      </span>
                    )}
                  </td>
                  <td className="py-3.5 px-3 font-mono text-zinc-400">{b.dueDate}</td>
                  <td className="py-3.5 px-3 text-right">
                    <button
                      onClick={() => showToast(`Recibo da cobrança ${b.id} enviado via E-mail!`)}
                      className="p-1.5 text-zinc-400 hover:text-white hover:bg-zinc-800 rounded-lg transition-colors cursor-pointer"
                      title="Enviar Recibo / Reenviar Cobrança"
                    >
                      <Send className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
