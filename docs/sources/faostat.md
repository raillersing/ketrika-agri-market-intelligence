# faostat : FAOSTAT – Food and Agriculture Organization Statistics (Madagascar)

- **Propriétaire / licence / attribution :** Food and Agriculture Organization of the United Nations (FAO). Licence : CC BY-NC-SA 3.0 IGO. Attribution : "FAOSTAT, Food and Agriculture Organization of the United Nations".
- **URL vérifiées (date, code HTTP) :**
  - https://www.fao.org/faostat/en/#data (2026-10-06, HTTP 200).
  - https://fenixservices.fao.org/faostat/api/v1/en/data/QCL (2026-10-06, HTTP 200).
- **robots.txt (extrait pertinent, date) :** `User-agent: * Allow: /` pour l'API et les données publiques.
- **CGU (URL, sha256, résumé des clauses de réutilisation) :** https://www.fao.org/contact-us/terms/en/. Données ouvertes pour usage analytique et non commercial direct sans altération de l'intégrité statistique.
- **Format(s) et structure (avec exemples réels, pages, colonnes) :** API REST JSON et CSV téléchargeables. Domaines : QCL (Crops and livestock products), FBS (Food Balance Sheets), TM (Detailed trade matrix). Champs : `AreaCode` (129 pour Madagascar), `ItemCode`, `ElementCode` (5510 Production, 5610 Importations), `Year`, `Unit`, `Value`, `Flag`.
- **Cadence constatée (dates des 6 dernières publications) :** Annuelle avec révisions consolidées.
- **Couverture :** Séries longues de bilans agricoles, productions et importations pour Madagascar.
- **Pièges connus :** Décalage temporel (T-1 ou T-2 pour les consolidations finales), codes d'items FAOSTAT à mapper explicitement vers notre taxonomie via `ref.products`.
- **Stratégie d'extraction :** Déterministe (Client HTTP / API JSON FAOSTAT).
- **Mapping vers les tables cibles :** `obs.production` et `obs.trade`.
- **Échantillons :** `backend/tests/fixtures/faostat/faostat_qcl_sample.json`.
- **Statut et incidents :** Actif, aucun incident.
