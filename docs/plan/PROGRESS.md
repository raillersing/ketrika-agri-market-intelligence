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
| **T0.4** | SHOULD | 0 | Configuration CI locale/GitHub Actions | T0.3 | **DONE** | .github/workflows/ci.yml valide (actionlint 0 erreur, dev.ps1 check vert) |
| **T1.1** | MUST | 1 | Reconnaissance des sources et registre | T0.3 | **DONE** | 447e704 (sources.yaml validé, 10 fiches docs, 10 fixtures, 8 tests pytest passants) |
| **T1.2** | MUST | 1 | Taxonomie produits et alias | T1.1 | **DONE** | f6d3fec (products.yaml, aliases.yaml, rice_varieties.yaml, 13 tests pytest passants) |
| **T1.3** | MUST | 1 | Unités et conversions | T1.1 | **DONE** | ed8639c (units.yaml, moteur de conversion, tests Hypothesis passants, 20 tests pytest) |
| **T1.4** | MUST | 1 | Géographie de référence | T1.1 | **DONE** | admin0/1/2 GeoJSON 23 régions, location_aliases.yaml, crop_calendar.yaml, 28 tests pytest |
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

### [2026-10-06T21:05:00Z] Démarrage de T0.4 : Configuration CI locale/GitHub Actions
- **Mini-plan T0.4 :**
  1. Créer le répertoire `.github/workflows`.
  2. Rédiger `.github/workflows/ci.yml` avec jobs de lint, typecheck, tests backend et frontend sous Docker, sans secret requis (`LLM_PROVIDER=replay`).
  3. Valider la syntaxe et conformité avec `rhysd/actionlint`.
  4. Valider le gate Phase 0 et préparer le tag `phase-0-done`.
  5. Committer `chore(T0.4): github actions ci workflow`.
- **Validation acceptation :**
  - Workflow `.github/workflows/ci.yml` créé avec jobs lint, typecheck, tests unitaires et intégration (services postgres postgis & minio).
  - Validation actionlint : `docker run --rm -v ${PWD}:/repo rhysd/actionlint` exécuté avec succès (0 erreur).
  - `./scripts/dev.ps1 check` vert.
- Statut : **DONE**.

### [2026-10-06T21:10:00Z] Gate de fin de Phase 0 (Bootstrap)
- **Résumé de phase (≤ 15 lignes) :**
  - **Livré :** Monorepo complet (backend FastAPI/Dagster, web Next.js/Tailwind), gouvernance documentaire (`AGENTS.md`, `SPECS.md`, `MVP_EXECUTION_PLAN.md`, `DECISIONS.md`, `PROGRESS.md`), outillage qualité (ruff, mypy, pytest, vitest, dev.ps1), stack Docker de développement orchestrée (PostGIS 17, MinIO bronze versionné, Dagster 1.13, API, Web, Mailpit) avec healthchecks et ports configurables (ADR-007), workflow CI GitHub Actions validé par actionlint.
  - **Chiffres clés :** 7 services conteneurisés sains, 3 tests unitaires passants backend, 1 test smoke passant web, 0 erreur mypy/ruff/actionlint.
  - **Dettes :** Aucune dette non tracée.
  - **Risques :** Conflit potentiel de ports sur machine hôte géré de manière pérenne par ADR-007.
  - **Tag :** `phase-0-done`.

### [2026-10-06T21:15:00Z] Démarrage de T1.1 : Reconnaissance des sources et registre
- **Mini-plan T1.1 :**
  1. Définir le modèle Pydantic `SourceDefinition` / `SourceSpec` dans `backend/src/ketrika/core/models/source.py`.
  2. Établir le registre `registry/sources.yaml` pour l'ensemble des sources de SPECS §5.2.
  3. Intégrer les fixtures réelles pour chaque source sous `backend/tests/fixtures/<source_id>/`.
  4. Rédiger les fiches descriptives normatives sous `docs/sources/<source_id>.md`.
  5. Implémenter le validateur CLI `python -m ketrika.core.registry`.
  6. Valider `./scripts/dev.ps1 validate-registry` et `./scripts/dev.ps1 check`.
  7. Mettre à jour PROGRESS.md et committer `feat(T1.1): source registry and documentation`.
