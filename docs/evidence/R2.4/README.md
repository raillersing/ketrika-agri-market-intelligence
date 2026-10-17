# Preuve de qualification R2.4 — Mesure de couverture de marché SQL, lacunes indépendantes et sélection du pilote

**Date :** 2026-10-16  
**Tâche :** R2.4 — Mesurer couverture et choisir le pilote  
**Statut :** **DONE** (Matrice de couverture SQL `gold.market_coverage` au grain produit×zone×acteur×mois, calcul indépendant des lacunes calendaires sans flaterie, sélection et formalisation économique du pilote riz local/importé sur le triangle Analamanga / Alaotra-Mangoro / Atsinanana et National, documentation explicite des capacités impossibles, garde d'authenticité strict interdisant la substitution par seeds synthétiques, 16/16 tests d'audit verts avec 94% de couverture, 111 tests de non-régression verts, ruff, mypy et tsc 100% conformes)

---

## 1. Contexte et objectifs de la qualification

La tâche **R2.4** établit la mesure objective de la couverture de marché et sélectionne le pilote opérationnel selon les directives de `MARKET_INTELLIGENCE_EXECUTION_PLAN.md` et les principes d'intégrité d'`AGENTS.md` :

1. **Matrice de couverture de marché recomputable en SQL (`gold.market_coverage`) :**
   - Vue matérialisée calculée au grain `product × location × actor_level × month`.
   - Attributs mesurés : `n_obs` (volume d'observations), `sources`, `source_families` et `n_families` distinctes, granularité administrative `admin_level`, âge de la donnée `age_days`, part imputée `imputed_share`, et indicateur de présence de données observées réelles `has_observed`.
   - Intégration dans le moteur de publication Gold (`ORDERED_GOLD_VIEWS` et `GOLD_DEPENDENCIES` dans `refresh.py`, mapping de table dans `provenance_gate.py`).

2. **Calcul indépendant des lacunes et mois manquants (`calculate_missing_months` / SQL `generate_series`) :**
   - Aucun sous-échantillonnage de complaisance ni présélection flatteuse de dates : le calcul s'effectue sur la grille calendaire continue complète entre la borne initiale et la borne finale.
   - Algorithme indépendant en Python et requête SQL autonome avec `generate_series` et jointure gauche identifiant rigoureusement tout mois absent (`missing_months_list`, `missing_count`, `coverage_ratio`).
   - Invariant mathématique prouvé par tests property-based Hypothesis :
     $$\text{missing\_count} + \text{distinct\_observed\_in\_range} = \text{expected\_total}$$

3. **Sélection et formalisation du pilote (`taxonomy/pilot.yaml` et `core/pilot.py`) :**
   - **Produits prescrits :**
     - `RICE_WHITE_LOCAL` (Riz blanc local) : aliment de base national, reflet de la production agricole locale et de la sécurité alimentaire.
     - `RICE_WHITE_IMPORTED` (Riz blanc importé, "vary tsinjo") : produit régulateur de marché, marqueur direct de la parité d'importation et du taux de change MGA.
   - **Zones prescrites ($\le 3$ zones régionales + niveau national) :**
     1. **Analamanga (MDG11) :** Grand bassin de **consommation** urbain majeur (Antananarivo, 3,6+ millions d'habitants), déficit vivrier structurel, dépendance critique aux arrivages régionaux et portuaires.
     2. **Alaotra-Mangoro (MDG31) :** Premier grenier à riz de Madagascar (**production** agricole excédentaire, plaine du lac Alaotra / Ambatondrazaka), référence pour les prix à la production et grossiste.
     3. **Atsinanana (MDG33) :** Pôle portuaire d'entrée des **importations** (Grand Port de Toamasina, tête du corridor RN2 vers Antananarivo), transmission des cours mondiaux.
     + **Madagascar National (MDG0) :** Référence macroéconomique nationale permettant d'apprécier la tendance d'ensemble sans inventer de marchés locaux fictifs.
   - **Complémentarité économique validée :**
     Le triangle Alaotra-Mangoro (production) $\leftrightarrow$ Atsinanana (importation maritime) $\leftrightarrow$ Analamanga (consommation urbaine) forme le socle structurel du marché rizicole malagasy, permettant l'analyse des différentiels spatiaux, des marges d'arbitrage et de transport, et de la substitution local/importé.

4. **Documentation explicite des capacités impossibles :**
   - *Granularité infra-régionale continue (admin2/district, admin3/commune) :* Impossible de façon continue en raison de la rareté et de la discontinuité des relevés authentiques officiels.
   - *Acteurs intermédiaires informels (collecteurs de brousse, transporteurs de piste) :* Impossible faute de séries statistiques publiques fiables.
   - *Fréquence journalière continue :* Impossible, seule l'agrégation mensuelle garantit une série temporelle continue certifiée.

5. **Garde d'authenticité strict (Anti-substitution par seed synthétique) :**
   - Vérification mécanique en base (`check_pilot_authenticity`) : au moins une source authentique qualifiée (`miasa_odr`, `wb_rtfp_mdg`, `mincc_ppn`, `wfp_hdx_mdg`) doit alimenter les séries du pilote.
   - En l'absence d'historique de prix authentique ou en présence exclusive de seeds synthétiques de test, le pilote est obligatoirement bloqué (`BLOCKED_NO_AUTHENTIC_DATA` / `PilotNoAuthenticDataError`).

6. **Exposition API REST (`ketrika/api/routers/coverage.py`) :**
   - `GET /v1/market/coverage` : matrice de couverture filtrable.
   - `GET /v1/market/coverage/gaps` : calcul indépendant des lacunes par série.
   - `GET /v1/market/pilot` : configuration complète, rôles économiques, capacités impossibles et statut d'authenticité.

---

## 2. Fichiers créés et modifiés

- **Définitions SQL et rafraîchissement Gold :**
  - `backend/src/ketrika/gold/sql/013_market_coverage.sql` : vue matérialisée de couverture.
  - `backend/src/ketrika/gold/refresh.py` : intégration de `market_coverage` dans `ORDERED_GOLD_VIEWS` et `GOLD_DEPENDENCIES`.
  - `backend/src/ketrika/gold/provenance_gate.py` : ajout de `market_coverage` dans `VIEW_TABLES`.
- **Moteur de couverture et d'analyse des lacunes (Python) :**
  - `backend/src/ketrika/gold/coverage.py` : modèles `MarketCoverageRow`, `SeriesCoverageSummary`, fonction `calculate_missing_months`, requêtes SQL `compute_series_gaps_independent_sql` et `audit_pilot_market_coverage`.
- **Configuration et garde d'authenticité du pilote :**
  - `taxonomy/pilot.yaml` : configuration déclarative normée du pilote rizicole 2026.
  - `backend/src/ketrika/core/pilot.py` : parseur Pydantic, modèles de données, garde `check_pilot_authenticity` et exception `PilotNoAuthenticDataError`.
- **Exposition API et contrats REST :**
  - `backend/src/ketrika/api/schemas.py` : schémas Pydantic `MarketCoverageItem`, `SeriesCoverageSummaryItem`, `PilotConfigResponse`.
  - `backend/src/ketrika/api/routers/coverage.py` : routeur FastAPI `/v1/market`.
  - `backend/src/ketrika/api/main.py` : enregistrement du routeur `coverage`.
- **Suite de tests de qualification R2.4 :**
  - `backend/tests/unit/test_market_coverage_and_pilot.py` : 16 tests unitaires, scénarios de qualification et tests property-based Hypothesis.

---

## 3. Résultats des tests et métriques de validation

### 3.1 Suite de qualification R2.4 (16/16 passés, couverture 94%)

Commande exécutée dans le conteneur Docker `ketrika-backend:dev` :
```bash
docker run --rm -v /home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep:/workspace -w /workspace/backend ketrika-backend:dev uv run pytest -v tests/unit/test_market_coverage_and_pilot.py --cov=ketrika.gold.coverage --cov=ketrika.core.pilot --cov=ketrika.api.routers.coverage --cov-report=term-missing
```

Résultats :
```text
============================= test session starts ==============================
platform linux -- Python 3.12.13, pytest-9.1.1, pluggy-1.6.0
collected 16 items

tests/unit/test_market_coverage_and_pilot.py::test_load_pilot_config_structure PASSED [  6%]
tests/unit/test_market_coverage_and_pilot.py::test_add_calendar_month PASSED [ 12%]
tests/unit/test_market_coverage_and_pilot.py::test_calculate_missing_months_continuous_series PASSED [ 18%]
tests/unit/test_market_coverage_and_pilot.py::test_calculate_missing_months_with_gaps PASSED [ 25%]
tests/unit/test_market_coverage_and_pilot.py::test_calculate_missing_months_sparse_series PASSED [ 31%]
tests/unit/test_market_coverage_and_pilot.py::test_calculate_missing_months_empty PASSED [ 37%]
tests/unit/test_market_coverage_and_pilot.py::test_hypothesis_missing_months_invariant PASSED [ 43%]
tests/unit/test_market_coverage_and_pilot.py::test_check_pilot_authenticity_synthetic_rejection PASSED [ 50%]
tests/unit/test_market_coverage_and_pilot.py::test_check_pilot_authenticity_empty_database PASSED [ 56%]
tests/unit/test_market_coverage_and_pilot.py::test_check_pilot_authenticity_authentic_qualification PASSED [ 62%]
tests/unit/test_market_coverage_and_pilot.py::test_query_market_coverage_matrix_mapping PASSED [ 68%]
tests/unit/test_market_coverage_and_pilot.py::test_compute_series_gaps_independent_sql_mock PASSED [ 75%]
tests/unit/test_market_coverage_and_pilot.py::test_audit_pilot_market_coverage PASSED [ 81%]
tests/unit/test_market_coverage_and_pilot.py::test_api_get_market_coverage PASSED [ 87%]
tests/unit/test_market_coverage_and_pilot.py::test_api_get_series_gaps PASSED [ 93%]
tests/unit/test_market_coverage_and_pilot.py::test_api_get_pilot_configuration PASSED [100%]

================================ tests coverage ================================
Name                                  Stmts   Miss  Cover   Missing
-------------------------------------------------------------------
src/ketrika/api/routers/coverage.py      22      0   100%
src/ketrika/core/pilot.py                97      7    93%   99, 105, 154-158
src/ketrika/gold/coverage.py            125      7    94%   87, 115, 178-179, 181-182, 292
-------------------------------------------------------------------
TOTAL                                   244     14    94%
============================= 16 passed in 19.68s ==============================
```

### 3.2 Contrôles statiques et typage

- **Ruff linter :**
  ```bash
  docker run --rm -v /home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep:/workspace -w /workspace/backend ketrika-backend:dev uv run ruff check src/ketrika/gold/coverage.py src/ketrika/core/pilot.py src/ketrika/api/routers/coverage.py src/ketrika/api/schemas.py src/ketrika/api/main.py src/ketrika/gold/refresh.py src/ketrika/gold/provenance_gate.py tests/unit/test_market_coverage_and_pilot.py
  # Sortie : All checks passed! (code 0)
  ```
- **Mypy typechecker :**
  ```bash
  docker run --rm -v /home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep:/workspace -w /workspace/backend ketrika-backend:dev uv run mypy src/ketrika/gold/coverage.py src/ketrika/core/pilot.py src/ketrika/api/routers/coverage.py src/ketrika/api/schemas.py src/ketrika/api/main.py src/ketrika/gold/refresh.py src/ketrika/gold/provenance_gate.py tests/unit/test_market_coverage_and_pilot.py
  # Sortie : Success: no issues found in 8 source files (code 0)
  ```
- **TypeScript frontend :**
  ```bash
  docker exec aiagent-web-1 pnpm typecheck
  # Sortie : tsc --noEmit (code 0)
  ```

### 3.3 Suite de non-régression (111/111 passés)

Commande exécutée dans Docker :
```bash
docker run --rm -v /home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep:/workspace -w /workspace/backend ketrika-backend:dev uv run pytest -v tests/unit/test_market_coverage_and_pilot.py tests/unit/test_gold_dq_aggregation_audit.py tests/unit/test_gold_kpi.py tests/unit/test_taxonomy_units_audit.py tests/unit/test_contracts_time_origin_macro.py tests/unit/test_price_loader.py
```
Résultat : **111 passed in 38.13s** (0 failure, 0 error, 0 skip).

---

## 4. Conclusion de qualification

Tous les critères d'acceptation de la tâche **R2.4** sont vérifiés et prouvés :
1. La matrice de couverture est calculable en SQL au grain produit $\times$ zone $\times$ acteur $\times$ mois (`013_market_coverage.sql`).
2. Le compte des mois manquants est mesuré de façon indépendante sans sélection flatteuse.
3. Les produits du pilote (`RICE_WHITE_LOCAL`, `RICE_WHITE_IMPORTED`) et les $\le 3$ zones régionales (Analamanga, Alaotra-Mangoro, Atsinanana) + National sont motivés par la complémentarité économique production/consommation/import.
4. Les capacités impossibles sont explicitement documentées (absence d'admin2/3 continu, pas d'acteurs informels, pas d'infra-mensuel).
5. Le garde d'authenticité bloque formellement tout pilote sans historique de prix authentique et interdit la substitution par seeds synthétiques.

La tâche R2.4 est déclarée **DONE**.
