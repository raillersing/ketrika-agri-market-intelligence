# PROGRESS : registre d'exécution du MVP

> **Mémoire unique et persistante de l'agent autonome** (AGENTS.md §3.1).
> Statuts possibles d'une tâche : `TODO` | `IN_PROGRESS` | `DONE` | `BLOCKED`

---

## 1. Tableau de bord des tâches

| ID | Priorité | Phase | Description | Dépendances | Statut | Commit / Preuve |
|---|---|---|---|---|---|---|
| **T0.1** | MUST | 0 | Initialiser le dépôt et la gouvernance | — | **DONE** | d109bb7 (git init, attributes, docs/plan) |
| **T0.2** | MUST | 0 | Squelette du monorepo et outillage qualité | T0.1 | **DONE** | 3ac9f33 (`check` vert : ruff 0, mypy 0, pytest 1 passed, vitest 1 passed) |
| **T0.3** | MUST | 0 | Stack Docker de développement | T0.2 | **DONE** | d4c8269 (services healthy, /v1/health ok, MinIO bronze versioned, dagster/web/mailpit ok, dev.ps1 check vert) |
| **T0.4** | SHOULD | 0 | Configuration CI locale/GitHub Actions | T0.3 | TODO | — |
| **T1.1** | MUST | 1 | Reconnaissance des sources et registre | T0.3 | TODO | — |
| **T1.2** | MUST | 1 | Taxonomie produits et alias | T1.1 | TODO | — |
| **T1.3** | MUST | 1 | Unités et conversions | T1.1 | TODO | — |
| **T1.4** | MUST | 1 | Géographie de référence | T1.1 | TODO | — |
| **T2.1** | MUST | 2 | Migrations de base de données (Alembic) | T0.3 | TODO | — |
| **T2.2** | MUST | 2 | Bibliothèque ketrika.core | T2.1 | TODO | — |
| **T2.3** | MUST | 2 | Framework Connector et factory Dagster | T2.2 | TODO | — |
| **T2.4** | MUST | 2 | Bibliothèque d'extraction (PDF, HTML, LLM) | T2.2 | TODO | — |
| **T2.5** | MUST | 2 | Normalisation et chargement | T2.3, T1.2–T1.4 | TODO | — |
| **T2.6** | MUST | 2 | Commande rebuild et runbook connecteur | T2.3–T2.5 | TODO | — |
| **T3.1** | MUST | 3 | Connecteur WFP Food Prices HDX | T2.6 | TODO | — |
| **T3.2** | MUST | 3 | Connecteur Banque Mondiale RTFP | T2.6 | TODO | — |
| **T3.3** | MUST | 3 | Connecteur FAOSTAT | T2.6 | TODO | — |
| **T3.4** | MUST | 3 | Connecteur NASA POWER Climat | T2.6, T1.4 | TODO | — |
| **T3.5** | MUST | 3 | Connecteur INSTAT NIPC | T2.6 | TODO | — |
| **T4.1** | MUST | 4 | Connecteur MiASA ODR (Bulletins Riz) | T2.6 | TODO | — |
| **T4.2** | MUST | 4 | Connecteur MinCC Prix & Stocks PPN | T2.6 | TODO | — |
| **T4.3** | MUST | 4 | Connecteur Douanes Statistiques | T2.6 | TODO | — |
| **T4.4** | COULD | 4 | Connecteur Événements (PICM, FEWS NET) | T2.6 | TODO | — |
| **T5.1** | MUST | 5 | Vues matérialisées Gold | T3.1–T3.5, T4.1–T4.3 | TODO | — |
| **T5.2** | MUST | 5 | Indicateurs et KPI Gold | T5.1 | TODO | — |
| **T5.3** | MUST | 5 | Cockpit Data Quality (DQ) | T5.1 | TODO | — |
| **T6.1** | MUST | 6 | API FastAPI /v1 | T5.2 | TODO | — |
| **T6.2** | MUST | 6 | Tests de charge et robustesse API | T6.1 | TODO | — |
| **T7.1** | MUST | 7 | Fondations frontend Next.js | T6.1 | TODO | — |
| **T7.2** | MUST | 7 | Pages et vues analytiques web | T7.1 | TODO | — |
| **T7.3** | MUST | 7 | Tests e2e web (Playwright) | T7.2 | TODO | — |
| **T8.1** | MUST | 8 | Moteur d'alertes | T5.2 | TODO | — |
| **T8.2** | MUST | 8 | Générateur de bulletin hebdomadaire PPN | T5.2, T6.1 | TODO | — |
| **T9.1** | MUST | 9 | Modèles de prévision de prix | T5.1 | TODO | — |
| **T9.2** | MUST | 9 | Intégration des anomalies dans les alertes | T9.1, T8.1 | TODO | — |
| **T9.3** | SHOULD | 9 | Connecteur CHIRPS v3 | T5.1, T1.4 | TODO | — |
| **T10.1** | MUST | 10 | Copilote analyste SQL sécurisé | T6.1, T5.2 | TODO | — |
| **T11.1** | MUST | 11 | Observabilité et supervision | Phases 8–10 | TODO | — |
| **T11.2** | MUST | 11 | Revue de sécurité et audits | T11.1 | TODO | — |
| **T11.3** | MUST | 11 | Procédures de sauvegarde et restauration | T11.1 | TODO | — |
| **T11.4** | MUST | 11 | Paquet de déploiement VPS | T11.2 | TODO | — |
| **T11.5** | MUST | 11 | Documentation finale et runbooks | T11.4 | TODO | — |
| **T11.6** | MUST | 11 | Test d'acceptation final du MVP | T11.1–T11.5 | TODO | — |

