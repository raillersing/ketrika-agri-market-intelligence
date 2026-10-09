import type { Metadata } from "next";
import "./globals.css";
import { AppShell } from "@/components/layout/AppShell";

export const metadata: Metadata = {
  title: "Ketrika Agri Market Intelligence",
  description:
    "Plateforme officielle de veille et d'analyse de marché sur les produits PPN vivriers à Madagascar.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="fr" className="dark">
      <body className="antialiased font-sans bg-background text-foreground min-h-screen selection:bg-emerald-500/20 selection:text-emerald-300">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