- **Validation acceptation :**
  - Modèle Pydantic `SourceDefinition` complet (champs obligatoires, validation stricte, types, validation `redistribution_allowed`).
  - `registry/sources.yaml` créé et conforme avec les 9 sources obligatoires du MVP + source CHIRPS (10 sources au total).
  - Fiches normatives rédigées dans `docs/sources/<source_id>.md` (10 fiches conformes au template SPECS §5.3).
  - Fixtures réelles versionnées dans `backend/tests/fixtures/<source_id>/` (GeoJSON, CSV, JSON, texte).
  - Commande `./scripts/dev.ps1 validate-registry` exécutée avec succès (10 sources vérifiées).
  - Tests unitaires `tests/unit/test_registry.py` (5 tests) et `./scripts/dev.ps1 check` verts (ruff 0, mypy 0, pytest 8 passed, vitest 1 passed).
- Statut : **DONE**.

### [2026-10-06T21:30:00Z] Démarrage de T1.2 : Taxonomie produits et alias
- **Mini-plan T1.2 :**
  1. Définir les modèles Pydantic de la taxonomie (`ProductDefinition`, `ProductAlias`, `RiceVariety`) dans `backend/src/ketrika/core/models/taxonomy.py`.
  2. Rédiger `taxonomy/products.yaml` avec l'ensemble des produits vivriers PPN (SPECS §6.1).
  3. Rédiger `taxonomy/aliases.yaml` couvrant les amorces (SPECS §6.2) et 100 % des libellés produits des fixtures (WFP, RTFP, ODR, MinCC, Douanes, FAOSTAT).
  4. Rédiger `taxonomy/rice_varieties.yaml` répertoriant les variétés de riz ODR (Makalioka, Tsipala, Vary mena, X265...).
  5. Implémenter le chargeur et validateur dans `backend/src/ketrika/core/taxonomy.py`.
  6. Écrire la suite de tests unitaires `tests/unit/test_taxonomy.py`.
  7. Valider `./scripts/dev.ps1 check` et committer `feat(T1.2): product taxonomy, aliases and rice varieties`.
- **Validation acceptation :**
  - Fichiers `taxonomy/products.yaml` (15 produits PPN), `taxonomy/aliases.yaml` (29 alias), `taxonomy/rice_varieties.yaml` (8 variétés ODR), `taxonomy/unmapped.yaml` rédigés.
  - 100 % des libellés produits des fixtures (WFP, RTFP, ODR, MinCC, Douanes) sont résolus vers un code produit canonique avec confiance ≥ 0,7.
  - Module `ketrika.core.taxonomy` avec fonctions `load_products`, `load_aliases`, `load_rice_varieties`, `resolve_product`, `validate_taxonomy`.
  - Tests unitaires `tests/unit/test_taxonomy.py` (5 tests) : unicité des codes produits, unicité des alias normalisés, validité des références, couverture complète des fixtures.
  - `./scripts/dev.ps1 check` vert (ruff 0, mypy 0, pytest 13 passed, vitest 1 passed).
- Statut : **DONE**.

### [2026-10-06T21:35:00Z] Démarrage de T1.3 : Unités et conversions
- **Mini-plan T1.3 :**
  1. Définir les modèles Pydantic (`UnitDefinition`, `ProductConversion`) dans `backend/src/ketrika/core/models/units.py`.
  2. Rédiger `taxonomy/units.yaml` avec unités SI, conditionnements standards et unités locales malagasy (kapoaka, daba, gony...) avec preuves documentaires obligatoires.
  3. Implémenter le moteur de conversion et de validation dans `backend/src/ketrika/core/units.py`.
  4. Écrire les tests unitaires et tests de propriétés (Hypothesis) dans `backend/tests/unit/test_units.py`.
  5. Valider `./scripts/dev.ps1 check` et committer `feat(T1.3): units taxonomy and conversion engine`.
- **Validation acceptation :**
  - Référentiel `taxonomy/units.yaml` créé avec unités métriques SI (kg, g, t, qx, l, ml), conditionnements standards (sac_50kg, sac_25kg, bouteille_1l) et unités traditionnelles malagasy (kapoaka, daba, gony).
  - Preuves documentaires obligatoires (ODR, CIRAD, INSTAT) associées à chaque conversion de confiance ≥ 0,8.
  - Moteur de conversion dans `backend/src/ketrika/core/units.py` implémentant `convert_to_base`, `convert_from_base`, `validate_units`.
  - Tests unitaires et de propriétés (Hypothesis) dans `backend/tests/unit/test_units.py` (7 tests) : cohérence inverse prouvée sur des nombres aléatoires, vérification stricte des preuves, validation des unités de fixtures.
  - `./scripts/dev.ps1 check` vert (ruff 0, mypy 0, pytest 20 passed, vitest 1 passed).
- Statut : **DONE**.