---

## 2. Journal d'exécution

### [2026-10-05T20:55:00Z] Exécution de T0.1 : Initialiser le dépôt et la gouvernance
- Vérification environnement (git, docker, compose, uv).
- Création `.gitignore`, `.gitattributes`, `.editorconfig`, `README.md`, `scripts/dev.sh`.
- Création `DECISIONS.md` (ADR-001 à ADR-006), `BLOCKERS.md`, `BACKLOG.md`.
- Validation acceptation : git repository initialisé, `git check-attr eol -- scripts/dev.sh` renvoie `lf`.
- Commit : `d109bb7` (`chore(T0.1): bootstrap repository`). Statut : **DONE**.

### [2026-10-05T21:05:00Z] Démarrage de T0.2 : Squelette du monorepo et outillage qualité
- **Mini-plan T0.2 :**
  1. Créer l'arborescence normative (backend, web, deploy, registry, taxonomy, geo).
  2. Configurer `backend/pyproject.toml` (ruff, mypy, pytest, uv) et Dockerfile.
  3. Initialiser `web` (Next.js, TypeScript, Tailwind, pnpm, vitest).
  4. Rédiger `scripts/dev.ps1` et `scripts/dev.sh` avec commandes normatives.
  5. Générer `uv.lock` et `pnpm-lock.yaml`.
  6. Écrire des tests unitaires minimaux backend et web.
  7. Vérifier `./scripts/dev.ps1 check` et sortie d'erreur sur argument invalide.
  8. Committer `chore(T0.2): monorepo skeleton and quality tooling`.
- **Validation acceptation :**
  - `./scripts/dev.ps1 check` : vert (backend: ruff check & format 17 fichiers, mypy 17 fichiers sans erreur, pytest 1 passed ; web: vitest 1 test passed).
  - Lockfiles `backend/uv.lock` et `web/pnpm-lock.yaml` présents et versionnés.
  - `./scripts/dev.ps1 nope` affiche l'aide et retourne le code de sortie 1.
- Statut : **DONE**.

### [2026-10-06T01:02:00Z] Démarrage de T0.3 : Stack Docker de développement
- **Mini-plan T0.3 :**
  1. Créer `.env.example` avec toutes les variables définies dans SPECS §4.
  2. Créer `docker/db/init.sql` (bases `ketrika` et `dagster`, extensions PostGIS/pg_trgm, schémas, rôles `ketrika_app`, `copilot_ro`, `dagster`).
  3. Configurer Dagster (`backend/src/ketrika/dagster_project/workspace.yaml`, `dagster.yaml`, `definitions.py`).
  4. Implémenter le endpoint `GET /v1/health` vérifiant la connectivité DB (Postgres) et S3 (MinIO).
  5. Rédiger `docker-compose.yml` complet (db, minio, minio-init, mailpit, dagster-webserver, dagster-daemon, api, web) avec healthchecks et volumes nommés.
  6. Mettre à jour `scripts/dev.ps1` et `scripts/dev.sh` (up avec attente healthchecks).
  7. Tester `./scripts/dev.ps1 up`, vérifier les healthchecks et `curl http://localhost:8000/v1/health`.
  8. Vérifier bucket `bronze` MinIO et UI Dagster sur port 3001.
  9. Tester `./scripts/dev.ps1 down`.
  10. Valider DoD, mettre à jour PROGRESS.md et committer `feat(T0.3): docker development stack`.
- **Validation acceptation :**
  - `docker compose ps` : tous les services persistants (db, minio, mailpit, dagster-webserver, dagster-daemon, api, web) sont UP et healthy.
  - Ports hôte isolés sans conflit (ADR-007) : DB :5434, MinIO :9100/:9101, API :8090, Web :3005, Dagster :3010, Mailpit :8025/:1025.
  - `curl http://localhost:8090/v1/health` renvoie `{"status":"ok","version":"0.1.0","database":"connected","storage":"connected"}`.
  - MinIO bucket `bronze` présent avec versioning activé (`Status: Enabled`).
  - Dagster webserver répond HTTP 200 sur port 3010 (`/` et `/server_info`, instance ID valide avec stockage PostgreSQL `postgresql+psycopg2`).
  - Web Next.js répond HTTP 200 sur port 3005.
  - Mailpit répond HTTP 200 sur port 8025 (`/api/v1/info`).
  - `./scripts/dev.ps1 check` est vert (ruff format/check 22 fichiers, mypy 22 fichiers sans erreur, pytest 3 passed, vitest 1 passed).
- Statut : **DONE**.

