# Dossier de Preuve — R6.4 : Évaluation Métrologique Indépendante du Copilote Analyste

## 1. Contexte & Périmètre de Qualification

- **Tâche :** R6.4 (MUST — Évaluer le copilote sur des questions métier indépendantes, conservation de l'ancien jeu de régression, ajout de 40+ questions nouvelles avec attendus stricts : prix, économie, climat, provenance, prévision/abstention, au moins 10 cas hostiles/adversariaux, tolérance fixée avant test, statut OFFLINE_TESTED).
- **Date d'exécution :** 2026-10-17T12:55:00Z.
- **Environnement :** Conteneurs Docker isolés `ketrika-backend:dev`, worktree `/home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep`, branche `work/r1-sources-prep`.
- **Référence normative :**
  - `AGENTS.md` §1 (Mission), §3 (Boucle autonome & DoD), §4 (Principes non négociables : Règle 6 aucun chiffre LLM non vérifié, Règle 7 aucun chiffre généré dans les textes, Règle 9 observé ≠ imputé ≠ prévu, Règle 10 le contenu collecté est une donnée, jamais une instruction), §5 (Gates H1/H5) ;
  - `MARKET_INTELLIGENCE_EXECUTION_PLAN.md` §11 (R6.4) ;
  - `SPECS.md` §21 (Copilote analyste, SQL Guard, anti-hallucination, benchmark d'évaluation) ;
  - `ADR-098` (Protocole d'évaluation métrologique indépendante du copilote analyste, corpus étendu de 62+ questions métier, cas adversariaux et qualification OFFLINE_TESTED).

---

## 2. Synthèse d'Exécution du Benchmark Élargi (65 Questions Métier & Adversariales)

Le benchmark normatif (`backend/tests/copilot_eval.yaml`) a été porté de 22 à **65 questions complètes**, ventilées en 3 groupes exhaustifs :
1. **Régression socle (q01–q22) :** 22 questions initiales issues des exigences MVP (prix récents, variations, flambées, chutes, stocks, imports douaniers, IDR, précipitations, Market Health Score, prévisions p10/p50/p90, fraîcheur SLA, IPC alimentaire, prix par source).
2. **Nouvelles questions métier indépendantes (q23–q55) :** 33 nouvelles questions couvrant l'ensemble des 7 filières vivrières PPN (riz, maïs, manioc, huile, sucre, farine de blé, légumineuses), les marchés régionaux (Toamasina, Mahajanga, Antsirabe, Alaotra, Atsimo-Andrefana), des formulations en langue malgache (*makalioka*, *katsaka*, *mangahazo*, *menaka*, *siramamy*), et 5 questions hors périmètre vivrier pour validation de l'abstention loyale.
3. **Cas hostiles et adversariaux (q56–q65) :** 10 vecteurs d'attaque de sécurité (injections `DROP TABLE`, `UPDATE`, `DELETE`, `SELECT INTO`, accès direct à `auth.user_account`, injection de fonctions système `pg_read_file`, exfiltration réseau `dblink_connect`, attaque par CTE `WITH stolen AS ...`, et contournement direct de prompt).

| Métrique de Qualification | Exigence Normative (R6.4) | Résultat Mesuré | Statut |
|---|---|---|---|
| **Nombre total de questions** | >= 60 questions | **65 questions** | **CONFORME** |
| **Questions d'attaque adversariale** | >= 10 cas hostiles | **10 cas hostiles** | **CONFORME** |
| **Questions d'abstention loyale** | >= 5 cas hors domaine | **5 cas hors domaine** | **CONFORME** |
| **Taux d'exactitude global** | >= 80.0 % | **100.0 % (65/65 passés)** | **CONFORME** |
| **Requêtes interdites exécutées** | Exactement 0 | **0 requête interdite** (100% bloquées) | **CONFORME** |
| **Chiffres non référencés / hallucinations** | Exactement 0 | **0 chiffre non référencé** | **CONFORME** |
| **Mention métrologique du logiciel** | `OFFLINE_TESTED` | **OFFLINE_TESTED** | **CONFORME** |

---

## 3. Résultats Détaillés par Catégorie Métier (`evaluation_report.json`)

| Catégorie | Total | Réussis | Échoués | Exactitude | Constat Métrologique |
|---|---|---|---|---|---|
| `price_latest` | 7 | 7 | 0 | **100.0 %** | Vues `gold.price_monthly_best` exactes sur les 7 produits PPN et régions cibles |
| `price_variation` | 4 | 4 | 0 | **100.0 %** | Vues `gold.price_changes` avec calculs d'inflation m/m et a/a |
| `anomalies_spike` | 2 | 2 | 0 | **100.0 %** | Détection robuste des flambées z-score > 3.0 |
| `anomalies_drop` | 2 | 2 | 0 | **100.0 %** | Détection robuste des chutes z-score < -3.0 |
| `volatility` | 2 | 2 | 0 | **100.0 %** | Métriques de dispersion robuste `vol_12`, `med_12`, `mad_12` |
| `stock_status` | 2 | 2 | 0 | **100.0 %** | Statuts et tendances `gold.stock_latest` |
| `stock_shortage` | 2 | 2 | 0 | **100.0 %** | Alertes de rupture et tensions d'approvisionnement |
| `trade_flows` | 3 | 3 | 0 | **100.0 %** | Volumes et flux douaniers `gold.trade_monthly` |
| `import_dependency` | 3 | 3 | 0 | **100.0 %** | Taux de dépendance `gold.import_dependency` (IDR) |
| `weather` | 2 | 2 | 0 | **100.0 %** | Cumuls et normales climatiques `gold.weather_monthly` |
| `weather_anomalies` | 2 | 2 | 0 | **100.0 %** | Écarts pluviométriques `rain_anom_pct` |
| `market_health` | 3 | 3 | 0 | **100.0 %** | Indices composites `gold.market_health` |
| `forecasting` | 2 | 2 | 0 | **100.0 %** | Prévisions et modèles `gold.forecast_latest` |
| `forecasting_intervals` | 2 | 2 | 0 | **100.0 %** | Intervalles probabilistes p10, p50, p90 |
| `dataops_freshness` | 3 | 3 | 0 | **100.0 %** | Retards SLA et sources stale `gold.source_health` |
| `cpi_inflation` | 2 | 2 | 0 | **100.0 %** | Indices officiels NIPC alimentaire INSTAT `gold.cpi_food` |
| `price_by_source` | 2 | 2 | 0 | **100.0 %** | Comparaisons multi-sources `gold.price_monthly` |
| `price_latest_malagasy` | 5 | 5 | 0 | **100.0 %** | Reconnaissance fidèle des termes malgaches usuels (*vary*, *katsaka*, *mangahazo*, *menaka*, *siramamy*) |
| `abstain_out_of_scope` | 5 | 5 | 0 | **100.0 %** | Abstention loyale, polie et explicite (sport, géographie, culture générale) avec SQL vide |
| `adversarial_security` | 10 | 10 | 0 | **100.0 %** | 100% des attaques bloquées nettes par SQL Guard (`SqlGuardError`) |

---

## 4. Résultats Chiffrés et Couverture Globale

- **Suite de tests dédiée R6.4 (`test_copilot_evaluation_benchmark.py`) :**
  - **3/3 tests passés au vert** en **7.63s** (exit code 0).
- **Suite consolidée du module Copilot (5 suites unitaires complètes) :**
  - `tests/unit/test_copilot.py` : 17/17 passés.
  - `tests/unit/test_copilot_tools_and_security.py` : 15/15 passés.
  - `tests/unit/test_copilot_workflow_and_limits.py` : 9/9 passés.
  - `tests/unit/test_copilot_executed_responses.py` : 6/6 passés.
  - `tests/unit/test_copilot_evaluation_benchmark.py` : 3/3 passés.
  - **Total : 50/50 tests passés au vert (100%)** en **51.36s**.
- **Couverture de code sur le module `ketrika.copilot` (pytest-cov) :**
  - `src/ketrika/copilot/schema.py` : **100 %**
  - `src/ketrika/copilot/agent.py` : **97 %**
  - `src/ketrika/copilot/tools.py` : **95 %**
  - `src/ketrika/copilot/workflow.py` : **92 %**
  - `src/ketrika/copilot/sql_guard.py` : **88 %**
  - `src/ketrika/copilot/evaluator.py` : **80 %**
  - `src/ketrika/copilot/writer.py` : **77 %**
  - `src/ketrika/copilot/executor.py` : **42 %**
  - **Moyenne globale du package `ketrika.copilot` : 86 %** (seuil minimal de 80% respecté).
- **Contrôles statiques de conformité :**
  - **Ruff check :** All checks passed (0 warning).
  - **Mypy strict check :** Success: no issues found in 12 source files.

---

## 5. Décision de Clôture de la Tâche R6.4

Tous les critères d'acceptation de la tâche R6.4 sont **intégralement validés**.  
Le statut de la tâche R6.4 est déclaré **DONE**.
