import type { Metadata, Viewport } from "next";
import { UserProvider } from "@/context/user-context";
import { PwaProvider } from "@/components/pwa-provider";
import { AiAssistant } from "@/components/ai-assistant";
import { themeInitializationScript } from "@/lib/theme";
import "./globals.css";

export const metadata: Metadata = {
  title: "LexFlow — Central do Advogado",
  description: "Gestão do escritório, consulta aos casos e produção documental em um só lugar.",
  applicationName: "LexFlow",
  appleWebApp: { capable: true, title: "LexFlow", statusBarStyle: "default" },
  icons: { icon: "/icons/icon-192.png", apple: "/icons/apple-touch-icon.png" },
};

export const viewport: Viewport = { themeColor: "#09090b", width: "device-width", initialScale: 1, viewportFit: "cover" };

import CommandPalette from "@/components/ui/command-palette";

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="pt-BR" suppressHydrationWarning>
      <body className="min-h-screen bg-zinc-950 font-sans text-zinc-100">
        <script dangerouslySetInnerHTML={{ __html: themeInitializationScript }} />
        <UserProvider>
          <PwaProvider>
          {children}
          <CommandPalette />
          <AiAssistant />
          </PwaProvider>
        </UserProvider>
      </body>
    </html>
  );
}
