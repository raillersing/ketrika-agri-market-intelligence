import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Ketrika Agri Market Intelligence",
  description: "Plateforme de veille de marché sur les produits PPN vivriers à Madagascar",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="fr">
      <body className="antialiased">{children}</body>
    </html>
  );
}
