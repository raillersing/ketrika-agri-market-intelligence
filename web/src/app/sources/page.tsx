"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  AlertCircle,
  ArrowRight,
  BookOpen,
  Calendar,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Clock,
  Compass,
  Database,
  ExternalLink,
  Filter,
  Flame,
  Globe,
  HelpCircle,
  Layers,
  LayoutGrid,
  List,
  RefreshCw,
  Search,
  Server,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  X,
  Zap,
} from "lucide-react";

import { freshnessLabel, freshnessSummary, measuredFreshness, recomputeIndicators } from "../../lib/sources-state";
import { ManualCollectionStatus, useManualCollection } from "../../components/ManualCollection";

interface SourceItem {
  sourceId: string;
  name: string;
  priority: string;
  status: string;
  freshnessSlaDays?: number;
  freshnessDays?: number;
  isStale?: boolean | null;
  latestRunStatus?: string;
  lastRunStartedAt?: string;
}

interface SourceRunItem {
  run_id: string;
  source_id: string;
  source_name?: string;
  status: string;
  started_at: string;
  finished_at?: string;
  duration_seconds?: number;
  n_records: number | null;
  n_fetched: number | null;
  error?: string;
}

// Catégories riches pour utilisateur non technique
interface SourceMeta {
  category: "rice" | "economy" | "climate" | "global";
  institution: string;
  products: string[];
  description: string;
  cadenceHuman: string;
  icon: string;
}

const SOURCES_METADATA: Record<string, SourceMeta> = {
  miasa_odr: {
    category: "rice",
    institution: "Ministère de l'Agriculture & Observatoire du Riz (ODR)",
    products: ["Riz blanc Vary Gasy", "Makalioka", "Tsipala", "Riz paddy", "Riz importé 25%"],
    description: "Disponibilité et couverture à vérifier dans les publications de cette source.",
    cadenceHuman: "Selon publication",
    icon: "🌾",
  },
  market_supply: {
    category: "rice",
    institution: "Observatoire du Riz & Direction Régionale du Commerce",
    products: ["Arrivages de riz", "Stocks de sécurité", "Maïs grain", "Manioc sec"],
    description: "Disponibilité et couverture à vérifier dans les publications de cette source.",
    cadenceHuman: "Selon publication",
    icon: "🚛",
  },
  mincc_ppn: {
    category: "rice",
    institution: "Ministère du Commerce et de la Consommation (MinCC)",
    products: ["Sucre roux & blanc", "Huile de palme/soja", "Farine de blé", "Riz local"],
    description: "Disponibilité et couverture à vérifier dans les publications de cette source.",
    cadenceHuman: "Selon publication",
    icon: "📦",
  },
  wfp_hdx_mdg: {
    category: "global",
    institution: "Programme Alimentaire Mondial (PAM / WFP)",
    products: ["Riz", "Maïs", "Manioc", "Haricots", "Huile alimentaire"],
    description: "Disponibilité et couverture à vérifier dans les publications de cette source.",
    cadenceHuman: "Selon publication",
    icon: "🌍",
  },
  bfm_public: {
    category: "economy",
    institution: "Banky Foiben'i Madagasikara (Banque Centrale BCM)",
    products: ["Taux de change USD/MGA", "EUR/MGA", "Marché Interbancaire de Devises (MID)"],
    description: "Disponibilité et couverture à vérifier dans les publications de cette source.",
    cadenceHuman: "Selon publication",
    icon: "💵",
  },
  douanes_stats: {
    category: "economy",
    institution: "Direction Générale des Douanes Malagasy",
    products: ["Importations de riz (HS 1006)", "Farine (HS 1101)", "Huiles brutes et raffinées"],
    description: "Disponibilité et couverture à vérifier dans les publications de cette source.",
    cadenceHuman: "Selon publication",
    icon: "🚢",
  },
  instat_nipc: {
    category: "economy",
    institution: "Institut National de la Statistique (INSTAT)",
    products: ["Indice des Prix à la Consommation (NIPC)", "Inflation alimentaire vivrière"],
    description: "Disponibilité et couverture à vérifier dans les publications de cette source.",
    cadenceHuman: "Selon publication",
    icon: "📈",
  },
  instat_tbe: {
    category: "economy",
    institution: "INSTAT – Tableau de Bord de l'Économie (TBE)",
    products: ["Indicateurs macroéconomiques", "Production agricole trimestrielle"],
    description: "Disponibilité et couverture à vérifier dans les publications de cette source.",
    cadenceHuman: "Selon publication",
    icon: "📊",
  },
  omh_public: {
    category: "economy",
    institution: "Office Malgache des Hydrocarbures (OMH)",
    products: ["Gas-oil transport", "Super carburant", "Pétrole lampant"],
    description: "Disponibilité et couverture à vérifier dans les publications de cette source.",
    cadenceHuman: "Selon publication",
    icon: "⛽",
  },
  nasa_power: {
    category: "climate",
    institution: "NASA Agroclimatology (POWER)",
    products: ["Précipitations (mm)", "Températures min/max", "Humidité relative"],
    description: "Disponibilité et couverture à vérifier dans les publications de cette source.",
    cadenceHuman: "Selon publication",
    icon: "☀️",
  },
  chirps: {
    category: "climate",
    institution: "Climate Hazards Center (CHIRPS / UCSB)",
    products: ["Précipitations satellitaires haute résolution", "Anomalies de pluie"],
    description: "Disponibilité et couverture à vérifier dans les publications de cette source.",
    cadenceHuman: "Selon publication",
    icon: "🌧️",
  },
  faostat: {
    category: "global",
    institution: "Organisation des Nations Unies pour l'Alimentation (FAO)",
    products: ["Bilan de production vivrière", "Superficies cultivées", "Rendements à l'hectare"],
    description: "Disponibilité et couverture à vérifier dans les publications de cette source.",
    cadenceHuman: "Selon publication",
    icon: "🌱",
  },
  wb_rtfp_mdg: {
    category: "global",
    institution: "Banque Mondiale (World Bank RTFP)",
    products: ["Indice des prix vivriers en temps réel", "Pression inflationniste alimentaire"],
    description: "Disponibilité et couverture à vérifier dans les publications de cette source.",
    cadenceHuman: "Selon publication",
    icon: "🏛️",
  },
};

