"use client";

import React, { useState } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Check,
  CheckCircle2,
  Clock,
  Copy,
  Cpu,
  Database,
  ExternalLink,
  Folder,
  Layers,
  RefreshCw,
  Server,
  ShieldCheck,
  Terminal,
} from "lucide-react";

export default function SystemPage() {
  const [copiedText, setCopiedText] = useState<string | null>(null);

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedText(id);
    setTimeout(() => setCopiedText(null), 2500);
  };

  const projectPath = "C:\\Users\\raillersing\\Documents\\#Entreprise\\Ketrika AI\\AI Agent";

  const localServices = [
    {
      name: "Dashboard Web (Next.js 14)",
      port: "3005",
      url: "http://localhost:3005",
      role: "Interface utilisateur principale et visualisations analytiques",
      badge: "Frontend",
      color: "border-emerald-500/30 bg-emerald-500/5",
    },
    {
      name: "API REST FastAPI & Swagger Docs",
      port: "8090",
      url: "http://localhost:8090/docs",
      role: "Endpoints v1 authentifiés, OpenAPI, export CSV, contrôle de santé (/v1/health)",
      badge: "Backend",
      color: "border-sky-500/30 bg-sky-500/5",
    },
    {
      name: "Orchestrateur Dagster Cockpit",
      port: "3010",
      url: "http://localhost:3010",
      role: "Graphe d'actifs de données, planification cron (Schedules) et sensors d'alerte",
      badge: "DataOps",
      color: "border-purple-500/30 bg-purple-500/5",
    },
    {
      name: "Webmail de capture Mailpit",
      port: "8025 / 1025",
      url: "http://localhost:8025",
      role: "Capture locale sécurisée des emails d'alertes et de diffusion des bulletins (Gate H3)",
      badge: "Supervision",
      color: "border-amber-500/30 bg-amber-500/5",
    },
    {
      name: "Stockage Bronze MinIO (S3)",
      port: "9101 / 9100",
      url: "http://localhost:9101",
      role: "Bucket S3 'bronze' versionné et immuable (identifiants: minioadmin / minioadmin)",
      badge: "Storage",
      color: "border-rose-500/30 bg-rose-500/5",
    },
    {
      name: "Base de données PostGIS 17",
      port: "5434",
      url: "localhost:5434",
      role: "Stockage PostgreSQL relationnel et spatial PostGIS 3.5 (base: ketrika)",
      badge: "Database",
      color: "border-indigo-500/30 bg-indigo-500/5",
    },
  ];

  const updateCadences = [
    {
      cadence: "Quotidienne (Daily)",
      cron: "0 6 * * * (06h00 UTC)",
      sources: "NASA POWER Agroclimatology & CHIRPS",
      description: "Précipitations, températures moyennes et minimales par district et région.",
      status: "Actif",
    },
    {
      cadence: "Hebdomadaire (Weekly)",
      cron: "0 7 * * 1 (Lundi 07h00 UTC)",
      sources: "MiASA / Observatoire du Riz (ODR), MinCC Prix & Stocks",
      description: "Bulletins hebdomadaires ODR (cours du riz), stocks régionaux déclarés, déclenchement du moteur d'alertes et édition du bulletin.",
      status: "Actif",
    },
    {
      cadence: "Mensuelle (Monthly)",
      cron: "0 8 1 * * (1er du mois 08h00 UTC)",
      sources: "Banque Mondiale RTFP, WFP HDX, INSTAT NIPC, Douanes",
      description: "Indices haute fréquence RTFP, cours WFP, indice officiel d'inflation alimentaire NIPC et flux d'importation sous douane.",
      status: "Actif",
    },
    {
      cadence: "Annuelle (Annual)",
      cron: "0 10 1 1 * (1er janvier 10h00 UTC)",
      sources: "FAOSTAT Madagascar",
      description: "Bilans statistiques nationaux de production vivrière (riz paddy, maïs, manioc).",
      status: "Actif",
    },
  ];

  const devCommands = [
    {
      cmd: "./scripts/dev.ps1 backfill <source_id>",
      desc: "Force l'ingestion immédiate d'une source spécifique (ex: miasa_odr, wfp_hdx_mdg, douanes_stats) ou de toutes ('all').",
    },
    {
      cmd: "./scripts/dev.ps1 bulletin",
      desc: "Génère un projet de bulletin hebdomadaire PDF certifié avec audit strict anti-chiffres inventés.",
    },
    {
      cmd: "./scripts/dev.ps1 rebuild",
      desc: "Purge Silver/Gold et rejoue l'intégralité des pipelines depuis les fichiers bruts du Bronze en mode 100% hors-ligne.",
    },
    {
      cmd: "./scripts/dev.ps1 check",
      desc: "Exécute le contrôle qualité complet (lint ruff, types mypy, 215 tests backend, tests frontend vitest).",
    },
    {
      cmd: "./scripts/dev.ps1 demo",
      desc: "Exécute le banc d'acceptation de référence vérifiant les 11 KPIs normatifs du MVP.",
    },
    {
      cmd: "./scripts/dev.ps1 backup",
      desc: "Génère une sauvegarde binaire compressée et scellée de la base de données PostGIS dans le dossier backups/.",
    },
    {
      cmd: "./scripts/dev.ps1 restore",
      desc: "Restaure la base de données à partir du dernier dump et rafraîchit automatiquement toutes les vues Gold.",
    },
  ];

  return (
    <div className="space-y-8 max-w-7xl mx-auto pb-12 animate-in fade-in duration-300">
      {/* Page Header */}
      <div>
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-600 border border-emerald-500/20 mb-3">
          <Cpu className="w-3.5 h-3.5" />
          DataOps & Infrastructure Système
        </div>
        <h1 className="text-3xl font-extrabold tracking-tight text-foreground flex items-center gap-3">
          Architecture, Emplacement & Mises à Jour Automatiques
        </h1>
        <p className="text-sm text-muted-foreground mt-2 max-w-3xl leading-relaxed">
          Guide technique complet sur le fonctionnement de l&apos;orchestration automatisée des pipelines, la chaîne de données médaillon (Bronze, Silver, Gold), l&apos;emplacement local des fichiers et les commandes de pilotage.
        </p>
      </div>

      {/* 1. Emplacement Local du Projet */}
      <section className="bg-card border border-border rounded-xl p-6 shadow-sm space-y-4">
        <div className="flex items-center gap-3 border-b border-border pb-4">
          <div className="w-10 h-10 rounded-lg bg-primary-action/10 border border-emerald-500/20 flex items-center justify-center text-emerald-600 font-bold">
            <Folder className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-foreground">
              Emplacement local du projet sur votre machine
            </h2>
            <p className="text-xs text-muted-foreground">
              Répertoire de travail racine contenant l&apos;ensemble du code source, de la configuration et des documents.
            </p>
          </div>
        </div>

        <div className="space-y-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 bg-muted/60 border border-border rounded-lg font-mono text-xs">
            <div className="flex items-center gap-2 overflow-x-auto text-foreground font-semibold">
              <span className="text-muted-foreground font-normal">Chemin absolu :</span>
              <span className="text-emerald-600 dark:text-primary-readable select-all">{projectPath}</span>
            </div>
            <button
              onClick={() => copyToClipboard(projectPath, "path")}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-card border border-border text-foreground hover:bg-muted text-xs font-medium transition-colors shrink-0"
            >
              {copiedText === "path" ? (
                <>
                  <Check className="w-3.5 h-3.5 text-emerald-600" />
                  <span>Copié !</span>
                </>
              ) : (
                <>
                  <Copy className="w-3.5 h-3.5" />
                  <span>Copier le chemin</span>
                </>
              )}
            </button>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
            <div className="p-3 bg-card border border-border rounded-lg">
              <div className="font-semibold text-foreground font-mono">backend/</div>
              <p className="text-muted-foreground mt-1 text-[11px]">API FastAPI, connecteurs, Dagster, SQLAlchemy, ML.</p>
            </div>
            <div className="p-3 bg-card border border-border rounded-lg">
              <div className="font-semibold text-foreground font-mono">web/</div>
              <p className="text-muted-foreground mt-1 text-[11px]">Frontend Next.js 14, Tailwind, composants et cartes.</p>
            </div>
            <div className="p-3 bg-card border border-border rounded-lg">
              <div className="font-semibold text-foreground font-mono">deploy/</div>
              <p className="text-muted-foreground mt-1 text-[11px]">Caddyfile, scripts de backup, restore et bootstrap VPS.</p>
            </div>
            <div className="p-3 bg-card border border-border rounded-lg">
              <div className="font-semibold text-foreground font-mono">docs/</div>
              <p className="text-muted-foreground mt-1 text-[11px]">Runbooks, fiches sources, rapport MVP et HANDOFF.</p>
            </div>
          </div>
        </div>
      </section>

      {/* 2. Console des Services Locaux & Ports */}
      <section className="bg-card border border-border rounded-xl p-6 shadow-sm space-y-4">
        <div className="flex items-center justify-between border-b border-border pb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-sky-600/10 border border-sky-500/20 flex items-center justify-center text-sky-600 font-bold">
              <Server className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-foreground">
                Services Docker conteneurisés en cours d&apos;exécution
              </h2>
              <p className="text-xs text-muted-foreground">
                Tous les services tournent en conteneurs autonomes isolés sans conflit de ports (ADR-007).
              </p>
            </div>
          </div>
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-600 border border-emerald-500/20">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            6/6 Services UP & Healthy
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {localServices.map((svc) => (
            <div
              key={svc.name}
              className={`border rounded-lg p-4 flex flex-col justify-between space-y-3 transition-all hover:shadow-md ${svc.color}`}
            >
              <div>
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-semibold px-2 py-0.5 rounded uppercase tracking-wider bg-background/80 border border-border">
                    {svc.badge}
                  </span>
                  <span className="font-mono text-xs font-semibold text-muted-foreground">
                    Port {svc.port}
                  </span>
                </div>
                <h3 className="font-bold text-sm text-foreground mt-2">{svc.name}</h3>
                <p className="text-xs text-muted-foreground mt-1 leading-relaxed">
                  {svc.role}
                </p>
              </div>

              {svc.url.startsWith("http") && (
                <a
                  href={svc.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center justify-between gap-1 text-xs font-semibold text-emerald-600 dark:text-primary-readable hover:underline pt-2 border-t border-border/50"
                >
                  <span>Ouvrir l&apos;interface</span>
                  <ExternalLink className="w-3.5 h-3.5" />
                </a>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* 3. Mises à Jour Automatiques (Dagster) */}
      <section className="bg-card border border-border rounded-xl p-6 shadow-sm space-y-4">
        <div className="flex items-center justify-between border-b border-border pb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-purple-600/10 border border-purple-500/20 flex items-center justify-center text-purple-600 font-bold">
              <RefreshCw className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-foreground">
                Comment les données sont-elles mises à jour automatiquement ?
              </h2>
              <p className="text-xs text-muted-foreground">
                Le démon <code className="font-mono text-purple-600 font-semibold">dagster-daemon</code> surveille et applique les fréquences d&apos;ingestion en continu.
              </p>
            </div>
          </div>
          <a
            href="http://localhost:3010/schedules"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-purple-600 text-primary-foreground text-xs font-medium hover:bg-purple-700 transition-colors"
          >
            <span>Gérer les Schedules dans Dagster</span>
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-xs text-left">
            <thead className="bg-muted/50 border-b border-border text-muted-foreground font-semibold uppercase text-[10px] tracking-wider">
              <tr>
                <th className="py-3 px-4">Cadence</th>
                <th className="py-3 px-4">Planification Cron</th>
                <th className="py-3 px-4">Sources Couvertes</th>
                <th className="py-3 px-4">Description du Traitement</th>
                <th className="py-3 px-4">Statut</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {updateCadences.map((cad) => (
                <tr key={cad.cadence} className="hover:bg-muted/30 transition-colors">
                  <td className="py-3.5 px-4 font-semibold text-foreground flex items-center gap-2">
                    <Clock className="w-3.5 h-3.5 text-purple-500" />
                    {cad.cadence}
                  </td>
                  <td className="py-3.5 px-4 font-mono text-muted-foreground">{cad.cron}</td>
                  <td className="py-3.5 px-4 font-medium text-foreground">{cad.sources}</td>
                  <td className="py-3.5 px-4 text-muted-foreground">{cad.description}</td>
                  <td className="py-3.5 px-4">
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/10 text-emerald-600 border border-emerald-500/20">
                      <CheckCircle2 className="w-3 h-3" />
                      {cad.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* 4. Architecture Médaillon (Bronze -> Silver -> Gold) */}
      <section className="bg-card border border-border rounded-xl p-6 shadow-sm space-y-4">
        <div className="flex items-center gap-3 border-b border-border pb-4">
          <div className="w-10 h-10 rounded-lg bg-amber-600/10 border border-amber-500/20 flex items-center justify-center text-amber-600 font-bold">
            <Layers className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-foreground">
              Architecture des données : Cycle de vie médaillon
            </h2>
            <p className="text-xs text-muted-foreground">
              Chaque observation affichée conserve une chaîne de provenance mécanique ininterrompue de bout en bout.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-2">
          {/* Bronze Card */}
          <div className="bg-muted/40 border border-border rounded-xl p-5 relative overflow-hidden flex flex-col justify-between">
            <div className="space-y-3">
              <div className="w-8 h-8 rounded-lg bg-amber-700/10 text-amber-700 dark:text-amber-400 font-bold flex items-center justify-center text-xs">
                1
              </div>
              <h3 className="font-bold text-base text-foreground">Couche Bronze (Immuable)</h3>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Stockage S3 MinIO / Cloudflare R2. Tous les objets bruts collectés (PDF, CSV, réponses JSON d&apos;API) sont archivés et indexés par leur empreinte cryptographique SHA-256. Aucune modification ni suppression n&apos;est autorisée.
              </p>
            </div>
            <div className="mt-4 pt-3 border-t border-border/60 text-[11px] font-mono text-muted-foreground">
              S3: bronze/&lt;source_id&gt;/&lt;sha256&gt;
            </div>
          </div>

          {/* Silver Card */}
          <div className="bg-muted/40 border border-border rounded-xl p-5 relative overflow-hidden flex flex-col justify-between">
            <div className="space-y-3">
              <div className="w-8 h-8 rounded-lg bg-muted/10 text-muted-foreground dark:text-muted-foreground font-bold flex items-center justify-center text-xs">
                2
              </div>
              <h3 className="font-bold text-base text-foreground">Couche Silver (Auditée)</h3>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Tables PostgreSQL du schéma <code className="font-mono text-xs">obs.*</code>. Normalisation des produits vivriers (Vary Gasy, Makalioka...), conversion d&apos;unités en kg de base, géolocalisation sur 23 régions officielles et révisions par ajout seul (<code className="font-mono text-xs">superseded_by</code>).
              </p>
            </div>
            <div className="mt-4 pt-3 border-t border-border/60 text-[11px] font-mono text-muted-foreground">
              SQL: obs.price_observation
            </div>
          </div>

          {/* Gold Card */}
          <div className="bg-muted/40 border border-border rounded-xl p-5 relative overflow-hidden flex flex-col justify-between">
            <div className="space-y-3">
              <div className="w-8 h-8 rounded-lg bg-yellow-500/10 text-yellow-600 dark:text-yellow-400 font-bold flex items-center justify-center text-xs">
                3
              </div>
              <h3 className="font-bold text-base text-foreground">Couche Gold (Analytique)</h3>
              <p className="text-xs text-muted-foreground leading-relaxed">
                12 vues matérialisées dans <code className="font-mono text-xs">gold.*</code>. Calcul des prix médians mensuels, Market Health Score (0-100), alertes automatiques et modèles prévisionnels LightGBM / AutoARIMA (quantiles p10/p50/p90).
              </p>
            </div>
            <div className="mt-4 pt-3 border-t border-border/60 text-[11px] font-mono text-muted-foreground">
              SQL: gold.price_monthly_best
            </div>
          </div>
        </div>
      </section>

      {/* 5. Commandes de Pilotage Manuel */}
      <section className="bg-card border border-border rounded-xl p-6 shadow-sm space-y-4">
        <div className="flex items-center gap-3 border-b border-border pb-4">
          <div className="w-10 h-10 rounded-lg bg-primary-action/10 border border-emerald-500/20 flex items-center justify-center text-emerald-600 font-bold">
            <Terminal className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-foreground">
              Commandes de déclenchement manuel (PowerShell / Bash)
            </h2>
            <p className="text-xs text-muted-foreground">
              Vous pouvez forcer manuellement n&apos;importe quelle étape depuis le terminal à la racine du projet.
            </p>
          </div>
        </div>

        <div className="space-y-3">
          {devCommands.map((cmdItem, idx) => (
            <div
              key={cmdItem.cmd}
              className="p-3 bg-muted/40 border border-border rounded-lg flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs"
            >
              <div className="space-y-1">
                <code className="font-mono font-semibold text-emerald-600 dark:text-primary-readable select-all">
                  {cmdItem.cmd}
                </code>
                <p className="text-muted-foreground text-[11px]">{cmdItem.desc}</p>
              </div>
              <button
                onClick={() => copyToClipboard(cmdItem.cmd, `cmd-${idx}`)}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-card border border-border text-foreground hover:bg-muted text-[11px] font-medium transition-colors shrink-0"
              >
                {copiedText === `cmd-${idx}` ? (
                  <>
                    <Check className="w-3 h-3 text-emerald-600" />
                    <span>Copié</span>
                  </>
                ) : (
                  <>
                    <Copy className="w-3 h-3" />
                    <span>Copier</span>
                  </>
                )}
              </button>
            </div>
          ))}
        </div>
      </section>

      {/* 6. Tolérance aux Pannes & Résilience */}
      <section className="bg-card border border-border rounded-xl p-6 shadow-sm space-y-4">
        <div className="flex items-center gap-3 border-b border-border pb-4">
          <div className="w-10 h-10 rounded-lg bg-rose-600/10 border border-rose-500/20 flex items-center justify-center text-rose-600 font-bold">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-foreground">
              Résilience et gestion des défaillances de sources externes
            </h2>
            <p className="text-xs text-muted-foreground">
              Que se passe-t-il si un site gouvernemental ou une API externe est indisponible ?
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
          <div className="p-4 bg-muted/30 border border-border rounded-lg space-y-2">
            <h3 className="font-semibold text-foreground flex items-center gap-1.5">
              <Activity className="w-4 h-4 text-primary-readable" />
              Politique HTTP Polie & Retries
            </h3>
            <p className="text-muted-foreground text-[11px] leading-relaxed">
              Cadence plafonnée à 0,2 requête/seconde, User-Agent officiel vérifiable, respect absolu des directives <code className="font-mono">robots.txt</code> et temporisation exponentielle Tenacity sur erreurs 429/503.
            </p>
          </div>

          <div className="p-4 bg-muted/30 border border-border rounded-lg space-y-2">
            <h3 className="font-semibold text-foreground flex items-center gap-1.5">
              <Database className="w-4 h-4 text-sky-500" />
              Non-Régression & Données Préservées
            </h3>
            <p className="text-muted-foreground text-[11px] leading-relaxed">
              En cas d&apos;échec réseau, l&apos;ingestion s&apos;interrompt proprement (<code className="font-mono">PolicyStop</code>). Les données historiques en base restent intactes et accessibles sur le dashboard sans aucune interruption.
            </p>
          </div>

          <div className="p-4 bg-muted/30 border border-border rounded-lg space-y-2">
            <h3 className="font-semibold text-foreground flex items-center gap-1.5">
              <AlertTriangle className="w-4 h-4 text-amber-500" />
              Alerte Sensor & Statut Dégradé
            </h3>
            <p className="text-muted-foreground text-[11px] leading-relaxed">
              Le capteur d&apos;échec Dagster (<code className="font-mono">pipeline_failure_sensor</code>) intercepte l&apos;erreur et expédie un email d&apos;alerte dans Mailpit. La source bascule en badge rouge &quot;failed&quot; sur le cockpit /sources.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}
