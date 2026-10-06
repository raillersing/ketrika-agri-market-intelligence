# wb_rtfp_mdg : World Bank Real-Time Food Prices – Madagascar (RTFP)

- **Propriétaire / licence / attribution :** World Bank Data360 / Development Economics Data Group (DECDG). Licence : CC BY 4.0. Attribution : "World Bank Real-Time Food Prices".
- **URL vérifiées (date, code HTTP) :**
  - https://microdata.worldbank.org/index.php/catalog/food-prices (2026-10-06, HTTP 200).
- **robots.txt (extrait pertinent, date) :** `User-agent: * Allow: /` (vérifié 2026-10-06).
- **CGU (URL, sha256, résumé des clauses de réutilisation) :** https://www.worldbank.org/en/about/legal/terms-and-conditions. Libre réutilisation sous licence ouverte CC-BY.
- **Format(s) et structure (avec exemples réels, pages, colonnes) :** CSV / Stata / Parquet. Colonnes typiques : `country`, `country_code`, `adm1_name`, `market_name`, `date`, `commodity`, `unit`, `currency`, `price_observed`, `price_imputed`, `value_kind`.
- **Cadence constatée (dates des 6 dernières publications) :** Mensuelle.
- **Couverture :** Historique étendu (depuis 2007) pour Madagascar. Produits vivriers clés (riz, blé, maïs, manioc).
- **Pièges connus :** Distinction essentielle entre valeurs observées et valeurs imputées (principe non-négociable n°9 d'AGENTS.md). `observed_or_imputed` obligatoire.
- **Stratégie d'extraction :** Déterministe (Polars / DuckDB).
- **Mapping vers les tables cibles :** `obs.prices` avec flag `observed_or_imputed`.
- **Échantillons :** `backend/tests/fixtures/wb_rtfp_mdg/wb_rtfp_mdg_sample.csv`.
- **Statut et incidents :** Actif, aucun incident.
