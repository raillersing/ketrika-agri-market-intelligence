# ocha_codab_mdg : OCHA Madagascar - Subnational Administrative Boundaries (COD-AB)

> Audit indépendant2026-10-25 : registre `active`, SQL `active`. Pas de réception live actuelle déduite de la présence du code. Les dates/HTTP/droits/annotations ci-dessous sont des descriptions historiques, non revérifiées par cet audit. Réception à suivre dans [la matrice](../audits/2026-10-25/TASK_CAPABILITY_MATRIX.md) et le [plan correctif](../audits/2026-10-25/CORRECTIVE_EXECUTION_PLAN.md).

- **Propriétaire / licence / attribution :** OCHA Madagascar / BNGRC / FTM. Licence : CC BY-IGO. Attribution obligatoire : "United Nations Office for the Coordination of Humanitarian Affairs (OCHA)".
- **Famille de source (`source_family`) :** `un_ocha` (United Nations Office for the Coordination of Humanitarian Affairs).
- **URL vérifiées (date, code HTTP) :**
  - https://data.humdata.org/dataset/cod-ab-mdg (historique 2026-10-06 HTTP 200, actuellement `verified: false` en raison du 403 Cloudflare sur HDX en direct).
- **robots.txt (extrait pertinent, date) :** `User-agent: * Allow: /` (historique vérifié 2026-10-06).
- **CGU & Qualification légale (C1 / R1.1) :** https://data.humdata.org/terms. Données ouvertes humanitaires du domaine public onusien/national BNGRC/FTM utilisables à des fins analytiques et cartographiques avec attribution. Aucune PII directe (`pii_class: none`), pas d'authentification requise.
- **Format(s) et structure (avec exemples réels, pages, colonnes) :** GeoJSON / ESRI Shapefile / Geopackage. Niveaux administratifs ADM0 (Pays), ADM1 (Régions, 23), ADM2 (Districts, 119), ADM3 (Communes, ~1695). Colonnes : `ADM0_PCODE`, `ADM1_PCODE`, `ADM1_FR`, `ADM2_PCODE`, `ADM2_FR`, `ADM3_PCODE`, `ADM3_FR`, `geometry`.
- **Cadences distinctes (R1.1) :**
  - Collecte technique (`collection_cadence`) : `static`
  - Observation sous-jacente (`observation_cadence`) : `static`
  - Publication éditeur (`publication_cadence`) : `static`
- **Cadence constatée (dates des 6 dernières publications) :** Statique / semi-statique (mises à jour lors des redécoupages administratifs BNGRC/FTM).
- **Couverture :** Ensemble du territoire malagasy, géométrie vectorielle de référence.
- **Pièges connus :** Évolution du nombre de régions (passage de 22 à 23 régions avec la création du Vatovavy/Fitovinany), orthographes alternatives des noms de communes, codes P-Code à préserver en minuscules/majuscules strictes.
- **Stratégie d'extraction :** Déterministe (GeoPandas / GDAL / Shapely).
- **Mapping vers les tables cibles :** `ref.geographies` (niveaux admin0 à admin3).
- **Échantillons :** `backend/tests/fixtures/ocha_codab_mdg/admin_sample.geojson`.
- **Statut et incidents :** Actif, aucun incident.
