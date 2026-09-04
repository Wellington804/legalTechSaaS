"use client";

import { api, ApiError, SESSION_EXPIRED_EVENT, SESSION_RESTORED_EVENT } from "@/lib/api-client";
import { clearBrowserPush } from "@/lib/pwa";
import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";

export type UserRole = "SUPER_ADMIN" | "SOCIO" | "ASSOCIADO" | "ESTAGIARIO" | "SECRETARIA";

export function isOfficeAdminRole(role: UserRole) {
  return role === "SUPER_ADMIN" || role === "SOCIO";
}

export interface UserProfile {
  id: string;
  tenantId?: string;
  permissionRole?: string;
  name: string;
  oabNumber: string;
  role: UserRole;
  email: string;
  officeName: string;
  avatarInitials: string;
  status: "ACTIVE" | "INACTIVE";
  createdAt: string;
  securitySetupRequired?: boolean;
}

interface ApiProfile {
  user_id: string;
  user_name: string;
  email: string;
  role: string;
  tenant_id: string;
  tenant_name?: string;
  oab_number?: string;
  mfa_required?: boolean;
  email_verification_required?: boolean;
}

interface UserContextType {
  user: UserProfile;
  usersList: UserProfile[];
  isLoggedIn: boolean;
  isLoading: boolean;
  requiresReauth: boolean;
  authError: string | null;
  setUser: (user: UserProfile) => void;
  updateUser: (fields: Partial<UserProfile>) => void;
  switchUserById: (id: string) => void;
  addUser: (newUser: Omit<UserProfile, "id" | "createdAt" | "status" | "avatarInitials">) => void;
  updateUserRole: (userId: string, newRole: UserRole) => void;
  toggleUserStatus: (userId: string) => void;
  deleteUser: (userId: string) => void;
  login: (email: string, password: string, otpCode?: string, rememberMe?: boolean) => Promise<boolean>;
  logout: () => Promise<void>;
  discardSessionDrafts: () => Promise<void>;
  drafts: Map<string, unknown>;
  isLoginModalOpen: boolean;
  setIsLoginModalOpen: (open: boolean) => void;
}

const anonymousUser: UserProfile = {
  id: "",
  name: "Usuário",
  oabNumber: "",
  role: "ASSOCIADO",
  email: "",
  officeName: "",
  avatarInitials: "U",
  status: "INACTIVE",
  createdAt: "",
};

function mapRole(role: string): UserRole {
  const normalized = role.trim().toUpperCase();
  if (normalized === "ADMIN" || normalized === "PARTNER") return "SOCIO";
  if (normalized === "LAWYER") return "ASSOCIADO";
  if (normalized === "PARALEGAL") return "ESTAGIARIO";
  if (["SUPER_ADMIN", "SOCIO", "ASSOCIADO", "ESTAGIARIO", "SECRETARIA"].includes(normalized)) return normalized as UserRole;
  return "ASSOCIADO";
}

function mapProfile(profile: ApiProfile): UserProfile {
  const initials = profile.user_name.split(" ").filter(Boolean).slice(0, 2).map((part) => part[0].toUpperCase()).join("");
  return {
    id: profile.user_id,
    tenantId: profile.tenant_id,
    permissionRole: profile.role,
    name: profile.user_name,
    oabNumber: profile.oab_number || "",
    role: mapRole(profile.role),
    email: profile.email,
    officeName: profile.tenant_name || "Escritório",
    avatarInitials: initials || "U",
    status: "ACTIVE",
    createdAt: "",
    securitySetupRequired: Boolean(profile.mfa_required || profile.email_verification_required),
  };
}

const UserContext = createContext<UserContextType | undefined>(undefined);

