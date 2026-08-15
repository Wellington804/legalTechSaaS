"use client";

import React, { createContext, useContext, useState, useEffect } from "react";

export type UserRole = "SUPER_ADMIN" | "SOCIO" | "ASSOCIADO" | "ESTAGIARIO" | "SECRETARIA";

export interface UserProfile {
  id: string;
  name: string;
  oabNumber: string;
  role: UserRole;
  email: string;
  officeName: string;
  avatarInitials: string;
  status: "ACTIVE" | "INACTIVE";
  createdAt: string;
}

export const defaultUsers: UserProfile[] = [
  {
    id: "user-super",
    name: "Dr. Wil Shaffer (Super Usuário)",
    oabNumber: "OAB/SP 00.001-MASTER",
    role: "SUPER_ADMIN",
    email: "super.admin@lexflow.law",
    officeName: "LEXFLOW ENTERPRISE MASTER HQ",
    avatarInitials: "WS",
    status: "ACTIVE",
    createdAt: "01/01/2026",
  },
  {
    id: "user-1",
    name: "Dra. Carolina Silva",
    oabNumber: "OAB/DF 12.345",
    role: "SOCIO",
    email: "carolina@silvaeassociados.adv.br",
    officeName: "SILVA & ASSOCIADOS ADVOCACIA",
    avatarInitials: "CS",
    status: "ACTIVE",
    createdAt: "10/01/2026",
  },
  {
    id: "user-2",
    name: "Dr. Alexandre Rossi",
    oabNumber: "OAB/SP 458.912",
    role: "ASSOCIADO",
    email: "alexandre@rossi.adv.br",
    officeName: "ROSSI & ASSOCIADOS ADVOCACIA",
    avatarInitials: "AR",
    status: "ACTIVE",
    createdAt: "15/02/2026",
  },
  {
    id: "user-3",
    name: "Lucas Mendes (Estagiário)",
    oabNumber: "OAB/DF 99.111-E",
    role: "ESTAGIARIO",
    email: "lucas.estagio@silvaeassociados.adv.br",
    officeName: "SILVA & ASSOCIADOS ADVOCACIA",
    avatarInitials: "LM",
    status: "ACTIVE",
    createdAt: "01/03/2026",
  },
  {
    id: "user-4",
    name: "Mariana Costa (Secretaria)",
    oabNumber: "SEC-9082",
    role: "SECRETARIA",
    email: "atendimento@silvaeassociados.adv.br",
    officeName: "SILVA & ASSOCIADOS ADVOCACIA",
    avatarInitials: "MC",
    status: "ACTIVE",
    createdAt: "10/04/2026",
  },
];

interface UserContextType {
  user: UserProfile;
  usersList: UserProfile[];
  isLoggedIn: boolean;
  setUser: (user: UserProfile) => void;
  updateUser: (fields: Partial<UserProfile>) => void;
  switchUserById: (id: string) => void;
  addUser: (newUser: Omit<UserProfile, "id" | "createdAt" | "status" | "avatarInitials">) => void;
  updateUserRole: (userId: string, newRole: UserRole) => void;
  toggleUserStatus: (userId: string) => void;
  deleteUser: (userId: string) => void;
  login: (email: string) => boolean;
  logout: () => void;
  isLoginModalOpen: boolean;
  setIsLoginModalOpen: (open: boolean) => void;
}

const UserContext = createContext<UserContextType | undefined>(undefined);

