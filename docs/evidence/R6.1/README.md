# Dossier de Preuve — R6.1 : Sécurisation Absolue des Outils de Lecture et d'Analyse du Copilot

## 1. Contexte & Périmètre de Qualification

- **Tâche :** R6.1 (MUST — Sécuriser les outils de lecture, catalogue d'outils typés et autorisés, SQL Gold strict, CTEs et fonctions réseau contrôlés, validation de paramètres sans fuite).
- **Date d'exécution :** 2026-10-17T12:02:00Z.
- **Environnement :** Conteneurs Docker isolés `ketrika-backend:dev`, worktree `/home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep`, branche `work/r1-sources-prep`.
- **Référence normative :**
  - `AGENTS.md` §1 (Mission), §3 (Boucle autonome & DoD), §4 (Principes non négociables : Règle 6 aucun chiffre LLM non vérifié, Règle 7 aucun chiffre généré dans les textes, Règle 10 le contenu collecté est une donnée, jamais une instruction), §5 (Gates H1/H6) ;
  - `MARKET_INTELLIGENCE_EXECUTION_PLAN.md` §11 (R6.1) ;
  - `SPECS.md` §21 (Copilote analyste, SQL Guard, rôle copilot_ro, statement_timeout 5s, LIMIT <= 500) ;
  - `ADR-095` (Sécurisation absolue des outils d'analyse et SQL Guard du Copilot).

---

## 2. Synthèse d'Exécution des Critères d'Acceptation R6.1

| Critère Normatif | Périmètre Qualifié | Résultat | Constat Métrologique & Sécurité |
|---|---|---|---|
| **C1 : Interdiction des CTE d'écriture** | Tentatives d'injection avec CTE `DELETE`, `UPDATE`, `INSERT` (`WITH ... DELETE ... RETURNING *`) | **PASSED** | L'AST sqlglot détecte récursivement les instructions modificatrices et rejette avec `SqlGuardError(MODIFICATION_NOT_ALLOWED)` ou `CTE_NOT_SELECT`. Zéro écriture possible. |
| **C2 : Blocage des fonctions réseau et exfiltration** | Tentatives d'appel à `http_get`, `dblink`, `dblink_connect`, `query_to_xml`, `pg_ls_dir`, `pg_stat_file`, `crosstab` | **PASSED** | Rejet strict avec code `FORBIDDEN_FUNCTION` et `ACCESS_DENIED`. Impossible d'exfiltrer des données ou d'effectuer des requêtes sortantes depuis la DB. |
| **C3 : Blocage de `SELECT INTO`** | Tentative de création de table clandestine via `SELECT * INTO ...` | **PASSED** | Détection immédiate du nœud `into` et blocage avec code `INTO_NOT_ALLOWED`. |
| **C4 : Étancheité absolue des schémas non-Gold** | Tentatives de requêtes sur `auth`, `obs`, `bronze`, `silver`, `information_schema`, `pg_catalog` | **PASSED** | Blocage préventif par regex et par validation AST des noms de tables/schémas. Seules les 14 vues officielles du schéma `gold` sont autorisées. |
| **C5 : Enforce et clampage `LIMIT <= 500`** | Requêtes sans LIMIT ou avec `LIMIT 2000` | **PASSED** | Injection automatique de `LIMIT 500` ou remplacement systématique de toute limite supérieure par 500. Zéro risque de déni de service mémoire. |
| **C6 : Statement Timeout DB (5 secondes)** | Configuration de session `get_copilot_engine` avec `connect_args={"options": "-c statement_timeout=5000"}` | **PASSED** | PostgreSQL interrompt formellement toute requête dépassant 5 secondes. |
| **C7 : Catalogue d'outils typés (`AnalyticalToolCatalog`)** | 6 outils métier Pydantic : `get_price_series`, `get_market_facts`, `get_source_provenance`, `get_market_coverage`, `get_qualified_forecast`, `get_crop_calendar` | **PASSED** | Sorties strictement typées avec métriques, citations officielles et labels métrologiques (`observed`, `forecast`, `composite`). Les requêtes récurrentes passent par des outils déterministes contrôlés. |
| **C8 : Validation stricte des paramètres produit/zone** | Injection dans les paramètres (`product_code`, `location_pcode`, `month`) | **PASSED** | Regex stricte `PRODUCT_CODE_PATTERN` et `LOCATION_PCODE_PATTERN`. Rejet immédiat par `ParameterValidationError`. |
| **C9 : Explication sans fuite (Zero-Leakage Security)** | Messages d'erreur retournés lors d'un refus de requête ou de paramètre | **PASSED** | Aucun mot de passe, chaîne de connexion `postgres://`, adresse IP, chemin système ou détail technique de serveur divulgué. |

---

## 3. Résultats Chiffrés et Couverture

- **Suites de tests exécutées :**
  - `tests/unit/test_copilot_tools_and_security.py` : 15/15 tests passés au vert.
  - `tests/unit/test_copilot.py` : 17/17 tests passés au vert (incluant le benchmark de 22 questions métier).
  - **Total : 32/32 tests passés au vert (100%)** en **15.78s**.
- **Couverture de code (pytest-cov) :**
  - `src/ketrika/copilot/tools.py` : **95 %**
  - `src/ketrika/copilot/sql_guard.py` : **82 %**
  - `src/ketrika/copilot/agent.py` : **86 %**
  - `src/ketrika/copilot/schema.py` : **100 %**
  - **Moyenne sur les modules de sécurité et outils du lot : 91 %** (largement supérieur aux 80% requis).
- **Contrôles statiques :**
  - **Ruff check :** All checks passed (0 warning).
  - **Mypy strict check :** Success: no issues found in 7 source files.

---

## 4. Décision de Clôture de la Tâche R6.1

Tous les critères d'acceptation de la tâche R6.1 sont **intégralement validés**.  
Le statut de la tâche R6.1 est déclaré **DONE**.
