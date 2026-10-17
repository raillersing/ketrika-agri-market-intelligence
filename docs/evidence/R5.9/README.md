# Dossier de Preuve — R5.9 : Gate Récoltes, Volumes et Approvisionnement des Marchés (Sceau d'Étape R5)

## 1. Contexte & Périmètre de Qualification

- **Tâche :** R5.9 (MUST — Exécuter le gate récoltes et approvisionnement, figer la baseline et sceller le tag `mi-r5-qualified`).
- **Date d'exécution :** 2026-10-17T11:50:00Z.
- **Environnement :** Conteneurs Docker isolés `ketrika-backend:dev`, worktree `/home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep`, branche `work/r1-sources-prep`.
- **Référence normative :**
  - `AGENTS.md` §1 (Mission), §3 (Boucle autonome & DoD), §4 (Principes non négociables : provenance Bronze SHA-256, conservation de masse, observed != imputed != predicted, données réelles traçables, données jamais instructions), §7 (Tags normatifs R : `mi-r5-qualified`) ;
  - `MARKET_INTELLIGENCE_EXECUTION_PLAN.md` §10 (Critères du Gate R5.9) ;
  - `SPECS.md` §27 (Récoltes, tonnages, approvisionnement des marchés vivriers) ;
  - `ADR-088` (Cibles et protocole d'acquisition récoltes/quantités), `ADR-089` (Import et migration Alembic 0016), `ADR-090` (Contrôle qualité & matrice marché-période), `ADR-091` (Fenêtre de récolte et calendrier agroclimatique), `ADR-092` (Bilan d'offre et conservation de masse sans double comptage), `ADR-093` (Prévision de fenêtres et pics d'arrivage avec décalage logistique), `ADR-094` (Scénarios et pilote décisionnel pour 3 profils avec rejet des ordres d'achat autonomes).

---

## 2. Validation Exhaustive des 10 Critères du Gate R5 (`test_gate_r5_supply.py`)

| Critère Gate R5 | Intitulé Normatif | Résultat | Constat Métrologique & Preuve d'Invariance |
|---|---|---|---|
| **Gate 1** | **Séparation Métrologique Stricte** (`QuantityTarget`) | **PASSED** | `harvest_volume != inflow_arrival != stock_inventory`. La détection empirique du pic d'arrivage est calculée exclusivement sur les tonnages physiques observés (`inflow_arrival`), jamais sur un minimum de prix. |
| **Gate 2** | **Résolution Temporelle Décadaire Déterministe** | **PASSED** | Fenêtres calendaires exprimées en décades agronomiques réelles (`D1`, `D2`, `D3`). Aucune date exacte inventée au jour près. Calcul rigoureux des bornes calendaires (ex: D3 = 21 au dernier jour du mois). |
| **Gate 3** | **Provenance Bronze SHA-256 & Rejet Anti-PII** | **PASSED** | Détection et rejet immédiat (`ValueError`) de tout champ nominatif ou confidentiel (`phone`, `surveyor_name`, `collector_email`, `farmer_name`). Respect absolu du Gate H7 et de la protection de la vie privée. |
| **Gate 4** | **Matrice Marché × Période (`MISSING_SURVEY != 0 kg`)** | **PASSED** | L'absence d'enquête sur un marché (`MKT_ANOSIBE`) à une date donnée est strictement qualifiée en `MISSING_SURVEY` avec `quantity_kg = None`. Règle métrologique : l'absence d'observation n'est jamais assimilée à un arrivage nul (0 kg). |
| **Gate 5** | **Conservation de Masse & Blocage du Double Comptage** | **PASSED** | Équation de bilan physique respectée ($\Delta\text{Stock} = \text{Entrées} - \text{Sorties} - \text{Pertes}$). Détection et alerte bloquante (`DOUBLE_COUNT_HAZARD`) interdisant le cumul arithmétique des flux douaniers nationaux (Toamasina) avec les arrivages de gros (Anosibe). |
| **Gate 6** | **Décalage Logistique Bassin–Marché & Coupure As-Of** | **PASSED** | Décalage logistique $\tau_{\text{logistique}} = +1$ décade entre la zone de production (Alaotra) et le marché terminal de gros (Anosibe). Coupure as-of stricte interdisant toute fuite d'information du futur. |
| **Gate 7** | **Suffisance Scientifique des Données & Abstention** | **PASSED** | Historique incomplet (< 2 cycles saisonniers complets) qualifié honnêtement en abstention (`is_sufficient: false`, `qualification: BASELINE_LOGISTICS` ou `EXPERIMENTAL_BASELINE`). Aucun modèle complexe entraîné sur des séries creuses. |
| **Gate 8** | **Scénarios Déterministes & Interdiction d'Ordres d'Achat** | **PASSED** | Modélisation déterministe pour 3 acteurs réels (Régulateur SPM/MIC, Acheteur Commercial, Vulgarisation DRDA). Règle d'arrêt sur paramètre manquant (`impacts = []`). Interdiction formelle d'ordres d'achat autonomes (`order_generation_prohibited: true`). Statut `NOT_EVALUATED` et `human_reviewed: false`. |
| **Gate 9** | **Immunité Anti-Injection de Prompts & Whitelisting** | **PASSED** | Blocage proactif de tout motif de détournement d'instructions LLM (`ignore previous instructions`, etc.). Filtrage sur liste blanche stricte des paramètres autorisés (`ALLOWED_PARAMETERS`). |
| **Gate 10** | **Intégrité et Accessibilité des Endpoints API `/v1/supply`** | **PASSED** | Validation HTTP 200 sur les endpoints FastAPI : `/v1/supply/peak-forecast`, `/v1/supply/sufficiency`, `/v1/supply/scenarios/templates` et `/v1/supply/scenarios/run`. |