### [2026-10-06T21:40:00Z] Démarrage de T1.4 : Géographie de référence
- **Mini-plan T1.4 :**
  1. Définir les modèles Pydantic (`GeographicEntity`, `LocationAlias`, `CropCalendarEntry`) dans `backend/src/ketrika/core/models/geo.py`.
  2. Établir les GeoJSON de référence simplifiés dans `geo/processed/` (admin0, admin1 avec les 23 régions officielles OCHA COD-AB, admin2).
  3. Rédiger `geo/README.md` avec provenance, `boundary_version`, dénombrement des entités et analyse 22 vs 23 vs 24 régions.
  4. Créer `taxonomy/location_aliases.yaml` couvrant 100 % des entités géographiques et marchés cités dans les fixtures.
  5. Rédiger `taxonomy/crop_calendar.yaml` pour le riz et le maïs par zone agro-climatique avec sources FAO GIEWS/FEWS NET.
  6. Implémenter le chargeur et résolveur géographique dans `backend/src/ketrika/core/geo.py`.
  7. Écrire les tests unitaires dans `backend/tests/unit/test_geo.py`.
  8. Valider `./scripts/dev.ps1 check`.
  9. Mettre à jour PROGRESS.md et committer `feat(T1.4): reference geography, location aliases and crop calendar`.
  10. Exécuter le Gate de fin de Phase 1 et créer le tag `phase-1-done`.
- **Validation acceptation :**
  - Modèles Pydantic `GeographicEntity`, `LocationAlias`, `CropCalendarEntry` dans `backend/src/ketrika/core/models/geo.py`.
  - GeoJSON de référence versionnés dans `geo/processed/` (admin0, admin1 avec les 23 régions officielles OCHA COD-AB, admin2).
  - Documentation `geo/README.md` détaillée avec provenance (`ocha_codab_mdg`), version `2024.1`, dénombrement et analyse du découpage (22 vs 23 vs 24 régions).
  - Référentiel `taxonomy/location_aliases.yaml` couvrant 100 % des entités et marchés cités dans les fixtures (Analamanga, Atsinanana, Vakinankaratra, Antananarivo, Antsirabe, Toamasina, Anosibe, Bazar Be, Asabotsy).
  - Calendrier des cultures `taxonomy/crop_calendar.yaml` couvrant le riz (cycles vakiambiaty, hosy, asara) et le maïs avec sources FAO GIEWS et FEWS NET.
  - Résolveur géographique et chargeurs dans `backend/src/ketrika/core/geo.py` avec `validate_geo()` renvoyant 0 erreur.
  - Suite de tests unitaires `backend/tests/unit/test_geo.py` (8 tests passants).
  - `./scripts/dev.ps1 check` vert (ruff 0, mypy 0, pytest 28 passed, vitest 1 passed).
- Statut : **DONE**.

### [2026-10-06T21:55:00Z] Gate de fin de Phase 1 (Reconnaissance et référentiels)
- **Résumé de phase (≤ 15 lignes) :**
  - **Livré :** Registre exhaustif des 9 sources MUST + CHIRPS (`registry/sources.yaml`), 10 fiches de documentation technique (`docs/sources/`), 10 jeux de fixtures représentatifs (`backend/tests/fixtures/`) ; taxonomie vivrière PPN (`taxonomy/products.yaml` avec codes HS6 et FAOSTAT vérifiés, `taxonomy/aliases.yaml`, `taxonomy/rice_varieties.yaml`) ; référentiel d'unités et conversions (`taxonomy/units.yaml` avec unités SI et traditionnelles malagasy prouvées par des sources documentaires) ; géographie de référence (`geo/processed/` avec 23 régions OCHA COD-AB, `geo/README.md`, `taxonomy/location_aliases.yaml`, `taxonomy/crop_calendar.yaml`). Moteurs de résolution et de validation `ketrika.core.registry`, `ketrika.core.taxonomy`, `ketrika.core.units`, `ketrika.core.geo`.
  - **Chiffres clés :** 10 sources documentées et vérifiées, 15 produits PPN, 29 alias produits résolvant 100 % des fixtures, 23 régions administratives officielles, 100 % des localisations de fixtures résolues, 28 tests unitaires backend passants (dont tests de propriétés Hypothesis sur conversions), 1 test web passant, 0 erreur lint/typecheck.
  - **Dettes :** Aucune dette non tracée.
  - **Risques :** Évolution future de la 24ème région administrative (Ambatosoa) documentée dans `geo/README.md` et gérée par alias sans rupture des séries historiques.
  - **Tag :** `phase-1-done`.


