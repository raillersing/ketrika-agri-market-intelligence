# wfp_hdx_mdg : WFP Food Prices – Madagascar (HDX)

- **Propriétaire / licence / attribution :** World Food Programme (WFP) / OCHA HDX. Licence : CC BY-IGO. Attribution obligatoire : "World Food Programme (WFP)".
- **URL vérifiées (date, code HTTP) :**
  - https://data.humdata.org/dataset/wfp-food-prices-for-madagascar (2026-10-06, HTTP 200).
- **robots.txt (extrait pertinent, date) :** `User-agent: * Allow: /` (vérifié 2026-10-06).
- **CGU (URL, sha256, résumé des clauses de réutilisation) :** https://data.humdata.org/terms. Utilisation libre avec attribution et mention de la source.
- **Format(s) et structure (avec exemples réels, pages, colonnes) :** CSV structuré. Colonnes : `date`, `admin1`, `admin2`, `market`, `latitude`, `longitude`, `category`, `commodity`, `unit`, `priceflag`, `pricetype`, `currency`, `price`, `usdprice`.
- **Cadence constatée (dates des 6 dernières publications) :** Mensuelle. Données consolidées par le WFP VAM.
- **Couverture :** Madagascar, principaux marchés urbains et ruraux. Produits : riz (local et importé), maïs, manioc, légumineuses, huile, sucre.
- **Pièges connus :** Variations des libellés de marchés selon les années, flags de prix (actual vs forecast), conversion monétaire MGA vs USD.
- **Stratégie d'extraction :** Déterministe (Polars / DuckDB / pandas CSV reader).
- **Mapping vers les tables cibles :** `obs.prices` avec rattachement via `ref.market` et `ref.products`.
- **Échantillons :** `backend/tests/fixtures/wfp_hdx_mdg/wfp_food_prices_mdg_sample.csv`.
- **Statut et incidents :** Actif, aucun incident.
