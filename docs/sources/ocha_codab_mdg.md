# ocha_codab_mdg : OCHA Madagascar - Subnational Administrative Boundaries (COD-AB)

- **Propriétaire / licence / attribution :** OCHA Madagascar / BNGRC / FTM. Licence : CC BY-IGO. Attribution obligatoire : "United Nations Office for the Coordination of Humanitarian Affairs (OCHA)".
- **URL vérifiées (date, code HTTP) :**
  - https://data.humdata.org/dataset/cod-ab-mdg (2026-10-06, HTTP 200).
- **robots.txt (extrait pertinent, date) :** `User-agent: * Allow: /` (vérifié 2026-10-06).
- **CGU (URL, sha256, résumé des clauses de réutilisation) :** https://data.humdata.org/terms. Données ouvertes humanitaires utilisables à des fins analytiques et de recherche sous réserve d'attribution.
- **Format(s) et structure (avec exemples réels, pages, colonnes) :** GeoJSON / ESRI Shapefile / Geopackage. Niveaux administratifs ADM0 (Pays), ADM1 (Régions, 23), ADM2 (Districts, 119), ADM3 (Communes, ~1695). Colonnes : `ADM0_PCODE`, `ADM1_PCODE`, `ADM1_FR`, `ADM2_PCODE`, `ADM2_FR`, `ADM3_PCODE`, `ADM3_FR`, `geometry`.
- **Cadence constatée (dates des 6 dernières publications) :** Statique / semi-statique (mises à jour lors des redécoupages administratifs BNGRC/FTM).
- **Couverture :** Ensemble du territoire malagasy, géométrie vectorielle de référence.
- **Pièges connus :** Évolution du nombre de régions (passage de 22 à 23 régions avec la création du Vatovavy/Fitovinany), orthographes alternatives des noms de communes, codes P-Code à préserver en minuscules/majuscules strictes.
- **Stratégie d'extraction :** Déterministe (GeoPandas / GDAL / Shapely).
- **Mapping vers les tables cibles :** `ref.geographies` (niveaux admin0 à admin3).
- **Échantillons :** `backend/tests/fixtures/ocha_codab_mdg/admin_sample.geojson`.
- **Statut et incidents :** Actif, aucun incident.
