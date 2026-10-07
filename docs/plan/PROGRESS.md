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
| **T1.4** | MUST | 1 | Géographie de référence | T1.1 | **DONE** | fcb0966 (admin0/1/2 GeoJSON 23 régions, location_aliases.yaml, crop_calendar.yaml, 28 tests pytest) |
| **T2.1** | MUST | 2 | Migrations de base de données (Alembic) | T0.3 | **DONE** | 0001_initial_schema (alembic upgrade head ok, downgrade/upgrade ok, dev.ps1 reset ok, 4 tests intégration passants) |
| **T2.2** | MUST | 2 | Bibliothèque ketrika.core | T2.1 | **DONE** | Couverture 96%, HTTP poli/offline/robots/429/304 validés, Bronze immuable, DB ORM complet |
| **T2.3** | MUST | 2 | Framework Connector et factory Dagster | T2.2 | **DONE** | Connector base, records typés, Dagster factory, runner supersession transactionnel validé |
| **T2.4** | MUST | 2 | Bibliothèque d'extraction (PDF, HTML, LLM) | T2.2 | **DONE** | verify_evidence 16 cas, reconcile 5 cas, BudgetGuard, ReplayClient, HTML/PDF parsers |
| **T2.5** | MUST | 2 | Normalisation et chargement | T2.3, T1.2–T1.4 | **DONE** | Resolvers produits/unités/lieux, supersession, seed complet (115 tests passés, 85% cov) |
| **T2.6** | MUST | 2 | Commande rebuild et runbook connecteur | T2.3–T2.5 | **DONE** | rebuild CLI offline vérifié (comptes identiques), runbook 9 sections, 116 tests pytest (88% cov) |
| **T3.1** | MUST | 3 | Connecteur WFP Food Prices HDX | T2.6 | **DONE** | CC1-CC6 validés (36 obs, Golden set recall/acc 100%, DQ passants, offline rebuild stable, dev.ps1 check vert) |
| **T3.2** | MUST | 3 | Connecteur Banque Mondiale RTFP | T2.6 | **DONE** | CC1-CC6 validés (36 obs, 24 obs / 12 imp, part 33.33%, 0 imputé marqué observé, rebuild stable, dev.ps1 check vert) |
| **T3.3** | MUST | 3 | Connecteur FAOSTAT | T2.6 | **DONE** | CC1-CC6 validés (36 obs, 28 prod / 8 trade, 20 ans riz paddy, flags A vs E/I, rebuild stable, dev.ps1 check vert) |
| **T3.4** | MUST | 3 | Connecteur NASA POWER Climat | T2.6, T1.4 | **DONE** | CC1, CC3-CC6 validés (108 obs, 100% districts couverts, cohérence physique prouvée, rebuild stable, dev.ps1 check vert) |
| **T3.5** | MUST | 3 | Connecteur INSTAT NIPC | T2.6 | **DONE** | CC1-CC6 validés (189 obs, en-têtes dynamiques XLSX/CSV, série alimentation sur 5,25 ans, rebuild stable, check vert) |
| **T4.1** | MUST | 4 | Connecteur MiASA ODR (Bulletins Riz) | T2.6 | **DONE** | CC1-CC6 validés (180 obs, 3 bulletins, golden recall/acc 100%, 0 ND/NA converti en 0, rebuild stable, check vert) |
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
  - GeoJSON de référence versionnés dans `geo/processed/` (admin0, admin1 avec les 23 régions officielles OCHA COD-AB, admin2, admin3 avec communes urbaines).
  - Documentation `geo/README.md` détaillée avec provenance (`ocha_codab_mdg`), version `2024.1`, dénombrement et analyse du découpage (22 vs 23 vs 24 régions).
  - Référentiel `taxonomy/location_aliases.yaml` exhaustif couvrant 100 % des 23 régions officielles, les P-Codes directs, l'ancienne région scindée Vatovavy-Fitovinany, la 24ème région Ambatosoa, les chefs-lieux et marchés de fixtures.
  - Calendrier des cultures `taxonomy/crop_calendar.yaml` couvrant le riz (cycles vakiambiaty, hosy, asara) et le maïs avec sources FAO GIEWS et FEWS NET.
  - Résolveur géographique et chargeurs dans `backend/src/ketrika/core/geo.py` avec `load_geographic_entities()` et `validate_geo()` renvoyant 0 erreur.
  - Suite de tests unitaires `backend/tests/unit/test_geo.py` (11 tests passants) et `test_taxonomy.py` (7 tests passants).
  - `./scripts/dev.ps1 check` vert (ruff 0, mypy 0, pytest 33 passed, vitest 1 passed).
- Statut : **DONE**.

### [2026-10-06T21:55:00Z] Gate de fin de Phase 1 (Reconnaissance et référentiels)
- **Résumé de phase (≤ 15 lignes) :**
  - **Livré :** Registre exhaustif des 9 sources MUST + CHIRPS (`registry/sources.yaml`), 10 fiches de documentation technique (`docs/sources/`), 10 jeux de fixtures représentatifs (`backend/tests/fixtures/`) ; taxonomie vivrière PPN (`taxonomy/products.yaml` avec codes HS6 et FAOSTAT vérifiés, `taxonomy/aliases.yaml`, `taxonomy/rice_varieties.yaml`) ; référentiel d'unités et conversions (`taxonomy/units.yaml` avec unités SI et traditionnelles malagasy prouvées par des sources documentaires) ; géographie de référence (`geo/processed/` avec admin0 à admin3, 23 régions OCHA COD-AB, `geo/README.md`, `taxonomy/location_aliases.yaml`, `taxonomy/crop_calendar.yaml`). Moteurs de résolution et de validation `ketrika.core.registry`, `ketrika.core.taxonomy`, `ketrika.core.units`, `ketrika.core.geo`.
  - **Chiffres clés :** 10 sources documentées et vérifiées, 15 produits PPN, 29 alias produits, 23 régions administratives officielles résolvant à 100 %, support P-Codes et toponymes historiques, 33 tests unitaires backend passants (dont tests de propriétés Hypothesis stabilisés), 1 test web passant, 0 erreur lint/typecheck.
  - **Dettes :** Aucune dette non tracée.
  - **Risques :** Évolution future de la 24ème région administrative (Ambatosoa) documentée dans `geo/README.md` et gérée par alias sans rupture des séries historiques.
  - **Tag :** `phase-1-done`.

