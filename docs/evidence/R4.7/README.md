# Preuve R4.7 — Versioning des calendriers culturaux, stades phénologiques et corridors commerciaux

## 1. Contexte et Objectifs

- **Tâche :** `R4.7 — Versionner les calendriers culturaux` (MUST).
- **Norme et Décision :** ADR-086 (`docs/plan/DECISIONS.md`), SPECS §26.
- **Principes cardinaux :**
  1. **Disjonction stricte entre calendrier traditionnel et recommandation saisonnière :**
     - Calendrier traditionnel pérenne (`calendar_type='traditional_baseline'`, `campaign='baseline_permanent'`).
     - Recommandation saisonnière officielle pour une campagne donnée (`calendar_type='seasonal_recommendation'`, ex: avis MinAE/DGM 2023/2024 face au retard pluviométrique) distincte et versionnée.
  2. **Immutabilité, révision et visibilité des versions passées (Principe 3 d'AGENTS.md) :**
     - Aucune mise à jour destructive. Une révision crée une nouvelle entrée avec `superseded_by` pointant vers la nouvelle version, tandis que l'ancienne reste consultable avec `is_active=False`.
  3. **Liaison explicite bassin de production -> marchés de consommation avec statut de preuve :**
     - Corridors commerciaux (`market_links`) étayés par des preuves documentées (`proof_status='documented_trade_corridor'` ou `'official_supply_basin'`).
     - Refus catégorique des attributions par simple proximité spatiale supposée (`unverified_assumption`).
  4. **Exclusion stricte des entrées non vérifiées des alertes de marché :**
     - Une entrée sans source officielle ou comportant une interprétation non mécanique a `verified=False` et est formellement exclue des alertes automatiques (`eligible_for_alerts=False`).
  5. **Aucun chiffre inventé (Principe 6 & 7 d'AGENTS.md) :**
     - Un calendrier cultural fournit exclusivement des fenêtres temporelles. Il ne contient ni ne produit aucune estimation de tonnage de récolte, ni de prévision de prix, ni de pic de volume de marché.

---

## 2. Composants implémentés

1. **Taxonomie officielle enrichie (`taxonomy/crop_calendar.yaml`) :**
   - 10 cycles agricoles représentatifs couvrant le riz irrigué/pluvial/bas-fond, le maïs et le manioc dans les principaux bassins de Madagascar (Lac Alaotra, Plaine de Marovoay, Hauts Plateaux, Côte Est, Grand Sud).
   - Corridors commerciaux documentés vers les grands marchés de consommation (Antananarivo, Toamasina, Mahajanga, Antsirabe, Ambovombe, Manakara, Toliara).
   - Recommandation saisonnière officielle 2023/2024 pour les Hauts Plateaux (repiquage décalé en novembre).
   - Entrée de test préliminaire `verified: false`, sans source officielle, isolée des alertes.
2. **Migration Alembic 0015 (`backend/alembic/versions/0015_crop_calendar_versioning_and_market_links.py`) :**
   - Ajout des colonnes `calendar_version`, `calendar_type`, `campaign`, `variety`, `eligible_for_alerts`, `is_active`, `superseded_by`, `basin_code`, `market_links`.
   - Contrainte check sur `calendar_type`.
   - Index partiel unique `uq_crop_calendar_active` sur `(product_id, location_id, season_name, crop_regime) WHERE is_active = TRUE`.
3. **Modèle SQLAlchemy `CropCalendar` (`backend/src/ketrika/core/models/db.py`) :**
   - Mappé sur le schéma `ref.crop_calendar` avec types PostgreSQL complets et relation d'auto-référencement sur `superseded_by`.
4. **Schémas Pydantic et Contrats (`backend/src/ketrika/geo/contracts.py`) :**
   - Énumérations `CalendarType` et `MarketLinkProofStatus`.
   - Modèle `MarketLink`.
   - Modèle `CropCalendarRecord` avec configuration stricte `extra="forbid"`, validateur d'intégrité rejetant les projections de tonnage/prix et forçant `eligible_for_alerts=False` si non vérifié.
5. **Moteur phénologique et de corridors (`backend/src/ketrika/geo/calendar.py`) :**
   - `is_month_in_window` gérant les fenêtres franchissant la limite de l'année civile (ex: nov-fév).
   - `detect_phenological_stage` identifiant `peak_harvest`, `harvest`, `planting`, `growing`.
   - `get_documented_trade_corridors_for_market` filtrant les bassins d'approvisionnement documentés et rejetant les proximités non vérifiées.
   - `supersede_calendar_record` assurant la révision non destructive.
   - `get_alert_eligible_calendars` et `get_calendar_history`.
6. **Suite de tests unitaires (`backend/tests/unit/test_crop_calendar_versioning.py`) :**
   - 8 tests complets couvrant l'ensemble des critères d'acceptation de R4.7.

---

## 3. Résultats de validation

### 3.1 Tests unitaires et couverture du package `ketrika.geo`

```text
tests/unit/test_crop_calendar_versioning.py::test_load_crop_calendar_taxonomy_complete PASSED [  4%]
tests/unit/test_crop_calendar_versioning.py::test_traditional_vs_seasonal_recommendation PASSED [  8%]
tests/unit/test_crop_calendar_versioning.py::test_phenological_stage_detection_and_wrap_around PASSED [ 13%]
tests/unit/test_crop_calendar_versioning.py::test_multi_cycle_overlap_management PASSED [ 17%]
tests/unit/test_crop_calendar_versioning.py::test_market_links_and_documented_trade_corridors PASSED [ 21%]
tests/unit/test_crop_calendar_versioning.py::test_unverified_entry_excluded_from_alerts PASSED [ 26%]
tests/unit/test_crop_calendar_versioning.py::test_rejection_of_prohibited_projections PASSED [ 30%]
tests/unit/test_crop_calendar_versioning.py::test_supersede_calendar_record_immutability PASSED [ 34%]
tests/unit/test_geo_anomalies.py::test_compute_climate_baseline_success PASSED [ 39%]
tests/unit/test_geo_anomalies.py::test_compute_climate_baseline_abstention_insufficient_history PASSED [ 43%]
tests/unit/test_geo_anomalies.py::test_compute_climate_anomaly_abstention_status PASSED [ 47%]
tests/unit/test_geo_anomalies.py::test_compute_climate_anomaly_rainfall_deficit_and_surplus PASSED [ 52%]
tests/unit/test_geo_anomalies.py::test_compute_climate_anomaly_temperature PASSED [ 56%]
tests/unit/test_geo_anomalies.py::test_zonal_aggregation_hand_calculated_grid PASSED [ 60%]
tests/unit/test_geo_anomalies.py::test_zonal_aggregation_cropland_weighted_strict_fallback PASSED [ 65%]
tests/unit/test_geo_agroclimate_contracts.py::test_geospatial_constants_and_bbox PASSED [ 69%]
tests/unit/test_geo_agroclimate_contracts.py::test_bounding_box_validation_and_clipping PASSED [ 73%]
tests/unit/test_geo_agroclimate_contracts.py::test_geo_bounding_box_pydantic PASSED [ 78%]
tests/unit/test_geo_agroclimate_contracts.py::test_zonal_aggregation_veracity_and_fallbacks PASSED [ 82%]
tests/unit/test_geo_agroclimate_contracts.py::test_weather_forecast_record_contract PASSED [ 86%]
tests/unit/test_geo_agroclimate_contracts.py::test_crop_calendar_taxonomy PASSED [ 91%]
tests/unit/test_geo_agroclimate_contracts.py::test_dry_spells_computation PASSED [ 95%]
tests/unit/test_geo_agroclimate_contracts.py::test_sqlalchemy_models_instantiation PASSED [100%]

Name                           Stmts   Miss  Cover   Missing
------------------------------------------------------------
src/ketrika/geo/__init__.py        5      0   100%
src/ketrika/geo/anomalies.py      76     12    84%   74, 93, 101, 109, 122, 154, 162, 169-174
src/ketrika/geo/calendar.py       62      7    89%   33, 77, 79, 81, 83, 85, 118
src/ketrika/geo/contracts.py     181      7    96%   129, 220, 231, 239, 267, 270, 276
src/ketrika/geo/raster.py         84      8    90%   35, 37, 48, 78, 102, 133-135
------------------------------------------------------------
TOTAL                            408     34    92%
============================= 23 passed in 13.90s ==============================
```

### 3.2 Contrôles statiques

```text
uv run ruff check -> All checks passed!
uv run mypy -> Success: no issues found in 8 source files
```

---

## 4. Conclusion

La tâche R4.7 est entièrement réalisée, qualifiée avec 92 % de couverture de code, migration PostgreSQL 0015 appliquée et documentée.
