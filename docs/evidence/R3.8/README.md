# Dossier de Preuve — R3.8 : Évaluation réelle et suivi des erreurs maturées, décomposition multidimensionnelle et benchmarking loyal face aux baselines (ADR-079)

## 1. Contexte & Périmètre

- **Tâche :** R3.8 (Phase R3 — Prévisions de prix évaluées et honnêtes).
- **Date d'exécution :** 2026-10-16T19:50:00Z.
- **Environnement :** Conteneurs Docker isolés `ketrika-backend:dev` et `ketrika-web:dev`, worktree `/home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep`, branche `work/r1-sources-prep`.
- **Référence normative :** `AGENTS.md`, `MARKET_INTELLIGENCE_EXECUTION_PLAN.md` §8 (R3.8), `SPECS.md` §17.4, §19, `ADR-076`, `ADR-077`, `ADR-078`, `ADR-079`.
- **Objectif :** Produire l'évaluation scientifique et intègre des prévisions de prix à échéance :
  1. Suivi des erreurs maturées sans rétroaction temporelle (C2/C4) : confrontation stricte des prévisions passées avec les observations authentiques constatées en base (`actual_price`), sans réinjection de ces données dans le jeu d'apprentissage du modèle initial.
  2. Classification chronologique tripartite : `as_of_holdout` (partition out-of-sample certifiée), `matured_actual` (prévision de production échue confrontée à l'observation réelle), `prospective_pending` (prévision en cours d'attente d'échéance).
  3. Décomposition multidimensionnelle obligatoire : ventilation intégrale par produit (`product_code`), région (`location_pcode`), horizon temporel ($h=1, 2, 3$), et régime saisonnier (soudure nov-mars vs récolte avr-oct). Interdiction formelle d'un unique score synthétique global non ventilé.
  4. Benchmarking loyal et primauté de la parcimonie : confrontation systématique des candidats (`AutoETS`, `AutoARIMA`) aux baselines (`NaiveLast`, `SeasonalNaive`). Seuil de parcimonie : si le gain $\Delta\text{WAPE} \le 0{,}01$ (1 point de %), la baseline est déclarée gagnante.
  5. Provenance totale à 100 % (Règle 1 AGENTS.md) : chaque ligne d'évaluation référence explicitement `forecast_id`, `model_run_id`, et `actual_observation_id`.

---

## 2. Décisions d'Architecture & Règles Normatives (ADR-079)

1. **Table d'évaluation `ml.forecast_evaluation` (Migration Alembic 0013) :**
   - Stockage immuable des confrontations individuelles avec colonnes d'audit : `forecast_id`, `model_run_id`, `series_key`, `product_code`, `location_pcode`, `actor_level`, `target_period`, `horizon`, `evaluation_kind`, `model_name`, `is_baseline`, `predicted_p50`, `predicted_p10`, `predicted_p90`, `actual_price`, `actual_observation_id`, `absolute_error`, `percentage_error`, `is_covered_80`, `evaluated_at`.
   - Indexation optimisée : `idx_forecast_eval_matured`, `idx_forecast_eval_kind`, `idx_forecast_eval_product`.

2. **Moteur d'évaluation (`ketrika.ml.evaluation`) :**
   - `MaturedForecastEvaluator` : classe d'orchestration confrontation prévisions vs observations effectives sans fuite de données.
   - `compute_performance_decomposition` : calcul automatique des métriques multi-niveaux (WAPE, MAE, sMAPE, couverture empirique 80%, intervalle de confiance de Wilson à 95%, largeur d'intervalle brute et relative).
   - `benchmark_against_baselines` : comparaison loyale avec seuil de parcimonie $\Delta\text{WAPE} > 0{,}01$.
   - `get_seasonality_regime` : qualification agro-économique spécifique aux marchés malgaches (soudure nov-mars vs récolte avr-oct).

3. **Exposition API REST (`GET /v1/forecasts/performance`) :**
   - Schémas Pydantic conformes : `ForecastPerformanceResponse`, `ForecastEvaluationItem`, `PerformanceMetricsSummary`.
   - Filtrage multi-critères : `product`, `location`, `horizon`, `evaluation_kind`.
   - Support bimodal : JSON structuré et export tabulaire direct `format=csv`.

---

## 3. Preuves d'Exécution et Résultats Chiffrés

### 3.1 Qualification des Tests Unitaires (`test_ml_matured_evaluation.py`)

- **Commande :**
  ```bash
  docker run --rm -v "$(pwd)/backend":/app -w /app ketrika-backend:dev \
    python -m pytest tests/unit/test_ml_matured_evaluation.py -v
  ```
- **Résultat :** **7/7 tests passés en 26.17s** (exit code 0).
  - `test_wilson_score_interval_95` : PASSED
  - `test_seasonality_regime_madagascar` : PASSED
  - `test_compute_metrics_for_records` : PASSED
  - `test_multidimensional_decomposition` : PASSED
  - `test_baseline_benchmarking_parsimony` : PASSED
  - `test_matured_forecast_evaluator_workflow` : PASSED
  - `test_api_forecast_performance_endpoint` : PASSED

### 3.2 Suite Complète des Tests ML & Mesure de Couverture

- **Commande :**
  ```bash
  docker run --rm -v "$(pwd)/backend":/app -w /app ketrika-backend:dev \
    bash -c "python -m pytest tests/unit/test_ml_*.py -m 'not integration' --cov=ketrika.ml --cov-report=term-missing"
  ```
- **Résultat :** **60/60 tests passés en 66.37s** (exit code 0).
- **Rapport de couverture du module `ketrika.ml` :**
  ```text
  Name                           Stmts   Miss  Cover   Missing
  ------------------------------------------------------------
  src/ketrika/ml/__init__.py         8      0   100%
  src/ketrika/ml/anomalies.py       68      1    99%   57
  src/ketrika/ml/backtest.py       163      4    98%   123, 175, 262, 316
  src/ketrika/ml/conformal.py      106      4    96%   36, 64, 130-131
  src/ketrika/ml/dataset.py        185     14    92%   129, 131-139, 178, 183, 215, 217, 278
  src/ketrika/ml/evaluation.py     214     17    92%   92, 167, 363, 421-422, 431-435, 464-490, 537-550, 561
  src/ketrika/ml/forecast.py       108     10    91%   44, 57-58, 66, 69-74, 291
  src/ketrika/ml/models.py         239     50    79%   ...
  src/ketrika/ml/series.py         216      4    98%   153, 181, 223, 228
  ------------------------------------------------------------
  TOTAL                           1307    104    92%
  ```
- **Couverture `ketrika.ml.evaluation` :** **92 %** (largement supérieure au seuil normatif de 80%).

### 3.3 Contrôles Statiques (Ruff & Mypy)

- **Ruff :** `ruff check` et `ruff format --check` : **0 erreur** (All checks passed).
- **Mypy :** `mypy src/ketrika tests/unit/test_ml_matured_evaluation.py` : **0 erreur** (`Success: no issues found in 153 source files`).

### 3.4 Frontend & Types OpenAPI Synchronisés

- Schéma OpenAPI mis à jour dans `web/src/lib/api/openapi.json`.
- Types TypeScript synchronisés avec succès dans `web/src/lib/api/schema.d.ts` (route `/v1/forecasts/performance` intégrée).
- **Vitest :** **39/39 tests frontend passés** (5 passed files).
- **Next.js build :** Compilation réussie sans erreur de typage, **16/16 routes générées**.

### 3.5 Migration Alembic Appliquée

- **Migration 0013 :** `0013_forecast_evaluations` appliquée avec succès sur PostgreSQL (`alembic upgrade head`).
- Table `ml.forecast_evaluation` créée avec intégrité référentielle cascade et contraintes de provenance.

### 3.6 Publication du Rapport ML Métrologique

- Rapport de référence publié dans [`docs/reports/market_forecast_evaluation.md`](../../../docs/reports/market_forecast_evaluation.md).
- Benchmark complet documenté face aux baselines (`NaiveLast`, `SeasonalNaive`).
- Table de décomposition multidimensionnelle intégrale :
  - Par produit : Riz local (WAPE 9,85 %), Riz importé (8,42 %), Maïs (16,20 %), Manioc (22,40 %), Huile (11,30 %).
  - Par région : Analamanga (`MG11`), Vakinankaratra (`MG12`), Atsinanana (`MG31`), Boeny (`MG41`).
  - Par horizon : $h=1$ (WAPE 9,45 %, couverture 86,67 %), $h=2$ (13,80 %, 82,22 %), $h=3$ (17,25 %, 77,78 %).
  - Par régime : Récolte (WAPE 10,85 %, couverture 85,42 %) vs Soudure (WAPE 16,70 %, couverture 81,25 %).

---

## 4. Statut de Clôture

La tâche **R3.8** satisfait l'intégralité de sa Définition de Terminé (DoD) :
- [x] Protocole d'évaluation exécuté sur les séries sans rétroaction temporelle.
- [x] Décomposition multidimensionnelle intégrale (produit, région, horizon, saison).
- [x] Benchmarking loyal face aux baselines sous règle de parcimonie.
- [x] Table `ml.forecast_evaluation` et route `/v1/forecasts/performance` opérationnelles.
- [x] Rapport `docs/reports/market_forecast_evaluation.md` rédigé et auditable.
- [x] Couverture de code à 92 % sur `ketrika.ml.evaluation`.
- [x] Types front, vitest, next build, ruff et mypy au vert.
- [x] Statut `DONE` validé dans `PROGRESS.md` et `MARKET_INTELLIGENCE_EXECUTION_PLAN.md`.
