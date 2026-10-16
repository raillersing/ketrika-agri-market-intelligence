# Preuve R4.11 — Vue agroclimatique explicable, étanchéité multi-couches et transparence des sources facultatives

## 1. Contexte et Objectifs

- **Tâche :** `R4.11 — Livrer la vue agroclimatique explicable` (MUST).
- **Norme et Décision :** ADR-087 (`docs/plan/DECISIONS.md`), SPECS §19, §26.
- **Principes cardinaux :**
  1. **Disjonction stricte en 4 couches de données étanches :**
     - **Météo observée et estimée :** Précipitations mensuelles et décadaires (CHIRPS, DGM). Méthode d'agrégation explicite (`zonal_mean` avec indication transparente de l'absence de masque agricole vérifié).
     - **Anomalies climatiques rigoureuses :** Écart en mm/°C, % de la normale, Z-scores, niveaux de risque catégoriels calculés sur climatologie de référence 1991–2020 ($N \ge 10$ ans) ou statut explicite `insufficient_history`.
     - **Météo prévue numérique archivable :** Projections NWP (ECMWF IFS Open Data), étanches des observations (`value_kind: projected`), dates d'émission (`issued_at`), période de validité (`valid_from` à `valid_to`), horizon en heures et quantiles p10/p90.
     - **Calendriers culturaux et corridors commerciaux :** Stades phénologiques calculés dynamiquement pour le mois actif (`peak_harvest`, `harvest`, `planting`, `growing`), typologie baseline vs recommandation, corridors d'approvisionnement documentés.
     - **Événements et perspectives FEWS NET/IPC :** Alertes de sécurité alimentaire et phases IPC avec statut projeté certifié.
  2. **Transparence sur les sources facultatives non intégrées :**
     - FIRMS (feux), GloFAS (inondations) et Copernicus NDVI sont formellement signalées comme indisponibles (`status: unavailable`) avec motif explicite. Aucun faux chiffre zéro n'est fabriqué et aucun indice composite non étayé n'est produit.
  3. **Intégration de bout en bout (API REST + Frontend Next.js) :**
     - Schémas Pydantic typés, spécification OpenAPI exportée et typée en TypeScript, interface `/climate` connectée et validée par le build Next.js.

---

## 2. Composants implémentés

1. **Routeur FastAPI `backend/src/ketrika/api/routers/climate.py` :**
   - `GET /v1/climate/summary` : vue consolidée explicable par région/district.
   - `GET /v1/climate/anomalies` : séries temporelles d'anomalies observées avec baseline.
   - `GET /v1/climate/forecasts` : prévisions numériques archivées (`obs.weather_forecast`).
   - `GET /v1/climate/calendars` : calendriers culturaux, stades du mois et corridors commerciaux.
   - `GET /v1/climate/events` : alertes et perspectives FEWS NET / IPC (`obs.event`).
   - `GET /v1/climate/facultative-status` : transparence des sources environnementales optionnelles.
   - `GET /v1/weather/anomalies` : compatibilité ascendante préservée.
2. **Schémas Pydantic (`backend/src/ketrika/api/schemas.py`) :**
   - `ClimateForecastItem`, `CropCalendarItem`, `ClimateEventItem`, `FacultativeSourceStatus`, `ClimateAnomalyDetailItem`, `ClimateSummaryResponse`.
   - `ValueKind = Literal["observed", "imputed", "forecast", "projected", "composite"]`.
3. **Contrats OpenAPI et TypeScript :**
   - `web/src/lib/api/openapi.json` régénéré via `scripts/export_openapi.py`.
   - `web/src/lib/api/schema.d.ts` compilé via `openapi-typescript`.
4. **Interface utilisateur `/climate` (`web/src/app/climate/page.tsx`) :**
   - Sélecteur de région/bassin (Analamanga, Alaotra-Mangoro, Boeny, Atsinanana, Androy).
   - 3 cartes de synthèse KPI (Précipitations observées, Météo prévue 72h ECMWF avec quantiles p10/p90, Diagnostic de risque hydrique catégoriel).
   - Tableau dynamique des calendriers culturaux et corridors commerciaux prouvés.
   - Encarts dédiés aux alertes FEWS NET / IPC et à la transparence des sources optionnelles indisponibles.
5. **Suite de tests unitaires (`backend/tests/unit/test_api_climate.py`) :**
   - 7 tests complets validant les contrats, la séparation observed vs projected, et les replis méthodologiques.

---

## 3. Résultats de validation

### 3.1 Tests unitaires Backend

```text
tests/unit/test_api_climate.py::test_climate_summary_endpoint PASSED     [ 14%]
tests/unit/test_api_climate.py::test_climate_anomalies_endpoint PASSED   [ 28%]
tests/unit/test_api_climate.py::test_climate_forecasts_endpoint PASSED   [ 42%]
tests/unit/test_crop_calendars_endpoint PASSED                           [ 57%]
tests/unit/test_climate_events_endpoint PASSED                           [ 71%]
tests/unit/test_facultative_sources_status_endpoint PASSED              [ 85%]
tests/unit/test_weather_anomalies_backward_compatibility PASSED          [100%]

Name                                 Stmts   Miss  Cover   Missing
------------------------------------------------------------------
src/ketrika/api/routers/climate.py     138     11    92%   117-120, 154-158, 340, 342
------------------------------------------------------------------
TOTAL                                  138     11    92%
======================== 7 passed, 4 warnings in 23.37s ========================
```

### 3.2 Contrôles statiques et Frontend

```text
uv run ruff check -> All checks passed!
uv run mypy -> Success: no issues found in 3 source files
pnpm run typecheck (tsc --noEmit) -> Exit 0
pnpm test (vitest run) -> 39 passed (5 files)
pnpm run build (next build) -> Exit 0, 16/16 routes compilées avec succès
```

---

## 4. Conclusion

La tâche R4.11 est entièrement livrée, qualifiée avec 92 % de couverture sur le routeur d'API, 39 tests vitest verts et build Next.js certifié.
