export type NavigationIcon = "overview" | "prices" | "map" | "trade" | "economy" | "climate" | "assistant" | "alerts" | "bulletins" | "sources" | "review" | "system" | "about";

export interface NavigationPage {
  href: string;
  label: string;
  description: string;
  group: "Vue d'ensemble" | "Explorer" | "Analyser" | "Suivre" | "Gestion des données" | "Informations";
  icon: NavigationIcon;
  keywords: string;
}

export const NAVIGATION_PAGES: readonly NavigationPage[] = [
  { href: "/", label: "Vue d'ensemble", description: "Veille des marchés vivriers", group: "Vue d'ensemble", icon: "overview", keywords: "accueil tableau de bord" },
  { href: "/prices", label: "Prix vivriers", description: "Séries disponibles et nature des valeurs", group: "Explorer", icon: "prices", keywords: "prix séries observations" },
  { href: "/map", label: "Territoires", description: "Prix par territoire ; carte en préparation", group: "Explorer", icon: "map", keywords: "carte territoires régions lieux" },
  { href: "/trade", label: "Commerce extérieur", description: "Données disponibles sur les échanges", group: "Explorer", icon: "trade", keywords: "importations exportations douanes" },
  { href: "/economy", label: "Économie", description: "Indicateurs et disponibilité des séries", group: "Analyser", icon: "economy", keywords: "conjoncture macroéconomie" },
  { href: "/climate", label: "Climat et cultures", description: "Données climatiques et état de qualification", group: "Analyser", icon: "climate", keywords: "météo agriculture pluie" },
  { href: "/copilot", label: "Assistant", description: "Questions sur les données disponibles", group: "Analyser", icon: "assistant", keywords: "copilote analyste questions" },
  { href: "/alerts", label: "Alertes", description: "Alertes enregistrées et suivi", group: "Suivre", icon: "alerts", keywords: "notifications incidents" },
  { href: "/bulletins", label: "Bulletins", description: "Brouillons et publications disponibles", group: "Suivre", icon: "bulletins", keywords: "rapports publications" },
  { href: "/sources", label: "Sources", description: "Origine et état des données", group: "Gestion des données", icon: "sources", keywords: "qualité provenance collecte dataops" },
  { href: "/admin/review", label: "À vérifier", description: "Revue des éléments en attente", group: "Gestion des données", icon: "review", keywords: "revue anomalies validation" },
  { href: "/system", label: "Système", description: "État et configuration de la plateforme", group: "Gestion des données", icon: "system", keywords: "architecture plateforme infrastructure" },
  { href: "/about", label: "À propos", description: "Irooa et son entreprise mère Ketrikay", group: "Informations", icon: "about", keywords: "entreprise société irooa ketrikay ketrikai" },
];

export const PRIMARY_NAVIGATION_GROUPS = ["Explorer", "Analyser", "Suivre"] as const;

function normalizedPath(path: string): string {
  return path.split(/[?#]/)[0].replace(/\/+$/, "") || "/";
}

export function isNavigationPageActive(pathname: string, href: string): boolean {
  const path = normalizedPath(pathname);
  return href === "/" ? path === "/" : path === href || path.startsWith(`${href}/`);
}

export function findNavigationPage(pathname: string): NavigationPage | undefined {
  return NAVIGATION_PAGES.find(page => isNavigationPageActive(pathname, page.href));
}

function searchable(value: string): string {
  return value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[’']/g, " ").toLowerCase();
}

export function searchNavigationPages(query: string): readonly NavigationPage[] {
  const words = searchable(query).trim().split(/\s+/).filter(Boolean);
  return NAVIGATION_PAGES.filter(page => {
    const text = searchable(`${page.label} ${page.group} ${page.keywords}`);
    return words.every(word => text.includes(word));
  });
}
