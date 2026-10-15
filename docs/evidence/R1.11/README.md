# Preuve de qualification R1.11 — NASA POWER

**Date :** 2026-10-15  
**Tâche :** R1.11 — Qualifier NASA POWER et ses révisions  
**Statut :** **DONE** (Logiciel, garde-fous PolicyStop, cohérence physique stricte, filtrage sentinelles, résolution géographique, rejeu Bronze offline) / **BLOCKED** pour la collecte live réseau (B-R010, `robots.txt Disallow: /api/`)  

---

## 1. Contexte et objectifs de la qualification

Le connecteur **NASA POWER** (`nasa_power`) ingère les observations agroclimatologiques quotidiennes (MERRA-2 / GEOS) pour les centroïdes de districts et cellules de grille de Madagascar :
- Précipitations quotidiennes (`PRECTOTCORR` -> `precip_mm`)
- Températures maximales et minimales à 2 m (`T2M_MAX` -> `t2m_max_c`, `T2M_MIN` -> `t2m_min_c`)
- Humidité relative à 2 m (`RH2M` -> `rh2m_pct`)

Selon les directives de la tâche **R1.11**, d'`AGENTS.md` (§8.1, §8.10) et de `SPECS.md` :
1. **Garde-fou strict sur la source désactivée (B-R010) :**
   - Directive officielle `robots.txt` interdisant `/api/` sur `power.larc.nasa.gov` (incident B-R010).
   - Levée immédiate de `PolicyStop` si tentative d'appel réseau live alors que `status: disabled` dans `registry/sources.yaml`. Interdiction absolue de contournement.
2. **Rejouabilité Bronze 100% offline :**
   - Support complet du mode `ctx.offline=True` chargeant la fixture authentique `nasa_power_point_sample.json` dans le `BronzeStore`.
3. **Paramètres de requête explicites (A14) :**
   - Requête paramétrée avec dates de début et fin explicites (`start`, `end`), `community=AG`, `parameters=PRECTOTCORR,T2M_MAX,T2M_MIN,RH2M`, `time-standard=UTC`.
   - Évite formellement l'anomalie A14 (« A14 : POWER sans période explicite »).
4. **Référence temporelle UTC :**
   - Référence temporelle `time-standard=UTC` documentée et consignée dans `evidence`. Interdiction d'assimiler le temps solaire local (LST) ou UTC au fuseau horaire applicatif `Indian/Antananarivo` (UTC+3) sans conversion explicite.
5. **Déduplication par cellule native de grille :**
   - Déduplication selon la résolution native 0.5° x 0.5° (`hints["grid_cell"]`) avec préservation du lien vers les districts et zones associées.
6. **Contrôles de cohérence physique et filtrage strict des sentinelles :**
   - Sentinelles `-999.0` (données manquantes de la NASA) strictement filtrées et ignorées (**jamais converties en 0.0**).
   - Cohérence thermique : `t2m_min_c <= t2m_max_c`. En cas d'inversion (`Tmin > Tmax`), émission d'une issue `physical_coherence_error` et rejet des températures invalides.
   - Non-négativité des précipitations : `precip_mm >= 0.0`. En cas de valeur négative, issue `physical_coherence_error`.
   - Humidité relative : `0.0 <= rh2m_pct <= 100.0`. En cas de dépassement, issue `physical_coherence_error`.
   - Plage réaliste de température à Madagascar : `-15.0 <= temp <= 55.0` °C.
7. **Suppression définitive du fallback aveugle vers MDG1101 :**
   - Conforme à R1.10 et AGENTS §8.10 : si un point ne peut être résolu vers un district de Madagascar (point en mer, hors limites lat [-26, -11] / lon [43, 51.5]), émission d'une issue `unresolved_location_needs_review` et **aucun enregistrement créé**.
8. **Traçabilité prédictive :**
   - Consignation explicite de `is_forecast_or_estimated = False` dans `evidence` : POWER est une réanalyse climatique rétrospective, jamais une prévision météorologique.

