# fao_fpma_mdg : FAO FPMA – Food Price Monitoring and Analysis (Madagascar)

> Implémenté dans le cadre de IA-DATA-07 (P1 : prix multisources).

- **Propriétaire / licence / attribution :** Food and Agriculture Organization of the United Nations (FAO / GIEWS). Licence : CC BY-NC-SA 3.0 IGO. Attribution : "FAO Food Price Monitoring and Analysis (FPMA) Tool, GIEWS".
- **Famille de source (`source_family`) :** `un_fao` (famille d'agences onusiennes spécialisées agriculture et alimentation).
- **URL vérifiées :**
  - https://fpma.fao.org/giews/fpma/api/v1/prices?country=MDG (HTTP 200, API JSON).
  - https://www.fao.org/giews/food-prices/tool/public/ (portail public).
- **robots.txt :** `User-agent: * Allow: /` pour les APIs publiques et données de marché.
- **CGU & Qualification légale :** https://www.fao.org/contact-us/terms/en/. Données ouvertes pour veille de marché, recherche et analyse sans altération de l'intégrité statistique. Aucune PII directe (`pii_class: none`), pas d'authentification requise.
- **Format(s) et structure :** API REST JSON et exports structurés.
  - Champs : `country`, `iso3`, `market`, `market_id`, `commodity`, `commodity_id`, `price_type`, `price`, `currency`, `unit`, `date` / `period_start`, `period`, `data_source`, `flag`.
- **Règles de parsing et normalisation strictes (IA-DATA-07) :**
  - Dérivation `actor_level` : `Retail` -> `retail`, `Wholesale` -> `wholesale`.
  - Dérivation `observed_or_imputed` : `flag` in (`forecast`, `imputed`, `estimated`) -> `imputed` (confiance 0.8), sinon `observed` (confiance 1.0).
  - Préservation des champs bruts : `product_raw`, `location_raw`, `price_raw`, `unit_raw`, `currency_raw`.
  - Règle absolue `no_arbitrary_default` : si le marché est absent ou non identifié, émission d'une issue `unresolved_market_needs_review` vers la file de revue humaine. Interdiction d'assigner arbitrairement la capitale ou le niveau national par défaut.
- **Biais de double comptage WB↔WFP↔FAO :**
  - FAO FPMA consolide des relevés provenant conjointement des ministères nationaux et du WFP VAM.
  - L'audit d'indépendance des familles de sources (`audit_source_family_independence`) détecte formellement la dépendance croisée (`has_dependent_derivation=True`) lorsqu'un jeu de données combine FAO FPMA, WFP HDX et WB RTFP.
- **Cadences :**
  - Collecte technique (`collection_cadence`) : `monthly`
  - Observation sous-jacente (`observation_cadence`) : `monthly`
  - Publication éditeur (`publication_cadence`) : `monthly`
- **Couverture géographique et produits :** Madagascar, principaux marchés urbains (Antananarivo, Toamasina, Mahajanga, etc.). Produits : riz usiné / local, maïs, manioc frais.
- **Fixtures et tests :**
  - Fixture authentique : `backend/tests/fixtures/fao_fpma_mdg/fpma_prices_mdg_sample.json`.
  - Tests unitaires : `backend/tests/unit/test_ia_data_07_multisource_prices.py`.
- **Statut :** `qualified`.
