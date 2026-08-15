"use client";

import React from "react";
import { CheckCircle2, Circle, Upload, FileText, AlertCircle } from "lucide-react";
import { ChecklistItem as ChecklistItemType, useOabStore } from "@/store/useOabStore";
import { cn } from "@/lib/utils";

interface Props {
  item: ChecklistItemType;
}

export function ChecklistItemCard({ item }: Props) {
  const { toggleChecklist } = useOabStore();

  return (
    <div
      className={cn(
        "p-4 rounded-xl border transition-all flex items-start justify-between space-x-4",
        item.is_completed
          ? "bg-zinc-900/40 border-emerald-500/30 text-zinc-300"
          : "bg-zinc-900 border-zinc-800 text-zinc-100 hover:border-zinc-700"
      )}
    >
      <div className="flex items-start space-x-3 flex-1">
        <button
          onClick={() => toggleChecklist(item.id)}
          className="mt-0.5 text-zinc-400 hover:text-emerald-400 transition-colors shrink-0"
        >
          {item.is_completed ? (
            <CheckCircle2 className="w-5 h-5 text-emerald-500" />
          ) : (
            <Circle className="w-5 h-5 text-zinc-600" />
          )}
        </button>

        <div>
          <h4
            className={cn(
              "text-xs font-semibold tracking-wide",
              item.is_completed ? "line-through text-zinc-400" : "text-zinc-100"
            )}
          >
            {item.title}
          </h4>
          <p className="text-[11px] text-zinc-500 mt-1">
            Código OAB: <span className="font-mono text-zinc-400">{item.item_code}</span>
          </p>

          {item.is_completed ? (
            <div className="flex items-center space-x-1.5 text-[10px] text-emerald-400 mt-2 font-medium">
              <FileText className="w-3 h-3" />
              <span>Documento validado via OCR automatizado</span>
            </div>
          ) : (
            <div className="flex items-center space-x-1.5 text-[10px] text-amber-400 mt-2 font-medium">
              <AlertCircle className="w-3 h-3" />
              <span>Pendente de upload e validação</span>
            </div>
          )}
        </div>
      </div>

      {/* Upload button */}
      <button
        onClick={() => toggleChecklist(item.id)}
        className={cn(
          "px-3 py-1.5 rounded-lg text-xs font-medium border flex items-center space-x-1.5 transition-colors shrink-0",
          item.is_completed
            ? "bg-zinc-800 border-zinc-700 text-zinc-300 hover:bg-zinc-700"
            : "bg-blue-600 hover:bg-blue-500 border-blue-500 text-white shadow-md shadow-blue-950"
        )}
      >
        <Upload className="w-3.5 h-3.5" />
        <span>{item.is_completed ? "Substituir" : "Enviar PDF"}</span>
      </button>
    </div>
  );
}
