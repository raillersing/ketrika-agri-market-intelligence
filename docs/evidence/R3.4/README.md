# Dossier de Preuve — R3.4 : Protocole d'évaluation en trois phases, étanchéité de sélection et holdout test (ADR-076)

## 1. Contexte & Périmètre

- **Tâche :** R3.4 (Phase R3 — Prévisions de prix évaluées et honnêtes).
- **Date d'exécution :** 2026-10-16T16:40:00Z.
- **Environnement :** Conteneurs Docker isolés `ketrika-backend:dev` et `ketrika-web:dev`, worktree `/home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep`, branche `work/r1-sources-prep`.
- **Référence normative :** `AGENTS.md`, `MARKET_INTELLIGENCE_EXECUTION_PLAN.md` §8 (R3.4), `SPECS.md` §17.3, `ADR-004`, `ADR-074`, `ADR-075`, `ADR-076`.
- **Objectif :** Imposer un protocole d'évaluation temporelle rigoureusement étanche en trois étapes chronologiques (Sélection rolling-origin à 6 fenêtres, Calibration des résidus, Évaluation finale sur test set hors-échantillon). Garantir qu'aucune erreur ou donnée de test final n'influence le choix du modèle ou des hyperparamètres, décomposer les métriques WAPE, MAE, sMAPE et couverture par horizon ($h \in \{1, 2, 3\}$), sécuriser les cas de dénominateur nul, et interdire la réduction discrète du nombre de fenêtres sans étiquetage expérimental.

---

## 2. Décisions d'Architecture & Règles Normatives (ADR-076)

1. **Protocole séquentiel étanche en trois phases :**
   - **Phase 1 (Sélection du modèle) :** Backtest rolling-origin mensuel glissant sur 6 fenêtres ($h=3$) avec exigence de train minimal ($\ge 24$ mois). Le modèle gagnant $M^*$ est choisi exclusivement sur la validation croisée de cette phase.
   - **Phase 2 (Calibration conforme) :** Collecte des résidus d'erreurs passés avant la cible finale, sans réutilisation de points futurs.
   - **Phase 3 (Évaluation finale hors-échantillon) :** Le modèle $M^*$ est évalué sur un jeu de test final ultérieur (`holdout_len`). Les erreurs de holdout ne rétro-agissent jamais sur le choix du modèle.

2. **Garantie d'anti-fuite temporelle :**
   - Pour chaque fenêtre $k$, $\text{train\_end} \le \text{test\_start}$. Aucune information de la cible ne peut être consultée lors du fit.
   - Les données de holdout sont strictement scellées lors de la phase de sélection.

3. **Intégrité des origines de sélection :**
   - Si une série ne dispose pas d'assez d'historique pour constituer les 6 fenêtres avec un train $\ge 24$ mois, le protocole renvoie le statut `experimental_insufficient_windows` et s'abstient d'une certification normative complète (éliminant le vice méthodologique de réduction discrète à 1 ou 2 fenêtres).

4. **Décomposition des métriques par horizon ($h=1, 2, 3$) :**
   - En plus des agrégats globaux, chaque pas temporel $h$ dispose de ses propres métriques (`HorizonMetrics`) : WAPE, MAE, sMAPE, couverture et effectif (`sample_size`).

5. **Sécurité numérique :**
   - Dénominateur nul ou absence de points valides : pas de division par zéro, statut explicite `no_data` ou métrique non biaisée.

---

## 3. Résultats et Preuves d'Exécution

### 3.1 Tests Unitaires Dédiés R3.4 (`test_ml_backtest_protocol.py` & Suite ML)

- **Commande :** `docker run --rm -e APP_ENV=test -v ".../r1-sources-prep:/workspace:ro" -v ".../r1-sources-prep/backend:/app" -w /app ketrika-backend:dev python -m pytest tests/unit/test_ml_backtest_protocol.py tests/unit/test_ml_as_of_dataset.py tests/unit/test_ml_series_eligibility.py tests/unit/test_ml_anomalies.py tests/unit/test_ml_forecast.py tests/unit/test_ml_models_conformance.py -m "not integration" -v --cov=ketrika.ml --cov-report=term-missing`
- **Résultat :** **44/44 tests passés en 26.80s** (exit code 0).
- **Couverture de code sur `ketrika.ml.backtest` :** **96%** (163 statements, 6 missed).
- **Couverture globale `ketrika.ml` :** **86%** (946 statements, 135 missed).

Détail des 6 cas d'acceptation validés spécifiquement pour R3.4 :
1. `test_partition_backtest_windows_strict_temporal_bounds` : étanchéité chronologique stricte de chaque fenêtre rolling origin ($\text{train\_end} \le \text{test\_start}$ et conformité de longueur).
2. `test_insufficient_history_marks_experimental_status` : refus de réduction discrète des fenêtres et attribution du statut `experimental_insufficient_windows`.
3. `test_model_selection_never_sees_holdout_errors` : preuve formelle d'invariance du choix du modèle face à des perturbations du test set final (zéro fuite vers la sélection).
4. `test_per_horizon_metrics_decomposition` : décomposition exacte des métriques WAPE, MAE, sMAPE et couverture pour chaque horizon $h \in \{1, 2, 3\}$.
5. `test_zero_actuals_division_by_zero_safety` : robustesse numérique face à des cibles nulles.
6. `test_evaluate_final_holdout_standalone` : évaluation indépendante de la Phase 3 hors-échantillon.

### 3.2 Contrôle de Qualité Statique (Linter & Types)

- **Ruff :** `uv run ruff check src/ketrika/ml/backtest.py tests/unit/test_ml_backtest_protocol.py` -> 0 erreur, 0 avertissement.
- **Mypy :** `uv run mypy src/ketrika/ml/backtest.py tests/unit/test_ml_backtest_protocol.py` -> Success: no issues found in 2 source files.

---

## 4. Conclusion & Qualification R3.4

La tâche R3.4 est intégralement complétée, testée et documentée en conformité stricte avec `AGENTS.md` et `MARKET_INTELLIGENCE_EXECUTION_PLAN.md`.
