# Preuve R4.6 — Calcul rigoureux des anomalies agroclimatiques et des agrégations zonales

## 1. Contexte et Objectifs

- **Tâche :** `R4.6 — Calculer anomalies et agrégations zonales correctement` (MUST).
- **Norme et Décision :** ADR-085 (`docs/plan/DECISIONS.md`), SPECS §26.
- **Principes cardinaux :**
  1. **Seuil minimal d'historique climatologique ($N \ge 10$ années) :**
     - Abstention formelle (`status='insufficient_history'`, valeurs d'anomalies à `None`) dès que le nombre d'années historiques disponibles est inférieur à 10. Refus d'inventer des moyennes climatiques ou de bruiter le signal.
  2. **Formules et métriques différenciées par variable :**
     - Précipitations : somme/cumul, écart absolu ($P - \bar{P}$ en mm), pourcentage de la normale ($P / \bar{P} \times 100\%$), indice standardisé Z-score.
     - Températures : moyenne, écart absolu ($T - \bar{T}$ en °C), Z-score standardisé.
  3. **Agrégation zonale rigoureuse :**
     - Raster test $3 \times 3$ à agrégat calculé à la main, exclusion des pixels nodata ($-9999{,}0$), conservation de la fraction de couverture spatiale (`coverage_ratio`).
     - Repli strict et transparent vers `zonal_mean` dès qu'un masque agricole n'est pas vérifié (`cropland_mask_available=False`).

---

## 2. Composants implémentés

1. **Module `ketrika.geo.anomalies` :**
   - Constante `MIN_BASELINE_YEARS = 10`.
   - Modèles typés `ClimateBaseline` et `ClimateAnomalyResult`.
   - Fonction `compute_climate_baseline(historical_values, period_years, min_years=10)` : moyenne, écart-type, bornes temporelles.
   - Fonction `compute_climate_anomaly(observed_value, baseline, variable)` : écart absolu, pourcentage de la normale, Z-score, niveau de risque catégoriel (`AgroClimateRiskLevel`).
   - Fonction `classify_rainfall_anomaly(percent_of_normal, standardized_anomaly)` : seuils agronomiques (sécheresse critique $< 50\%$, déficit modéré $< 75\%$, normal $75-125\%$, excédent modéré $125-160\%$, risque inondation $> 160\%$).
2. **Extensions `ketrika.geo.contracts` et `ketrika.geo.raster` :**
   - Énumérations `AgroClimateRiskLevel` et `ClimateAnomalyMethod`.
   - Agrégation zonale `aggregate_zonal` avec ratio de couverture et repli explicable.
3. **Suite de tests unitaires et de vérification mathématique :**
   - `backend/tests/unit/test_geo_anomalies.py` : 7 tests validant calculs manuels, seuil $N < 10$, anomalies de pluie et température, et agrégation zonale synthétique.

---

## 3. Résultats de validation

### 3.1 Tests unitaires et couverture du package `ketrika.geo`

```text
tests/unit/test_geo_anomalies.py::test_compute_climate_baseline_success PASSED [  6%]
tests/unit/test_geo_anomalies.py::test_compute_climate_baseline_abstention_insufficient_history PASSED [ 13%]
tests/unit/test_geo_anomalies.py::test_compute_climate_anomaly_abstention_status PASSED [ 20%]
tests/unit/test_geo_anomalies.py::test_compute_climate_anomaly_rainfall_deficit_and_surplus PASSED [ 26%]
tests/unit/test_geo_anomalies.py::test_compute_climate_anomaly_temperature PASSED [ 33%]
tests/unit/test_geo_anomalies.py::test_zonal_aggregation_hand_calculated_grid PASSED [ 40%]
tests/unit/test_geo_anomalies.py::test_zonal_aggregation_cropland_weighted_strict_fallback PASSED [ 46%]
tests/unit/test_geo_agroclimate_contracts.py::test_geospatial_constants_and_bbox PASSED [ 53%]
tests/unit/test_geo_agroclimate_contracts.py::test_bounding_box_validation_and_clipping PASSED [ 60%]
tests/unit/test_geo_agroclimate_contracts.py::test_geo_bounding_box_pydantic PASSED [ 66%]
tests/unit/test_geo_agroclimate_contracts.py::test_zonal_aggregation_veracity_and_fallbacks PASSED [ 73%]
tests/unit/test_geo_agroclimate_contracts.py::test_weather_forecast_record_contract PASSED [ 80%]
tests/unit/test_geo_agroclimate_contracts.py::test_crop_calendar_taxonomy PASSED [ 86%]
tests/unit/test_geo_agroclimate_contracts.py::test_dry_spells_computation PASSED [ 93%]
tests/unit/test_geo_agroclimate_contracts.py::test_sqlalchemy_models_instantiation PASSED [100%]

Name                           Stmts   Miss  Cover   Missing
------------------------------------------------------------
src/ketrika/geo/__init__.py        4      0   100%
src/ketrika/geo/anomalies.py      76     12    84%   74, 93, 101, 109, 122, 154, 162, 169-174
src/ketrika/geo/contracts.py     139      4    97%   104, 198, 201, 207
src/ketrika/geo/raster.py         84      8    90%   35, 37, 48, 78, 102, 133-135
------------------------------------------------------------
TOTAL                            303     24    92%
============================= 15 passed in 10.57s ==============================
```

### 3.2 Contrôles statiques

```text
uv run ruff check -> All checks passed!
uv run mypy -> Success: no issues found in 4 source files
```

---

## 4. Conclusion

La tâche R4.6 est entièrement achevée et qualifiée avec 92 % de couverture sur l'ensemble du sous-système géospatial et agroclimatique.
