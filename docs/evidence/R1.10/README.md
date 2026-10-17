# Preuve de qualification R1.10 — Géographie et résolution spatiale

**Date :** 2026-10-15  
**Tâche :** R1.10 — Requalifier géographie et résolution  
**Statut :** **DONE** (Référentiel 23 régions, manifestes et empreintes concordants, non-assignation aveugle prouvée, validité spatiale 100%)  

---

## 1. Contexte et objectifs de la qualification

Le référentiel géographique de Ketrika standardise les niveaux administratifs de Madagascar pour la localisation de toutes les observations de marché (prix, production, stocks, flux, météo).
Selon les exigences de la tâche **R1.10** et les règles non négociables d'**AGENTS.md** :
1. **Dénombrement officiel et source authentique :**
   - Source authentique : OCHA Madagascar COD-AB (`ocha_codab_mdg`), Foiben-Taosarintanin'i Madagasikara (FTM), BNGRC.
   - Standard pivot : **23 régions administratives officielles** (Loi n° 2021-010 portant scission de Vatovavy et Fitovinany).
   - Les nombres par niveau sont validés contre la source et scellés dans un manifeste machine `geo/manifest.json`.
2. **Traçabilité des divergences historiques :**
   - 22 régions (période 2004–2021) : résolution de `Vatovavy-Fitovinany` vers `MDG23` avec confiance 0.85.
   - 23 régions (2021–courant) : référentiel pivot officiel (MDG11 à MDG72).
   - 24 régions (2024, création récente d'Ambatosoa sans séries historiques propres) : résolution vers `MDG32` (Analanjirofo).
3. **Principe de non-assignation aveugle (AGENTS §8.10) :**
   - **Interdiction formelle** d'attribuer un marché manquant ou ambigu à la région de la capitale (`MDG1101`) ou à une région par défaut.
   - Toute entrée non reconnue retourne strictement `None` et produit une issue documentée (`unresolved_location_needs_review`).
4. **Validité géométrique spatiale :**
   - 100% des coordonnées et polygones se trouvent strictement dans la boîte englobante de Madagascar (Latitude [-26.0, -11.0], Longitude [43.0, 51.5]).

---

## 2. Implémentation technique

- **Manifeste géographique :** `geo/manifest.json` recensant chaque couche GeoJSON, version (`2024.1`), compte de features et hash SHA-256 réel.
- **Chargeur et vérificateur :** `backend/src/ketrika/core/geo.py` avec :
  - `load_geo_manifest()`
  - `validate_geo()` renforçant le contrôle de concordance manifeste/fichiers et la validation des coordonnées spatiales.
  - `resolve_location()` garantissant l'absence de repli par défaut erroné.

---

## 3. Résultats des tests et métriques de validation

Exécution dans le conteneur Docker `ketrika-backend:dev` :

```bash
docker run --rm -v /home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep:/workspace -w /workspace/backend ketrika-backend:dev uv run pytest -v tests/unit/test_geo.py
```

### Résultats d'exécution (16/16 tests passés) :
1. `test_validate_geo_has_no_errors` : **PASSED** (validation complète sans anomalie).
2. `test_admin0_geojson_valid` : **PASSED** (contour national `MDG`, polygone valide).
3. `test_admin1_geojson_has_23_official_regions` : **PASSED** (exactement 23 régions `MDG11`–`MDG72`, présence explicite de `MDG23` et `MDG24`).
4. `test_admin2_geojson_sample_districts` : **PASSED** (districts clés `MDG1101`, `MDG1201`, `MDG3101`).
5. `test_admin3_geojson_sample_communes` : **PASSED** (commune urbaine `MDG110101`).
6. `test_load_geographic_entities_admin1` : **PASSED** (23 entités typées `GeographicEntity` chargées avec coordonnées valides).
7. `test_load_admin_geojson_invalid_level_raises` : **PASSED** (levée de `FileNotFoundError` sur niveau invalide).
8. `test_all_23_official_regions_resolve` : **PASSED** (100% des 23 régions résolues avec confiance 1.0).
9. `test_resolve_location_fixture_locations` : **PASSED** (résolution exacte des toponymes des golden sets : Anosibe, Bazar Be, Asabotsy, etc.).
10. `test_resolve_location_edge_cases_and_normalization` : **PASSED** (normalisation apostrophes, tirets, P-codes directs).
11. `test_load_crop_calendar_structure_and_sources` : **PASSED** (calendrier cultural vérifié).
12. `test_geo_manifest_concordance` : **PASSED** (manifeste conforme, comptes et empreintes sha256 validés).
13. `test_unresolved_location_never_falls_back_to_mdg1101_or_default_region` : **PASSED** (refus systématique d'assignation aveugle sur toponymes inconnus).
14. `test_geographic_divergences_traceability` : **PASSED** (traçabilité des 22, 23 et 24 régions).
15. `test_all_features_within_madagascar_bounding_box` : **PASSED** (100% des polygones dans la boîte englobante nationale).
16. `test_geo_error_handling_and_corrupt_files` : **PASSED** (gestion robuste des formats corrompus et fichiers manquants).

### Couverture du code :
- Fichier : `backend/src/ketrika/core/geo.py`
- Statements : 210
- Miss : 22
- **Couverture de code : 90 %** (largement supérieure au seuil normatif de 80 %).

### Contrôles de style et de types :
- `ruff check` : 0 erreur.
- `mypy` : 0 erreur (type checking strict).

---

## 4. Statut et suite

- **Statut R1.10 :** **DONE**.
- **Prochaine tâche éligible du plan R :** **R1.11 — Qualifier NASA POWER** (`connectors/nasa_power.py`).
