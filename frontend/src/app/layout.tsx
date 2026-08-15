import type { Metadata } from "next";
import { Inter, Playfair_Display, Outfit, JetBrains_Mono } from "next/font/google";
import { UserProvider } from "@/context/user-context";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const playfair = Playfair_Display({
  subsets: ["latin"],
  variable: "--font-playfair",
  display: "swap",
});

const outfit = Outfit({
  subsets: ["latin"],
  variable: "--font-outfit",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "LexFlow Enterprise - SaaS LegalTech & Hub OAB",
  description: "Plataforma SaaS Enterprise para Escritórios de Advocacia, Gestão Jurídica e Iniciação Profissional OAB.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="pt-BR" className={`dark ${inter.variable} ${playfair.variable} ${outfit.variable} ${jetbrainsMono.variable}`}>
      <body className={`${inter.className} bg-zinc-950 text-zinc-100 min-h-screen`}>
        <UserProvider>
          {children}
        </UserProvider>
      </body>
    </html>
  );
}
