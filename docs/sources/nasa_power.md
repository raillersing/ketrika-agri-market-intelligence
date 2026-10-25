# nasa_power : NASA POWER Agroclimatology Daily Point API

> Audit indépendant2026-10-25 : registre `disabled`, SQL `disabled`. Source arrêtée : aucune relance, archives autorisées seulement. Les dates/HTTP/droits/annotations ci-dessous sont des descriptions historiques, non revérifiées par cet audit. Réception à suivre dans [la matrice](../audits/2026-10-25/TASK_CAPABILITY_MATRIX.md) et le [plan correctif](../audits/2026-10-25/CORRECTIVE_EXECUTION_PLAN.md).

> Requalification R1.11 (2026-10-15) : source déclarée `disabled` dans `registry/sources.yaml` en raison de la directive `Disallow: /api/` dans le `robots.txt` officiel de `power.larc.nasa.gov` (incident B-R010, AGENTS §8.1).
> Tout accès réseau live non exempté lève immédiatement un `PolicyStop`.
> Le connecteur `NasaPowerConnector` v1.1.0 est entièrement qualifié en mode offline rejouable sur le BronzeStore, avec contrôles stricts de cohérence physique, filtrage des sentinelles sans conversion en zéro, et non-imputation géographique aveugle.
> POWER est une météorologie de grille/modélisée (réanalyse MERRA-2/GEOS), pas une observation de station locale ni une prévision météo ([méthodologie officielle](https://power.larc.nasa.gov/docs/methodology/), consultée le 2026-10-09).

- **Propriétaire / licence / attribution :** NASA Langley Research Center. Licence : Public Domain (US Government Open Data). Attribution : "NASA POWER Project, NASA Langley Research Center".
- **Famille de source (`source_family`) :** `nasa` (National Aeronautics and Space Administration).
- **Statut opérationnel :**
  - Collecte live réseau : `BLOCKED` / `disabled` (incident B-R010, `robots.txt Disallow: /api/`, AGENTS §8.1 interdit tout contournement).
  - Logiciel connecteur, validation physique et rejeu Bronze : `QUALIFIED` (v1.1.0, 10 tests unitaires verts, couverture 93 %).
- **URL vérifiées (date, code HTTP) :**
  - https://power.larc.nasa.gov/api/temporal/daily/point (`verified: false` en raison de la directive robots.txt interdisant `/api/` B-R010).
- **robots.txt (extrait pertinent, date) :** `Disallow: /api/` avec exception `/api/pages/` (B-R010, vérifié 2026-10-09).
- **CGU & Qualification légale (C1 / R1.1) :** https://power.larc.nasa.gov/docs/services/api/. Accès public au domaine public US mais restreint par robots.txt pour les scripts automatiques non exemptés. Aucune PII directe (`pii_class: none`).
- **Format(s) et structure :** API REST GeoJSON / JSON.
  - Paramètres de requête : communauté `AG` (agroclimatology), paramètres `PRECTOTCORR,T2M_MAX,T2M_MIN,RH2M`, `longitude`, `latitude`, `start`, `end`, `time-standard=UTC`, `format=JSON`.
  - Structure de réponse : dictionnaire horodaté `properties.parameter.<PARAM>.<YYYYMMDD>`.
- **Référence temporelle (R1.11) :**
  - Référence fournisseur : `UTC` (`time-standard=UTC`).
  - Règle métier : Ne jamais assimiler le temps solaire local (LST) ni UTC au fuseau horaire applicatif `Indian/Antananarivo` (UTC+3) sans conversion explicite.
- **Cadences distinctes (R1.1) :**
  - Collecte technique (`collection_cadence`) : `daily`
  - Observation sous-jacente (`observation_cadence`) : `daily`
  - Publication éditeur (`publication_cadence`) : `daily`
- **Mapping des variables :**
  - `PRECTOTCORR` → `precip_mm` (précipitations quotidiennes en millimètres) ;
  - `T2M_MAX` → `t2m_max_c` (température maximale quotidienne à 2m en °C) ;
  - `T2M_MIN` → `t2m_min_c` (température minimale quotidienne à 2m en °C) ;
  - `RH2M` → `rh2m_pct` (humidité relative à 2m en %).
- **Règles de cohérence physique et sentinelles (R1.11) :**
  - Sentinelles `-999.0` (données manquantes de la NASA) strictement filtrées et ignorées (**jamais converties en 0.0**) ;
  - Cohérence thermique : `t2m_min_c <= t2m_max_c` ; en cas d'inversion, issue `physical_coherence_error` et valeurs thermiques rejetées ;
  - Non-négativité des précipitations : `precip_mm >= 0.0` ; en cas de valeur négative, issue `physical_coherence_error` ;
  - Bornes d'humidité relative : `0.0 <= rh2m_pct <= 100.0` ;
  - Plage réaliste de température à Madagascar : `-15.0 <= temp <= 55.0` °C.
- **Résolution géographique et déduplication de grille (R1.11 / R1.10) :**
  - Déduplication native par cellule de grille 0.5° x 0.5° (`hints["grid_cell"]`) avec traçabilité vers les zones associées.
  - Refus d'imputation aveugle : aucun point non résolu n'est assigné arbitrairement à `MDG1101` ; émission obligatoire d'une issue `unresolved_location_needs_review` si coordonnées hors Madagascar ou district introuvable.
- **Nature des données et traçabilité prédictive :**
  - `is_forecast_or_estimated = False` : données issues de modèles de réanalyse climatique historique, ne doivent jamais être présentées comme des prévisions météorologiques en aval.
  - `value_kind = "observed"` (réanalyse climatique de grille).
- **Mapping vers la table cible :** `obs.weather_observation` avec contrainte unique `(provider, location_id, date, variable)`.
- **Fixtures et tests :**
  - Fixture authentique : `backend/tests/fixtures/nasa_power/nasa_power_point_sample.json`.
  - Tests unitaires et de cohérence physique : `backend/tests/unit/test_nasa_power.py` (10 tests, couverture 93 %).
  - Tests de cycle de vie et migration : `backend/tests/unit/test_weather_provenance.py` et `test_weather_migration.py` (19 tests).
