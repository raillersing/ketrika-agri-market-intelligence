# wfp_hdx_mdg : WFP Food Prices – Madagascar (HDX)

> Requalification R0.4, 2026-10-09 : le catalogue a répondu 403 via le lecteur web (B-R009),
> acquisition arrêtée sans contournement. Les anciennes fixtures/attendus sont `unverified`
> dans corpus-manifest.json : les affirmations de vérification ci-dessous sont historiques,
> pas des preuves actuelles d'acquisition ni de performance sur prix réels. H5 non réalisé.
> R1.7 doit établir disponibilité, droits et corpus authentique avant qualification live.

- **Propriétaire / licence / attribution :** World Food Programme (WFP) / OCHA HDX. Licence : CC BY-IGO. Attribution obligatoire : "World Food Programme (WFP)".
- **URL vérifiées (date, code HTTP) :**
  - https://data.humdata.org/dataset/wfp-food-prices-for-madagascar (2026-10-06, HTTP 200).
- **robots.txt (extrait pertinent, date) :** `User-agent: * Allow: /` (vérifié 2026-10-06).
- **CGU (URL, sha256, résumé des clauses de réutilisation) :** https://data.humdata.org/terms. Utilisation libre avec attribution et mention de la source.
- **Format(s) et structure (avec exemples réels, pages, colonnes) :** CSV structuré. Colonnes : `date`, `admin1`, `admin2`, `market`, `latitude`, `longitude`, `category`, `commodity`, `unit`, `priceflag`, `pricetype`, `currency`, `price`, `usdprice`.
- **Cadence constatée (dates des 6 dernières publications) :** Mensuelle. Données consolidées par le WFP VAM.
- **Couverture :** Madagascar, principaux marchés urbains et ruraux. Produits : riz (local et importé), maïs, manioc, légumineuses, huile, sucre.
- **Pièges connus :** Variations des libellés de marchés selon les années, flags de prix (actual vs forecast), conversion monétaire MGA vs USD.
- **Stratégie d'extraction :** Déterministe (`WfpHdxMdgConnector`, parsing CSV avec élimination de la ligne HXL `#`).
- **Mapping vers les tables cibles :** `obs.price_observation` avec rattachement via `ref.location` (marchés en `admin_level = 9`, districts, régions) et `ref.product` (`RICE_WHITE_LOCAL`, `RICE_WHITE_IMPORTED`, `MAIZE_GRAIN`, `CASSAVA_FRESH`, `BEANS_DRY`, `VEG_OIL`, `SUGAR`).
- **Échantillons et golden set :**
  - Fixture : `backend/tests/fixtures/wfp_hdx_mdg/wfp_food_prices_mdg_sample.csv` (35 observations).
  - Golden set : `backend/tests/golden/wfp_hdx_mdg/wfp_sample.expected.json` (35 valeurs vérifiées manuellement).
  - Tests unitaires et d'intégration : `backend/tests/unit/test_wfp_hdx_mdg.py`, `backend/tests/integration/test_wfp_hdx_mdg.py`.
- **Statut et incidents :** `active`, aucun incident. Rejouabilité Bronze et checks DQ validés (CC1–CC6).
