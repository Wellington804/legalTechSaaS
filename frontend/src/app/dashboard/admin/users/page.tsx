"use client";

import React, { useState } from "react";
import { useUser, UserRole, UserProfile } from "@/context/user-context";
import {
  Users,
  ShieldCheck,
  UserPlus,
  Search,
  Shield,
  CheckCircle2,
  XCircle,
  Trash2,
  Lock,
  AlertTriangle,
  KeyRound,
  Building2,
  Mail,
  Award
} from "lucide-react";

export default function UsersManagementPage() {
  const {
    user: currentUser,
    usersList,
    addUser,
    updateUserRole,
    toggleUserStatus,
    deleteUser,
  } = useUser();

  const [searchTerm, setSearchTerm] = useState("");
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);

  // Form State for New User
  const [name, setName] = useState("");
  const [oabNumber, setOabNumber] = useState("");
  const [role, setRole] = useState<UserRole>("ASSOCIADO");
  const [email, setEmail] = useState("");
  const [officeName, setOfficeName] = useState(currentUser.officeName || "SILVA & ASSOCIADOS ADVOCACIA");

  const isSuperAdmin = currentUser.role === "SUPER_ADMIN";
  const isSocio = currentUser.role === "SOCIO";
  const canManage = isSuperAdmin || isSocio;

  const filteredUsers = usersList.filter(
    (u) =>
      u.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      u.oabNumber.toLowerCase().includes(searchTerm.toLowerCase()) ||
      u.email.toLowerCase().includes(searchTerm.toLowerCase()) ||
      u.role.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const handleCreateUser = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !email.trim()) return;

    addUser({
      name,
      oabNumber: oabNumber || "SEM OAB",
      role,
      email,
      officeName,
    });

    setName("");
    setOabNumber("");
    setEmail("");
    setIsAddModalOpen(false);
    alert(`Usuário "${name}" cadastrado com sucesso com o papel ${role}!`);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <div className="flex items-center space-x-2 text-xs text-blue-400 font-mono uppercase tracking-wider mb-1">
            <ShieldCheck className="w-4 h-4 text-blue-400" />
            <span>Módulo de Governança & Administração Master</span>
          </div>
          <h1 className="text-2xl font-extrabold text-zinc-100 tracking-tight">
            Gestão de Usuários & Controle de Privilégios (RBAC)
          </h1>
          <p className="text-xs text-zinc-400 mt-1 max-w-3xl leading-relaxed">
            Painel exclusivo para cadastrar advogados, estagiários e membros da equipe, gerenciar permissões de acesso e definir privilégios por papel de trabalho.
          </p>
        </div>

        {canManage && (
          <button
            onClick={() => setIsAddModalOpen(true)}
            className="px-4 py-2.5 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-xl text-xs flex items-center space-x-2 shadow-lg shadow-blue-950 cursor-pointer transition-colors"
          >
            <UserPlus className="w-4 h-4" />
            <span>Criar Novo Usuário</span>
          </button>
        )}
      </div>

      {/* Access Lock Banner for Non-Admins */}
      {!canManage && (
        <div className="p-6 bg-rose-950/80 border border-rose-800 rounded-2xl flex items-center space-x-4 text-rose-200">
          <Lock className="w-8 h-8 text-rose-400 shrink-0" />
          <div>
            <h3 className="text-sm font-bold text-rose-100">Acesso Restrito ao Painel de Administração</h3>
            <p className="text-xs text-rose-300 mt-0.5">
              Seu perfil atual ({currentUser.role}) não possui autorização para criar ou alterar usuários. Entre em contato com o <strong>Super Usuário Master</strong> ou com um <strong>Sócio</strong> do escritório.
            </p>
          </div>
        </div>
      )}

      {/* Main Table Card */}
      <div className={`bg-zinc-900 border border-zinc-800 rounded-2xl p-6 space-y-4 ${!canManage ? "opacity-50 pointer-events-none" : ""}`}>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center space-x-2">
            <Users className="w-4 h-4 text-blue-400" />
            <h3 className="text-xs font-bold text-zinc-100 uppercase tracking-wider">
              Usuários Cadastrados no Sistema
            </h3>
            <span className="px-2 py-0.5 bg-blue-950 text-blue-400 border border-blue-800 text-[10px] font-mono rounded">
              {filteredUsers.length} Usuários
            </span>
          </div>

          {/* Search Input */}
          <div className="relative w-full sm:w-72">
            <Search className="w-4 h-4 text-zinc-500 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Buscar por nome, OAB ou e-mail..."
              className="w-full bg-zinc-950 border border-zinc-800 rounded-xl pl-9 pr-3 py-1.5 text-xs text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:border-blue-500"
            />
          </div>
        </div>

        {/* Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-zinc-300">
            <thead className="bg-zinc-950 border-b border-zinc-800 text-[11px] font-mono text-zinc-400 uppercase">
              <tr>
                <th className="p-3">Advogado / Usuário</th>
                <th className="p-3">Inscrição OAB</th>
                <th className="p-3">Papel de Acesso (RBAC)</th>
                <th className="p-3">Status</th>
                <th className="p-3">Data de Cadastro</th>
                <th className="p-3 text-right">Ações</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/60 font-sans">
              {filteredUsers.map((u) => (
                <tr key={u.id} className="hover:bg-zinc-950/50 transition-colors">
                  <td className="p-3">
                    <div className="flex items-center space-x-3">
                      <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-blue-600 to-indigo-700 flex items-center justify-center text-white text-xs font-bold font-mono shadow-sm">
                        {u.avatarInitials}
                      </div>
                      <div>
                        <p className="font-bold text-zinc-100">{u.name}</p>
                        <p className="text-[10px] text-zinc-500 font-mono">{u.email}</p>
                      </div>
                    </div>
                  </td>

                  <td className="p-3 font-mono text-zinc-300">{u.oabNumber}</td>

                  {/* Role Dropdown Selector */}
                  <td className="p-3">
                    <select
                      value={u.role}
                      onChange={(e) => updateUserRole(u.id, e.target.value as UserRole)}
                      disabled={!canManage || (u.role === "SUPER_ADMIN" && !isSuperAdmin)}
                      className={`bg-zinc-950 border rounded-lg px-2.5 py-1 text-xs font-semibold focus:outline-none ${
                        u.role === "SUPER_ADMIN"
                          ? "border-amber-700 text-amber-300 bg-amber-950/40"
                          : u.role === "SOCIO"
                          ? "border-blue-700 text-blue-300 bg-blue-950/40"
                          : u.role === "ASSOCIADO"
                          ? "border-indigo-700 text-indigo-300 bg-indigo-950/40"
                          : u.role === "ESTAGIARIO"
                          ? "border-purple-700 text-purple-300 bg-purple-950/40"
                          : "border-emerald-700 text-emerald-300 bg-emerald-950/40"
                      }`}
                    >
                      <option value="SUPER_ADMIN">SUPER_ADMIN (Master)</option>
                      <option value="SOCIO">Sócio / Administrador</option>
                      <option value="ASSOCIADO">Advogado Associado</option>
                      <option value="ESTAGIARIO">Estagiário de Direito</option>
                      <option value="SECRETARIA">Secretaria / Financeiro</option>
                    </select>
                  </td>

                  <td className="p-3">
                    <button
                      onClick={() => toggleUserStatus(u.id)}
                      className={`inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-mono font-semibold cursor-pointer border ${
                        u.status === "ACTIVE"
                          ? "bg-emerald-950 text-emerald-400 border-emerald-800"
                          : "bg-rose-950 text-rose-400 border-rose-800"
                      }`}
                    >
                      {u.status === "ACTIVE" ? <CheckCircle2 className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
                      <span>{u.status === "ACTIVE" ? "Ativo" : "Inativo"}</span>
                    </button>
                  </td>

                  <td className="p-3 font-mono text-zinc-500 text-[11px]">{u.createdAt}</td>

                  <td className="p-3 text-right space-x-2">
                    {u.id !== currentUser.id && u.role !== "SUPER_ADMIN" && (
                      <button
                        onClick={() => {
                          if (confirm(`Deseja realmente remover o usuário ${u.name}?`)) {
                            deleteUser(u.id);
                          }
                        }}
                        className="p-1.5 text-zinc-500 hover:text-rose-400 hover:bg-rose-950/40 rounded-lg transition-colors cursor-pointer"
                        title="Excluir Usuário"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* CREATE NEW USER MODAL */}
      {isAddModalOpen && (
        <div
          onClick={() => setIsAddModalOpen(false)}
          className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4"
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="bg-zinc-950 border border-zinc-800 rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl"
          >
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <div className="flex items-center space-x-2 text-xs font-bold text-zinc-100 uppercase tracking-wider">
                <UserPlus className="w-4 h-4 text-blue-400" />
                <span>Cadastrar Novo Usuário / Advogado</span>
              </div>
              <button
                onClick={() => setIsAddModalOpen(false)}
                className="text-zinc-400 hover:text-zinc-200 p-1 cursor-pointer"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateUser} className="space-y-3 text-xs">
              <div>
                <label className="block text-zinc-300 mb-1 font-medium">Nome Completo</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Ex: Dra. Patrícia Lima"
                  className="w-full bg-zinc-900 border border-zinc-800 rounded-xl px-3 py-2 text-zinc-100 focus:outline-none focus:border-blue-500"
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-zinc-300 mb-1 font-medium">Registro OAB</label>
                  <input
                    type="text"
                    value={oabNumber}
                    onChange={(e) => setOabNumber(e.target.value)}
                    placeholder="Ex: OAB/SP 123.456"
                    className="w-full bg-zinc-900 border border-zinc-800 rounded-xl px-3 py-2 text-zinc-100 font-mono focus:outline-none focus:border-blue-500"
                    required
                  />
                </div>

                <div>
                  <label className="block text-zinc-300 mb-1 font-medium">Papel de Acesso (RBAC)</label>
                  <select
                    value={role}
                    onChange={(e) => setRole(e.target.value as UserRole)}
                    className="w-full bg-zinc-900 border border-zinc-800 rounded-xl px-3 py-2 text-zinc-100 focus:outline-none focus:border-blue-500"
                  >
                    <option value="SUPER_ADMIN">SUPER_ADMIN (Master)</option>
                    <option value="SOCIO">Sócio / Administrador</option>
                    <option value="ASSOCIADO">Advogado Associado</option>
                    <option value="ESTAGIARIO">Estagiário de Direito</option>
                    <option value="SECRETARIA">Secretaria / Financeiro</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-zinc-300 mb-1 font-medium">E-mail Profissional</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="exemplo@advocacia.com.br"
                  className="w-full bg-zinc-900 border border-zinc-800 rounded-xl px-3 py-2 text-zinc-100 focus:outline-none focus:border-blue-500"
                  required
                />
              </div>

              <div>
                <label className="block text-zinc-300 mb-1 font-medium">Razão Social do Escritório</label>
                <input
                  type="text"
                  value={officeName}
                  onChange={(e) => setOfficeName(e.target.value)}
                  className="w-full bg-zinc-900 border border-zinc-800 rounded-xl px-3 py-2 text-zinc-100 focus:outline-none focus:border-blue-500"
                  required
                />
              </div>

              <div className="pt-3 flex justify-end space-x-2">
                <button
                  type="button"
                  onClick={() => setIsAddModalOpen(false)}
                  className="px-4 py-2 bg-zinc-900 hover:bg-zinc-800 text-zinc-300 rounded-xl text-xs font-semibold border border-zinc-800 cursor-pointer"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-semibold shadow-lg shadow-blue-950 cursor-pointer"
                >
                  Salvar Usuário
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