export function UserProvider({ children }: { children: React.ReactNode }) {
  const [usersList, setUsersList] = useState<UserProfile[]>(defaultUsers);
  const [user, setUserState] = useState<UserProfile>(defaultUsers[0]);
  const [isLoggedIn, setIsLoggedIn] = useState(true);
  const [isLoginModalOpen, setIsLoginModalOpen] = useState(false);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const savedList = localStorage.getItem("lexflow_users_list");
      const savedUser = localStorage.getItem("lexflow_active_user");
      const savedLoggedIn = localStorage.getItem("lexflow_is_logged_in");

      if (savedList) {
        try {
          setUsersList(JSON.parse(savedList));
        } catch (e) {}
      }

      if (savedUser) {
        try {
          setUserState(JSON.parse(savedUser));
        } catch (e) {}
      }

      if (savedLoggedIn !== null) {
        setIsLoggedIn(savedLoggedIn === "true");
      }
    }
  }, []);

  const saveUsersList = (list: UserProfile[]) => {
    setUsersList(list);
    if (typeof window !== "undefined") {
      localStorage.setItem("lexflow_users_list", JSON.stringify(list));
    }
  };

  const setUser = (newUser: UserProfile) => {
    setUserState(newUser);
    setIsLoggedIn(true);
    if (typeof window !== "undefined") {
      localStorage.setItem("lexflow_active_user", JSON.stringify(newUser));
      localStorage.setItem("lexflow_user_role", newUser.role);
      localStorage.setItem("lexflow_is_logged_in", "true");
      window.dispatchEvent(new CustomEvent("userChanged", { detail: newUser }));
      window.dispatchEvent(new CustomEvent("roleChanged", { detail: newUser.role }));
    }
  };

  const updateUser = (fields: Partial<UserProfile>) => {
    const updated = { ...user, ...fields };
    setUser(updated);

    const updatedList = usersList.map((u) => (u.id === user.id ? updated : u));
    saveUsersList(updatedList);
  };

  const switchUserById = (id: string) => {
    const found = usersList.find((u) => u.id === id);
    if (found) {
      setUser(found);
    }
  };

  const addUser = (userData: Omit<UserProfile, "id" | "createdAt" | "status" | "avatarInitials">) => {
    const initials = userData.name
      .split(" ")
      .filter(Boolean)
      .slice(0, 2)
      .map((n) => n[0].toUpperCase())
      .join("");

    const newUser: UserProfile = {
      ...userData,
      id: `user-${Date.now()}`,
      status: "ACTIVE",
      createdAt: new Date().toLocaleDateString("pt-BR"),
      avatarInitials: initials || "ADV",
    };

    const updatedList = [newUser, ...usersList];
    saveUsersList(updatedList);
  };

  const updateUserRole = (userId: string, newRole: UserRole) => {
    const updatedList = usersList.map((u) => (u.id === userId ? { ...u, role: newRole } : u));
    saveUsersList(updatedList);
    if (user.id === userId) {
      updateUser({ role: newRole });
    }
  };

  const toggleUserStatus = (userId: string) => {
    const updatedList: UserProfile[] = usersList.map((u) =>
      u.id === userId ? { ...u, status: (u.status === "ACTIVE" ? "INACTIVE" : "ACTIVE") as "ACTIVE" | "INACTIVE" } : u
    );
    saveUsersList(updatedList);
  };

  const deleteUser = (userId: string) => {
    const updatedList = usersList.filter((u) => u.id !== userId);
    saveUsersList(updatedList);
  };

  const login = (email: string) => {
    const found = usersList.find((u) => u.email.toLowerCase() === email.toLowerCase());
    if (found) {
      setUser(found);
      return true;
    }
    // Se não encontrar, entra como Super Usuário Master por padrão
    setUser(defaultUsers[0]);
    return true;
  };

  const logout = () => {
    setIsLoggedIn(false);
    if (typeof window !== "undefined") {
      localStorage.setItem("lexflow_is_logged_in", "false");
    }
    setIsLoginModalOpen(true);
  };

  return (
    <UserContext.Provider
      value={{
        user,
        usersList,
        isLoggedIn,
        setUser,
        updateUser,
        switchUserById,
        addUser,
        updateUserRole,
        toggleUserStatus,
        deleteUser,
        login,
        logout,
        isLoginModalOpen,
        setIsLoginModalOpen,
      }}
    >
      {children}
    </UserContext.Provider>
  );
}

export function useUser() {
  const context = useContext(UserContext);
  if (!context) {
    throw new Error("useUser deve ser usado dentro de um UserProvider");
  }
  return context;
}
