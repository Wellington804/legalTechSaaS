"use client";

import { LoginModal } from "./login-modal";
import { useUser } from "@/context/user-context";
import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, isLoggedIn, isLoading, requiresReauth } = useUser(); const pathname = usePathname(); const router = useRouter();
  const setupRequired = isLoggedIn && user.securitySetupRequired && pathname !== "/dashboard/account";
  useEffect(() => { if (setupRequired) router.replace("/dashboard/account"); }, [setupRequired, router]);
  if (isLoading || !isLoggedIn) return <LoginModal />;
  if (setupRequired) return <p role="status" className="p-6">Conclua a verificação de e-mail e segurança da conta para acessar o escritório.</p>;
  // A hidden, still-mounted tree preserves same-user drafts while excluding them from focus/a11y.
  return <><div key={`${user.tenantId}:${user.id}:${user.permissionRole}`} hidden={requiresReauth}>{children}</div><LoginModal /></>;
}
