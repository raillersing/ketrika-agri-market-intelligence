# chirps : CHIRPS – Climate Hazards Center InfraRed Precipitation with Station Data

> Audit indépendant2026-10-25 : registre `planned`, SQL `planned`. Pas de réception live actuelle déduite de la présence du code. Les dates/HTTP/droits/annotations ci-dessous sont des descriptions historiques, non revérifiées par cet audit. Réception à suivre dans [la matrice](../audits/2026-10-25/TASK_CAPABILITY_MATRIX.md) et le [plan correctif](../audits/2026-10-25/CORRECTIVE_EXECUTION_PLAN.md).

- **Propriétaire / licence / attribution :** Climate Hazards Center, University of California, Santa Barbara (UCSB). Licence : Public Domain / CC0. Attribution : "Climate Hazards Center, UC Santa Barbara".
- **Famille de source (`source_family`) :** `chc_ucsb` (Climate Hazards Center, University of California Santa Barbara).
- **URL vérifiées (date, code HTTP) :**
  - https://www.chc.ucsb.edu/data/chirps (2026-10-06, HTTP 200, verified: true).
- **robots.txt (extrait pertinent, date) :** `User-agent: * Allow: /`
- **CGU & Qualification légale (C1 / R1.1) :** https://www.chc.ucsb.edu/data/terms. Données ouvertes mondiales du domaine public à vocation de surveillance des sécheresses et sécurité alimentaire. Aucune PII directe (`pii_class: none`), pas d'authentification requise.
- **Format(s) et structure (avec exemples réels, pages, colonnes) :** GeoTIFF rasters (résolution 0.05° soit ~5km) et NetCDF mensuels et décadaires.
- **Cadences distinctes (R1.1) :**
  - Collecte technique (`collection_cadence`) : `monthly`
  - Observation sous-jacente (`observation_cadence`) : `monthly`
  - Publication éditeur (`publication_cadence`) : `monthly`
- **Cadence constatée (dates des 6 dernières publications) :** Mensuelle.
- **Couverture :** Territoire complet de Madagascar (latitudes 11°S à 26°S, longitudes 43°E à 51°E).
- **Pièges connus :** Données matricielles lourdes nécessitant un découpage zonal ou extraction ponctuelle (`rasterio` / zonal statistics) selon les limites administratives `ocha_codab_mdg`.
- **Stratégie d'extraction :** Déterministe (Rasterio / Xarray / GDAL).
- **Mapping vers les tables cibles :** `obs.weather` (cumuls pluviométriques par commune / région).
- **Échantillons :** `backend/tests/fixtures/chirps/chirps_sample.txt`.
- **Statut et incidents :** Prévu (Phase 9 - SHOULD), aucun incident.
