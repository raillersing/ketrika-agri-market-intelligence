# ecmwf_open : ECMWF Open Data Numerical Weather Predictions

> Audit indépendant2026-10-25 : registre `active`, SQL `absent`. Pas de réception live actuelle déduite de la présence du code. Les dates/HTTP/droits/annotations ci-dessous sont des descriptions historiques, non revérifiées par cet audit. Réception à suivre dans [la matrice](../audits/2026-10-25/TASK_CAPABILITY_MATRIX.md) et le [plan correctif](../audits/2026-10-25/CORRECTIVE_EXECUTION_PLAN.md).

- **Propriétaire / licence / attribution :** Centre Européen pour les Prévisions Météorologiques à Moyen Terme (ECMWF). Licence : Creative Commons Attribution 4.0 International (CC-BY 4.0). Attribution obligatoire : « European Centre for Medium-Range Weather Forecasts (ECMWF) ».
- **Famille de source (`source_family`) :** `international_public` (organisation météorologique intergouvernementale).
- **URL vérifiées (date, code HTTP) :**
  - https://data.ecmwf.int (2026-10-10, HTTP 200, verified: true).
- **robots.txt :** `User-agent: * Allow: /`
- **CGU & Qualification légale (C1 / R1.1) :** Données ouvertes ouvertes sous licence CC-BY 4.0, sans restriction commerciale, sous respect de la citation. `pii_class: none`.
- **Format(s) et structure :** Prévisions météorologiques numériques globales (GRIB2 / NetCDF / JSON), horizons 24h à 168h (précipitations totales cumulées `tp`, températures à 2m `2t`).
- **Cadences distinctes (R1.1) :**
  - Collecte technique (`collection_cadence`) : `daily`
  - Observation sous-jacente (`observation_cadence`) : `daily`
  - Publication éditeur (`publication_cadence`) : `daily`
- **Couverture :** Grille globale découpée sur la boîte englobante de Madagascar ([43.0, -25.8, 50.8, -11.8]).
- **Pièges connus :** Stockage d'émissions prévues (`value_kind: projected`) archivables sans écrasement dans `obs.weather_forecast` ; ne jamais présenter une météo prévue comme une observation physique passée (`observed`).
- **Stratégie d'extraction :** Connecteur `EcmwfOpenConnector` (`ketrika.connectors.ecmwf_open`).
- **Mapping vers les tables cibles :** `obs.weather_forecast`.
