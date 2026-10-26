import type { Metadata } from "next";
import "./globals.css";
import { AppShell } from "@/components/layout/AppShell";
import { BRAND } from "@/lib/brand";
import { ThemeProvider } from "@/components/theme/ThemeProvider";
import { THEME_INIT_SCRIPT } from "@/lib/theme";

export const metadata: Metadata = {
  title: BRAND.name,
  description:
    "Veille et exploration des données disponibles sur les marchés vivriers à Madagascar.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="fr" suppressHydrationWarning>
      <head><script id="irooa-theme" dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} /></head>
      <body className="antialiased font-sans bg-background text-foreground min-h-screen selection:bg-emerald-500/20 selection:text-primary-readable">
        <ThemeProvider><AppShell>{children}</AppShell></ThemeProvider>
      </body>
    </html>
  );
}
