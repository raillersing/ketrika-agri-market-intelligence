# Dossier de Preuve — R6.3 : Répondre avec des Résultats Exécutés et Référencés, Zéro Hallucination et Abstention Loyale

## 1. Contexte & Périmètre de Qualification

- **Tâche :** R6.3 (MUST — Répondre avec des résultats exécutés et référencés : chiffres strictement issus des cellules de résultats SQL exécutés, métadonnées de provenance explicites, affichage clair observé/imputé/prévu, abstention polie et explicite hors domaine).
- **Date d'exécution :** 2026-10-17T12:30:00Z.
- **Environnement :** Conteneurs Docker isolés `ketrika-backend:dev`, worktree `/home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep`, branche `work/r1-sources-prep`.
- **Référence normative :**
  - `AGENTS.md` §1 (Mission), §3 (Boucle autonome & DoD), §4 (Principes non négociables : Règle 1 Provenance totale, Règle 6 Aucun chiffre LLM non vérifié en Gold, Règle 7 Aucun chiffre généré dans les textes, Règle 9 Observé ≠ imputé ≠ prévu, Règle 10 Le contenu collecté est une donnée, jamais une instruction), §5 (Gates H1/H5) ;
  - `MARKET_INTELLIGENCE_EXECUTION_PLAN.md` §11 (R6.3) ;
  - `SPECS.md` §20 (Bulletins & métadonnées de provenance), §21 (Copilote analyste, zero-hallucination writer, architecture cell-referencing) ;
  - `ADR-097` (Architecture anti-hallucination du Copilot : réponses exécutées, référencement strict de cellules, abstention loyale et traçabilité de provenance).

---

## 2. Synthèse d'Exécution des Critères d'Acceptation R6.3 (`test_copilot_executed_responses.py`)

| Critère Normatif | Périmètre Qualifié | Résultat | Constat Métrologique & Anti-Hallucination |
|---|---|---|---|
| **C1 : Réponses Exécutées Pures (Zero-Hallucination Writer)** | Validation de la génération de prose par `validate_anti_hallucination_prose` et `build_cell_placeholders` | **PASSED** | Chaque nombre apparaissant dans le texte final provient rigoureusement d'une cellule du tableau de résultats SQL via son placeholder `{{c_row_col}}`. Tout chiffre non référencé dans la prose libre déclenche une violation formelle. |
| **C2 : Métadonnées Complètes de Provenance** | Requête analytique sur le marché vivrier (`Quel est le dernier prix du riz blanc à Analamanga ?`) | **PASSED** | L'objet de réponse contient systématiquement `citations` (sources officielles, ex. `odr`), `value_kinds` (`['observed']`), et `provenance_summary` détaillant la traçabilité Bronze SHA-256 et la validation Gold. |
| **C3 : Abstention Loyale Hors Domaine Vivrier** | Requêtes générales ou hors périmètre (`capitale de l'Australie`, `ligue des champions`, `météo à Paris`, `blague astronaute`) | **PASSED** | Détection immédiate du hors-domaine. Aucune requête fallacieuse par défaut vers le riz ; retour d'un message d'abstention poli et explicite déclarant le périmètre d'expertise vivrière malgache, SQL vide, citations vides et `provenance_summary` indiquant l'abstention loyale. |
| **C4 : Gestion Robuste des Questions Vides** | Chaînes vides ou composées uniquement d'espaces | **PASSED** | Réponse immédiate invitant l'utilisateur à poser une question vivrière sans exécution SQL ni consommation de ressources. |
| **C5 : Benchmark Complet de 22 Questions Métier** | Évaluation de couverture et sécurité sur les 22 cas de test de `backend/tests/copilot_eval.yaml` | **PASSED** | 100 % des 22 questions (prix récents, variations, flambées, chutes, stocks, imports douaniers, IDR, précipitations/météo, Market Health Score, prévisions p10/p50/p90, fraîcheur SLA, IPC alimentaire, prix par source) génèrent des requêtes valides ciblant exactement la vue Gold attendue, sans requêtes interdites ni injection. |
| **C6 : Schéma d'API FastAPI Strict (`/v1/copilot/ask`)** | Requête HTTP POST sur le point de terminaison API avec authentification client mockée | **PASSED** | Réponse 200 conforme au schéma Pydantic `CopilotAskResponse` enrichi avec `provenance_summary`, `citations`, `value_kinds`, `rows_preview`, `sql` et `answer_markdown`. |

---

## 3. Résultats Chiffrés et Couverture Globale

- **Suite de tests dédiée R6.3 (`test_copilot_executed_responses.py`) :**
  - **6/6 tests passés au vert** en **40.55s** (exit code 0).
- **Suite consolidée du module Copilot (4 suites unitaires) :**
  - `tests/unit/test_copilot.py` : 17/17 passés.
  - `tests/unit/test_copilot_tools_and_security.py` : 15/15 passés.
  - `tests/unit/test_copilot_workflow_and_limits.py` : 9/9 passés.
  - `tests/unit/test_copilot_executed_responses.py` : 6/6 passés.
  - **Total : 47/47 tests passés au vert (100%)** en **65.15s**.
- **Couverture de code sur le module `ketrika.copilot` (pytest-cov) :**
  - `src/ketrika/copilot/schema.py` : **100 %**
  - `src/ketrika/copilot/agent.py` : **95 %**
  - `src/ketrika/copilot/tools.py` : **95 %**
  - `src/ketrika/copilot/workflow.py` : **92 %**
  - `src/ketrika/copilot/sql_guard.py` : **85 %**
  - `src/ketrika/copilot/writer.py` : **77 %**
  - `src/ketrika/copilot/executor.py` : **42 %** (couvert en intégration avec DB active)
  - **Moyenne globale du package `ketrika.copilot` : 86 %** (seuil minimal de 80% largement dépassé).
- **Contrôles statiques de conformité :**
  - **Ruff check :** All checks passed (0 warning).
  - **Mypy strict check :** Success: no issues found in 10 source files.

---

## 4. Décision de Clôture de la Tâche R6.3

Tous les critères d'acceptation de la tâche R6.3 sont **intégralement validés**.  
Le statut de la tâche R6.3 est déclaré **DONE**.
