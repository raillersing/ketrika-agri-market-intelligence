# Dossier de Preuve — R4.1 : Formalisation des contrats géospatiaux et agroclimatiques

## 1. Contexte & Périmètre

- **Tâche :** R4.1 (MUST) — Formaliser les contrats géospatiaux et agroclimatiques, modèle météo observée vs prévue, calendriers culturaux.
- **Date d'exécution :** 2026-10-16T20:45:00Z.
- **Environnement :** Conteneur Docker `ketrika-backend:dev`, base de données PostgreSQL `aiagent-db-1` (PostGIS 17-3.5), worktree `/home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep`, branche `work/r1-sources-prep`.
- **Référence normative :** `AGENTS.md` §1, §4 (règles 1, 3, 8, 9), §10 ; `MARKET_INTELLIGENCE_EXECUTION_PLAN.md` §9 (R4.1) ; `SPECS.md` §26 ; `ADR-080`.

---

## 2. Décisions d'Architecture et Contrats Métrologiques (ADR-080, SPECS §26)

1. **Référentiel Spatial et Découpage Raster :**
   - Système de coordonnées de référence (CRS) standard : `EPSG:4326` (WGS84).
   - Bounding Box officielle Madagascar : `[43.0, -25.8, 50.8, -11.8]` (min_lon, min_lat, max_lon, max_lat).
   - Découpage (clipping) immédiat sur la BBOX Madagascar avant archivage Bronze ou transformation en Silver.
   - Plafond budgétaire de stockage Bronze raster : $\le 50\text{ Mo}$ par partition mensuelle.
2. **Séparation Étanche Météo Observée vs Météo Prévue :**
   - **Météo observée (`obs.weather_observation`) :** Stocke strictement les réalisations passées. Extension avec les colonnes `stage` (`preliminary` | `final`), `spatial_resolution`, `coverage_ratio`, et `raster_source_record_id`.
   - **Double versioning fournisseur sans écrasement (C2/C4) :** Une version préliminaire (ex: CHIRPS préliminaire à J+5) n'est jamais écrasée. Lors de la publication définitive (à M+1), un nouvel enregistrement `stage='final'` est inséré avec `superseded_by` pointant vers la version préliminaire.
   - **Météo prévue (`obs.weather_forecast`) :** Table dédiée et étanche pour les projections météorologiques numériques (ECMWF, GFS, Météo Madagascar), avec `issued_at`, `valid_from`, `valid_to`, `horizon_hours`, `variable`, `model_name`, `predicted_value`, quantiles `predicted_p10`/`predicted_p90`. Aucune observation de marché ne peut consommer de météo prévue sans scénario exogène explicite.
3. **Calendriers Culturaux Normalisés (`ref.crop_calendar` et `taxonomy/crop_calendar.yaml`) :**
   - Modélisation fine des cycles culturaux rizicoles et PPN prioritaires par bassin : Hauts Plateaux (riz vakiambiaty et hosy), Lac Alaotra (grenier à riz irrigué), Marovoay / Boeny (2e grenier à riz), Grand Sud (maïs et manioc de soudure), Côte Est (riz asara et hosy).
   - Définition des stades : `planting_start_month`, `planting_end_month`, `growing_start_month`, `growing_end_month`, `harvest_start_month`, `harvest_end_month`, `peak_harvest_month`, et `water_sensitivity_profile`.
4. **Véracité Agronomique de l'Agrégation Zonale :**
   - Méthodes reconnues : `point_centroid`, `zonal_mean`, `cropland_weighted_mean`.
   - Règle de loyauté métrologique : `cropland_weighted_mean` exige formellement la présence d'un raster de masque agricole vérifié. À défaut, l'agrégation bascule loyalement en `zonal_mean` avec `is_fallback=True` et motif explicite, sans usurper une fausse précision agronomique.

---

## 3. Preuves de Validation et Résultats Numériques

### 3.1 Migration Alembic
- **Migration :** `alembic/versions/0014_geospatial_weather_and_crop_calendar.py`.
- **Application :**
  ```text
  INFO  [alembic.runtime.migration] Running upgrade 0013_forecast_evaluations -> 0014_geospatial_weather_and_crop_calendar
  0014_geospatial_weather_and_crop_calendar (head)
  ```
- **Résultat :** Colonnes ajoutées à `obs.weather_observation`, tables `obs.weather_forecast` et `ref.crop_calendar` créées avec leurs index et contraintes uniques sur PostgreSQL.

### 3.2 Tests Unitaires et Métrologiques (`backend/tests/unit/test_geo_agroclimate_contracts.py`)
- **Commande :**
  `docker run --rm -v /home/.../r1-sources-prep:/workspace -w /workspace/backend ketrika-backend:dev uv run pytest -v tests/unit/test_geo_agroclimate_contracts.py --cov=ketrika.geo --cov-report=term-missing`
- **Résultats :** 8/8 tests passés en 10.08s.
  - `test_geospatial_constants_and_bbox` : PASSED
  - `test_bounding_box_validation_and_clipping` : PASSED
  - `test_geo_bounding_box_pydantic` : PASSED
  - `test_zonal_aggregation_veracity_and_fallbacks` : PASSED
  - `test_weather_forecast_record_contract` : PASSED
  - `test_crop_calendar_taxonomy` : PASSED
  - `test_dry_spells_computation` : PASSED
  - `test_sqlalchemy_models_instantiation` : PASSED

### 3.3 Couverture de Code `ketrika.geo`
- `ketrika.geo.__init__` : **100 %**
- `ketrika.geo.contracts` : **97 %**
- `ketrika.geo.raster` : **90 %**
- **TOTAL :** **94 %** (exigence $\ge 80\%$).

### 3.4 Contrôles Statiques
- **Ruff :** All checks passed! 0 warning, code formaté.
- **Mypy strict :** Success: no issues found in 5 source files.

---

## 4. Conclusion

La tâche R4.1 est **entièrement validée et qualifiée (DONE)**.
Les contrats géospatiaux et agroclimatiques sont scellés et prêts à accueillir les connecteurs CHIRPS (R4.2) et Météo Madagascar (R4.3).
