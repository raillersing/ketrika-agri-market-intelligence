# Dossier de Preuve — R3.3 : Références et modèles conformes (ADR-075, A09)

## 1. Contexte & Périmètre

- **Tâche :** R3.3 (Phase R3 — Prévisions de prix évaluées et honnêtes).
- **Date d'exécution :** 2026-10-16T16:25:00Z.
- **Environnement :** Conteneurs Docker isolés `ketrika-backend:dev` et `ketrika-web:dev`, worktree `/home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep`, branche `work/r1-sources-prep`.
- **Référence normative :** `AGENTS.md`, `MARKET_INTELLIGENCE_EXECUTION_PLAN.md` §8 (R3.3), `SPECS.md` §17.3, `ADR-004`, `ADR-075`, constat d'audit `A09`.
- **Objectif :** Éliminer radicalement toute dissimulation d'échec ou altération silencieuse de saisonnalité (A09). Implémenter les références normatives authentiques (`NaiveLast`, `SeasonalNaive` avec `season_length=12` strictement annuel), les modèles statistiques candidats (`AutoETS`, `AutoARIMA` avec `season_length=12`), la traçabilité absolue `model_requested` vs `model_effective` et `fallback_reason`, l'imputation locale étanche des lacunes calendaires du jeu d'entraînement (`impute_training_gaps`), la conservation stricte des unités/devises, et la primauté de la parcimonie (la référence naïve peut légitimement gagner).

---

## 2. Décisions d'Architecture & Règles Normatives (ADR-075)

1. **Références normatives de diagnostic et saisonnières :**
   - **`NaiveLast` :** Projection constante du dernier prix observé ($y_{t+h} = y_t$). Intervalles calculés à partir de la dispersion historique observée.
   - **`SeasonalNaive` :** Projection annuelle stricte avec `season_length = 12` ($y_{t+h} = y_{t+h-12}$).
   - **Interdiction formelle des saisons artificielles :** Tout repli silencieux vers une saison de 2, 3 ou 4 mois est formellement banni.

2. **Candidats statistiques normatifs (AutoETS, AutoARIMA) :**
   - `AutoETS` et `AutoARIMA` sont configurés avec `season_length = 12`.
   - Nécessitent au moins $2 \times \text{season\_length} = 24$ mois d'observations pour modéliser la saisonnalité. Si la série est plus courte, le modèle déclare un repli explicite vers `SeasonalNaive` (si $\ge 12$ mois) ou `NaiveLast`.

3. **Transparence et étanchéité des métadonnées (Anti-tricherie A09) :**
   - Chaque prédiction retourne un `ModelForecastResult` contenant :
     - `model_requested` (ex: "AutoARIMA")
     - `model_effective` (ex: "SeasonalNaive" ou "NaiveLast" si repli)
     - `status` ("fitted", "fallback", "abstained")
     - `fallback_reason` (ex: "insufficient_history: length 15 < 2*season_length (24)")
     - `parameters`, `unit` (ex: "kg"), `currency` (ex: "MGA").
   - **Zéro AutoARIMA affiché lorsqu'une moyenne ou un modèle naïf a tourné.**

4. **Traitement documenté et étanche des lacunes d'entraînement (`impute_training_gaps`) :**
   - Les trous de calendrier de la grille régulière (`np.nan`) sont imputés localement par interpolation linéaire sur `train_y` exclusivement.
   - Règle stricte d'abstention : si le taux de trous dépasse 30 % ou si une lacune consécutive excède 4 mois, le modèle s'abstient pour cause de données lacunaires (`excessive_missing_ratio` ou `excessive_consecutive_gap`).

5. **Légitimité et parcimonie du modèle naïf :**
   - Si `NaiveLast` ou `SeasonalNaive` obtient un WAPE inférieur ou égal (dans une marge de 0,01) à celui d'un modèle statistique complexe, la référence naïve est sélectionnée et affichée comme vainqueur légitime.

---

## 3. Résultats et Preuves d'Exécution

### 3.1 Tests Unitaires Dédiés R3.3 (`test_ml_models_conformance.py` & Suite ML)

- **Commande :** `docker run --rm -e APP_ENV=test -v ".../r1-sources-prep:/workspace:ro" -v ".../r1-sources-prep/backend:/app" -w /app ketrika-backend:dev python -m pytest tests/unit/test_ml_models_conformance.py tests/unit/test_ml_as_of_dataset.py tests/unit/test_ml_series_eligibility.py tests/unit/test_ml_forecast.py tests/unit/test_ml_anomalies.py -m "not integration" -v --cov=ketrika.ml --cov-report=term-missing`
- **Résultat :** **38/38 tests passés en 26.57s** (exit code 0).
- **Couverture globale `ketrika.ml` :** **84%** (875 statements, 136 missed).
  - `ketrika.ml.series` : **98%**
  - `ketrika.ml.dataset` : **92%**
  - `ketrika.ml.backtest` : **92%**
  - `ketrika.ml.anomalies` : **99%**
  - `ketrika.ml.models` : **79%**

Détail des 9 cas d'acceptation validés spécifiquement pour R3.3 :
1. `test_naive_last_exact_calculation` : calcul exact à la main de la projection constante NaiveLast et quantiles valides.
2. `test_seasonal_naive_annual_exact_calculation` : calcul exact à la main de SeasonalNaive annuel (lag-12).
3. `test_insufficient_history_explicit_fallback_traceability_a09` : traçabilité du repli A09, historique insuffisant explicite et aucun AutoARIMA masquant un naïf.
4. `test_training_gap_imputation_clean_and_interpolated` : validation de l'imputation linéaire déterministe et des seuils stricts d'abstention (gap > 4 mois ou ratio > 30%).
5. `test_models_with_imputed_gaps` : exécution réussie des modèles candidats sur des séries régulières avec lacunes admissibles.
6. `test_deterministic_reproducibility` : invariance stricte sous double exécution sur le même jeu de données.
7. `test_naive_baseline_can_win_selection` : victoire légitime de la référence naïve sur série plate ou compétitive.
8. `test_model_failure_does_not_abort_selection` : résilience de la sélection face au crash d'un candidat.
9. `test_model_simplicity_ranking` : hiérarchie de parcimonie (NaiveLast < SeasonalNaive < AutoETS < AutoARIMA).

### 3.2 Contrôle de Qualité Statique (Linter & Types)

- **Ruff :** `uv run ruff check src/ketrika/ml/ tests/unit/test_ml_models_conformance.py tests/unit/test_ml_forecast.py` -> 0 erreur, 0 avertissement.
- **Mypy :** `uv run mypy src/ketrika/ml/ tests/unit/test_ml_models_conformance.py tests/unit/test_ml_forecast.py` -> Success: no issues found in 9 source files.

---

## 4. Conclusion & Qualification R3.3

La tâche R3.3 est intégralement complétée, testée et documentée en conformité stricte avec `AGENTS.md` et `MARKET_INTELLIGENCE_EXECUTION_PLAN.md`.
