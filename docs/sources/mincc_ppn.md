# mincc_ppn : MinCC – Relevés Prix & Stocks PPN

- **Propriétaire / licence / attribution :** Ministère de l'Industrialisation et du Commerce (MinCC) / Direction de la Régulation du Commerce et de la Consommation (DRCC). Licence : Données publiques officielles gouvernementales. Attribution : "Ministère du Commerce, Madagascar".
- **URL vérifiées (date, code HTTP) :**
  - http://www.commerce.gov.mg (2026-10-06, HTTP 200).
- **robots.txt (extrait pertinent, date) :** `User-agent: * Allow: /`
- **CGU (URL, sha256, résumé des clauses de réutilisation) :** Surveillance légale des marchés et protection du consommateur (PPN vivriers). Accès public et officiel.
- **Format(s) et structure (avec exemples réels, pages, colonnes) :** Communiqués périodiques, fichiers Excel et tableaux récapitulatifs des prix de gros et de détail et stocks disponibles au débarquement et en entrepôts. Produits : Huile de palme/soja (vrac et embouteillée), Sucre blanc/roux, Farine de blé, Riz.
- **Cadence constatée (dates des 6 dernières publications) :** Hebdomadaire ou bimensuelle.
- **Couverture :** Grands centres d'approvisionnement (Antananarivo, Toamasina, Mahajanga, etc.).
- **Pièges connus :** Unités variables (litres vs bouteilles 1L vs fûts, sacs de 50 kg vs kg au détail), données de stocks déclaratives des importateurs.
- **Stratégie d'extraction :** Déterministe pour les tableaux réguliers ; LLM extracteur pour les communiqués textuels ou notes de cadrage.
- **Mapping vers les tables cibles :** `obs.prices` et `obs.stocks`.
- **Échantillons :** `backend/tests/fixtures/mincc_ppn/mincc_ppn_sample.csv`.
- **Statut et incidents :** Actif, aucun incident.
