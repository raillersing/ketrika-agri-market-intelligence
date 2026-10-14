# nasa_power : NASA POWER Agroclimatology Daily Point API

> Requalification R0.4, 2026-10-09 : robots.txt HTTP 200 interdit `/api/` (exception `/api/pages/`).
> Acquisition Docker refusée par PolicyStop avant toute donnée API ; B-R010, aucun contournement.
> La règle `Allow: /` et la couverture « 100 % » ci-dessous sont des affirmations historiques
> non qualifiées actuellement. La fixture est `unverified`, H5 non réalisé ; R1.11 doit résoudre
> légalement l'accès ou spécifier une alternative autorisée, sans appeler l'URL interdite.
> POWER est une météorologie de grille/modelée, pas une observation de station locale
> ([méthodologie officielle](https://power.larc.nasa.gov/docs/methodology/), consultée le 2026-10-09).

- **Propriétaire / licence / attribution :** NASA Langley Research Center. Licence : Public Domain (US Government Open Data). Attribution : "NASA POWER Project, NASA Langley Research Center".
- **Famille de source (`source_family`) :** `nasa` (National Aeronautics and Space Administration).
- **URL vérifiées (date, code HTTP) :**
  - https://power.larc.nasa.gov/api/temporal/daily/point (historique 2026-10-06 HTTP 200, actuellement `verified: false` en raison de la directive robots.txt interdisant `/api/` B-R010).
- **robots.txt (extrait pertinent, date) :** `Disallow: /api/` avec exception `/api/pages/` (B-R010, vérifié 2026-10-09).
- **CGU & Qualification légale (C1 / R1.1) :** https://power.larc.nasa.gov/docs/services/api/. Accès public au domaine public US mais restreint par robots.txt pour les scripts automatiques non exemptés. Statut `degraded` / attente résolution R1.11 sans appel prohibé. Aucune PII directe (`pii_class: none`).
- **Format(s) et structure :** API REST GeoJSON / JSON.
  - Paramètres de requête : communauté `AG` (agroclimatology), paramètres `PRECTOTCORR,T2M_MAX,T2M_MIN,RH2M`, `longitude`, `latitude`, `format=JSON`.
  - Structure de réponse : dictionnaire horodaté `properties.parameter.<PARAM>.<YYYYMMDD>`.
- **Cadences distinctes (R1.1) :**
  - Collecte technique (`collection_cadence`) : `daily`
  - Observation sous-jacente (`observation_cadence`) : `daily`
  - Publication éditeur (`publication_cadence`) : `daily`
- **Mapping des variables :**
  - `PRECTOTCORR` → `precip_mm` (précipitations quotidiennes en millimètres) ;
  - `T2M_MAX` → `t2m_max_c` (température maximale quotidienne à 2m en °C) ;
  - `T2M_MIN` → `t2m_min_c` (température minimale quotidienne à 2m en °C) ;
  - `RH2M` → `rh2m_pct` (humidité relative à 2m en %).
- **Règles de cohérence physique et sentinelles :**
  - Sentinelles `-999.0` (données manquantes de la NASA) strictement filtrées et ignorées (jamais stockées comme valeurs valides) ;
  - Cohérence thermique : `t2m_min_c <= t2m_max_c` ;
  - Non-négativité des précipitations : `precip_mm >= 0.0` ;
  - Borne d'humidité relative : `0.0 <= rh2m_pct <= 100.0`.
- **Cadence constatée :** Quotidienne avec latence de 2 à 3 jours pour les données consolidées.
- **Couverture validée :**
  - 100 % des centroïdes de districts (`admin_level = 2`) de Madagascar couverts.
  - Résolution de `location_id` vers `ref.location` par P-Code de district (ex: `MDG1101`, `MDG1201`, `MDG3101`).
- **Stratégie d'extraction :** Déterministe via client HTTP poli (`NasaPowerConnector`).
- **Mapping vers la table cible :** `obs.weather_observation` avec contrainte unique `(provider, location_id, date, variable)`.
- **Fixtures et tests :**
  - Fixture : `backend/tests/fixtures/nasa_power/nasa_power_point_sample.json`.
  - Tests unitaires et de cohérence physique : `backend/tests/unit/test_nasa_power.py`.
  - Test d'intégration cycle de vie et backfill : `backend/tests/integration/test_nasa_power.py`.
- **Statut :** `active` (validé CC1, CC3–CC6 dans le cadre de T3.4).
