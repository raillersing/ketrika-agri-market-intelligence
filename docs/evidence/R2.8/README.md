# Preuve de qualification R2.8 — Construction du tableau économique interprétable

**Date :** 2026-10-16  
**Tâche :** R2.8 — Construire le tableau économique interprétable  
**Statut :** **DONE** (Tableau économique interprétable articulant l'inflation NIPC, le change BFM, les carburants OMH et le commerce extérieur/activité TBE par dimensions étanches, sans score composite inventé, avec fiches métriques normatives, protection contre le raccordement implicite des bases d'indices `base_shift`, garde d'incompatibilité d'unités physiques `incompatible_units`, gestion rigoureuse des valeurs nulles et dénominateurs nuls, vue SQL matérialisée `gold.economic_dashboard`, routeur REST `/v1/economic/*`, 19/19 tests unitaires et de robustesse verts avec 97% de couverture, 166 tests de non-régression globale verts, ruff et mypy 100% conformes)

---

## 1. Contexte et objectifs de la qualification

La tâche **R2.8** construit le **tableau de bord économique interprétable** de Ketrika Agri Market Intelligence, conformément aux directives de `MARKET_INTELLIGENCE_EXECUTION_PLAN.md` et à l'**ADR-070** :

1. **Architecture multi-dimensionnelle étanche (Aucun faux score global) :**
   - Interdiction formelle d'inventer un « score global de santé macroéconomique » synthétique. Les grandeurs macroéconomiques sont structurellement hétérogènes et sont présentées selon 5 dimensions autonomes :
     - `inflation` : Indice des prix à la consommation NIPC général et alimentaire (INSTAT).
     - `exchange_rate` : Cours de change journaliers de référence MID USD/MGA et EUR/MGA (BFM).
     - `fuel_energy` : Prix plafonds réglementés des carburants Gazole, SP95, Pétrole lampant (OMH) et consommation d'électricité.
     - `external_trade` : Volumes et valeurs CAF des importations de riz (TBE / Douanes), coût unitaire CAF frontière et ratio de dépendance (IDR).
     - `real_activity` : PIB réel trimestriel, indice de la production industrielle IPI et ciment (TBE).

2. **Distinctions conceptuelles rigoureuses :**
   - **Inflation vs Prix de marché :** L'inflation NIPC (taux de variation d'un panier urbain pondéré) est formellement ségréguée des variations de prix de marché vivriers au kg (relevés de terrain). La fonction `audit_inflation_vs_market_price_distinctness` audite cet écart sans jamais les moyenner ni les substituer.
   - **Commerce en volume vs valeur :** Les flux physiques en tonnes métriques (`tons`) et les valeurs monétaires (`MGA`) sont strictement distingués. Le coût unitaire d'importation CAF en MGA/kg est certifié avec vérification mathématique et physique.

3. **Invariants d'intégrité et gestion stricte des valeurs nulles :**
   - **Garde de rupture de base indiciaire (`base_shift`) :** Tout décalage de base temporelle entre deux indices (ex: base 2016 vs base 2024) interdit formellement le calcul de variation et produit strictement `NULL` avec la raison `base_shift`.
   - **Garde d'unités physiques (`incompatible_units`) :** Refus immédiat de calcul si les grandeurs physiques sont hétérogènes (ex: diviser des devises par des litres sans facteur certifié).
   - **Dénominateurs nuls et séries manquantes :** Tout dénominateur nul produit `NULL` (`zero_denominator`), toute série manquante produit `NULL` (`missing_series`), sans jamais inventer de nombre LLM ni substituer un `0.0` trompeur.
   - **Statut de complétude observable :** Chaque dimension et le tableau complet exposent leur complétude réelle (`complete`, `partial`, `no_data`).

4. **Vue SQL Gold et raccordement au moteur de publication :**
   - Création de la vue matérialisée `gold.economic_dashboard` (`014_economic_dashboard.sql`) recomputable de manière déterministe depuis `obs.macro_observation`.
   - Intégration de `economic_dashboard` dans `ORDERED_GOLD_VIEWS` (`backend/src/ketrika/gold/refresh.py`) et dans `VIEW_TABLES` (`backend/src/ketrika/gold/provenance_gate.py`).

