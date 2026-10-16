# Dossier de Preuve — R3.1 : Application de l'éligibilité et du calendrier des séries

## 1. Contexte & Périmètre

- **Tâche :** R3.1 (Phase R3 — Prévisions de prix évaluées et honnêtes).
- **Date d'exécution :** 2026-10-16T15:55:00Z.
- **Environnement :** Conteneurs Docker isolés `ketrika-backend:dev` et `ketrika-web:dev`, worktree `/home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep`, branche `work/r1-sources-prep`.
- **Référence normative :** `AGENTS.md`, `MARKET_INTELLIGENCE_EXECUTION_PLAN.md` §8 (R3.1), `SPECS.md` §17, `ADR-004`, `ADR-073`.
- **Objectif :** Imposer des critères stricts de sélection et de temporalité pour les séries de prix candidates à l'apprentissage et à l'évaluation, exclure tout seuil artificiel de 6 points ou saisonnalité factice, interdire la compression des lacunes calendaires, rejeter la granularité district pour la publication de prévisions de prix, et auditer systématiquement les motifs d'exclusion sans aucune fabrication de séries pour satisfaire un quota.

---

## 2. Décisions d'Architecture & Règles Normatives (ADR-073)

1. **Clé de série explicite à 5 composantes :**
   Format canonique : `build_series_key(product_code, quality_grade, actor_level, location_pcode, unit)`
   Exemple : `rice_milled|standard|retail|MG11|kg`.
   Compatibilité assurée avec le parseur `parse_series_key` qui gère le format historique à 3 composantes (`product_code|location_pcode|actor_level`) en réinjectant les valeurs par défaut (`quality_grade='standard'`, `unit='kg'`).

2. **Restriction géographique stricte (ADR-004) :**
   Seuls les niveaux national (`admin_level = 0`) et régional (`admin_level = 1`) sont éligibles pour la publication et modélisation de prévisions de prix.
   Tout niveau district (`admin_level = 2`) ou commune (`admin_level = 3`) est rejeté avec motif explicite : `ineligible_geo_granularity`.

3. **Reconstruction de grille calendaire continue sans compression :**
   Chaque série est projetée sur une grille mensuelle régulière complète du premier mois observé au mois de coupure (`data_cutoff`).
   Les mois sans observation sont explicitement présents avec `price = None` (`np.nan` en tableau numpy), interdisant formellement l'écrasement des trous temporels et préservant l'intégrité des décalages lag-12.

4. **Seuils d'éligibilité historique et récence :**
   - Minimum 36 mois observés non nuls (`total_valid_points >= 36`). Rejet strict de 35 points (`insufficient_total_points`).
   - Récence minimale de 12 mois observés non nuls sur la fenêtre mobile des 24 derniers mois calendaires précédant `data_cutoff` (`recent_points_24m >= 12`). Rejet strict de 36 points sans récence récente (`insufficient_recency`).
   - Rejet de tout seuil arbitraire de 6 points.

5. **Étanchéité des types de prix :**
   Exclusion stricte des prix réglementés (`official_ppn`, prix administrés OMH) et des séries d'indices (CPI/NIPC) de la modélisation des prix de marché vivriers (`forbidden_price_type`).

6. **Séparation des cohortes et vérité terrain :**
   - Cohorte `observed` : séries composées à 100 % d'observations observées non imputées.
   - Cohorte `mixed` : séries comportant au moins une valeur imputée.
   - Vérité terrain d'évaluation strictement réservée à la cohorte observée (`require_observed_only=True`).

7. **Audit exhaustif et rapport d'exclusions :**
   Production de `SeriesEligibilityReport` recensant toutes les séries évaluées, les séries éligibles et les séries exclues avec leurs motifs précis et agrégat `summary_reasons`.
   Zéro fabrication de série fictive pour satisfaire un quota ou un KPI.

---

## 3. Résultats et Preuves d'Exécution

### 3.1 Tests Unitaires Dédiés R3.1 (`test_ml_series_eligibility.py`)

