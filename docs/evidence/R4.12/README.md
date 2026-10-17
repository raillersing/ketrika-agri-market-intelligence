# Dossier de Preuve — R4.12 : Gate Agroclimat, Météo, Calendriers et Environnement (Tag : `mi-r4-qualified`)

## 1. Contexte & Périmètre de Qualification

- **Tâche :** R4.12 (Gate MUST de fin de Phase R4 — Observatoire agroclimatique, météo, calendriers culturaux et contrats géospatiaux).
- **Date d'exécution :** 2026-10-17T01:45:00Z.
- **Environnement :** Conteneurs Docker isolés `ketrika-backend:dev` et `ketrika-web:dev`, base de données PostgreSQL `aiagent-db-1`, worktree `/home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep`, branche `work/r1-sources-prep`.
- **Référence normative :** `AGENTS.md` §1, §3, §4, §10 ; `MARKET_INTELLIGENCE_EXECUTION_PLAN.md` §9 (R4.1–R4.12) ; `SPECS.md` §19, §26 ; `ADR-080`, `ADR-081`, `ADR-082`, `ADR-083`, `ADR-084`, `ADR-085`, `ADR-086`, `ADR-087`.
- **Objectif :** Valider formellement les 8 exigences scientifiques, géospatiales et agronomiques de la phase R4 sans dérogation :
  1. Contrats géospatiaux stricts (`ketrika.geo.contracts`), séparation absolue météo observée (`WeatherRecord`) vs météo prévue (`WeatherForecastRecord`), bounding box Madagascar et géométries valides.
  2. Qualification CHIRPS v2.0 à double cycle (version préliminaire dekad vs version finale mensuelle), distinction rigoureuse des valeurs nodata (-9999.0) vs 0.0 mm observés, traçabilité et supersession C2/C4.
  3. Extraction déterministe des bulletins agrométéorologiques DGM Météo Madagascar (`meteo_mg`), disjonction stricte date d'émission vs période de validité, rejet catégorique des probabilités de pluie inventées.
  4. Intégration des événements de sécurité alimentaire et perspectives FEWS NET (`fewsnet_mdg`) et IPC (`ipc_mdg`), typologie standardisée des phases IPC 1 à 5, séparation formelle période courante vs perspectives projetées.
  5. Qualification des prévisions numériques du temps étanches et archivables (ECMWF Open Data ensemble IFS 0.4°), respect de l'ordonnancement non croisé des quantiles d'incertitude ($p10 \le p50 \le p90$), horizons $d+1$ à $d+10$, immutabilité du forecast run.
  6. Calcul rigoureux des anomalies agroclimatiques (`ketrika.geo.anomalies`), seuil minimal d'historique climatologique $N \ge 10$ années de baseline, abstention formelle avec statut `insufficient_history` si l'historique est incomplet, agrégations zonales pondérées.
  7. Versioning complet des calendriers culturaux (`taxonomy/crop_calendar.yaml`, migration Alembic 0015), disjonction nette calendrier permanent traditionnel vs recommandation de campagne 2023/2024, détection des stades phénologiques avec wrap-around calendaire, identification des corridors commerciaux d'approvisionnement documentés et rejet absolu des conjectures économiques arbitraires.
  8. Déclaration transparente et contractuelle des sources environnementales facultatives non intégrées (`/v1/climate/facultative-status`, FIRMS, GloFAS, Copernicus NDVI) avec motif explicite et refus absolu de substitution par de faux zéros numériques.

---

## 2. Synthèse d'Exécution des Critères du Gate R4 (`test_gate_r4_agroclimate.py`)

