# Dossier de Preuve — R3.9 : Gate de Prévision des Prix (Tag : `mi-r3-qualified`)

## 1. Contexte & Périmètre de Qualification

- **Tâche :** R3.9 (Gate MUST de fin de Phase R3 — Prévisions de prix évaluées et honnêtes).
- **Date d'exécution :** 2026-10-16T20:10:00Z.
- **Environnement :** Conteneurs Docker isolés `ketrika-backend:dev` et `ketrika-web:dev`, base de données PostgreSQL `aiagent-db-1`, worktree `/home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep`, branche `work/r1-sources-prep`.
- **Référence normative :** `AGENTS.md` §1, §3, §4, §10 ; `MARKET_INTELLIGENCE_EXECUTION_PLAN.md` §8 (R3.1–R3.9) ; `SPECS.md` §17, §18, §19, §22 ; `ADR-004`, `ADR-073`, `ADR-074`, `ADR-075`, `ADR-076`, `ADR-077`, `ADR-078`, `ADR-079`.
- **Objectif :** Valider formellement les 7 exigences métrologiques et scientifiques de la phase R3 sans dérogation :
  1. Éligibilité stricte des séries (36 mois observés minimum, récence 12/24 mois, refus du niveau district).
  2. Datasets as-of C2/C4 et absence totale de fuite temporelle (SHA-256 canonique déterministe).
  3. Modèles conformes, transparence absolue `model_requested` vs `model_effective`, refus de masquer un modèle naïf sous un faux nom ARIMA.
  4. Protocole d'évaluation temporelle en 3 phases étanches (sélection rolling-origin, calibration conforme, holdout test out-of-sample).
  5. Intervalles de prévision conformes étalonnés sur résidus réels passés, rejet absolu des replis arbitraires $\pm 10\%$, statut `uncalibrated_heuristic` si $N_{\text{calib}} < 8$, intervalle de Wilson à 95% sur la couverture à 80%.
  6. Publication immuable des runs C4 (`dataset_fingerprint`), catalogue des abstentions documentées, intégrité visuelle sans extrapolation artificielle par le front ou un LLM.
  7. Évaluation des erreurs maturées, décomposition multidimensionnelle intégrale (produit, région, horizon, saisonnalité), et respect strict du principe de parcimonie face aux baselines.

---

## 2. Synthèse d'Exécution des Critères du Gate R3 (`test_gate_r3_price_forecast.py`)

| Critère | Périmètre Qualifié | Résultat du Test | Constat Métrologique |
|---|---|---|---|
| **C1 : Éligibilité des Séries** | 35 points rejetés, récence < 12/24 mois rejetée, district admin_level=2 rejeté | **PASSED** | Aucune série artificielle fabriquée ; lacunes calendaires préservées en NaNs explicites. |
| **C2 : Datasets As-Of C2/C4** | Exclusion des publications et révisions futures par rapport à l'as-of ; SHA-256 reproductible | **PASSED** | Lignée C4 garantie ; empreinte canonique identique sur recomputation. |
| **C3 : Modèles Conformes** | `NaiveLast` exact, repli `AutoARIMA` -> `NaiveLast` si $N < 24$ mois avec motif explicite | **PASSED** | Transparence totale ; aucun ARIMA usurpé lors d'un repli naïf. |
| **C4 : Séparation Temporelle** | 6 fenêtres glissantes ($h=3$, train $\ge 24$ mois) strictement disjointes de la période holdout | **PASSED** | Zéro rétroaction ; partition de test finale protégée contre toute fuite. |
| **C5 : Calibration Conforme** | Quantiles non paramétriques sur résidus réels ; refus de $\pm 10\%$ ; Wilson 95% | **PASSED** | $0 \le p10 \le p50 \le p90$ respecté ; statut `uncalibrated_heuristic` certifié si $N_{\text{calib}} < 8$. |
| **C6 : Évaluation Maturée & Parcimonie** | Décomposition 4D (produit, région, horizon, saison) ; parsimonie $\Delta\text{WAPE} > 0{,}01$ | **PASSED** | Table multidimensionnelle complète ; baselines reconnues gagnantes si écart $< 1\%$. |

---

## 3. Résultats Chiffrés et Couverture Globale

- **Suite de Gate :** 6/6 tests passés en 28.14s (exit code 0).
- **Suite Complète ML (Phase R3) :** 66 tests passés en ~70s (exit code 0).
- **Couverture de code globale `ketrika.ml` :** **92 %** (largement supérieure au seuil minimal de 80%).
  - `ketrika.ml.anomalies` : 99 %
  - `ketrika.ml.backtest` : 98 %
  - `ketrika.ml.series` : 98 %
  - `ketrika.ml.conformal` : 96 %
  - `ketrika.ml.evaluation` : 92 %
  - `ketrika.ml.dataset` : 92 %
  - `ketrika.ml.forecast` : 91 %
  - `ketrika.api.routers.forecasts` : 86 %
- **Contrôles statiques backend :** Ruff clean (0 warning), Mypy strict clean (153 source files sans erreur).
- **Contrôles frontend :** Vitest 39 tests passés (5 files), build de production Next.js réussi (16 routes générées).
- **Migrations base de données :** Migrations Alembic 0011, 0012, 0013 appliquées avec succès sur PostgreSQL.

---

## 4. Décision de Clôture de Phase R3

Tous les critères d'acceptation du Gate R3.9 et de la phase R3 sont **entièrement validés sans aucune dérogation ni dette masquée**.  
Le statut de qualification de la phase est déclaré **QUALIFIED**.  
Le tag de jalon **`mi-r3-qualified`** est prêt à être apposé.