- **Commande :** `uv run pytest tests/unit/test_ml_series_eligibility.py -v --cov=ketrika.ml.series --cov-report=term-missing`
- **Résultat :** 16/16 tests passés en 12.70s (exit code 0).
- **Couverture de code sur `ketrika.ml.series` :** **98%** (215 statements, 4 missed).

Détail des 16 cas d'acceptation validés :
- `test_series_key_construction_and_parsing` : format 5 composantes et rétro-compatibilité 3 composantes.
- `test_calendar_shift_and_generation` : arithmétique de décalage mensuel et continuité calendaire.
- `test_rejection_of_insufficient_points_35` : refus strict de 35 points (< 36).
- `test_acceptance_of_36_points_with_sufficient_recency` : qualification de 36 points avec récence >= 12.
- `test_rejection_of_36_points_lacking_recency` : refus strict de 36 points sans récence (< 12 sur les 24 derniers mois).
- `test_rejection_of_district_granularity_admin_level_2` : refus de granularité district (admin_level=2).
- `test_rejection_of_commune_granularity_admin_level_3` : refus de granularité commune (admin_level=3).
- `test_acceptance_of_national_and_regional_granularity` : éligibilité nationale (0) et régionale (1).
- `test_rejection_of_regulated_prices_and_indices` : refus des prix officiels PPN et administrés.
- `test_calendar_grid_explicit_holes_not_compressed` : grille avec trous explicites (`None`, `np.nan`), forward fill et interpolation linéaire.
- `test_cohort_separation_observed_vs_mixed` : étiquetage et exclusion cohorte mixte en vérité terrain.
- `test_protocol_capacities_flags` : validation des drapeaux `can_backtest_6_windows` et `can_calibrate_conformal`.
- `test_no_synthetic_series_fabricated_for_kpi` : intégrité et zéro création artificielle.
- `test_fill_strategy_invalid` : levée d'exception sur stratégie de remplissage inconnue.
- `test_empty_observations_series` : gestion des séries sans prix valides.
- `test_audit_and_extract_eligible_series_session_mock` : qualification des fonctions d'accès SQL via session.

### 3.2 Non-Régression ML Globale (`ketrika.ml`)

- **Commande :** `uv run pytest tests/unit/test_ml_forecast.py tests/unit/test_ml_anomalies.py tests/unit/test_ml_series_eligibility.py -m "not integration" -v --cov=ketrika.ml --cov-report=term-missing`
- **Résultat :** 21/21 tests passés en 21.03s (exit code 0).
- **Couverture globale du package `ketrika.ml` :** **82%** (584 statements, 106 missed).

### 3.3 Contrôles Statiques (Lint & Typage)

- **Ruff check :** `uv run ruff check src/ketrika/ml/ tests/unit/test_ml_series_eligibility.py` -> All checks passed (exit code 0).
- **Mypy strict :** `uv run mypy src/ketrika/ml/ tests/unit/test_ml_series_eligibility.py` -> Success: no issues found in 7 source files (exit code 0).

### 3.4 Non-Régression Backend & Frontend

- **Backend core tests :** 50/50 tests passés en 36.83s (`test_gate_r2_decision_observatory.py`, `test_economic_dashboard.py`, `test_copilot.py`, `test_alerts.py`).
- **Frontend Vitest :** 39/39 tests passés en 3.32s (`smoke.test.ts`, `qa-runner.test.js`, `formatters.test.ts`, `proxy.test.ts`, `economy.test.ts`).
- **Frontend Typage & Lint :** `tsc --noEmit` code 0, `next lint` code 0 (0 warning, 0 error).

---

## 4. Conclusion de Qualification

La tâche **R3.1** satisfait l'intégralité des critères d'acceptation du plan d'exécution `MARKET_INTELLIGENCE_EXECUTION_PLAN.md` et des normes `AGENTS.md` :
- Les clés de séries sont formellement identifiées sur 5 composantes.
- La grille mensuelle régulière préserve strictement les trous calendaires.
- Les seuils d'éligibilité (>= 36 points totaux et >= 12 récents sur 24 mois) et de granularité (niveaux national et régional uniquement) sont appliqués mécaniquement.
- L'audit exhaustif consigne les séries exclues avec leurs motifs sans aucune fabrication artificielle de séries.
- Le statut passe à **DONE**.
