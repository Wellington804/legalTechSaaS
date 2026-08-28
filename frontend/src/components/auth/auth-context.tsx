"use client";

import React, { createContext, useContext, useState, useEffect } from "react";

export interface UserSession {
  user_id: string;
  user_name: string;
  email: string;
  role: string;
  tenant_id: string;
  oab_number?: string;
  oab_uf?: string;
  access_token: string;
}

interface AuthContextType {
  user: UserSession | null;
  token: string | null;
  loading: boolean;
  loginSession: (sessionData: UserSession) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const AUTH_STORAGE_KEY = "lexflow_auth_session";

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserSession | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    try {
      const storedSession = localStorage.getItem(AUTH_STORAGE_KEY);
      if (storedSession) {
        const parsed = JSON.parse(storedSession);
        setUser(parsed);
      }
    } catch (e) {
      console.error("Erro ao carregar sessão:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  const loginSession = (sessionData: UserSession) => {
    setUser(sessionData);
    localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(sessionData));
  };

  const logout = () => {
    setUser(null);
    localStorage.removeItem(AUTH_STORAGE_KEY);
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token: user?.access_token || null,
        loading,
        loginSession,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth deve ser utilizado dentro de um AuthProvider");
  }
  return context;
}