5. **Exposition REST :**
   - `GET /v1/economic/indicators` : Répertoire des 14 fiches métriques normatives.
   - `GET /v1/economic/dashboard` : Tableau économique structuré par dimension avec justifications de nullité.
   - `GET /v1/economic/pilot-context` : Articulation directe avec le pilote rizicole R2.4 (transmission fret gazole, change USD/MGA, coût unitaire d'importation CAF vs prix de détail local).

---

## 2. Fichiers créés et modifiés

- **Architecture, contrats et documentation :**
  - `docs/plan/DECISIONS.md` : Rédaction de l'ADR-070.
  - `docs/plan/SPECS.md` : Mise à jour des vues Gold (§15) et des endpoints REST (§19).
  - `docs/metrics/economic_indicators.md` : Spécification normative des 14 fiches métriques.
  - `docs/plan/PROGRESS.md` : Journal d'exécution et traçabilité.
  - `docs/plan/MARKET_INTELLIGENCE_EXECUTION_PLAN.md` : Synchronisation du statut R2.8.
- **Couche Gold (SQL & Python) :**
  - `backend/src/ketrika/gold/sql/014_economic_dashboard.sql` : Vue SQL matérialisée avec calculs calendaires exacts.
  - `backend/src/ketrika/gold/economic.py` : Catalogue `ECONOMIC_METRIC_CARDS`, fonctions de calcul sécurisé (`calculate_safe_variation`, `calculate_import_unit_cost`, `calculate_import_dependency_ratio`), audit de séparation et requêtes DB.
  - `backend/src/ketrika/gold/refresh.py` : Enregistrement de `economic_dashboard` dans `ORDERED_GOLD_VIEWS`.
  - `backend/src/ketrika/gold/provenance_gate.py` : Enregistrement dans `VIEW_TABLES`.
- **Couche API (FastAPI) :**
  - `backend/src/ketrika/api/schemas.py` : Schémas Pydantic typés (`EconomicMetricCardItem`, `IndicatorObservationOut`, `DimensionSummaryOut`, `EconomicDashboardOut`, `PilotEconomicContextOut`).
  - `backend/src/ketrika/api/routers/economic.py` : Routeur des endpoints `/v1/economic/*`.
  - `backend/src/ketrika/api/main.py` : Déclaration et inclusion du routeur.
- **Suite de tests :**
  - `backend/tests/unit/test_economic_dashboard.py` : 19 tests unitaires et de qualification couvrant tous les invariants, calculs et endpoints.

---

## 3. Preuves d'exécution des tests

### 3.1 Tests unitaires et couverture du tableau économique
```bash
docker run --rm -v /home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep:/workspace -w /workspace/backend ketrika-backend:dev uv run pytest -v tests/unit/test_economic_dashboard.py --cov=ketrika.gold.economic --cov=ketrika.api.routers.economic --cov-report=term-missing
```
Résultat :
```text
============================= test session starts ==============================
collected 19 items

tests/unit/test_economic_dashboard.py::test_economic_metric_cards_catalog_structure PASSED [  5%]
tests/unit/test_economic_dashboard.py::test_safe_variation_normal_computation PASSED [ 10%]
tests/unit/test_economic_dashboard.py::test_safe_variation_refuses_base_shift PASSED [ 15%]
tests/unit/test_economic_dashboard.py::test_safe_variation_zero_denominator_guard PASSED [ 21%]
tests/unit/test_economic_dashboard.py::test_safe_variation_missing_denominator_guard PASSED [ 26%]
tests/unit/test_economic_dashboard.py::test_safe_variation_missing_series_guard PASSED [ 31%]
tests/unit/test_economic_dashboard.py::test_calculate_import_unit_cost_valid PASSED [ 36%]
tests/unit/test_economic_dashboard.py::test_calculate_import_unit_cost_incompatible_units PASSED [ 42%]
tests/unit/test_economic_dashboard.py::test_calculate_import_unit_cost_zero_or_negative_volume PASSED [ 47%]
tests/unit/test_economic_dashboard.py::test_calculate_import_dependency_ratio_valid PASSED [ 52%]
tests/unit/test_economic_dashboard.py::test_calculate_import_dependency_ratio_unaligned_period PASSED [ 57%]
tests/unit/test_economic_dashboard.py::test_calculate_import_dependency_ratio_zero_availability PASSED [ 63%]
tests/unit/test_economic_dashboard.py::test_audit_inflation_vs_market_price_distinctness PASSED [ 68%]
tests/unit/test_economic_dashboard.py::test_economic_dashboard_sql_view_and_refresh_registration PASSED [ 73%]
tests/unit/test_economic_dashboard.py::test_api_get_economic_indicators_catalog PASSED [ 78%]
tests/unit/test_economic_dashboard.py::test_api_get_economic_dashboard_structure PASSED [ 84%]
tests/unit/test_economic_dashboard.py::test_api_get_pilot_economic_context PASSED [ 89%]
tests/unit/test_economic_dashboard.py::test_api_get_pilot_economic_context_with_populated_db PASSED [ 94%]
tests/unit/test_economic_dashboard.py::test_api_get_economic_dashboard_with_db_rows PASSED [100%]

================================ tests coverage ================================
Name                                  Stmts   Miss  Cover   Missing
-------------------------------------------------------------------
src/ketrika/api/routers/economic.py      81      4    95%   132-134, 146
src/ketrika/gold/economic.py            108      2    98%   290, 307
-------------------------------------------------------------------
TOTAL                                   189      6    97%
============================= 19 passed in 30.73s ==============================
```

### 3.2 Contrôles statiques (Ruff & Mypy)
```bash
docker run --rm -v /home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep:/workspace -w /workspace/backend ketrika-backend:dev uv run ruff check src/ketrika/gold/economic.py src/ketrika/api/routers/economic.py tests/unit/test_economic_dashboard.py
docker run --rm -v /home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep:/workspace -w /workspace/backend ketrika-backend:dev uv run mypy src/ketrika/gold/economic.py src/ketrika/api/routers/economic.py src/ketrika/api/schemas.py tests/unit/test_economic_dashboard.py
```
Résultat :
```text
All checks passed!
Success: no issues found in 4 source files
```

### 3.3 Non-régression globale (166 tests sur 11 modules)
```bash
docker run --rm -v /home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep:/workspace -w /workspace/backend ketrika-backend:dev uv run pytest -v \
  tests/unit/test_economic_dashboard.py \
  tests/unit/test_omh_public.py \
  tests/unit/test_bfm_public.py \
  tests/unit/test_instat_tbe.py \
  tests/unit/test_instat_nipc.py \
  tests/unit/test_registry.py \
  tests/unit/test_registry_conformance.py \
  tests/unit/test_source_definitions.py \
  tests/unit/test_contracts_time_origin_macro.py \
  tests/unit/test_market_coverage_and_pilot.py \
  tests/unit/test_gold_dq_aggregation_audit.py
```
Résultat :
```text
============================= 166 passed in 48.74s =============================
```

---

## 4. Conclusion et conformité Definition of Done

- Tous les critères d'acceptation de **R2.8** sont satisfaits.
- Couverture globale des modules développés : **97%** (exigence $\ge 80\%$).
- Aucune régression : **166/166** tests passés avec succès.
- La tâche **R2.8** est validée et marquée **DONE**.
