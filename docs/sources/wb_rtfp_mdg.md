# wb_rtfp_mdg : World Bank Real-Time Food Prices – Madagascar (RTFP)

> **Statut de qualification R1.8 (2026-10-15) :**
> - Connecteur, découverte dynamique, règles de normalisation C3 et tests : **QUALIFIÉ & VALIDÉ (DONE)**.
> - Traçabilité stricte de la dépendance primaire (`source_dependency: wfp_fao`) pour interdire toute double confirmation fallacieuse WFP + RTFP.
> - Exclusion systématique des observations imputées (`is_forecast_or_estimated: true`) de la vérité terrain d'évaluation des modèles prédictifs.
> - Aucun flag inconnu promu en `observed` (routage obligatoire en revue humaine).
> - Résolution géographique stricte : refus d'imputation géographique aveugle si ni marché ni région ne sont précisés.
> - Rejouabilité 100% offline via BronzeStore.

- **Propriétaire / licence / attribution :** World Bank Data360 / Development Economics Data Group (DECDG). Licence : CC BY 4.0. Attribution : "World Bank Real-Time Food Prices".
- **Famille de source (`source_family`) :** `world_bank` (famille Banque Mondiale, strictement isolée de `un_wfp` pour prévenir toute double comptabilisation de prix imputés selon C3).
- **Dépendance primaire (`source_dependency`) :** `wfp_fao` (les séries RTFP de la Banque Mondiale agrègent et imputent des relevés issus principalement du PAM et de la FAO ; une concordance WFP/RTFP ne constitue donc pas une validation indépendante).
- **URL vérifiées (date, code HTTP) :**
  - https://microdata.worldbank.org/index.php/catalog/food-prices (2026-10-06, HTTP 200, verified: true).
  - https://microdata.worldbank.org/index.php/catalog/food-prices/download/mdg_rtfp.csv (téléchargement direct série Madagascar).
- **robots.txt (extrait pertinent, date) :** `User-agent: * Allow: /` (vérifié 2026-10-06).
- **CGU & Qualification légale (C1 / R1.1) :** https://www.worldbank.org/en/about/legal/terms-and-conditions. Libre réutilisation sous licence ouverte CC-BY. Aucune PII directe (`pii_class: none`), pas d'authentification requise.
- **Format(s) et structure (avec exemples réels, pages, colonnes) :** CSV structuré. Colonnes : `country`, `country_code`, `adm1_name`, `market_name`, `date`, `commodity`, `unit`, `currency`, `price_observed`, `price_imputed`, `value_kind`.
- **Cadences distinctes (R1.1) :**
  - Collecte technique (`collection_cadence`) : `monthly`
  - Observation sous-jacente (`observation_cadence`) : `monthly`
  - Publication éditeur (`publication_cadence`) : `monthly`
- **Cadence constatée :** Mensuelle. Données consolidées par DECDG.
- **Couverture géographique et produits :** Madagascar, principaux marchés régionaux (Analamanga, Atsinanana, Vakinankaratra, Boeny...). Produits vivriers : riz, maïs, manioc, blé.
- **Règles de qualification et d'imputation exactes (SPECS §5.2, R1.8, C3) :**
  - **Découverte dynamique :** Support de métadonnées (`file_urls`, `file_url`, `csv_url`), exploration dynamique du catalogue via `CatalogDiscoveryEngine` avec filtrage regex, ou URL officielle directe.
  - **Garantie d'observation vs imputation (AGENTS §4.9, §8.9) :**
    - Si `value_kind == 'imputed'` ou si `price_observed` est absent, vide ou non numérique (`null`, `none`, `nd`, `na`, `nan`) :
      - `observed_or_imputed = 'imputed'`
      - `confidence = 0.8`
      - `price_raw = price_imputed`
      - `is_forecast_or_estimated = True`
    - Si `value_kind == 'observed'` et `price_observed` est une valeur numérique valide :
      - `observed_or_imputed = 'observed'`
      - `confidence = 1.0`
      - `price_raw = price_observed`
      - `is_forecast_or_estimated = False`
    - Si `value_kind` est un flag inconnu :
      - **Interdiction absolue** de promouvoir en `observed` !
      - Routage immédiat dans la file d'anomalies : `kind = 'unknown_value_kind_needs_review'`.
  - **Résolution géographique :**
    - Si `market_name` est présent -> `location_raw = market_name`.
    - Si `market_name` est absent mais `adm1_name` présent -> `location_raw = adm1_name` (agrégat régional).
    - Si ni marché ni région ne sont indiqués -> génération d'une issue `unresolved_location_needs_review`. Aucune imputation géographique aveugle vers "Madagascar" ou vers un code P-code fictif.
  - **Calcul explicite du dénominateur (R1.8) :**
    - Le connecteur consigne systématiquement `total_processed = len(records) + len(issues)`, `n_observed`, `n_imputed`, `imputed_share`.
- **Échantillons et tests :**
  - Fixture authentique : `backend/tests/fixtures/wb_rtfp_mdg/wb_rtfp_mdg_sample.csv` (36 observations).
  - Golden set : `backend/tests/golden/wb_rtfp_mdg/wb_rtfp_sample.expected.json` (36 enregistrements vérifiés indépendamment, 288 champs comparés).
  - Tests unitaires : `backend/tests/unit/test_wb_rtfp_mdg.py` (10 tests verts, couverture de test : 95 %).
  - Précision des champs : 100 % (seuil normatif >= 99 %).
  - Rappel des enregistrements : 100 % (seuil normatif >= 98 %).
- **Statut et incidents :** `qualified`, aucun incident bloquant. Rejouabilité Bronze et traçabilité C3 validées.
