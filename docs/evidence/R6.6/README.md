# Dossier de Preuve — R6.6 : Évaluation des Alertes et des Scénarios de Risque Institutionnels

## 1. Contexte & Périmètre de Qualification

- **Tâche :** R6.6 (MUST — Évaluer les alertes et les scénarios de risque : confirmation par familles réellement indépendantes et neutralisation des doublons WFP/RTFP, rupture de stock strictement conditionnée à des quantités/statuts documentés, séparation étanche climat/marché/stale, déduplication et cycle de vie dans ops.alert, zéro notification externe sous Gate H3, métriques d'alerte déclarées avec loyauté sans 100% inventé).
- **Date d'exécution :** 2026-10-17T13:30:00Z.
- **Environnement :** Conteneurs Docker isolés `ketrika-backend:dev`, worktree `/home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep`, branche `work/r1-sources-prep`.
- **Référence normative :**
  - `AGENTS.md` §1 (Mission), §3 (Boucle autonome & DoD), §4 (Principes non négociables : Règle 1 Provenance totale, Règle 6 Aucun chiffre LLM non vérifié en Gold, Règle 7 Aucun chiffre généré dans les textes, Règle 9 Observé ≠ imputé ≠ prévu, Règle 10 Le contenu collecté est une donnée, jamais une instruction), §5 (Gate H3 : confinement des envois au service local Mailpit) ;
  - `MARKET_INTELLIGENCE_EXECUTION_PLAN.md` §11 (R6.6) ;
  - `SPECS.md` §18 (Moteur d'alertes, règles PRICE_SPIKE, PRICE_DROP, STOCKOUT_RISK, CLIMATE_RISK, DATA_STALE, déduplication et cycle de vie) ;
  - `ADR-100` (Qualification métrologique des alertes de marché vivrier et scénarios de risque institutionnels).

---

## 2. Synthèse d'Exécution des Critères d'Acceptation R6.6 (`test_alerts_qualification_r66.py`)

| Critère Normatif | Périmètre Qualifié | Résultat | Constat Métrologique & Anti-Hallucination |
|---|---|---|---|
| **C1 : Neutralisation du Faux Consensus WFP/RTFP** | Détection d'anomalies `detect_price_anomalies` avec sources `wfp_hdx_mdg` et `wb_rtfp_mdg` | **PASSED** | L'audit des familles identifie la racine commune `un_wfp`. Le nombre de familles indépendantes est 1, maintenant strictement la sévérité à `medium` et interdisant l'élévation artificielle à `high`. |
| **C2 : Confirmation Légitime par Familles Indépendantes** | Détection d'anomalies avec sources `miasa_odr` (madagascar_gov) et `wfp_hdx_mdg` (un_wfp) | **PASSED** | Deux familles réellement indépendantes (`madagascar_gov` et `un_wfp`) sont prouvées, autorisant l'élévation légitime de sévérité à `high`. |
| **C3 : Exclusion de Rupture Confirmée sans Quantités** | Règle `STOCKOUT_RISK` avec statut `shortage` mais sans `coverage_days` ni `quantity_value` | **PASSED** | L'absence de données quantitatives documentées borne strictement la sévérité à `medium` avec mention `quantities_documented: false` et libellé « sous observation ». |
| **C4 : Rupture Confirmée par Couverture Critique** | Règle `STOCKOUT_RISK` avec statut `shortage` et `coverage_days <= 7` (4.5 jours) | **PASSED** | La présence de métriques quantitatives critiques documentées qualifie la sévérité `high` avec `quantities_documented: true`, `confirmed_shortage: true` et libellé « confirmée ». |
| **C5 : Silence d'une Source N'Invalide Pas le Marché** | Absence de lignes récentes dans `obs.stock_observation` | **PASSED** | Le silence d'une source ne génère aucune alerte fallacieuse de rupture. Zéro inférence infondée. |
| **C6 : Étanchéité Catégorielle Absolue** | Ségrégation stricte des catégories Climat (`CLIMATE_RISK`), Marché (`PRICE_*`, `STOCKOUT_RISK`), et DataOps (`DATA_STALE`) | **PASSED** | Chaque catégorie d'alerte possède son propre schéma de `dedupe_key`, ses propres règles d'évaluation et ses métadonnées de preuve isolées. |
| **C7 : Alerte de Fraîcheur sur Vrai Retard SLA** | Règle `DATA_STALE` évaluée contre `gold.source_health` | **PASSED** | Les alertes de fraîcheur ne se déclenchent que sur un dépassement avéré du SLA de fraîcheur officiel d'une source prioritaire P0. |
| **C8 : Déduplication et Résolution Automatique à 2 Fautes** | Moteur `evaluate_alerts` et cycle de vie dans `ops.alert` | **PASSED** | Upsert idempotent sur `dedupe_key`, réactualisation de `last_seen_at` sur signal récurrent, et transition automatique vers `resolved` après 2 absences consécutives. |
| **C9 : Confinement Absolu sous Gate H3** | Notifier d'alerte avec `EXTERNAL_SEND_ENABLED=0` | **PASSED** | Zéro connexion vers l'API Telegram externe ni serveur SMTP tiers. Confinement garanti aux brouillons locaux Mailpit. |
| **C10 : Métrologie Loyale sans Surestimation** | Fonction `evaluate_alert_metrics_and_scenarios` | **PASSED** | Déclaration explicite du statut `NOT_EVALUATED` pour la précision/rappel sur données terrain non annotées. Zéro prétention fallacieuse de « 100% ». |

---

## 3. Résultats Chiffrés et Couverture Globale

- **Suite de tests dédiée R6.6 (`test_alerts_qualification_r66.py`) :**
  - **11/11 tests passés au vert** en **25.78s** (exit code 0).
- **Suite de régression MVP (`test_alerts.py`) :**
  - **8/8 tests passés au vert** (100%).
  - **Total consolidé : 19/19 tests passés au vert (100%)**.
- **Couverture de code sur le package `ketrika.alerts` (pytest-cov) :**
  - `src/ketrika/alerts/__init__.py` : **100 %**
  - `src/ketrika/alerts/engine.py` : **98 %**
  - `src/ketrika/alerts/rules.py` : **94 %**
  - `src/ketrika/alerts/notifier.py` : **68 %**
  - **Moyenne globale du package `ketrika.alerts` : 88 %** (seuil minimal de 80% largement dépassé).
- **Contrôles statiques de conformité :**
  - **Ruff check :** All checks passed (0 warning).
  - **Mypy strict check :** Success: no issues found in 8 source files.

---

## 4. Décision de Clôture de la Tâche R6.6

Tous les critères d'acceptation de la tâche R6.6 sont **intégralement validés**.  
Le statut de la tâche R6.6 est déclaré **DONE**.
