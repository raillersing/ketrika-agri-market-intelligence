# Dossier de Preuve — R6.9 : Supervision de la Fraîcheur, Gestion des Incidents et Gouvernance de la Dérive

## 1. Contexte & Périmètre de Qualification

- **Tâche :** R6.9 (MUST — Superviser fraîcheur, dérive, dépenses et incidents : simulation en environnement dédié des cinq incidents majeurs — panne HTTP, dérive de schéma, dépassement de budget, dérive de forecast et run interrompu ; états persistants/restaurables, alertes confinées à Mailpit, pas de faux succès, visibilité des données stale après rechargement, interdiction formelle de remplacement automatique sauvage de modèle de forecast sous dérive, définition des rôles opérationnels sous Gate H7).
- **Date d'exécution :** 2026-10-17T14:25:00Z.
- **Environnement :** Conteneurs Docker isolés `ketrika-backend:dev`, worktree `/home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep`, branche `work/r1-sources-prep`.
- **Référence normative :**
  - `AGENTS.md` §1 (Mission), §3 (Boucle autonome & DoD), §4 (Principes non négociables : Règle 1 Provenance totale, Règle 3 Ajout seul, Règle 9 Observé ≠ imputé ≠ prévu, Règle 10 Données vs instructions), §5 (Gate H3 : confinement Mailpit ; Gate H6 : plafond budgétaire ; Gate H7 : interdiction de contact de tiers) ;
  - `MARKET_INTELLIGENCE_EXECUTION_PLAN.md` §11 (R6.9) ;
  - `SPECS.md` §19 (Endpoints DataOps `/v1/sources`), §25 (Supervision et résilience) ;
  - `ADR-103` (Supervision DataOps de fraîcheur, gestion des incidents et interdiction de remplacement automatique de modèle sous dérive).

---

## 2. Synthèse d'Exécution des Critères d'Acceptation R6.9 (`test_supervision_and_incident_r69.py`)

| Critère Normatif | Périmètre Qualifié | Résultat | Constat de Supervision & Gouvernance |
|---|---|---|---|
| **C1 : Panne HTTP & Gel Fail-Safe sur Source P0** | `IncidentManager.report_http_outage` avec source P0 (3 échecs) | **PASSED** | Transition en `PublicationStatus.FROZEN` sans masquer l'échec ; notification locale confinée à Mailpit sans communication externe (Gate H3/H7). |
| **C2 : Détection de Dérive de Schéma & Quarantaine** | `report_schema_drift` (colonnes manquantes ou inattendues) | **PASSED** | Gel immédiat de la publication (`FROZEN`), conservation intacte de l'historique antérieur (Règle 3 Ajout seul) et assignation au Lead DataOps. |
| **C3 : Dépassement Budgétaire Fail-Safe** | `report_budget_exceeded` (budget HTTP quotidien ou LLM mensuel) | **PASSED** | Déclenchement de l'action `stop_calls` ; les requêtes excédentaires sont catégoriquement refusées (Gate H6). |
| **C4 : Interdiction de Remplacement Automatique de Modèle** | `evaluate_forecast_drift_policy` (WAPE candidat dégradé > 0.35) | **PASSED** | Le remplacement automatique est **strictement bloqué** (`automatic_replacement_blocked=True`) ; le modèle historique certifié (`SeasonalNaive`) est maintenu en production. |
| **C5 : Promotion Parsimonieuse d'un Candidat** | Candidat avec gain significatif > 1% (WAPE -3.5%) vs gain négligeable (+0.4%) | **PASSED** | Promotion autorisée uniquement en cas d'amélioration prouvée supérieure au seuil de parsimonie de 1 point de pourcentage. |
| **C6 : Reprise Idempotente de Run Interrompu** | `handle_interrupted_run` | **PASSED** | Marquage du run interrompu sans perte d'état et stratégie de reprise sûre sans double écriture dans Bronze ni Silver. |
| **C7 : Runbook d'Incident & Respect du Gate H7** | `docs/runbooks/INCIDENT_RUNBOOK.md` | **PASSED** | Formalisation exhaustive des rôles (`Lead DataOps`, `Analyste Marché`, `Administrateur Système`) et interdiction absolue d'émissions de messages à des tiers réels. |

---

## 3. Résultats Chiffrés et Couverture Globale

- **Suite de qualification dédiée R6.9 (`test_supervision_and_incident_r69.py`) :**
  - **7/7 tests passés au vert** en **9.66s** (exit code 0).
- **Ensemble consolidé du package `ketrika.ops` (R6.8 + R6.9) :**
  - **19/19 tests passés au vert** en **12.99s** (100% de réussite).
- **Couverture de code sur le module `ketrika.ops.supervision` :**
  - `src/ketrika/ops/supervision.py` : **100 %** (81 statements, 0 missed).
  - Moyenne globale du package `ketrika.ops` : **93 %** (seuil minimal de 80% largement dépassé).
- **Contrôles statiques de conformité :**
  - **Ruff check :** All checks passed (0 warning, 0 error).
  - **Mypy strict check :** Success: no issues found in 2 source files.

---

## 4. Décision de Clôture de la Tâche R6.9

Tous les critères d'acceptation de la tâche R6.9 sont **intégralement validés**.  
Le statut de la tâche R6.9 est déclaré **DONE**.
