"use client";

import React, { useEffect, useState, useRef } from "react";
import { Building2, ChevronDown, Check, Sparkles } from "lucide-react";

export interface TenantProfile {
  id: string;
  name: string;
  lawyerName: string;
  oabNumber: string;
  address: string;
  phoneEmail: string;
  presetStyle: "SILVA_ASSOCIADOS" | "WIL_SHAFFER" | "GRADIENT";
}

export const tenantProfiles: TenantProfile[] = [
  {
    id: "silva",
    name: "SILVA & ASSOCIADOS ADVOCACIA",
    lawyerName: "Dra. Carolina Silva",
    oabNumber: "OAB/DF 12.345",
    address: "Setor Comercial Sul, Quadra 04, Bloco C, Edifício Trade, Sala 1001, Brasília - DF",
    phoneEmail: "silvaeassociados.adv.br | (61) 3212-0000",
    presetStyle: "SILVA_ASSOCIADOS",
  },
  {
    id: "shaffer",
    name: "WIL SHAFFER IMPERIAL LAW FIRM",
    lawyerName: "Dr. Wil Shaffer",
    oabNumber: "OAB/SP 98.765",
    address: "Av. Brigadeiro Faria Lima, 3477, 14º Andar, Itaim Bibi, São Paulo - SP",
    phoneEmail: "wilshaffer.law | (11) 4004-9900",
    presetStyle: "WIL_SHAFFER",
  },
  {
    id: "techlaw",
    name: "TECHLAW PARTNERS & COMPLIANCE",
    lawyerName: "Dr. Gabriel Santos",
    oabNumber: "OAB/RJ 54.321",
    address: "Av. Rio Branco, 156, Centro, Rio de Janeiro - RJ",
    phoneEmail: "techlawpartners.com.br | (21) 2500-1100",
    presetStyle: "GRADIENT",
  },
];

export function TenantSwitcher() {
  const [isOpen, setIsOpen] = useState(false);
  const [activeTenant, setActiveTenant] = useState<TenantProfile>(tenantProfiles[0]);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const savedId = localStorage.getItem("lexflow_active_tenant_id");
      if (savedId) {
        const found = tenantProfiles.find((t) => t.id === savedId);
        if (found) setActiveTenant(found);
      }
    }
  }, []);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
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

  const handleSelect = (tenant: TenantProfile) => {
    setActiveTenant(tenant);
    setIsOpen(false);
    if (typeof window !== "undefined") {
      localStorage.setItem("lexflow_active_tenant_id", tenant.id);
      window.dispatchEvent(new CustomEvent("tenantChanged", { detail: tenant }));
    }
  };

  return (
    <div ref={dropdownRef} className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center justify-between w-full px-3 py-2 text-xs font-semibold text-zinc-200 bg-zinc-900 border border-zinc-800 rounded-xl hover:bg-zinc-800/80 transition-all shadow-sm cursor-pointer"
      >
        <div className="flex items-center space-x-2 truncate">
          <Building2 className="w-4 h-4 text-blue-400 shrink-0" />
          <span className="truncate">{activeTenant.name}</span>
        </div>
        <ChevronDown className="w-3.5 h-3.5 text-zinc-400 shrink-0 ml-1.5" />
      </button>

      {isOpen && (
        <div className="absolute left-0 top-full mt-1.5 w-full z-50 bg-zinc-950 border border-zinc-800 rounded-xl shadow-2xl py-1 space-y-0.5">
          <div className="px-3 py-1.5 border-b border-zinc-800 text-[10px] font-mono text-zinc-500 uppercase tracking-wider flex items-center justify-between">
            <span>Alternar Escritório (Multi-Tenant)</span>
            <Sparkles className="w-3 h-3 text-amber-400" />
          </div>
          {tenantProfiles.map((tenant) => (
            <button
              key={tenant.id}
              onClick={() => handleSelect(tenant)}
              className={`flex items-center justify-between w-full px-3 py-2 text-[11px] text-left transition-all cursor-pointer ${
                activeTenant.id === tenant.id
                  ? "bg-blue-600/20 text-blue-300 font-bold"
                  : "text-zinc-300 hover:bg-zinc-900"
              }`}
            >
              <div className="truncate pr-2">
                <p className="font-semibold truncate">{tenant.name}</p>
                <p className="text-[9px] text-zinc-500 font-mono truncate">{tenant.lawyerName} • {tenant.oabNumber}</p>
              </div>
              {activeTenant.id === tenant.id && <Check className="w-3.5 h-3.5 text-blue-400 shrink-0" />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
