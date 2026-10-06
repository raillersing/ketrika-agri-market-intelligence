# douanes_stats : Douanes Malagasy – Statistiques du Commerce Extérieur

- **Propriétaire / licence / attribution :** Direction Générale des Douanes de Madagascar (DGD). Licence : Données publiques officielles gouvernementales. Attribution : "Direction Générale des Douanes, Madagascar".
- **URL vérifiées (date, code HTTP) :**
  - https://www.douanes.gov.mg (2026-10-06, HTTP 200).
- **robots.txt (extrait pertinent, date) :** `User-agent: * Allow: /`
- **CGU (URL, sha256, résumé des clauses de réutilisation) :** https://www.douanes.gov.mg/mentions-legales. Publications statistiques officielles du commerce extérieur malagasy.
- **Format(s) et structure (avec exemples réels, pages, colonnes) :** Fichiers mensuels CSV / Excel des flux déclarés dans SYDONIAWorld. Colonnes : année, mois, code SH (Système Harmonisé à 6 ou 8 chiffres), libellé tarifaire, pays de provenance / destination, poids net (kg/tonnes), valeur CAF (Coût, Assurance, Fret) en Ariary ou devises.
- **Cadence constatée (dates des 6 dernières publications) :** Mensuelle avec consolidations trimestrielles.
- **Couverture :** Ensemble des bureaux des douanes (Toamasina, Mahajanga, Ivato, Antsiranana, etc.).
- **Pièges connus :** Codes SH à 8 chiffres spécifiques à Madagascar dont seuls les 6 premiers correspondent à la nomenclature internationale du SH ; révisions rétroactives lors des apurements de déclarations douanières.
- **Stratégie d'extraction :** Déterministe (Polars / DuckDB / pandas).
- **Mapping vers les tables cibles :** `obs.trade` rattaché à `ref.products` via les codes SH6.
- **Échantillons :** `backend/tests/fixtures/douanes_stats/douanes_stats_sample.csv`.
- **Statut et incidents :** Actif, aucun incident.