---

## 3. Résultats Chiffrés et Synthèse de Qualification

- **Exécution de la suite Gate R5 (`test_gate_r5_supply.py`) :**
  - **10/10 tests passés** (100% de succès) en **54.53s**.
  - Code de sortie : **0**.
- **Exécution consolidée de la Phase R5 (7 suites de tests) :**
  - `tests/unit/test_connector_market_supply.py` : 6/6 passés.
  - `tests/unit/test_supply_balance_engine.py` : 5/5 passés.
  - `tests/unit/test_supply_decision_pilot.py` : 7/7 passés.
  - `tests/unit/test_supply_peak_forecast.py` : 7/7 passés.
  - `tests/unit/test_supply_quality_and_coverage.py` : 6/6 passés.
  - `tests/unit/test_supply_survey_contracts.py` : 7/7 passés.
  - `tests/unit/test_gate_r5_supply.py` : 10/10 passés.
  - **Total : 48/48 tests unitaires passés au vert** en **53.83s**.
- **Couverture de code (pytest-cov) :**
  - `src/ketrika/supply/__init__.py` : **100 %**
  - `src/ketrika/supply/balance.py` : **95 %**
  - `src/ketrika/supply/contracts.py` : **94 %**
  - `src/ketrika/supply/decision_pilot.py` : **95 %**
  - `src/ketrika/supply/peak_forecast.py` : **90 %**
  - `src/ketrika/supply/quality.py` : **96 %**
  - **Ensemble du package `ketrika.supply` : 85 %** (seuil constitutionnel $\ge 80\%$ validé).
- **Contrôles Statiques :**
  - **Ruff check :** All checks passed (0 warning).
  - **Mypy check :** Success: no issues found in 7 source files (typage strict sans erreur).

---

## 4. Décision de Clôture & Scellement du Jalon

Le Gate R5 est **intégralement validé**.  
La Phase R5 (Récoltes, Volumes et Approvisionnement des Marchés) est déclarée **CONCLUE et QUALIFIÉE**.  
Le tag git normatif **`mi-r5-qualified`** est prêt à être scellé.