export function UserProvider({ children }: { children: React.ReactNode }) {
  const [user, setUserState] = useState<UserProfile>(anonymousUser);
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [authError, setAuthError] = useState<string | null>(null);
  const [isLoginModalOpen, setIsLoginModalOpen] = useState(false);
  const [requiresReauth, setRequiresReauth] = useState(false);
  const drafts = useRef(new Map<string, unknown>());
  const draftOwner = useRef("");

  const applyProfile = useCallback((profile: ApiProfile) => {
    const owner = `${profile.tenant_id}:${profile.user_id}:${profile.role}`;
    if (draftOwner.current !== owner) drafts.current.clear();
    draftOwner.current = owner;
    setUserState(mapProfile(profile));
    setIsLoggedIn(true);
    setRequiresReauth(false);
    setAuthError(null);
  }, []);

  useEffect(() => {
    let active = true;
    api.get<ApiProfile>("/auth/me")
      .then((profile) => {
        if (active) applyProfile(profile);
      })
      .catch(() => {
        if (active) {
          setUserState(anonymousUser);
          setIsLoggedIn(false);
        }
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });
    return () => { active = false; };
  }, [applyProfile]);

  useEffect(() => {
    const expire = () => { if (isLoggedIn) { setRequiresReauth(true); setIsLoginModalOpen(true); setAuthError("Sua sessão expirou. Entre novamente com a mesma conta para continuar com o rascunho."); } };
    window.addEventListener(SESSION_EXPIRED_EVENT, expire);
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, expire);
  }, [isLoggedIn]);

  const login = useCallback(async (email: string, password: string, otpCode?: string, rememberMe = false) => {
    setAuthError(null);
    try {
      const profile = await api.post<ApiProfile>("/auth/login", { email, password, otp_code: otpCode || undefined, remember_me: rememberMe });
      if (requiresReauth && (profile.user_id !== user.id || profile.tenant_id !== user.tenantId)) {
        // Never reveal the old form to another identity, even if an unexpected account is returned.
        drafts.current.clear(); draftOwner.current = ""; setUserState(anonymousUser); setIsLoggedIn(false); setRequiresReauth(false);
        await api.post("/auth/logout", {}).catch(() => {});
        setAuthError("A identidade mudou. Os rascunhos anteriores foram descartados por segurança. Entre novamente.");
        return false;
      }
      applyProfile(profile);
      if (requiresReauth) window.dispatchEvent(new Event(SESSION_RESTORED_EVENT));
      setIsLoginModalOpen(false);
      return true;
    } catch (error) {
      setAuthError(error instanceof ApiError && error.status === 401
        ? error.message
        : "Não foi possível autenticar. Verifique a conexão e tente novamente.");
      return false;
    }
  }, [applyProfile, requiresReauth, user.id, user.tenantId]);

  const discardSessionDrafts = useCallback(async () => {
    await clearBrowserPush().catch(() => {});
    await api.post("/auth/logout", {}).catch(() => {});
    drafts.current.clear(); draftOwner.current = ""; setUserState(anonymousUser); setIsLoggedIn(false); setRequiresReauth(false); setIsLoginModalOpen(true); setAuthError(null);
  }, []);

  const logout = useCallback(async () => {
    setAuthError(null);
    try {
      await clearBrowserPush().catch(() => {});
      await api.post<void>("/auth/logout", {});
      drafts.current.clear(); draftOwner.current = "";
      setUserState(anonymousUser);
      setIsLoggedIn(false);
      setRequiresReauth(false);
      setIsLoginModalOpen(true);
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        drafts.current.clear(); draftOwner.current = ""; setUserState(anonymousUser); setIsLoggedIn(false); setRequiresReauth(false); setIsLoginModalOpen(true); return;
      }
      setAuthError("Não foi possível encerrar a sessão. Tente novamente.");
      setIsLoginModalOpen(true);
    }
  }, []);

  const blockedMutation = useCallback(() => {
    setAuthError("Gestão de usuários e edição de perfil indisponíveis nesta versão.");
    setIsLoginModalOpen(true);
  }, []);
  const value = useMemo<UserContextType>(() => ({
    user,
    usersList: isLoggedIn ? [user] : [],
    isLoggedIn,
    isLoading,
    requiresReauth,
    authError,
    setUser: blockedMutation,
    updateUser: blockedMutation,
    switchUserById: blockedMutation,
    addUser: blockedMutation,
    updateUserRole: blockedMutation,
    toggleUserStatus: blockedMutation,
    deleteUser: blockedMutation,
    login,
    logout,
    discardSessionDrafts,
    drafts: drafts.current,
    isLoginModalOpen,
    setIsLoginModalOpen,
  }), [authError, blockedMutation, discardSessionDrafts, isLoading, isLoggedIn, isLoginModalOpen, login, logout, requiresReauth, user]);

  return <UserContext.Provider value={value}>{children}</UserContext.Provider>;
}

export function useUser() {
  const context = useContext(UserContext);
  if (!context) throw new Error("useUser deve ser usado dentro de UserProvider");
  return context;
}
