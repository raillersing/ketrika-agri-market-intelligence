# chirps : CHIRPS – Climate Hazards Center InfraRed Precipitation with Station Data

- **Propriétaire / licence / attribution :** Climate Hazards Center, University of California, Santa Barbara (UCSB). Licence : Public Domain / CC0. Attribution : "Climate Hazards Center, UC Santa Barbara".
- **URL vérifiées (date, code HTTP) :**
  - https://www.chc.ucsb.edu/data/chirps (2026-10-06, HTTP 200).
- **robots.txt (extrait pertinent, date) :** `User-agent: * Allow: /`
- **CGU (URL, sha256, résumé des clauses de réutilisation) :** https://www.chc.ucsb.edu/data/terms. Données ouvertes mondiales à vocation de surveillance des sécheresses et sécurité alimentaire.
- **Format(s) et structure (avec exemples réels, pages, colonnes) :** GeoTIFF rasters (résolution 0.05° soit ~5km) et NetCDF mensuels et décadaires.
- **Cadence constatée (dates des 6 dernières publications) :** Mensuelle.
- **Couverture :** Territoire complet de Madagascar (latitudes 11°S à 26°S, longitudes 43°E à 51°E).
- **Pièges connus :** Données matricielles lourdes nécessitant un découpage zonal ou extraction ponctuelle (`rasterio` / zonal statistics) selon les limites administratives `ocha_codab_mdg`.
- **Stratégie d'extraction :** Déterministe (Rasterio / Xarray / GDAL).
- **Mapping vers les tables cibles :** `obs.weather` (cumuls pluviométriques par commune / région).
- **Échantillons :** `backend/tests/fixtures/chirps/chirps_sample.txt`.
- **Statut et incidents :** Prévu (Phase 9 - SHOULD), aucun incident.
