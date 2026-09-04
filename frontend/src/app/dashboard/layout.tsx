import React from "react";
import { Sidebar } from "@/components/layout/sidebar";
import { Header } from "@/components/layout/header";
import { ProtectedRoute } from "@/components/layout/protected-route";
import { ConnectivityNotice } from "@/components/workspace/shared";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ProtectedRoute>
      <a href="#main-content" className="sr-only z-[100] rounded-lg bg-blue-600 px-4 py-3 text-white focus:not-sr-only focus:fixed focus:left-4 focus:top-4">Pular para o conteúdo</a>
      <div className="flex h-dvh flex-col overflow-hidden bg-zinc-950 text-zinc-100 antialiased selection:bg-blue-600 selection:text-white md:h-auto md:min-h-screen md:flex-row md:overflow-visible">
        <Sidebar />
        <div className="order-1 flex min-h-0 min-w-0 flex-1 flex-col md:order-none">
          <Header />
          <main id="main-content" tabIndex={-1} className="min-h-0 min-w-0 flex-1 overflow-y-auto px-4 py-6 md:overflow-visible md:p-8"><ConnectivityNotice />{children}</main>
        </div>
      </div>
    </ProtectedRoute>
  );
}