---

## 2. Implémentation technique

- **Connecteur :** `backend/src/ketrika/connectors/nasa_power.py` (version `1.1.0`).
- **Tests unitaires et de cohérence :** `backend/tests/unit/test_nasa_power.py`.
- **Fiche source mise à jour :** `docs/sources/nasa_power.md`.
- **Modèle de données cible :** `obs.weather_observation` (`WeatherRecord` / `WeatherObservation`).

---

## 3. Résultats des tests et métriques de validation

Exécution dans le conteneur Docker `ketrika-backend:dev` :

```bash
docker run --rm -v /home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep:/workspace -w /workspace/backend ketrika-backend:dev uv run pytest -v tests/unit/test_nasa_power.py --cov=ketrika.connectors.nasa_power --cov-report=term-missing
```

### Résultats d'exécution (10/10 tests passés) :

1. `test_nasa_power_parse_fixture` : **PASSED** (36 enregistrements extraits sur les 9 dates valides, filtrage strict de la date sentinelle `2024-01-06`, aucun zéro inventé, traçabilité `evidence` complète).
2. `test_nasa_power_physical_coherence` : **PASSED** (vérification de `t2m_min <= t2m_max`, `precip >= 0.0`, `0 <= rh <= 100` sur toutes les dates observées).
3. `test_nasa_power_physical_coherence_violations` : **PASSED** (détection et rejet des violations injectées : `precip < 0`, `Tmin > Tmax`, `RH > 100`, émission des issues `physical_coherence_error`).
4. `test_nasa_power_unresolved_location_rejection` : **PASSED** (point océanique hors Madagascar sans P-code -> émission de `unresolved_location_needs_review`, 0 enregistrement créé, aucun fallback aveugle vers MDG1101).
5. `test_nasa_power_discover` : **PASSED** (découverte avec paramètres explicites `start`, `end`, `time-standard=UTC`, `parameters=PRECTOTCORR,T2M_MAX,T2M_MIN,RH2M`, `community=AG`, `grid_cell`).
6. `test_nasa_power_strict_policy_disabled_guard` : **PASSED** (levée immédiate de `PolicyStop` en mode réseau lorsque `status: disabled` dans `registry/sources.yaml`).
7. `test_nasa_power_offline_reproducibility` : **PASSED** (chargement offline déterministe dans le `BronzeStore` avec hachage sha256).
8. `test_nasa_power_discover_override_urls` : **PASSED** (respect des URLs personnalisées de test dans les métadonnées).
9. `test_nasa_power_parse_coordinates_resolution` : **PASSED** (résolution par centroïde de district dans Madagascar lorsque le P-code n'est pas spécifié dans properties).
10. `test_nasa_power_parse_error_branches` : **PASSED** (gestion propre des JSON corrompus, types inattendus, et blocs `parameter` manquants).

### Couverture du code :
- Fichier : `backend/src/ketrika/connectors/nasa_power.py`
- Statements : **167**
- Couverture : **93 %** (dépasse largement le seuil normatif de 80 %).

### Tests de non-régression météo :
- Exécution de `tests/unit/test_weather_provenance.py` et `tests/unit/test_weather_migration.py` :
  - **19/19 tests passés** (cycle d'ingestion avec supersession sans écrasement, précision NUMERIC(10,3), liaison aux cellules sources vérifiée).

---

## 4. Statut de qualification

- **Logiciel connecteur (`NasaPowerConnector` v1.1.0) :** **QUALIFIED**
- **Validation physique et sentinelles :** **QUALIFIED**
- **Provenance Bronze & Rejouabilité offline :** **QUALIFIED**
- **Résolution géographique et concordance :** **QUALIFIED**
- **Collecte réseau en direct :** **BLOCKED** (`status: disabled`, incident B-R010, robots.txt Disallow /api/, respect absolu d'AGENTS §8.1).
