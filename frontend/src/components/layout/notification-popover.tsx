"use client";

import React, { useState, useEffect, useRef } from "react";
import { Bell, Scale, FileSignature, DollarSign, AlertTriangle, Check, X, CheckCheck } from "lucide-react";

export interface LegalNotification {
  id: string;
  title: string;
  message: string;
  time: string;
  type: "DATAJUD" | "SIGNATURE" | "PAYMENT" | "RBAC_APPROVAL";
  read: boolean;
}

export function NotificationPopover() {
  const [isOpen, setIsOpen] = useState(false);
  const popoverRef = useRef<HTMLDivElement>(null);
  const [notifications, setNotifications] = useState<LegalNotification[]>([
    {
      id: "notif-1",
      title: "Novo Andamento Processual (DataJud)",
      message: "TJSP: Processo nº 0123456-78.2026.8.07.0000 teve despacho de juntada proferido pelo Juiz da 1ª Vara Cível.",
      time: "há 10 min",
      type: "DATAJUD",
      read: false,
    },
    {
      id: "notif-2",
      title: "Contrato Assinado Digitalmente",
      message: "Marcos Paulo Silva assinou o Contrato de Honorários Quota Litis com validação SHA-256.",
      time: "há 45 min",
      type: "SIGNATURE",
      read: false,
    },
    {
      id: "notif-3",
      title: "Cobrança Pix Confirmada",
      message: "Recebimento de R$ 4.500,00 confirmado via Asaas/Pix Copia e Cola (Honorários Tributários).",
      time: "há 2 horas",
      type: "PAYMENT",
      read: false,
    },
    {
      id: "notif-4",
      title: "Solicitação de Aprovação do Sócio",
      message: "Estagiário Lucas Mendes submeteu a minuta 'Ação de Restituição' para sua aprovação final (RBAC).",
      time: "há 3 horas",
      type: "RBAC_APPROVAL",
      read: false,
    },
  ]);

  // Fechar o popover de notificações ao clicar em qualquer lugar fora dele
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (popoverRef.current && !popoverRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isOpen]);

  const unreadCount = notifications.filter((n) => !n.read).length;

  const markAllAsRead = () => {
    setNotifications(notifications.map((n) => ({ ...n, read: true })));
  };

  const markAsRead = (id: string) => {
    setNotifications(notifications.map((n) => (n.id === id ? { ...n, read: true } : n)));
  };

  const clearAll = () => {
    setNotifications([]);
  };

  return (
    <div ref={popoverRef} className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="p-2 text-zinc-400 hover:text-zinc-200 bg-zinc-950 border border-zinc-800 rounded-xl relative transition-all cursor-pointer shadow-sm"
        title="Central de Notificações Jurídicas"
      >
        <Bell className="w-4 h-4" />
        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 w-4 h-4 bg-blue-600 text-white font-mono font-bold text-[9px] rounded-full flex items-center justify-center border-2 border-zinc-950 shadow-md">
            {unreadCount}
          </span>
        )}
      </button>

      {isOpen && (
        <div className="absolute right-0 top-full mt-2 w-80 sm:w-96 z-50 bg-zinc-950 border border-zinc-800 rounded-2xl shadow-2xl overflow-hidden text-xs">
          {/* Header */}
          <div className="p-3 border-b border-zinc-800 bg-zinc-900/90 flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Bell className="w-4 h-4 text-blue-400" />
              <span className="font-bold text-zinc-100 uppercase tracking-wider text-[11px]">
                Central de Notificações ({unreadCount})
              </span>
            </div>

            <div className="flex items-center space-x-1">
              {unreadCount > 0 && (
                <button
                  onClick={markAllAsRead}
                  className="px-2 py-1 text-[10px] text-blue-400 hover:text-blue-300 font-semibold flex items-center space-x-1 cursor-pointer"
                >
                  <CheckCheck className="w-3 h-3" />
                  <span>Ler Todas</span>
                </button>
              )}
              <button onClick={() => setIsOpen(false)} className="text-zinc-500 hover:text-zinc-300 p-1 cursor-pointer">
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* List */}
          <div className="max-h-80 overflow-y-auto divide-y divide-zinc-800/60">
            {notifications.length > 0 ? (
              notifications.map((n) => (
                <div
                  key={n.id}
                  onClick={() => markAsRead(n.id)}
                  className={`p-3 transition-colors cursor-pointer flex items-start space-x-3 ${
                    n.read ? "opacity-60 bg-zinc-950" : "bg-zinc-900/40 hover:bg-zinc-900"
                  }`}
                >
                  <div className="p-2 rounded-xl border shrink-0 mt-0.5">
                    {n.type === "DATAJUD" && <Scale className="w-4 h-4 text-blue-400" />}
                    {n.type === "SIGNATURE" && <FileSignature className="w-4 h-4 text-purple-400" />}
                    {n.type === "PAYMENT" && <DollarSign className="w-4 h-4 text-emerald-400" />}
                    {n.type === "RBAC_APPROVAL" && <AlertTriangle className="w-4 h-4 text-amber-400" />}
                  </div>

                  <div className="flex-1 space-y-1">
                    <div className="flex items-center justify-between">
                      <p className="font-bold text-zinc-100 text-xs">{n.title}</p>
                      <span className="text-[9px] font-mono text-zinc-500">{n.time}</span>
                    </div>
                    <p className="text-[11px] text-zinc-300 leading-snug">{n.message}</p>
                  </div>
                </div>
              ))
            ) : (
              <div className="p-6 text-center text-zinc-500 text-xs">
                Nenhuma notificação recente.
              </div>
            )}
          </div>

          {/* Footer */}
          {notifications.length > 0 && (
            <div className="p-2.5 bg-zinc-900/90 border-t border-zinc-800 flex justify-between items-center text-[10px]">
              <span className="text-zinc-500 font-mono">Alertas DataJud + Asaas + RBAC</span>
              <button onClick={clearAll} className="text-zinc-400 hover:text-rose-400 font-semibold cursor-pointer">
                Limpar Notificações
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