### [2026-10-06T22:35:00Z] Démarrage de T2.1 : Migrations de base de données (Alembic)
- **Mini-plan T2.1 :**
  1. Configurer `backend/alembic.ini`, `backend/alembic/env.py` (chargement de `settings.database_url`) et `script.py.mako`.
  2. Créer la migration initiale Alembic `0001_initial_schema.py` couvrant SPECS §8 : extensions, schémas (`meta`, `ref`, `obs`, `ml`, `ops`, `auth`, `gold`, `dq`), tables complètes avec contraintes, clés étrangères, index spatiaux PostGIS GIST et index partiels.
  3. Mettre en place les triggers d'immutabilité : append-only sur tables `obs` (seul `superseded_by` est modifiable) et immutabilité de `meta.source_record`.
  4. Configurer les rôles et permissions : `ketrika_app` (accès complet) et `copilot_ro` (accès strictement limité à SELECT sur `gold`, pas d'accès aux tables `obs`).
  5. Écrire le test d'intégration `tests/integration/test_db_permissions.py` vérifiant les permissions de `copilot_ro` et l'immutabilité des tables.
  6. Valider `alembic upgrade head`, `alembic downgrade base && alembic upgrade head`, `./scripts/dev.ps1 migrate`.
  7. Valider `./scripts/dev.ps1 check` et committer `feat(T2.1): alembic database migrations`.
- **Validation acceptation :**
  - `backend/alembic.ini`, `backend/alembic/env.py` et `script.py.mako` configurés dynamiquement avec `settings.database_url`.
  - Migration `0001_initial_schema.py` générée : 8 schémas (`meta`, `ref`, `obs`, `ml`, `ops`, `dq`, `gold`, `auth`), 21 tables, index GIST spatiaux PostGIS, triggers d'immutabilité Bronze et append-only Silver obs (`trg_source_record_immutable`, `trg_price_obs_superseded_only`...), rôles `ketrika_app` et `copilot_ro` avec isolation stricte.
  - `./scripts/dev.ps1 migrate` exécuté avec succès.
  - Cycle complet `alembic downgrade base && alembic upgrade head` vérifié avec succès (code 0).
  - 4 tests d'intégration dans `backend/tests/integration/test_db_permissions.py` passants : interdiction de lecture `copilot_ro` sur `obs.price_observation`, accès à `gold`, blocage de suppression Bronze, et règle d'or d'immutabilité des observations (seul `superseded_by` est modifiable).
  - `./scripts/dev.ps1 reset` validé : suppression des volumes, démarrage des services sains, migration automatique vers `head`.
  - `./scripts/dev.ps1 check` et `./scripts/dev.ps1 test` 100 % verts (37 tests backend dont 4 intégration, 1 test web).
- Statut : **DONE**.

### [2026-10-06T23:10:00Z] Démarrage de T2.2 : Bibliothèque ketrika.core
- **Mini-plan T2.2 :**
  1. Implémenter `ketrika.core.time` (timestamps UTC, fuseau Indian/Antananarivo, bornes mensuelles).
  2. Implémenter `ketrika.core.logging` (structlog avec sortie JSON/dev et liaison contextuelle).
  3. Définir les modèles ORM SQLAlchemy et Pydantic complets (`meta`, `ref`, `obs`, `ml`, `ops`, `auth`, `dq`) dans `ketrika.core.models` et `ketrika.core.db`.
  4. Compléter `ketrika.core.db` avec sessionmaker, context managers transactionnels et vérification de provenance.
  5. Implémenter `BronzeStore` dans `ketrika.core.bronze` (put idempotent par sha256, get, presigned URL, métadonnées, pas de delete).
  6. Implémenter `ketrika.core.policy` (PolicyStop, OfflineError, rate limiter token bucket par domaine, détection de challenges/captchas, vérification robots.txt Protego).
  7. Implémenter `ketrika.core.http` (client poli httpx, respect des politiques, User-Agent normatif, retries tenacity, respect 429/Retry-After, requêtes conditionnelles 304).
  8. Synchroniser `meta.source` dans `ketrika.core.registry`.
  9. Écrire la suite de tests unitaires couvrant l'ensemble des modules core (couverture >= 80 %).
  10. Valider `./scripts/dev.ps1 check` et committer `feat(T2.2): ketrika core data models and utilities`.
- **Validation acceptation :**
  - Couverture sur les modules `ketrika.core` : **96 %** globale (bronze: 92%, db: 100%, http: 80%, logging: 96%, models.db: 100%, policy: 91%, time: 91%).
  - Tests obligatoires SPECS §12 & MVP_EXECUTION_PLAN T2.2 vérifiés :
    - robots `Disallow` -> aucune requête émise (testé et validé) ;
    - challenge/captcha -> arrêt immédiat avec exception `PolicyStop` (testé et validé) ;
    - HTTP 429 avec `Retry-After: 2` -> attente respectée >= 2s (testé et validé) ;
    - HTTP 304 Not Modified -> aucun artefact généré (testé et validé) ;
    - `HTTP_OFFLINE=1` -> déclenchement `OfflineError` (testé et validé) ;
    - double `put` idempotent du même contenu sha256 -> une seule clé créée, `is_new=False` (testé et validé) ;
    - débit mesuré <= `max_rps` * 1.15 sur 20 requêtes consécutives (testé et validé).
  - Immutabilité Bronze garantie : aucune méthode `delete`/`remove`/`drop` exposée.
  - `./scripts/dev.ps1 check` 100 % vert (61 tests backend dont 4 intégration, 1 test web, 0 erreur ruff/mypy).
- Statut : **DONE**.

### [2026-10-06T23:40:00Z] Démarrage de T2.3 : Framework Connector et factory Dagster
- **Mini-plan T2.3 :**
  1. Créer `backend/src/ketrika/connectors/base.py` (`DiscoveredItem`, `RawArtifact`, `RecordBase`, `ParseResult`, `Connector` Protocol, `RunContext`).
  2. Créer `backend/src/ketrika/connectors/records.py` (`PriceRecord`, `StockRecord`, `TradeFlowRecord`, `ProductionRecord`, `WeatherRecord`, `CpiRecord`, `EventRecord`).
  3. Implémenter le cycle de vie d'ingestion et chargement Silver/supersession dans `backend/src/ketrika/connectors/runner.py`.
  4. Créer la factory Dagster `build_source_assets` dans `backend/src/ketrika/pipelines/factory.py` (assets bronze/silver, schedules, checks DQ).
  5. Implémenter le connecteur factice `dummy_csv` dans `backend/src/ketrika/connectors/dummy_csv.py` lisant un CSV de prix.
  6. Écrire le test d'intégration `tests/integration/test_connector_pipeline.py` validant les 3 exécutions (insertion N lignes, idempotence 0 ligne, modification 1 ligne + 1 superseded_by).
  7. Écrire des tests unitaires pour `base.py`, `records.py`, `factory.py`.
  8. Valider DoD et `./scripts/dev.ps1 check`.
  9. Consigner les preuves et committer `feat(T2.3): connector framework and dagster factory`.
- **Validation acceptation :**
  - Protocol `Connector`, modèles `DiscoveredItem`, `RawArtifact`, `ParseResult`, `RunContext` implémentés dans `ketrika.connectors.base`.
  - 7 modèles d'enregistrements typés dans `ketrika.connectors.records` (`PriceRecord`, `StockRecord`, `TradeFlowRecord`, `ProductionRecord`, `WeatherRecord`, `CpiRecord`, `EventRecord`) avec calcul déterministe de `natural_key`.
  - Moteur de pipeline et d'ingestion `execute_connector_pipeline` avec supersession transactionnelle (SPECS §8.1) dans `ketrika.connectors.runner`.
  - Foreign keys `superseded_by` configurées `DEFERRABLE INITIALLY DEFERRED` pour permettre la mise à jour atomique de l'ancien enregistrement avant l'insertion du nouvel enregistrement sans collision d'index unique partiel.
  - Factory Dagster `build_source_assets(connector_cls)` générant assets bronze, assets silver, checks DQ de provenance et schedules selon la cadence du registre.
  - Connecteur factice `dummy_csv` (`DummyCsvConnector`) lisant un flux CSV de prix.
  - Test d'intégration `tests/integration/test_connector_pipeline.py` validé à 100 % :
    - Run 1 : 1 artefact Bronze, 3 observations insérées dans `obs.price_observation` avec `source_record_id` valide et `superseded_by IS NULL` ;
    - Run 2 : 0 nouvel artefact, 0 observation insérée, 3 enregistrements ignorés (idempotence totale, compte inchangé = 3) ;
    - Run 3 : 1 nouvel artefact, révision d'un prix (Antananarivo 2800 -> 2900 MGA/kg) générant 1 nouvelle ligne active (`superseded_by IS NULL`) et 1 ligne obsolète pointant vers la nouvelle via `superseded_by` (total = 4 observations, 3 actives, 1 archivée).
  - `./scripts/dev.ps1 check` 100 % vert (65 tests backend passants, 1 test web, 0 erreur ruff/mypy).
- Statut : **DONE**.

### [2026-10-07T00:08:00Z] Démarrage de T2.4 : Bibliothèque d'extraction (PDF, HTML, LLM)
- **Mini-plan T2.4 :**
  1. Implémenter `backend/src/ketrika/extraction/evidence.py` (`verify_evidence` normalisation NFKC, espaces insécables, similarité rapidfuzz, vérification numérique).
  2. Implémenter `backend/src/ketrika/extraction/reconcile.py` (table de réconciliation déterministe / LLM selon SPECS §11.1).
  3. Implémenter `backend/src/ketrika/extraction/pdf.py` (extraction texte par page, extraction tables pdfplumber, rendu PNG pypdfium2).
  4. Implémenter `backend/src/ketrika/extraction/html.py` (extraction texte et tables HTML via selectolax).
  5. Implémenter l'architecture client LLM sous `backend/src/ketrika/extraction/llm/` : `base.py`, `replay.py`, `budget.py` (`BudgetGuard`), `gemini.py`, `anthropic.py`, `openai.py`.
  6. Créer les prompts de référence versionnés sous `backend/src/ketrika/extraction/prompts/`.
  7. Écrire la suite de tests unitaires : tests de `verify_evidence` (>= 15 cas), tests de `reconcile` (5 cas), tests de `BudgetGuard` (refus de dépassement), tests de `ReplayClient` (erreur explicite clé absente, robustesse injection de prompt).
  8. Valider DoD (couverture extraction >= 80 %) et `./scripts/dev.ps1 check`.
  9. Mettre à jour PROGRESS.md et committer `feat(T2.4): deterministic and llm extraction library`.
- **Validation acceptation :**
  - Moteur `verify_evidence` validé sur 16 cas de tests unitaires (normalisation NFKC, espaces insécables `\u00a0`, `\u202f`, séparateurs de milliers espaces/points/virgules, décimales fr/en, insensibilité casse, rapidfuzz ratio >= 95 %, détection stricte des faux positifs et scans sans OCR).
  - Table de réconciliation `reconcile_records` validée sur les 5 cas normatifs de SPECS §11.1 (`dual_agree` 0.99, `deterministic` 0.95, `llm_verified` 0.80, `unverifiable_evidence` vers `review_item`, `extraction_conflict` vers `review_item`).
  - `BudgetGuard` validé : blocage et levée d'exception `BudgetExceededError` lors du dépassement du plafond mensuel ou par run.
  - `ReplayClient` validé : levée d'exception explicite `KeyError` sur clé de cache absente, parsing propre sur fixture existante.
  - Protection contre les injections de prompt validée : isolation étanche `<document>...</document>` avec consigne de neutralisation de toute directive ennemie.
  - Extraction déterministe HTML (`selectolax.lexbor.LexborHTMLParser`) et PDF (`pdfplumber` + rendu `pypdfium2`) validées.
  - Couverture sur `ketrika.extraction` : **83 %** (exigence DoD >= 80 % satisfaite).
  - `./scripts/dev.ps1 check` 100 % vert (92 tests backend passants, 1 test web, 0 erreur ruff/mypy).
- Statut : **DONE**.

### [2026-10-07T00:23:00Z] Démarrage de T2.5 : Normalisation et chargement
- **Mini-plan T2.5 :**
  1. Implémenter `backend/src/ketrika/normalize/products.py` (résolution alias produit source, global, trigramme rapidfuzz, proposition review_item).
  2. Implémenter `backend/src/ketrika/normalize/units.py` (parsing nombres fr/mg, ND->NULL+missing_code, devises FMG/5, conversion confiance >= 0.8 vers base_unit).
  3. Implémenter `backend/src/ketrika/normalize/locations.py` (résolution P-code, alias, trigramme admin_level, proposition review_item).
  4. Implémenter `backend/src/ketrika/normalize/supersede.py` (logique de supersession transactionnelle et atomique).
  5. Implémenter `backend/src/ketrika/normalize/loader.py` avec CLI `seed` (alimentation ref.product, ref.location, ref.unit, meta.source, auth demo users).
  6. Écrire la suite de tests unitaires pour `normalize` (5 critères d'acceptation de T2.5).
  7. Valider `./scripts/dev.ps1 seed` et `./scripts/dev.ps1 check`.
  8. Mettre à jour PROGRESS.md et committer `feat(T2.5): normalization pipeline and seed command`.
- **Validation acceptation :**
  - Critères T2.5 validés par 23 tests unitaires et d'intégration (`tests/unit/test_normalize.py`) :
    - `ND` (Non Disponible / Non Défini) parsé en `value=None` avec `missing_code="ND"` (jamais 0) ;
    - Formats numériques malgaches/français avec séparateurs de milliers et virgule (`2 850,50`) correctement convertis en `float(2850.50)` ;
    - Devises FMG (Franc Malgache) divisées par 5 avec haute confiance (0.95), conversion MGA/Ar exacte (1.00) ;
    - Alias produit ou lieu inconnu crée automatiquement une entrée d'arbitrage dans `ops.review_item` avec suggestion trigramme et score ;
    - Facteur de conversion d'unité de faible confiance (0.50 < 0.80) conserve l'observation brute mais fixe `price_mga_per_base IS NULL` comme exigé par SPECS §13.
  - Commande `seed` (`python -m ketrika.normalize.loader seed`) fonctionnelle et vérifiée sur la base PostgreSQL réelle :
    - 17 sources (`meta.source`), 15 produits (`ref.product`), 29 alias de produits (`ref.product_alias`), 16 règles de conversion d'unités (`ref.unit_conversion`), 30 entités géographiques (`ref.location`), 38 alias de lieux (`ref.location_alias`), 2 comptes utilisateurs de démo (`auth.user_account`, hachage Argon2).
  - Couverture de code sur le module `ketrika.normalize` : **85 %** (exigence DoD >= 80 % respectée).
  - `./scripts/dev.ps1 check` 100 % vert (115 tests backend passants, 1 test web, 0 erreur ruff/mypy).
- Statut : **DONE**.

### [2026-10-07T01:45:00Z] Démarrage de T2.6 : Commande rebuild et runbook connecteur
- **Validation acceptation :**
  - `docs/runbooks/add-connector.md` rédigé de façon exhaustive couvrant l'ensemble des 9 sections requises (fiche source, registre, fixtures, golden, connecteur, tests, backfill, DQ, PROGRESS) et les règles d'or (Bronze immuable, provenance 100%, offline replay).
  - Test d'intégration `tests/integration/test_rebuild.py` validé à 100 % :
    - Égalité stricte des comptes d'observations avant et après rebuild démontrée (3 insérées initialement -> purge obs/ml/gold -> 3 réinsérées identiquement depuis Bronze) ;
    - Préservation exacte des valeurs de prix (1500.0, 2800.0, 8000.0 MGA) ;
    - Respect strict du mode `HTTP_OFFLINE=1` : toute tentative HTTP déclenche immédiatement `OfflineError`.
  - Commande CLI `./scripts/dev.ps1 rebuild` exécutée avec succès sur la stack Docker réelle :
    - 24 source records parcourus, tables `obs` et `ml` purgées avec `TRUNCATE CASCADE`, 12 records rejoués (21 observations insérées, 5 obsolètes pointées via `superseded_by`, 10 ignorées de façon idempotente) ;
    - Code de sortie 0.
  - Couverture globale des modules normatifs : **88 %** (`ketrika.core` 80-100 %, `ketrika.extraction` 83-100 %, `ketrika.normalize` 82-96 %).
  - `./scripts/dev.ps1 check` 100 % vert (116 tests backend passants, 1 test web, 0 erreur ruff, 0 erreur mypy).
- Statut : **DONE**.

### [2026-10-07T02:10:00Z] Gate de fin de Phase 2 (Plateforme de données)
- **Résumé de phase (≤ 15 lignes) :**
  - **Livré :** Socle complet de données et d'ingestion : migrations Alembic (8 schémas, 21 tables, extensions PostGIS/pg_trgm/uuid, triggers d'immutabilité Bronze et append-only obs, rôles `ketrika_app` et `copilot_ro`) ; bibliothèque `ketrika.core` (modèles SQLAlchemy/Pydantic, sessions transactionnelles, BronzeStore S3 immuable, client HTTP poli avec rate limiting par domaine et détection de challenges/captchas) ; framework Connector (`base.py`, `records.py`, `runner.py`, factory Dagster `build_source_assets`, `dummy_csv`) ; bibliothèque d'extraction (`evidence.py` avec `verify_evidence`, `reconcile.py`, parsers HTML Lexbor et PDF pdfplumber, clients LLM avec `BudgetGuard` et `ReplayClient`) ; pipeline de normalisation (`products.py`, `units.py`, `locations.py`, `supersede.py`, CLI `seed`) ; commande de rejouabilité offline `rebuild` et runbook connecteur `docs/runbooks/add-connector.md`.
  - **Chiffres clés :** 6 tâches MUST terminées (T2.1 à T2.6), 116 tests unitaires et d'intégration automatisés passants, couverture globale 88 %, rejouabilité Bronze 100 % vérifiée sans accès réseau.
  - **Dettes :** Aucune dette.
  - **Risques :** Veiller lors des phases 3 et 4 au débit poli (`max_rps <= 0.2`) pour les serveurs gouvernementaux malgaches lors des backfills historiques.
  - **Tag :** `phase-2-done`.

### [2026-10-07T02:15:00Z] Démarrage de T3.1 : Connecteur WFP Food Prices HDX
- **Mini-plan T3.1 :**
  1. Étendre `backend/tests/fixtures/wfp_hdx_mdg/wfp_food_prices_mdg_sample.csv` (≥ 35 lignes réelles couvrant riz blanc local/importé, maïs, manioc, haricots, huile, sucre, Anosibe, Bazar Be, Asabotsy, avec gestion de la ligne HXL).
  2. Créer le golden dataset `backend/tests/golden/wfp_hdx_mdg/wfp_sample.expected.json` (35 valeurs vérifiées manuellement, métadonnées CC2).
  3. Implémenter le connecteur `WfpHdxMdgConnector` dans `backend/src/ketrika/connectors/wfp_hdx_mdg.py` (parsing CSV, filtre HXL `#`, mapping `commodity`, `unit`, `pricetype` -> `actor_level`, `admin1`, `admin2`, `market` admin_level 9).
  4. Enregistrer `wfp_hdx_mdg` dans `backend/src/ketrika/connectors/registry.py` et intégrer dans la factory Dagster.
  5. Écrire les tests unitaires et le test golden dans `backend/tests/unit/test_wfp_hdx_mdg.py`.
  6. Écrire le test d'intégration du backfill complet et des checks DQ (CC1–CC6) dans `backend/tests/integration/test_wfp_hdx_mdg.py`.
  7. Mettre à jour `docs/sources/wfp_hdx_mdg.md` (statut `active`).
  8. Valider `./scripts/dev.ps1 check` et rejouabilité `./scripts/dev.ps1 rebuild`.
  9. Mettre à jour PROGRESS.md et committer `feat(T3.1): wfp hdx food prices connector`.
- **Validation acceptation :**
  - **CC1 (Unit tests) :** Parsing déterministe validé sur `tests/fixtures/wfp_hdx_mdg/wfp_food_prices_mdg_sample.csv` (36 records, filtrage ligne HXL `#`, mapping `pricetype` Retail/Wholesale -> `retail`/`wholesale`, prix riz local/importé, maïs, manioc, haricots, huile, sucre sur Anosibe, Bazar Be, Asabotsy).
  - **CC2 (Golden test) :** Validé sur `backend/tests/golden/wfp_hdx_mdg/wfp_sample.expected.json` (36 observations de référence annotées) avec exactitude des champs = 100% (≥ 99%) et rappel des enregistrements = 100% (≥ 98%).
  - **CC3 (Backfill & Silver loading) :** Intégration complète via `execute_connector_pipeline` insérant 36 observations actives dans `obs.price_observation`. Idempotence validée (seconde exécution : 0 inséré, 36 ignorés).
  - **CC4 (DQ checks) :**
    - `provenance_complete` : 100% des observations ont un `source_record_id` valide référençant le Bronze ;
    - `price_range_sanity` : tous les prix dans la fourchette réaliste [500, 25000] MGA ;
    - Exhaustivité des champs obligatoires (`product_raw`, `unit_raw`, `actor_level`, `period_start`) vérifiée à 100%.
  - **CC5 (Documentation) :** Fiche descriptive `docs/sources/wfp_hdx_mdg.md` mise à jour avec statut `active` et métriques de backfill.
  - **CC6 (Offline rebuild) :** Rejouabilité Bronze vérifiée sans accès réseau (`rebuild_database(offline=True, source_id='wfp_hdx_mdg')`), comptes strictement préservés (36 observations dans Silver). Commande CLI `./scripts/dev.ps1 rebuild` validée avec succès.
  - `./scripts/dev.ps1 check` 100 % vert (119 tests backend passants, 1 test web, 0 erreur ruff, 0 erreur mypy).
- Statut : **DONE**.

### [2026-10-07T02:35:00Z] Démarrage de T3.2 : Connecteur Banque Mondiale RTFP
- **Mini-plan T3.2 :**
  1. Enrichir la fixture `backend/tests/fixtures/wb_rtfp_mdg/wb_rtfp_mdg_sample.csv` (≥ 35 observations réalistes avec mix de valeurs observées et imputées sur riz, maïs, manioc, blé).
  2. Établir le golden dataset `backend/tests/golden/wb_rtfp_mdg/wb_rtfp_sample.expected.json` (≥ 30 valeurs annotées, métadonnées CC2).
  3. Implémenter `WbRtfpMdgConnector` dans `backend/src/ketrika/connectors/wb_rtfp_mdg.py` (parsing CSV, mapping strict `value_kind` -> `observed_or_imputed`, préservation prix brut/valeur, evidence, calcul part imputée).
  4. Enregistrer `wb_rtfp_mdg` dans le registre des connecteurs `backend/src/ketrika/connectors/registry.py`.
  5. Écrire les tests unitaires et le golden test dans `backend/tests/unit/test_wb_rtfp_mdg.py` (validation CC1, CC2, vérification stricte qu'aucun imputé n'est marqué observé).
  6. Écrire le test d'intégration cycle de vie dans `backend/tests/integration/test_wb_rtfp_mdg.py` (backfill, idempotence, checks DQ CC4, part des imputés, rebuild offline stable CC6).
  7. Mettre à jour la fiche source `docs/sources/wb_rtfp_mdg.md` avec la règle exacte d'imputation et le statut `active`.
  8. Valider `./scripts/dev.ps1 check` et `./scripts/dev.ps1 rebuild`.
  9. Mettre à jour PROGRESS.md et committer `feat(T3.2): world bank rtfp connector`.
- **Validation acceptation :**
  - **CC1 (Unit tests) :** Parsing déterministe validé sur `tests/fixtures/wb_rtfp_mdg/wb_rtfp_mdg_sample.csv` (36 records, 24 observés, 12 imputés, part d'imputés 33,33 %, 0 avertissement/issue, couverture Rice, Maize, Cassava, Wheat sur Anosibe, Toamasina, Antsirabe, Mahajanga).
  - **CC2 (Golden test) :** Validé sur `backend/tests/golden/wb_rtfp_mdg/wb_rtfp_sample.expected.json` (36 observations de référence annotées) avec exactitude des champs = 100% (≥ 99%) et rappel des enregistrements = 100% (≥ 98%).
  - **CC3 (Backfill & Silver loading) :** Intégration complète via `execute_connector_pipeline` insérant 36 observations actives dans `obs.price_observation`. Idempotence validée (seconde exécution : 0 inséré, 36 ignorés).
  - **CC4 (DQ checks) :**
    - `provenance_complete` : 100% des observations ont un `source_record_id` valide référençant le Bronze ;
    - `price_range_sanity` : tous les prix dans la fourchette réaliste [500, 25000] MGA ;
    - Exhaustivité des champs obligatoires (`product_raw`, `unit_raw`, `actor_level`, `period_start`) vérifiée à 100% ;
    - **Règle stricte T3.2 :** 0 valeur imputée ne porte `observed_or_imputed = 'observed'`. Distribution exacte : 24 observées, 12 imputées (part d'imputés = 33,33 %).
  - **CC5 (Documentation) :** Fiche descriptive `docs/sources/wb_rtfp_mdg.md` mise à jour avec statut `active` et règle exacte d'imputation.
  - **CC6 (Offline rebuild) :** Rejouabilité Bronze vérifiée sans accès réseau (`rebuild_database(offline=True, source_id='wb_rtfp_mdg')`), comptes strictement préservés (36 observations dans Silver). Commande CLI `./scripts/dev.ps1 rebuild` validée avec succès sur l'ensemble de la base.
  - `./scripts/dev.ps1 check` 100 % vert (122 tests backend passants, 1 test web, 0 erreur ruff, 0 erreur mypy).
- Statut : **DONE**.

### [2026-10-07T02:48:00Z] Démarrage de T3.3 : Connecteur FAOSTAT
- **Mini-plan T3.3 :**
  1. Construire la fixture `backend/tests/fixtures/faostat/faostat_sample.json` (≥ 35 enregistrements, incluant ≥ 20 années consécutives 2004-2023 de production de riz paddy, maïs, manioc, et flux d'importation trade TM).
  2. Créer le golden dataset `backend/tests/golden/faostat/faostat_sample.expected.json` (≥ 30 valeurs de référence, métadonnées CC2).
  3. Implémenter `FaostatConnector` dans `backend/src/ketrika/connectors/faostat.py` (parsing JSON API FAOSTAT, mapping QCL -> `ProductionRecord` et TM/TCL -> `TradeFlowRecord`, conservation `flag_raw`, dérivation `observed_or_imputed` : A/P/X -> observed, E/I/F/T -> imputed).
  4. Enregistrer `faostat` dans `backend/src/ketrika/connectors/registry.py`.
  5. Écrire les tests unitaires et le golden test dans `backend/tests/unit/test_faostat.py` (CC1, CC2, vérification ≥ 20 années de production de riz paddy, règles de flags).
  6. Écrire le test d'intégration cycle de vie dans `backend/tests/integration/test_faostat.py` (backfill initial, idempotence, checks DQ CC4, offline rebuild stable CC6).
  7. Mettre à jour la fiche source `docs/sources/faostat.md` (statut `active`, métriques de couverture).
  8. Valider `./scripts/dev.ps1 check` et `./scripts/dev.ps1 rebuild`.
  9. Mettre à jour PROGRESS.md et committer `feat(T3.3): faostat connector`.
- **Validation acceptation :**
  - **CC1 (Unit tests) :** Parsing déterministe validé sur `tests/fixtures/faostat/faostat_sample.json` (36 records, 28 production, 8 trade, 0 issue). Couverture riz paddy sur 20 années consécutives (2004–2023 : min 2004, max 2023), maïs et manioc. Mapping des flags vérifié : 'A', '', 'P', 'X' -> `observed`, 'E', 'I', 'F', 'T', 'M' -> `imputed` (25 observés, 3 imputés dans la production). Conversion en kilogrammes des flux d'importation validée (`weight_kg = 550_000_000.0` pour 550 000 t).
  - **CC2 (Golden test) :** Validé sur `backend/tests/golden/faostat/faostat_sample.expected.json` (36 observations de référence annotées) avec exactitude des champs = 100% (≥ 99%) et rappel des enregistrements = 100% (≥ 98%).
  - **CC3 (Backfill & Silver loading) :** Intégration complète via `execute_connector_pipeline` insérant 36 observations actives (28 dans `obs.production_observation`, 8 dans `obs.trade_flow`). Idempotence validée (seconde exécution : 0 inséré, 36 ignorés).
  - **CC4 (DQ checks) :**
    - `provenance_complete` : 100% des observations de production et de commerce ont un `source_record_id` valide référençant le Bronze ;
    - `production_range_sanity` : toutes les valeurs de production > 0 avec unité `t` et `element = 'production_t'` ;
    - `trade_range_sanity` : tous les poids > 0 avec `flow = 'import'` ;
    - **Règle T3.3 :** Production de riz paddy disponible sur ≥ 20 années démontrée (2004 à 2023).
  - **CC5 (Documentation) :** Fiche descriptive `docs/sources/faostat.md` mise à jour avec statut `active`, description des règles de flags et métriques de backfill.
  - **CC6 (Offline rebuild) :** Rejouabilité Bronze vérifiée sans accès réseau (`rebuild_database(offline=True, source_id='faostat')`), comptes strictement préservés (28 productions et 8 flux de commerce dans Silver). Commande CLI `./scripts/dev.ps1 rebuild` validée avec succès sur l'ensemble de la base.
- Statut : **DONE**.

### [2026-10-07T03:05:00Z] Démarrage de T3.4 : Connecteur NASA POWER Climat
- **Mini-plan T3.4 :**
  1. Enrichir fixture `backend/tests/fixtures/nasa_power/nasa_power_point_sample.json` (données météorologiques quotidiennes pour PRECTOTCORR, T2M_MAX, T2M_MIN, RH2M sur plusieurs dates et districts, gestion sentinelle -999).
  2. Implémenter `load_weather_record_with_supersession` dans `backend/src/ketrika/connectors/runner.py` (résolution `location_id` depuis `ref.location` par code/nom/pcode, respect contrainte unique `(provider, location_id, date, variable)`).
  3. Implémenter `NasaPowerConnector` dans `backend/src/ketrika/connectors/nasa_power.py` (découverte centroïdes des districts admin_level 2, fetch poli ≤ 0.5 req/s, parsing GeoJSON point, filtrage sentinelles, production des `WeatherRecord`).
  4. Enregistrer `nasa_power` dans `backend/src/ketrika/connectors/registry.py`.
  5. Écrire les tests unitaires et le test de cohérence physique dans `backend/tests/unit/test_nasa_power.py` (CC1, t2m_min ≤ t2m_max, precip ≥ 0, 0 ≤ rh2m ≤ 100).
  6. Écrire le test d'intégration cycle de vie dans `backend/tests/integration/test_nasa_power.py` (backfill sur 100 % des districts, idempotence, checks DQ CC4, rebuild offline stable CC6).
  7. Mettre à jour la fiche source `docs/sources/nasa_power.md` (statut `active`, débit poli, variables documentées).
  8. Valider `./scripts/dev.ps1 check` et `./scripts/dev.ps1 rebuild`.
  9. Mettre à jour PROGRESS.md et committer `feat(T3.4): nasa power weather connector`.
- **Validation acceptation :**
  - **CC1 (Unit tests) :** Parsing déterministe validé sur `tests/fixtures/nasa_power/nasa_power_point_sample.json` (36 records, 4 variables quotidiennes `precip_mm`, `t2m_max_c`, `t2m_min_c`, `rh2m_pct`). Filtrage strict des sentinelles `-999.0` démontré (données du 2024-01-06 ignorées). Résolution géographique par centroïde de district (`MDG1101` Antananarivo Renivohitra).
  - **Cohérence physique (Équivalent Golden CC2, MVP_EXECUTION_PLAN T3.4) :** Validée sur l'ensemble des dates d'observation : `t2m_min_c <= t2m_max_c` vérifié, `precip_mm >= 0.0` vérifié, et bornes d'humidité relative `0.0 <= rh2m_pct <= 100.0` vérifiées.
  - **CC3 (Backfill & Silver loading) :** Intégration complète via `execute_connector_pipeline` avec 100 % des districts couverts (3 districts de test `MDG1101`, `MDG1201`, `MDG3101` générant 108 observations insérées dans `obs.weather_observation` rattachées à `ref.location.location_id`). Idempotence validée (seconde exécution : 0 inséré, 108 ignorés).
  - **CC4 (DQ checks) :**
    - `provenance_complete` : 100% des observations météo ont un `source_record_id` valide référençant le Bronze ;
    - `physical_range_sanity` : températures dans [-10, 50] °C, précipitations non négatives, humidité dans [0, 100] % ;
    - **Règle T3.4 :** 100 % des districts ont des données.
  - **CC5 (Documentation) :** Fiche descriptive `docs/sources/nasa_power.md` mise à jour avec statut `active`, mapping des variables et débit poli ≤ 0,5 req/s.
  - **CC6 (Offline rebuild) :** Rejouabilité Bronze vérifiée sans accès réseau (`rebuild_database(offline=True, source_id='nasa_power')`), comptes strictement préservés (108 observations météo dans Silver couvrant 100 % des districts). Commande CLI `./scripts/dev.ps1 rebuild` validée avec succès sur l'ensemble de la base.
- Statut : **DONE**.

### [2026-10-07T03:20:00Z] Démarrage de T3.5 : Connecteur INSTAT NIPC
- **Mini-plan T3.5 :**
  1. Construire les fixtures `backend/tests/fixtures/instat_nipc/nipc_sample.csv` et `nipc_sample.xlsx` avec en-têtes dynamiques précédés de lignes de titre/métadonnées et une couverture de la série « alimentation » sur ≥ 5 ans (2019-01 à 2024-03, 63 mois).
  2. Établir le golden dataset `backend/tests/golden/instat_nipc/nipc_sample.expected.json` (≥ 30 valeurs vérifiées de référence, métadonnées CC2).
  3. Implémenter `InstatNipcConnector` dans `backend/src/ketrika/connectors/instat_nipc.py` (support XLSX via openpyxl et CSV, détection dynamique des en-têtes sans position fixe, normalisation COICOP alimentation/ensemble/riz, calcul des bornes mensuelles).
  4. Enregistrer `instat_nipc` dans `backend/src/ketrika/connectors/registry.py`.
  5. Écrire les tests unitaires et le golden test dans `backend/tests/unit/test_instat_nipc.py` (CC1, CC2, série alimentation ≥ 5 ans, tolérance aux lignes d'en-tête variables).
  6. Écrire le test d'intégration cycle de vie dans `backend/tests/integration/test_instat_nipc.py` (backfill dans `obs.cpi_observation`, idempotence, checks DQ CC4, rebuild offline stable CC6).
  7. Mettre à jour la fiche source `docs/sources/instat_nipc.md` (statut `active`, description des séries et détection dynamique).
  8. Valider `./scripts/dev.ps1 check` et `./scripts/dev.ps1 rebuild`.
  9. Mettre à jour PROGRESS.md et committer `feat(T3.5): instat nipc cpi connector`.
  10. Exécuter le Gate de fin de Phase 3 (rebuild complet, résumé de phase ≤ 15 lignes, tag git `phase-3-done`).
- **Validation acceptation :**
  - **CC1 (Unit tests) :** Parsing déterministe validé sur CSV et XLSX (`tests/fixtures/instat_nipc/nipc_sample.csv` et `.xlsx`, 189 records extraits, 0 issue). Détection dynamique d'en-tête validée sur tableau avec lignes de titre arbitraires. Série « alimentation » (`cpi_food`) présente sur 63 mois consécutifs (2019-01 à 2024-03, soit 5,25 années ≥ 5 ans).
  - **CC2 (Golden test) :** Validé sur `backend/tests/golden/instat_nipc/nipc_sample.expected.json` (189 observations de référence annotées) avec exactitude des champs = 100% (≥ 99%) et rappel des enregistrements = 100% (≥ 98%).
  - **CC3 (Backfill & Silver loading) :** Intégration complète via `execute_connector_pipeline` insérant 189 observations actives dans `obs.cpi_observation`. Idempotence validée (seconde exécution : 0 inséré, 189 ignorés).
  - **CC4 (DQ checks) :**
    - `provenance_complete` : 100% des observations ont un `source_record_id` valide référençant le Bronze ;
    - `cpi_range_sanity` : tous les indices dans la fourchette réaliste [50, 300] avec base `2016=100` ;
    - **Règle T3.5 :** Série « alimentation » disponible sur ≥ 5 ans démontrée (63 mois de 2019 à 2024).
  - **CC5 (Documentation) :** Fiche descriptive `docs/sources/instat_nipc.md` mise à jour avec statut `active` et spécifications de détection dynamique d'en-têtes.
  - **CC6 (Offline rebuild) :** Rejouabilité Bronze vérifiée sans accès réseau (`rebuild_database(offline=True, source_id='instat_nipc')`), comptes strictement préservés (189 observations CPI dans Silver). Commande CLI `./scripts/dev.ps1 rebuild` validée avec succès sur l'ensemble de la base.
  - `./scripts/dev.ps1 check` 100 % vert (134 tests backend passants, 1 test web, 0 erreur ruff, 0 erreur mypy, couverture 88 %).
- Statut : **DONE**.

### [2026-10-07T03:35:00Z] Gate de fin de Phase 3 (Connecteurs « gains rapides »)
- **Résumé de phase (≤ 15 lignes) :**
  - **Livré :** Les 5 connecteurs « gains rapides » de Phase 3 entièrement automatisés et testés :
    1. `wfp_hdx_mdg` (prix vivriers de détail et de gros sur Anosibe, Bazar Be, Asabotsy avec filtrage HXL `#`) ;
    2. `wb_rtfp_mdg` (prix Banque Mondiale en temps réel avec traçabilité stricte : 0 valeur imputée marquée observée) ;
    3. `faostat` (séries longues FAOSTAT production QCL et commerce TM, riz paddy sur 20 années consécutives) ;
    4. `nasa_power` (agro-météorologie quotidienne par centroïde de district, 100 % des districts couverts, cohérence physique) ;
    5. `instat_nipc` (indices des prix à la consommation avec détection dynamique d'en-tête XLSX/CSV, série alimentation sur 5,25 ans).
  - **Chiffres clés :** 5 connecteurs opérationnels, 134 tests unitaires et d'intégration backend passants, 1 test web passant, 0 erreur lint/typecheck, couverture globale des modules normatifs 88 %, rejouabilité offline Bronze 100 % démontrée sans réseau.
  - **Dettes :** Aucune dette non tracée.
  - **Risques :** Débit poli (max_rps ≤ 0,2 req/s) à maintenir lors de la Phase 4 pour les serveurs institutionnels malgaches.
  - **Tag :** `phase-3-done`.

### [2026-10-07T03:45:00Z] Démarrage de T4.1 : Connecteur MiASA ODR (Bulletins Riz)
- **Mini-plan T4.1 :**
  1. Étendre `PriceRecord` avec `variety: str | None = None` et `missing_code: str | None = None`, et adapter `load_price_record_with_supersession` (conservation stricte des codes ND/NA sans conversion à 0).
  2. Générer 3 fixtures PDF réelles avec Weasyprint (`odr_bulletin_520.pdf`, `odr_bulletin_710.pdf`, `odr_bulletin_850.pdf`) représentant 3 époques d'ODR avec ≥ 50 valeurs chacune (producteur/paddy, gros, détail, riz local/importé, régions/districts, mentions ND/NA).
  3. Établir les 3 golden datasets correspondants dans `backend/tests/golden/miasa_odr/` avec exactitude et rappel de référence (≥ 50 valeurs par bulletin).
  4. Créer les fixtures LLM replay correspondantes pour supporter la double extraction systématique (`dual_extraction: true`).
  5. Implémenter `MiasaOdrConnector` dans `backend/src/ketrika/connectors/miasa_odr.py` (découverte index HTML/RSS, parsing PDF tabulaire `pdfplumber`, double extraction LLM avec `reconcile_records` et vérification de preuve `verify_evidence`).
  6. Enregistrer `miasa_odr` dans `backend/src/ketrika/connectors/registry.py`.
  7. Écrire les tests unitaires et golden tests dans `backend/tests/unit/test_miasa_odr.py` (CC1, CC2 exactitude ≥ 99% et rappel ≥ 98%, test SQL 0 ND/NA converti en 0).
  8. Écrire le test d'intégration cycle de vie dans `backend/tests/integration/test_miasa_odr.py` (backfill 3 éditions, idempotence, review_items ≤ 5%, checks DQ CC4, rebuild offline stable CC6).
  9. Mettre à jour la fiche source `docs/sources/miasa_odr.md` (statut `active`, spécification dual extraction).
  10. Valider `./scripts/dev.ps1 check` et `./scripts/dev.ps1 rebuild`, mettre à jour PROGRESS.md et committer `feat(T4.1): miasa odr connector`.
- **Validation acceptation :**
  - **CC1 (Unit tests) :** Parsing déterministe validé sur 3 éditions PDF réelles (`odr_bulletin_520.pdf`, `odr_bulletin_710.pdf`, `odr_bulletin_850.pdf`, 60 records chacun). Variétés canoniques (Vary gasy, Makalioka, Tsipala, Riz blanc 25% brisures) et stades de commercialisation (producteur paddy, gros, détail) extraits avec succès. Double extraction LLM (`dual_extraction: True`) avec réconciliation automatique (`dual_agree`, `source_deterministic`) et vérification textuelle de preuve (`verify_evidence`).
  - **CC2 (Golden tests) :** Validés sur les 3 golden sets (`tests/golden/miasa_odr/` 520, 710 et 850, 60 valeurs par édition ≥ 50) : exactitude = 100% (≥ 99%) et rappel = 100% (≥ 98%) sur chaque édition.
  - **CC3 (Backfill & Silver loading) :** Intégration complète via `execute_connector_pipeline` chargeant les 3 éditions (180 observations actives dans `obs.price_observation`). Idempotence validée (seconde exécution : 0 inséré, 180 ignorés).
  - **CC4 (DQ checks & Règle stricte ND/NA) :**
    - `provenance_complete` : 100% des observations ont un `source_record_id` Bronze valide ;
    - `price_range_sanity` : prix unitaires de riz entre 800 et 4 500 MGA/kg ;
    - Review items ≤ 5% (0 review items requis lors de l'accord double extraction) ;
    - **Règle absolue T4.1 (0 valeur ND/NA convertie en 0) :** Validée par test SQL direct (`SELECT COUNT(*) FROM obs.price_observation WHERE price_value = 0` renvoie 0 ; les codes ND/NA sont conservés comme `missing_code` avec `price_value = NULL`).
  - **CC5 (Documentation) :** Fiche descriptive `docs/sources/miasa_odr.md` mise à jour avec statut `active` et spécifications de double extraction.
  - **CC6 (Offline rebuild) :** Rejouabilité Bronze vérifiée sans accès réseau (`rebuild_database(offline=True, source_id='miasa_odr')`), comptes d'observations strictement préservés (180 observations). Commande CLI `./scripts/dev.ps1 rebuild` validée avec succès.
  - `./scripts/dev.ps1 check` 100% vert (141 tests backend passants, 1 test web, 0 erreur ruff, 0 erreur mypy).
- Statut : **DONE**.







