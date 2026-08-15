"use client";

import React, { useState } from "react";
import { FileText, Download, ShieldCheck, Printer } from "lucide-react";

export function DeclarationPreview() {
  const [declType, setDeclType] = useState<"IDONEIDADE" | "INCOMPATIBILIDADE">("IDONEIDADE");
  const [formData, setFormData] = useState({
    nome: "Alexandre Rossi Santos",
    cpf: "123.456.789-00",
    rg: "45.890.123-X SSP/SP",
    estadoCivil: "Solteiro(a)",
    endereco: "Av. Paulista, 1000, Cj 50, São Paulo/SP",
  });

  const declText =
    declType === "IDONEIDADE"
      ? `Eu, ${formData.nome.toUpperCase()}, estado civil ${formData.estadoCivil}, portador(a) do RG nº ${formData.rg} e inscrito(a) no CPF/MF sob o nº ${formData.cpf}, residente e domiciliado(a) no endereço ${formData.endereco}, DECLARO, sob as penas da lei e para os fins previstos no artigo 8º, inciso VI, da Lei nº 8.906/1994 (Estatuto da Advocacia e da OAB), gozar de ilibada idoneidade moral, não respondendo a processo penal ou qualquer procedimento incompatível com o exercício da advocacia.`
      : `Eu, ${formData.nome.toUpperCase()}, estado civil ${formData.estadoCivil}, portador(a) do RG nº ${formData.rg} e inscrito(a) no CPF/MF sob o nº ${formData.cpf}, residente e domiciliado(a) no endereço ${formData.endereco}, DECLARO, sob as penas da lei, nos termos dos artigos 27 a 30 da Lei nº 8.906/1994, que NÃO EXERÇO cargo ou função incompatível com a atividade de advocacia, nem me encontro em situação de impedimento legal para o exercício da profissão de Advogado(a).`;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Form Editor */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 space-y-4">
        <h3 className="text-xs font-bold text-zinc-100 uppercase tracking-wider flex items-center space-x-2">
          <FileText className="w-4 h-4 text-blue-500" />
          <span>Formulário de Declaração Oficial (Lei 8.906/94)</span>
        </h3>

        <div className="flex space-x-2 p-1 bg-zinc-950 rounded-lg border border-zinc-800">
          <button
            onClick={() => setDeclType("IDONEIDADE")}
            className={`flex-1 py-1.5 text-xs font-medium rounded-md transition-colors ${
              declType === "IDONEIDADE" ? "bg-blue-600 text-white" : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            Idoneidade Moral
          </button>
          <button
            onClick={() => setDeclType("INCOMPATIBILIDADE")}
            className={`flex-1 py-1.5 text-xs font-medium rounded-md transition-colors ${
              declType === "INCOMPATIBILIDADE" ? "bg-blue-600 text-white" : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            Não Incompatibilidade
          </button>
        </div>

        <div className="space-y-3 text-xs">
          <div>
            <label className="text-zinc-400 block mb-1">Nome Completo</label>
            <input
              type="text"
              value={formData.nome}
              onChange={(e) => setFormData({ ...formData, nome: e.target.value })}
              className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-zinc-200 focus:outline-none focus:border-blue-500"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-zinc-400 block mb-1">CPF</label>
              <input
                type="text"
                value={formData.cpf}
                onChange={(e) => setFormData({ ...formData, cpf: e.target.value })}
                className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-zinc-200 focus:outline-none focus:border-blue-500"
              />
            </div>
            <div>
              <label className="text-zinc-400 block mb-1">RG / Órgão</label>
              <input
                type="text"
                value={formData.rg}
                onChange={(e) => setFormData({ ...formData, rg: e.target.value })}
                className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-zinc-200 focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>

          <div>
            <label className="text-zinc-400 block mb-1">Endereço Residencial Completo</label>
            <input
              type="text"
              value={formData.endereco}
              onChange={(e) => setFormData({ ...formData, endereco: e.target.value })}
              className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-zinc-200 focus:outline-none focus:border-blue-500"
            />
          </div>
        </div>
      </div>

      {/* Live Preview Paper */}
      <div className="bg-white text-zinc-900 rounded-xl p-8 shadow-2xl flex flex-col justify-between font-serif relative">
        <div className="space-y-6">
          <div className="text-center border-b border-zinc-200 pb-4">
            <h4 className="text-xs font-bold uppercase tracking-widest text-zinc-600 font-sans">
              Ordem dos Advogados do Brasil - Seccional
            </h4>
            <h2 className="text-sm font-bold text-zinc-900 mt-2 tracking-wide uppercase font-sans">
              {declType === "IDONEIDADE"
                ? "Declaração de Idoneidade Moral"
                : "Declaração de Não Incompatibilidade (Arts. 27 a 30)"}
            </h2>
          </div>

          <p className="text-xs leading-relaxed text-justify indent-8 text-zinc-800 font-serif">
            {declText}
          </p>

          <div className="pt-8 text-center text-xs font-sans text-zinc-600 space-y-1">
            <p>São Paulo/SP, 12 de agosto de 2026.</p>
            <div className="pt-12">
              <div className="w-48 h-px bg-zinc-400 mx-auto mb-2" />
              <p className="font-bold text-zinc-900">{formData.nome}</p>
              <p className="text-[10px] text-zinc-500">Requerente - OAB Inscrição Originária</p>
            </div>
          </div>
        </div>

        <div className="mt-8 pt-4 border-t border-zinc-200 flex items-center justify-between font-sans">
          <div className="flex items-center space-x-1.5 text-[10px] text-emerald-700 bg-emerald-50 px-2 py-1 rounded">
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>Hash SHA-256 Validado</span>
          </div>

          <div className="flex space-x-2">
            <button className="px-3 py-1.5 bg-zinc-100 hover:bg-zinc-200 text-zinc-800 rounded-md text-xs font-medium flex items-center space-x-1">
              <Printer className="w-3.5 h-3.5" />
              <span>Imprimir</span>
            </button>
            <button className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-md text-xs font-medium flex items-center space-x-1 shadow-sm">
              <Download className="w-3.5 h-3.5" />
              <span>Baixar PDF Assinado</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
