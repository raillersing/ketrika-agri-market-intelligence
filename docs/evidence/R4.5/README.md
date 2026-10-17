# Preuve R4.5 — Qualification d'une météo prévue archivable (ECMWF Open Data)

## 1. Contexte et Objectifs

- **Tâche :** `R4.5 — Qualifier une météo prévue archivable` (MUST).
- **Norme et Décision :** ADR-084 (`docs/plan/DECISIONS.md`), SPECS §26.
- **Principes cardinaux :**
  1. **Séparation étanche météo observée vs météo prévue (Règle 9) :**
     - Les prévisions numériques du temps sont exclusivement insérées dans la table dédiée `obs.weather_forecast` (créée en R4.1 via la migration 0014) et ne contaminent jamais `obs.weather_observation`.
  2. **Archivage Bronze immuable avant expiration glissante (Règles 2 & 4) :**
     - Les cycles de prévision (00z, 12z) sont archivés dans Bronze avec leur empreinte SHA-256 et leurs métadonnées d'émission (`issued_at`), garantissant le rejeu hors ligne 100 % reproductible sans réseau.
  3. **Quantiles d'incertitude et horizons temporels :**
     - Horizons déclarés en heures (24h à 168h), conservation des quantiles probabilistes d'ensemble (`predicted_p10`, `predicted_p90`) et de la médiane attendue (`predicted_value`).
  4. **Contrôles de cohérence physique et refus d'inventions :**
     - Rejet des anomalies physiques aberrantes (précipitations négatives, températures supérieures à 60 °C).
     - Refus catégorique de fabriquer des pseudo-hindcasts à partir des observations réelles réalisées (anti-triche A09, Règle 10).

---

## 2. Composants implémentés

1. **Déclaration de la source officielle :**
   - Source `ecmwf_open` enregistrée dans `registry/sources.yaml` avec priorité P2, licence CC-BY-4.0 / WMO Essential.
2. **Type de données normalisé :**
   - `WeatherForecastRecord` défini dans `backend/src/ketrika/connectors/records.py` avec clé naturelle 6 composantes (`location_raw`, `issued_at`, `valid_from`, `horizon_hours`, `variable`, `model_name`).
3. **Connecteur opérationnel :**
   - `backend/src/ketrika/connectors/ecmwf_open.py` (`EcmwfOpenConnector`, `Connector = EcmwfOpenConnector`).
   - Découverte des cycles quotidiens (00z, 12z) pour Madagascar.
   - Contrôles physiques (pluie négative -> `invalid_physical_value`, température irréaliste -> `unrealistic_temperature`).
   - Enregistrement dans `backend/src/ketrika/connectors/registry.py`.
4. **Chargeur et supersession en base :**
   - `load_weather_forecast_record_with_supersession` implémenté dans `backend/src/ketrika/connectors/runner.py` avec résolution géographique et supersession non destructive.
5. **Fixtures officielles et d'anomalies :**
   - `backend/tests/fixtures/ecmwf_open/ecmwf_ifs_20240301_00z.json` (multi-horizons 24h/48h/72h, quantiles p10/p90).
   - `backend/tests/fixtures/ecmwf_open/ecmwf_ifs_20240301_12z.json` (succession de runs).
   - `backend/tests/fixtures/ecmwf_open/ecmwf_unavailable.json` (indisponibilité fail-safe).
   - `backend/tests/fixtures/ecmwf_open/ecmwf_invalid_physical.json` (rejet physique).
6. **Suite de tests unitaires et de contrats :**
   - `backend/tests/unit/test_ecmwf_open.py` : 7 tests validant découverte, parsing, succession de runs, contrôles physiques, indisponibilité, et étanchéité absolue de stockage.

---

## 3. Résultats de validation

### 3.1 Tests unitaires et couverture

```text
tests/unit/test_ecmwf_open.py::test_ecmwf_open_discovery PASSED          [ 14%]
tests/unit/test_ecmwf_open.py::test_ecmwf_open_discovery_override PASSED [ 28%]
tests/unit/test_ecmwf_open.py::test_ecmwf_open_parse_standard_run PASSED [ 42%]
tests/unit/test_ecmwf_open.py::test_ecmwf_open_two_runs_succession PASSED [ 57%]
tests/unit/test_ecmwf_open.py::test_ecmwf_open_physical_consistency_checks PASSED [ 71%]
tests/unit/test_ecmwf_open.py::test_ecmwf_open_unavailable_and_empty PASSED [ 85%]
tests/unit/test_ecmwf_open.py::test_ecmwf_loader_watertight_separation_and_supersession PASSED [100%]

Name                                   Stmts   Miss  Cover   Missing
--------------------------------------------------------------------
src/ketrika/connectors/ecmwf_open.py      84      9    89%   68, 77-81, 155, 192-194
--------------------------------------------------------------------
TOTAL                                     84      9    89%
============================== 7 passed in 16.90s ==============================
```

### 3.2 Contrôles statiques

```text
uv run ruff check -> All checks passed!
uv run mypy -> Success: no issues found in 5 source files
```

---

## 4. Conclusion

La météo prévue archivable est pleinement qualifiée avec son connecteur ECMWF Open Data, son schéma étanche dans `obs.weather_forecast`, et ses contrôles physiques rigoureux.
