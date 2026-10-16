# Dossier de Preuve — R3.7 : Publication des prévisions, traçabilité des limites, gestion des abstentions et intégrité visuelle sans extrapolation (ADR-078)

## 1. Contexte & Périmètre

- **Tâche :** R3.7 (Phase R3 — Prévisions de prix évaluées et honnêtes).
- **Date d'exécution :** 2026-10-16T17:35:00Z.
- **Environnement :** Conteneurs Docker isolés `ketrika-backend:dev` et `ketrika-web:dev`, worktree `/home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep`, branche `work/r1-sources-prep`.
- **Référence normative :** `AGENTS.md`, `MARKET_INTELLIGENCE_EXECUTION_PLAN.md` §8 (R3.7), `SPECS.md` §17, §18, §19, §22, `ADR-004`, `ADR-073`, `ADR-074`, `ADR-075`, `ADR-076`, `ADR-077`, `ADR-078`.
- **Objectif :** Publier les prévisions de prix de marché en garantissant la transparence absolue des modèles et des limites :
  1. Versionner les runs et le dataset C4 (`dataset_fingerprint`), interdire formellement tout écrasement destructif des runs antérieurs.
  2. Exposer horizon, cible, origine (`data_cutoff`), modèle effectif, erreurs, intervalles `[p10, p90]`, couverture, cohorte, statut et raisons d'abstention.
  3. Qualifier loyalement toute référence naïve gagnante en tant que baseline (`is_baseline = True`).
  4. Interdire rigoureusement toute courbe de prévision de remplacement générée par le front ou un LLM lorsque les données sont absentes (panneau d'abstention loyale obligatoire).

---

## 2. Décisions d'Architecture & Règles Normatives (ADR-078)

1. **Conservation immuable des runs (C4) et traçabilité d'origine :**
   - Chaque exécution crée un nouvel enregistrement horodaté dans `ml.model_run` avec `params->>'dataset_fingerprint'`, `params->>'cohort'`, et son découpage d'horizon.
   - Les prévisions historiques associées dans `ml.forecast` ne sont jamais écrasées (`model_run_id` unique).
   - Les clients de l'API peuvent réinterroger n'importe quel run archivé via `/v1/forecasts?model_run_id={id}` ou `/v1/forecasts/runs/{id}`.

2. **Transparence totale des modèles et replis (Anti-tricherie A09) :**
   - Distinction formelle de `model_requested` (ex: `AutoARIMA`) et `model_effective` (ex: `SeasonalNaive`).
   - Présence obligatoire de `fallback_reason` (ex: `insufficient_history_for_arima`) et `status` (`nominal` | `baseline_fallback` | `experimental_insufficient_windows` | `abstained`).
   - Préservation de l'unité physique (`kg`) et de la devise (`MGA`).

3. **Intégration de la calibration conforme (R3.5) :**
   - Présence des champs `is_calibrated` (booléen), `calibration_sample_size` ($N_{\text{calib}}$), `interval_width` et `coverage_rate_80`.
   - Si $N_{\text{calib}} < 8$, label `is_calibrated = False` obligatoire avec avertissement explicite.

4. **Gestion des abstentions loyales :**
   - Catalogue des séries écartées ou abstenues (`/v1/forecasts/abstentions`) consignant la clé de série, la localisation, le niveau d'acteur, et la cause normative de rejet (ex: `insufficient_total_points_20_lt_36`, `district_granularity_rejected`, `excessive_missing_values`).

5. **Intégrité visuelle de l'interface (`PriceChart`, `/prices`) :**
   - L'UI distingue clairement les points observés et les points de prévision.
   - Tooltip analytique exhaustif affichant le modèle effectif, le statut de baseline, la calibration conforme, et la cause de repli éventuelle.
   - Si une série ne dispose pas de prévision qualifiée, un panneau d'abstention loyale est affiché. **Zéro point fictif ou interpolation LLM n'est inséré.**

---

## 3. Résultats et Preuves d'Exécution

### 3.1 Tests Unitaires & Intégration R3.7 (`test_ml_forecast_publication.py` & Suite ML)

- **Commande :**
  ```bash
  docker run --rm -e APP_ENV=test \
    -v "/home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep:/workspace:ro" \
    -v "/home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep/backend:/app" \
    -w /app ketrika-backend:dev \
    python -m pytest tests/unit/test_ml_forecast_publication.py tests/unit/test_ml_conformal_intervals.py tests/unit/test_ml_backtest_protocol.py tests/unit/test_ml_as_of_dataset.py tests/unit/test_ml_series_eligibility.py tests/unit/test_ml_anomalies.py tests/unit/test_ml_forecast.py tests/unit/test_ml_models_conformance.py -m "not integration" -v --cov=ketrika.ml --cov=ketrika.api.routers.forecasts --cov-report=term-missing
  ```
- **Résultat :** **53/53 tests passés en 81.60s** (exit code 0).
- **Couverture de code sur le routeur `ketrika.api.routers.forecasts` :** **86%** (86 statements, 12 missed).
- **Couverture globale `ketrika.ml` + `routers.forecasts` :** **92%** (1179 statements, 99 missed).
  - `ketrika.ml.backtest` : 98%
  - `ketrika.ml.series` : 98%
  - `ketrika.ml.conformal` : 96%
  - `ketrika.ml.dataset` : 92%
  - `ketrika.ml.forecast` : 91%

Détail des cas d'acceptation validés pour R3.7 :
1. `test_series_fingerprint_deterministic_and_unique` : calcul déterministe de l'empreinte SHA-256 du snapshot de données d'entrée.
2. `test_run_price_forecasting_pipeline_preserves_lineage_and_metadata` : persistance sans écrasement du `model_run_id`, liaison au fingerprint, préservation des quantiles `p10 <= p50 <= p90` et des métadonnées de calibration.
3. `test_forecast_abstentions_and_rejections_recorded` : génération de 0 fausse prévision et enregistrement formel des abstentions documentées en cas de critères non satisfaits.
4. `test_api_forecasts_endpoints` : conformité des endpoints REST `/v1/forecasts`, `/v1/forecasts/runs`, `/v1/forecasts/runs/{id}`, `/v1/forecasts/abstentions` et validation de l'export CSV.

### 3.2 Contrôle de Qualité Statique Backend (Linter & Types)

- **Ruff :** `uv run ruff check src/ketrika/ml/forecast.py src/ketrika/api/routers/forecasts.py src/ketrika/api/schemas.py src/ketrika/core/models/db.py alembic/versions/0012_forecast_metadata_and_abstentions.py tests/unit/test_ml_forecast_publication.py`
  - Statut : **0 erreur, 0 avertissement** (All checks passed!).
- **Mypy :** `uv run mypy src/ketrika/ml/forecast.py src/ketrika/api/routers/forecasts.py src/ketrika/api/schemas.py src/ketrika/core/models/db.py alembic/versions/0012_forecast_metadata_and_abstentions.py tests/unit/test_ml_forecast_publication.py`
  - Statut : **Success: no issues found in 6 source files**.

### 3.3 Contrôle de Qualité Statique & Build Frontend

- **Typecheck TypeScript (`npm run typecheck`) :** `tsc --noEmit` -> **0 erreur**.
- **Linter Frontend (`npm run lint`) :** `next lint` -> **✔ No ESLint warnings or errors**.
- **Tests Frontend Vitest (`npm run test`) :** **39/39 tests passés** (5 test files).
- **Build Production Next.js (`npm run build`) :** Compilation de 16 routes avec succès, dont `/prices` et `/economy`.
- **Synchronisation OpenAPI :** Schéma OpenAPI exporté dans `web/src/lib/api/openapi.json` et types synchronisés dans `web/src/lib/api/schema.d.ts`.

---

## 4. Conclusion & Qualification R3.7

- Tous les critères d'acceptation de la tâche **R3.7** sont formellement satisfaits et vérifiés.
- Le système garantit l'immutabilité des runs, l'honnêteté méthodologique sur les modèles et leurs limites, la publication explicite des abstentions et l'absence totale de fausse courbe générée par l'UI.
- La tâche passe à l'état `DONE`.