const CATEGORIES = [
  { id: "all", label: "Toutes les sources", icon: Database },
  { id: "rice", label: "Riz & Vivres vivriers", icon: Flame },
  { id: "economy", label: "Devises & Économie", icon: TrendingUp },
  { id: "climate", label: "Météo & Climat", icon: Globe },
  { id: "global", label: "Bailleurs & International", icon: Compass },
];

export default function SourcesPage() {
  const [sources, setSources] = useState<SourceItem[]>([]);
  const [runs, setRuns] = useState<SourceRunItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filtres & recherche
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("all");
  const [statusFilter, setStatusFilter] = useState<"all" | "ok" | "stale">("all");
  const [viewMode, setViewMode] = useState<"cards" | "table">("cards");

  // Guide utilisateur repliable
  const [guideOpen, setGuideOpen] = useState(true);

  // État des actualisations en cours
  const [isRefreshingAll, setIsRefreshingAll] = useState(false);
  const requestPending = useRef(false);
  const [canRefresh, setCanRefresh] = useState(false);
  const [refreshStep, setRefreshStep] = useState<string | null>(null);
  const [refreshingSourceId, setRefreshingSourceId] = useState<string | null>(null);

  // Toast notification
  const [toast, setToast] = useState<{ type: "success" | "error"; message: string } | null>(null);

  const showToast = (type: "success" | "error", message: string) => {
    setToast({ type, message });
    setTimeout(() => setToast(null), 5000);
  };

  // Chargement des sources et de l'historique
  const loadData = async () => {
    try {
      setError(null);
      const [sourcesRes, runsRes, meRes] = await Promise.all([
        fetch("/api/v1/sources", { credentials: "include" }),
        fetch("/api/v1/sources/runs", { credentials: "include" }),
        fetch("/api/v1/auth/me", { credentials: "include" }),
      ]);

      if (!sourcesRes.ok || !runsRes.ok || !meRes.ok) {
        setCanRefresh(false);
        throw new Error("Catalogue ou historique indisponible. Vérifiez votre connexion et votre session.");
      }
      setCanRefresh((await meRes.json()).role === "admin");
      if (sourcesRes.ok) {
        const raw = await sourcesRes.json();
        const items: SourceItem[] = raw.map((s: any) => ({
          sourceId: s.source_id,
          name: s.name,
          priority: s.priority || "P1",
          status: s.status ?? "unknown",
          freshnessSlaDays: s.freshness_sla_days,
          freshnessDays: s.freshness_days,
          isStale: measuredFreshness(s.freshness_days, s.is_stale),
          latestRunStatus: s.latest_run_status,
          lastRunStartedAt: s.last_run_started_at,
        }));
        setSources(items);
      }

      if (runsRes.ok) {
        const rawRuns = await runsRes.json();
        setRuns(rawRuns);
      }
    } catch (err: any) {
      setError("Impossible de joindre le service de données. Veuillez réessayer.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // A pending response is not a measured progress percentage or a completed collection.
  const handleRefreshAll = async () => {
    if (requestPending.current || !canRefresh) return;
    requestPending.current = true;
    setIsRefreshingAll(true);
    setRefreshStep("Vérification et recalcul des indicateurs existants…");
    try {
      const message = await recomputeIndicators("/api/v1/sources/refresh");
      await loadData();
      showToast("success", message);
    } catch (error) {
      showToast("error", error instanceof Error ? error.message : "Résultat non confirmé.");
    } finally {
      requestPending.current = false;
      setIsRefreshingAll(false);
      setRefreshStep(null);
    }
  };

  const collection = useManualCollection(() => { void loadData(); });
  const handleRefreshSource = async (sourceId: string) => {
    if (requestPending.current || !canRefresh || collection.busy) return;
    setRefreshingSourceId(sourceId);
    try { await collection.start(sourceId); }
    finally { setRefreshingSourceId(null); }
  };

  // Filtrage intelligent
  const filteredSources = useMemo(() => {
    return sources.filter((s) => {
      const meta = SOURCES_METADATA[s.sourceId];
      const query = searchQuery.toLowerCase().trim();

      // Filtre catégorie
      if (selectedCategory !== "all") {
        if (!meta || meta.category !== selectedCategory) return false;
      }

      // Filtre statut
      if (statusFilter === "ok" && (s.status !== "active" || s.isStale !== false)) return false;
      if (statusFilter === "stale" && (s.status !== "active" || s.isStale !== true)) return false;

      // Filtre texte
      if (!query) return true;

      const inName = s.name.toLowerCase().includes(query);
      const inId = s.sourceId.toLowerCase().includes(query);
      const inInst = meta?.institution.toLowerCase().includes(query) ?? false;
      const inProducts = meta?.products.some((p) => p.toLowerCase().includes(query)) ?? false;
      const inDesc = meta?.description.toLowerCase().includes(query) ?? false;

      return inName || inId || inInst || inProducts || inDesc;
    });
  }, [sources, searchQuery, selectedCategory, statusFilter]);

  // Statistiques d'ensemble
  const totalCount = sources.length;
  const summary = freshnessSummary(sources);
  const compliantCount = summary.fresh;

  return (
    <div className="space-y-8 animate-in fade-in duration-300 pb-12">
      {/* Toast flottant inspiré Awwwards */}
      {toast && (
        <div
          role={toast.type === "error" ? "alert" : "status"}
          aria-live="polite"
          className={`fixed bottom-6 right-6 z-50 flex items-center gap-3 px-5 py-3.5 rounded-2xl shadow-2xl backdrop-blur-xl border transition-all animate-in slide-in-from-bottom-5 ${
            toast.type === "success"
              ? "bg-emerald-950/90 text-emerald-100 border-emerald-500/40 shadow-emerald-950/60"
              : "bg-rose-950/90 text-rose-100 border-rose-500/40 shadow-rose-950/60"
          }`}
        >
          {toast.type === "success" ? (
            <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
          ) : (
            <AlertCircle className="w-5 h-5 text-rose-400 shrink-0" />
          )}
          <span className="text-xs font-medium">{toast.message}</span>
          <button
            aria-label="Fermer la notification"
            onClick={() => setToast(null)}
            className="ml-2 text-slate-400 hover:text-white transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Hero Header Awwwards-inspired */}
      <div className="relative rounded-3xl p-6 sm:p-8 bg-gradient-to-br from-slate-900/90 via-slate-950/95 to-slate-900/80 border border-white/10 shadow-2xl overflow-hidden">
        {/* Glow atmosphérique en arrière-plan */}
        <div className="absolute top-0 right-1/4 w-96 h-96 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute -bottom-10 left-10 w-80 h-80 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none" />

        <div className="relative z-10 flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">
          <div className="space-y-3 max-w-2xl">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-xs font-mono font-medium">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              Catalogue des sources • Qualification à vérifier
            </div>

            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white">
              Sources & indicateurs
            </h1>

            <p className="text-sm text-slate-300 leading-relaxed">
              Collectez les publications publiques autorisées et recalculez leurs indicateurs en{" "}
              <strong className="text-white font-semibold">1 clic</strong>, sans aucune
              manipulation technique ni code complexe.
            </p>
          </div>

          {/* Bouton d'action principal héroïque */}
          <div className="flex flex-col sm:flex-row sm:flex-wrap items-stretch sm:items-center gap-3">
            <button
              onClick={handleRefreshAll}
              disabled={isRefreshingAll || refreshingSourceId !== null || collection.busy || !canRefresh}
              className="relative group inline-flex items-center justify-center gap-2.5 px-6 py-4 rounded-2xl bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 text-white font-bold text-sm shadow-xl shadow-emerald-950/60 hover:shadow-emerald-900/80 border border-emerald-400/40 active:scale-98 transition-all disabled:opacity-60 disabled:pointer-events-none"
            >
              <RefreshCw className={`w-4 h-4 ${isRefreshingAll ? "animate-spin text-white" : "group-hover:rotate-180 transition-transform duration-500"}`} />
              <span>{isRefreshingAll ? "Recalcul en cours..." : "Recalculer les indicateurs"}</span>
              <Sparkles className="w-4 h-4 text-emerald-200 group-hover:scale-110 transition-transform" />
            </button>
            {!canRefresh && <p className="text-xs text-slate-300">Collecte et recalcul réservés aux administrateurs.</p>}
            <button
              onClick={() => collection.start()}
              disabled={!canRefresh || collection.busy || isRefreshingAll || collection.eligible.length === 0}
              className="rounded-2xl bg-cyan-500 px-5 py-4 font-bold text-slate-950 disabled:opacity-50"
            >{collection.busy ? "Collecte en cours…" : "Collecter les nouvelles données"}</button>

            <button
              aria-expanded={guideOpen}
              aria-controls="sources-guide"
              onClick={() => setGuideOpen(!guideOpen)}
              className="inline-flex items-center justify-center gap-2 px-4 py-4 rounded-2xl bg-white/[0.05] hover:bg-white/[0.08] text-slate-200 hover:text-white border border-white/10 text-xs font-medium transition-all"
            >
              <BookOpen className="w-4 h-4 text-emerald-400" />
              <span>{guideOpen ? "Masquer le guide" : "Guide utilisateur"}</span>
              {guideOpen ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            </button>
          </div>
        </div>

        {/* Indicateur de progression temps réel lors de l'actualisation globale */}
        {isRefreshingAll && (
          <div role="status" aria-live="polite" className="mt-6 pt-5 border-t border-white/10 animate-in fade-in duration-200">
            <div className="flex items-center justify-between text-xs font-mono mb-2">
              <span className="text-emerald-300 font-semibold flex items-center gap-2">
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                {refreshStep || "Traitement des données..."}
              </span>
              <span className="text-slate-400">Durée non estimée</span>
            </div>
            <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
              <div className="h-full bg-gradient-to-r from-emerald-400 via-teal-300 to-cyan-400 animate-pulse rounded-full w-full transition-all duration-500" />
            </div>
          </div>
        )}
      </div>

      <ManualCollectionStatus receipt={collection.receipt} error={collection.error} />
      {/* Guide d'utilisation très clair pour non-technicien */}
      {guideOpen && (
        <div id="sources-guide" className="glass-panel rounded-3xl p-6 sm:p-7 border border-emerald-500/20 bg-emerald-950/10 space-y-5 animate-in slide-in-from-top-3 duration-300">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="p-2 rounded-xl bg-emerald-500/20 text-emerald-300">
                <HelpCircle className="w-5 h-5" />
              </div>
              <div>
                <h2 className="text-base font-bold text-white">
                  Guide d&apos;utilisation : Collecter ou recalculer ?
                </h2>
                <p className="text-xs text-slate-400">
                  Comprendre le fonctionnement sans jargon informatique.
                </p>
              </div>
            </div>
            <span className="text-[11px] font-mono px-2.5 py-1 rounded-full bg-white/[0.06] text-slate-300">
              3 étapes claires
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-4 rounded-2xl bg-slate-900/60 border border-white/5 space-y-2">
              <div className="w-7 h-7 rounded-xl bg-emerald-500/20 text-emerald-300 font-bold text-xs flex items-center justify-center">
                1
              </div>
              <h3 className="text-xs font-bold text-white uppercase tracking-wider">
                Choisissez votre action
              </h3>
              <p className="text-xs text-slate-300 leading-relaxed">
                Cliquez sur <strong className="text-emerald-300">« Collecter les nouvelles données »</strong> pour les sources autorisées, ou « Collecter » sur une carte. « Recalculer les indicateurs » utilise seulement les données déjà présentes.
              </p>
            </div>

            <div className="p-4 rounded-2xl bg-slate-900/60 border border-white/5 space-y-2">
              <div className="w-7 h-7 rounded-xl bg-teal-500/20 text-teal-300 font-bold text-xs flex items-center justify-center">
                2
              </div>
              <h3 className="text-xs font-bold text-white uppercase tracking-wider">
                Vérification avant publication
              </h3>
              <p className="text-xs text-slate-300 leading-relaxed">
                La collecte télécharge les documents publics, les archive puis contrôle et intègre leurs données. La publication des indicateurs peut être refusée si les preuves sont insuffisantes.
              </p>
            </div>

            <div className="p-4 rounded-2xl bg-slate-900/60 border border-white/5 space-y-2">
              <div className="w-7 h-7 rounded-xl bg-cyan-500/20 text-cyan-300 font-bold text-xs flex items-center justify-center">
                3
              </div>
              <h3 className="text-xs font-bold text-white uppercase tracking-wider">
                Consultez le résultat
              </h3>
              <p className="text-xs text-slate-300 leading-relaxed">
                Suivez les étapes réelles et le résultat par source. Le suivi reste disponible après rechargement. Aucun nombre ne garantit une fraîcheur universelle ; les bulletins ne sont pas régénérés.
              </p>
            </div>
          </div>

          <div className="pt-2 text-xs text-slate-400 flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-t border-white/5">
            <p className="flex items-center gap-1.5">
              <Zap className="w-4 h-4 text-amber-400 shrink-0" />
              <span>
                <strong>Bon à savoir :</strong> Une source peut ne publier aucun nouveau document ou refuser l’accès. Une collecte interrompue n’est jamais relancée automatiquement.
              </span>
            </p>
          </div>
        </div>
      )}

      {/* Cartes de métriques de santé des données */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="glass-card rounded-2xl p-4 sm:p-5 flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 shrink-0">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <div>
            <p className="text-xs text-slate-400 font-medium">Sources enregistrées</p>
            <p className="text-xl sm:text-2xl font-extrabold text-white">{totalCount}</p>
            <p className="text-[11px] text-emerald-400 mt-0.5">Qualification selon les preuves disponibles</p>
          </div>
        </div>

        <div className="glass-card rounded-2xl p-4 sm:p-5 flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-teal-500/10 border border-teal-500/20 flex items-center justify-center text-teal-400 shrink-0">
            <CheckCircle2 className="w-6 h-6" />
          </div>
          <div>
            <p className="text-xs text-slate-400 font-medium">Conformité aux délais</p>
            <p className="text-xl sm:text-2xl font-extrabold text-white">
              {summary.percent === null ? "Non mesuré" : `${summary.percent}%`}
            </p>
            <p className="text-[11px] text-teal-400 mt-0.5">{compliantCount} dans le délai sur {summary.measured} mesurées</p>
          </div>
        </div>

        <div className="glass-card rounded-2xl p-4 sm:p-5 flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400 shrink-0">
            <Database className="w-6 h-6" />
          </div>
          <div>
            <p className="text-xs text-slate-400 font-medium">Stockage immuable</p>
            <p className="text-xl sm:text-2xl font-extrabold text-white">Bronze S3</p>
            <p className="text-[11px] text-cyan-400 mt-0.5">Empreintes SHA-256</p>
          </div>
        </div>

        <div className="glass-card rounded-2xl p-4 sm:p-5 flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400 shrink-0">
            <Clock className="w-6 h-6" />
          </div>
          <div>
            <p className="text-xs text-slate-400 font-medium">Mode de collecte</p>
            <p className="text-xl sm:text-2xl font-extrabold text-white">Selon configuration</p>
            <p className="text-[11px] text-purple-300 mt-0.5">Exécution à vérifier</p>
          </div>
        </div>
      </div>

      {/* Barre de recherche et filtres de navigation */}
      <div className="space-y-4">
        <div className="flex flex-col sm:flex-row gap-3 items-stretch sm:items-center justify-between">
          {/* Recherche intuitive */}
          <div className="relative flex-1 max-w-lg">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              aria-label="Rechercher une source, une institution ou un produit"
              placeholder="Rechercher un produit, une institution ou une source…"
              className="w-full pl-10 pr-9 py-2.5 rounded-2xl bg-slate-900/80 border border-white/10 text-white placeholder-slate-400 text-xs focus:outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/30 transition-all shadow-inner"
            />
            {searchQuery && (
              <button
                aria-label="Effacer la recherche"
                onClick={() => setSearchQuery("")}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          {/* Sélecteur de vue : Cartes vs Tableau */}
          <div className="flex items-center gap-2 self-end sm:self-auto">
            <div className="flex items-center p-1 rounded-xl bg-slate-900/80 border border-white/10 text-xs">
              <button
                onClick={() => setViewMode("cards")}
                className={`p-1.5 rounded-lg flex items-center gap-1.5 transition-all ${
                  viewMode === "cards"
                    ? "bg-emerald-500/20 text-emerald-300 font-semibold"
                    : "text-slate-400 hover:text-white"
                }`}
                aria-label="Vue grille de cartes"
                aria-pressed={viewMode === "cards"}
                title="Vue grille de cartes"
              >
                <LayoutGrid className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Cartes</span>
              </button>
              <button
                onClick={() => setViewMode("table")}
                className={`p-1.5 rounded-lg flex items-center gap-1.5 transition-all ${
                  viewMode === "table"
                    ? "bg-emerald-500/20 text-emerald-300 font-semibold"
                    : "text-slate-400 hover:text-white"
                }`}
                aria-label="Vue liste détaillée"
                aria-pressed={viewMode === "table"}
                title="Vue liste détaillée"
              >
                <List className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Tableau</span>
              </button>
            </div>
          </div>
        </div>

        {/* Pilules de catégories à la Awwwards */}
        <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-none">
          {CATEGORIES.map((cat) => {
            const Icon = cat.icon;
            const isSelected = selectedCategory === cat.id;
            return (
              <button
                key={cat.id}
                onClick={() => setSelectedCategory(cat.id)}
                className={`inline-flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs whitespace-nowrap transition-all border ${
                  isSelected
                    ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/40 shadow-lg shadow-emerald-950/40 font-semibold"
                    : "bg-slate-900/60 text-slate-400 border-white/5 hover:bg-slate-900 hover:text-slate-200"
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                <span>{cat.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Affichage des sources : Cartes ou Tableau */}
      {loading ? (
        <div className="p-16 text-center text-xs text-slate-400 flex flex-col items-center justify-center gap-3 glass-card rounded-3xl font-mono">
          <RefreshCw className="w-6 h-6 animate-spin text-emerald-400" />
          <span>Chargement du catalogue des données officielles...</span>
        </div>
      ) : filteredSources.length === 0 ? (
        <div className="p-12 text-center glass-card rounded-3xl space-y-3">
          <Search className="w-8 h-8 text-slate-500 mx-auto" />
          <h3 className="text-sm font-bold text-white">Aucune source ne correspond à votre recherche</h3>
          <p className="text-xs text-slate-400 max-w-sm mx-auto">
            Essayez de modifier votre recherche (« riz », « devises », « climat ») ou réinitialisez les filtres.
          </p>
          <button
            onClick={() => {
              setSearchQuery("");
              setSelectedCategory("all");
              setStatusFilter("all");
            }}
            className="px-4 py-2 rounded-xl bg-white/10 hover:bg-white/15 text-xs text-white font-medium transition-all"
          >
            Réinitialiser les filtres
          </button>
        </div>
      ) : viewMode === "cards" ? (
        /* VUE GRILLE DE CARTES INTUITIVE */
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
          {filteredSources.map((source) => {
            const meta = SOURCES_METADATA[source.sourceId] || {
              category: "rice",
              institution: "Institution nationale",
              products: ["Données de marché"],
              description: "Disponibilité et couverture à vérifier dans les publications de cette source.",
              cadenceHuman: "Selon publication",
              icon: "📊",
            };
            const isRefreshing = refreshingSourceId === source.sourceId;

            return (
              <div
                key={source.sourceId}
                className="glass-card rounded-3xl p-5 sm:p-6 flex flex-col justify-between space-y-4 hover:border-emerald-500/40 transition-all duration-300 group"
              >
                <div className="space-y-3">
                  {/* Top Bar de la Carte */}
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="flex min-w-0 max-w-full items-center gap-3">
                      <span className="text-2xl p-2.5 rounded-2xl bg-white/[0.04] border border-white/5">
                        {meta.icon}
                      </span>
                      <div>
                        <span className="text-[10px] font-mono uppercase tracking-wider text-emerald-400/90 font-bold block">
                          {source.priority} • {source.sourceId}
                        </span>
                        <h3 className="text-sm font-bold text-white group-hover:text-emerald-300 transition-colors line-clamp-1">
                          {source.name}
                        </h3>
                      </div>
                    </div>

                    <span
                      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-mono font-medium border shrink-0 ${
                        (source.status !== "active" || source.isStale !== false)
                          ? "bg-amber-500/15 text-amber-300 border-amber-500/25"
                          : "bg-emerald-500/15 text-emerald-300 border-emerald-500/25"
                      }`}
                    >
                      <span
                        className={`w-1.5 h-1.5 rounded-full ${(source.status !== "active" || source.isStale !== false) ? "bg-amber-400" : "bg-emerald-400 animate-pulse"}`}
                      />
                      {freshnessLabel(source.status, source.isStale)}
                    </span>
                  </div>

                  {/* Institution */}
                  <p className="text-xs font-medium text-slate-300 flex items-center gap-1.5">
                    <span className="text-slate-500">Source :</span> {meta.institution}
                  </p>

                  {/* Description vulgarisée */}
                  <p className="text-xs text-slate-400 line-clamp-2 leading-relaxed">
                    {meta.description}
                  </p>

                  {/* Produits suivis */}
                  <div className="space-y-1.5 pt-1">
                    <span className="text-[11px] font-mono text-slate-400 block">Produits & Données :</span>
                    <div className="flex flex-wrap gap-1.5">
                      {meta.products.slice(0, 3).map((prod, idx) => (
                        <span
                          key={idx}
                          className="px-2 py-0.5 rounded-lg text-[10px] font-medium bg-white/[0.04] text-slate-300 border border-white/5"
                        >
                          {prod}
                        </span>
                      ))}
                      {meta.products.length > 3 && (
                        <span className="px-2 py-0.5 rounded-lg text-[10px] font-medium bg-white/[0.02] text-slate-500">
                          +{meta.products.length - 3} autres
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Footer de la carte avec bouton d'actualisation 1 clic */}
                <div className="pt-3 border-t border-white/5 flex items-center justify-between gap-2">
                  <div className="text-[11px] font-mono text-slate-400">
                    <span className="text-slate-500">Fréquence :</span> {meta.cadenceHuman}
                  </div>

                  <button
                    onClick={() => handleRefreshSource(source.sourceId)}
                    disabled={refreshingSourceId !== null || isRefreshingAll || collection.busy || !canRefresh || !collection.eligible.includes(source.sourceId)}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-emerald-500/15 hover:bg-emerald-500/25 text-emerald-300 border border-emerald-500/30 text-xs font-semibold transition-all active:scale-95 disabled:opacity-50"
                  >
                    <RefreshCw className={`w-3 h-3 ${isRefreshing ? "animate-spin" : ""}`} />
                    <span>{isRefreshing ? "Collecte..." : "Collecter"}</span>
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        /* VUE TABLEAU STRUCTURÉ */
        <div className="glass-card rounded-3xl overflow-hidden border border-white/10">
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead className="bg-slate-950/80 text-slate-400 border-b border-white/[0.08] uppercase font-mono text-[10px] tracking-wider">
                <tr>
                  <th className="px-5 py-4">Source & Émetteur</th>
                  <th className="px-5 py-4">Produits couverts</th>
                  <th className="px-5 py-4">Fréquence</th>
                  <th className="px-5 py-4">État de fraîcheur</th>
                  <th className="px-5 py-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.04]">
                {filteredSources.map((source) => {
                  const meta = SOURCES_METADATA[source.sourceId] || {
                    institution: "Organisme officiel",
                    products: ["Vivres divers"],
                    cadenceHuman: "Selon publication",
                  };
                  const isRefreshing = refreshingSourceId === source.sourceId;

                  return (
                    <tr key={source.sourceId} className="hover:bg-white/[0.02] transition-colors">
                      <td className="px-5 py-4">
                        <div className="font-bold text-white text-xs">{source.name}</div>
                        <div className="text-[11px] text-slate-400 mt-0.5">{meta.institution}</div>
                      </td>
                      <td className="px-5 py-4">
                        <div className="flex flex-wrap gap-1 max-w-xs">
                          {meta.products.slice(0, 2).map((p, i) => (
                            <span
                              key={i}
                              className="px-2 py-0.5 rounded bg-white/[0.04] text-[10px] text-slate-300"
                            >
                              {p}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="px-5 py-4 font-mono text-slate-300 text-[11px]">
                        {meta.cadenceHuman}
                      </td>
                      <td className="px-5 py-4">
                        <span
                          className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-mono font-medium border ${
                            (source.status !== "active" || source.isStale !== false)
                              ? "bg-amber-500/15 text-amber-300 border-amber-500/25"
                              : "bg-emerald-500/15 text-emerald-300 border-emerald-500/25"
                          }`}
                        >
                          <span
                            className={`w-1.5 h-1.5 rounded-full ${(source.status !== "active" || source.isStale !== false) ? "bg-amber-400" : "bg-emerald-400"}`}
                          />
                          {freshnessLabel(source.status, source.isStale)}
                        </span>
                      </td>
                      <td className="px-5 py-4 text-right">
                        <button
                          onClick={() => handleRefreshSource(source.sourceId)}
                          disabled={refreshingSourceId !== null || isRefreshingAll || collection.busy || !canRefresh || !collection.eligible.includes(source.sourceId)}
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-emerald-500/15 hover:bg-emerald-500/25 text-emerald-300 border border-emerald-500/30 text-xs font-semibold transition-all active:scale-95 disabled:opacity-50"
                        >
                          <RefreshCw className={`w-3 h-3 ${isRefreshing ? "animate-spin" : ""}`} />
                          <span>{isRefreshing ? "Collecte..." : "Collecter"}</span>
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Historique des Dernières Synchronisations (Timeline lisible) */}
      <div className="glass-card rounded-3xl p-6 sm:p-7 border border-white/10 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-white/[0.08] pb-4">
          <div className="flex items-center gap-2.5">
            <Activity className="w-5 h-5 text-emerald-400" />
            <div>
              <h2 className="text-sm font-bold text-white">
                Historique des traitements enregistrés
              </h2>
              <p className="text-xs text-slate-400">
                Traitements déclarés et volumes enregistrés ; cet historique ne certifie pas une collecte.
              </p>
            </div>
          </div>
          <button
            onClick={loadData}
            className="self-start sm:self-auto inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-white/[0.04] hover:bg-white/[0.08] text-slate-300 text-xs font-mono transition-all"
          >
            <RefreshCw className="w-3 h-3" />
            <span>Rafraîchir le journal</span>
          </button>
        </div>

        {runs.length === 0 ? (
          <div className="p-8 text-center text-xs text-slate-400 font-mono">
            Aucun historique d&apos;actualisation récent enregistré.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2">
            {runs.slice(0, 6).map((run) => (
              <div
                key={run.run_id}
                className="p-3.5 rounded-2xl bg-slate-900/50 border border-white/5 flex items-center justify-between gap-3 text-xs"
              >
                <div className="flex items-center gap-3">
                  <div
                    className={`w-2.5 h-2.5 rounded-full shrink-0 ${
                      run.status === "success" ? "bg-emerald-400" : "bg-rose-400"
                    }`}
                  />
                  <div>
                    <span className="font-bold text-white block">
                      {run.source_name || run.source_id} — {({ success: "Terminé", running: "En cours", failed: "Échec", partial: "Partiel" } as Record<string, string>)[run.status] || "État inconnu"}
                    </span>
                    <span className="text-[11px] text-slate-400 font-mono">
                      {new Date(run.started_at).toLocaleString("fr-FR", {
                        day: "2-digit",
                        month: "short",
                        hour: "2-digit",
                        minute: "2-digit",
                        timeZone: "Indian/Antananarivo",
                      })}
                    </span>
                  </div>
                </div>

                <div className="text-right">
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 font-medium">
                    {run.n_records === null ? "Volume non mesuré" : `${run.n_records} enregistrements`}
                  </span>
                  {run.duration_seconds !== null && run.duration_seconds !== undefined && (
                    <span className="text-[10px] text-slate-500 font-mono block mt-0.5">
                      {run.duration_seconds}s
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Section Mode Expert / Dagster (Discret et bien séparé) */}
      <div className="p-5 rounded-2xl bg-purple-950/20 border border-purple-500/20 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-purple-500/20 text-purple-300 shrink-0">
            <Server className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-2">
              Dagster Cockpit (Mode Ingénieur & DataOps)
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Outil technique avancé réservé aux administrateurs pour inspecter le graphe de calcul et les pipelines bruts.
            </p>
          </div>
        </div>

        <a
          href={process.env.NEXT_PUBLIC_DAGSTER_URL || "http://localhost:3010"}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center justify-center gap-2 px-4 py-2 bg-purple-600/30 hover:bg-purple-600/40 text-purple-200 border border-purple-500/30 rounded-xl text-xs font-semibold shadow-lg shadow-purple-950/40 transition-all shrink-0 self-start sm:self-auto"
        >
          <span>Ouvrir Dagster</span>
          <ExternalLink className="w-3.5 h-3.5" />
        </a>
      </div>
    </div>
  );
}
