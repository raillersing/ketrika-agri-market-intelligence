# Dossier de Preuve — R3.5 : Calibration des intervalles conformes et surveillance de couverture empirique (ADR-077)

## 1. Contexte & Périmètre

- **Tâche :** R3.5 (Phase R3 — Prévisions de prix évaluées et honnêtes).
- **Date d'exécution :** 2026-10-16T16:55:00Z.
- **Environnement :** Conteneurs Docker isolés `ketrika-backend:dev` et `ketrika-web:dev`, worktree `/home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep`, branche `work/r1-sources-prep`.
- **Référence normative :** `AGENTS.md`, `MARKET_INTELLIGENCE_EXECUTION_PLAN.md` §8 (R3.5), `SPECS.md` §17.3, `ADR-004`, `ADR-073`, `ADR-074`, `ADR-075`, `ADR-076`, `ADR-077`.
- **Objectif :** Implémenter des intervalles de prévision honnêtes et calibrés (Conformal Prediction non paramétrique, quantile fini corrigé $(1-\alpha)(1+1/n)$). Supprimer tout repli heuristique arbitraire (ex: $\pm 10\%$). Exiger un effectif minimal de calibration ($N_{\text{calib}} \ge 8$) pour revendiquer le statut `is_calibrated = True` (sinon `uncalibrated_heuristic` avec avertissement explicite). Calculer l'intervalle d'incertitude binomial de Wilson à 95% sur la couverture empirique et surveiller les sous-couvertures significatives (`severe_undercoverage`, `mild_undercoverage`, `nominal_or_conservative`).

---

## 2. Décisions d'Architecture & Règles Normatives (ADR-077)

1. **Prédiction conforme non paramétrique :**
   - Calcul des résidus absolus passés $R_i = |y_i - \hat{y}_i|$.
   - Quantile conforme empirique fini : $\hat{q} = \text{Quantile}\left(|R|, \min\left(1.0, \frac{\lceil (n+1)(1-\alpha) \rceil}{n}\right)\right)$.
   - Bornes symétriques autour de la prévision ponctuelle $\hat{y}$ : $[\max(0, \hat{y} - \hat{q}), \hat{y} + \hat{q}]$.
   - Garantie mathématique de monotonie stricte : $[q_{10}, q_{90}] \subseteq [q_{05}, q_{95}]$.

2. **Seuil de qualification d'échantillon ($N_{\text{calib}} \ge 8$) :**
   - Si le nombre de résidus passés est strictement inférieur à 8 : interdiction formelle d'apposer le label `is_calibrated = True`.
   - La prévision reste utilisable avec mention explicite `is_calibrated = False`, statut `uncalibrated_heuristic` et `sample_size = n`.

3. **Incertitude statistique de la couverture (Intervalle de Wilson à 95%) :**
   - Sur $N$ observations réelles évaluées, la proportion de couverture observée $\hat{p} = \frac{k}{N}$ est encadrée par l'intervalle de Wilson asymptotiquement exact :
     $$w = \frac{\hat{p} + \frac{z^2}{2N} \pm z \sqrt{\frac{\hat{p}(1-\hat{p})}{N} + \frac{z^2}{4N^2}}}{1 + \frac{z^2}{N}}$$
     avec $z = 1.95996$ pour le niveau de confiance à 95%.
   - Évite les déductions hâtives de non-conformité sur de petits échantillons de test.

4. **Audit et diagnostic de santé des intervalles (`CoverageReport`) :**
   - Ventilation de la couverture pour chaque niveau nominal (50%, 80%, 95%).
   - Diagnostic automatique :
     - `nominal_or_conservative` : couverture dans ou au-dessus de l'intervalle de Wilson ou du nominal.
     - `mild_undercoverage` : légère sous-couverture.
     - `severe_undercoverage` : borne supérieure de Wilson strictement inférieure à la cible nominale moins une marge de tolérance.

---

## 3. Résultats et Preuves d'Exécution

### 3.1 Tests Unitaires Dédiés R3.5 (`test_ml_conformal_intervals.py` & Suite ML)

- **Commande :**
  ```bash
  docker run --rm -e APP_ENV=test \
    -v "/home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep:/workspace:ro" \
    -v "/home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep/backend:/app" \
    -w /app ketrika-backend:dev \
    python -m pytest tests/unit/test_ml_conformal_intervals.py tests/unit/test_ml_backtest_protocol.py tests/unit/test_ml_as_of_dataset.py tests/unit/test_ml_series_eligibility.py tests/unit/test_ml_anomalies.py tests/unit/test_ml_forecast.py tests/unit/test_ml_models_conformance.py -m "not integration" -v --cov=ketrika.ml --cov-report=term-missing
  ```
- **Résultat :** **49/49 tests passés en 31.30s** (exit code 0).
- **Couverture de code sur `ketrika.ml.conformal` :** **96%** (106 statements, 4 missed).
- **Couverture globale `ketrika.ml` :** **87%** (1066 statements, 142 missed).

Détail des 5 cas d'acceptation validés spécifiquement pour R3.5 :
1. `test_conformal_quantiles_strictly_ordered_and_positive` : respect de l'ordonnancement strict des quantiles ($q_{10} < q_{20} < \dots < q_{90}$) et positivité des bornes.
2. `test_insufficient_residuals_prevents_calibrated_label` : rejet formel du label `is_calibrated = True` lorsque $N_{\text{calib}} < 8$, préservation de la traçabilité `sample_size` et du statut `uncalibrated_heuristic`.
3. `test_wilson_score_interval_exactness` : conformité analytique des bornes de Wilson pour proportions extrêmes (0/10, 10/10, 8/10).
4. `test_audit_interval_coverage_full_breakdown` : audit complet de la couverture empirique avec détection loyale des sous-couvertures et sur-couvertures.
5. `test_empty_actuals_safe_handling` : robustesse numérique absolue en l'absence de valeurs réelles ou de résidus.

### 3.2 Contrôle de Qualité Statique (Linter & Types)

- **Ruff :** `uv run ruff check src/ketrika/ml/conformal.py src/ketrika/ml/models.py src/ketrika/ml/__init__.py tests/unit/test_ml_conformal_intervals.py`
  - Statut : **0 erreur, 0 avertissement** (All checks passed!).
- **Mypy :** `uv run mypy src/ketrika/ml/conformal.py src/ketrika/ml/models.py src/ketrika/ml/__init__.py tests/unit/test_ml_conformal_intervals.py`
  - Statut : **Success: no issues found in 4 source files**.

---

## 4. Conclusion & Qualification R3.5

- Tous les critères de la tâche **R3.5** sont formellement satisfaits et vérifiés.
- Le module `ketrika.ml.conformal` fournit l'infrastructure de confiance et de transparence pour les incertitudes de prévision du programme Market Intelligence.
- La tâche passe à l'état `DONE`.