| Critère | Périmètre Qualifié | Résultat du Test | Constat Métrologique |
|---|---|---|---|
| **C1 : Contrats Géospatiaux** | Bounding box Madagascar validée, séparation étanche `WeatherRecord` (observé) vs `WeatherForecastRecord` (prévu), rejet des fenêtres de validité inversées | **PASSED** | Aucune confusion entre passé observé et futur projeté ; géométrie Madagascar vérifiée. |
| **C2 : Dualité CHIRPS** | Découpage raster 0.05°, nodata -9999.0 filtré sans être assimilé à 0 mm, cycles `preliminary` vs `final` distincts | **PASSED** | Conservation de la vérité terrain ; les 0 mm réels ne sont pas éliminés. |
| **C3 : Bulletins DGM Météo** | Extraction PDF/texte déterministe, distinction date d'émission (ex. 11/11) vs décade valide (01-10/11), zéro probabilité hallucinée | **PASSED** | Dates et avis textuels conformes aux sources officielles sans falsification. |
| **C4 : FEWS NET & IPC** | Événements et classifications IPC 1 à 5 (`fewsnet_mdg`, `ipc_mdg`), distinction horizon courant vs projeté | **PASSED** | Gravité des crises documentée ; traçabilité des perspectives d'insécurité alimentaire. |
| **C5 : Prévisions ECMWF Open** | Modèle IFS ensemble, respect strict $p10 \le p50 \le p90$, horizons 24h à 240h, rejet des runs rétroactifs | **PASSED** | Intégrité des distributions prédictives physiques garantie. |
| **C6 : Anomalies & Baselines** | Règle d'or $N \ge 10$ ans pour baseline climatologique, abstention si $N < 10$ (`insufficient_history`), classification en 4 niveaux de risque | **PASSED** | Aucun diagnostic climatique hasardeux sur historique insuffisant. |
| **C7 : Calendriers & Corridors** | Migration Alembic 0015, baseline traditionnelle vs campagne 2023/2024, stades phénologiques calendaires, corridors documentés (Alaotra, Boeny, Centre), interdiction des projections économiques extra | **PASSED** | Pas de dérivation arbitraire de tonnages ou prix ; corridors certifiés par études institutionnelles. |
| **C8 : Transparence Facultative** | Statut transparent des sources optionnelles (NASA FIRMS, GloFAS, Copernicus), motif documenté, zéro remplissage artificiel par 0.0 | **PASSED** | Zéro faux zéro ; intégrité de l'API `/v1/climate` pour les intégrations ultérieures. |

---

## 3. Résultats Chiffrés et Couverture Globale

- **Suite de Gate R4 :** 8/8 tests passés en 25.05s (exit code 0).
- **Suite Complète Agroclimat/Météo (Phase R4) :** 66 tests passés en 29.12s (exit code 0).
  - `tests/unit/test_gate_r4_agroclimate.py` : 8 passed
  - `tests/unit/test_geo_agroclimate_contracts.py` : 8 passed
  - `tests/unit/test_chirps.py` : 7 passed
  - `tests/unit/test_meteo_mg.py` : 6 passed
  - `tests/unit/test_fewsnet_ipc.py` : 8 passed
  - `tests/unit/test_ecmwf_open.py` : 7 passed
  - `tests/unit/test_geo_anomalies.py` : 7 passed
  - `tests/unit/test_crop_calendar_versioning.py` : 8 passed
  - `tests/unit/test_api_climate.py` : 7 passed
- **Couverture de code globale `ketrika.geo` et `ketrika.api.routers.climate` :** **92 %** (largement supérieure au seuil normatif de 80%).
  - `ketrika.geo.__init__` : 100 %
  - `ketrika.geo.contracts` : 97 %
  - `ketrika.geo.raster` : 92 %
  - `ketrika.api.routers.climate` : 92 %
  - `ketrika.geo.calendar` : 89 %
  - `ketrika.geo.anomalies` : 84 %
- **Contrôles statiques backend :** Ruff clean (0 warning), Mypy strict clean (0 issue).
- **Contrôles frontend :** Vitest 39 tests passés (5 suites), build Next.js 16/16 routes générées sans erreur.
- **Migrations base de données :** Migrations Alembic 0014 et 0015 appliquées avec succès sur PostgreSQL.

---

## 4. Décision de Clôture de Phase R4

Tous les critères d'acceptation du Gate R4.12 et de l'ensemble de la Phase R4 sont **entièrement validés sans aucune dérogation, omission ni dette masquée**.  
Le statut de qualification de la Phase R4 est déclaré **QUALIFIED**.  
Le tag de jalon **`mi-r4-qualified`** est prêt à être apposé.
