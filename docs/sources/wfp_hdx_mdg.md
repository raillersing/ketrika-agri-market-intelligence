# wfp_hdx_mdg : WFP Food Prices – Madagascar (HDX)

> **Statut de qualification R1.7 (2026-10-15) :**
> - Code du connecteur et règles de parsing : **QUALIFIÉ & VALIDÉ** (règles strictes de politique, HXL parsing, distinction `observed`/`imputed`, refus d'imputation géographique aveugle).
> - Collecte réseau live : **BLOCKED** conformément à B-R009 (403 Cloudflare persistant sur le catalogue/direct download HDX).
> - Interdiction stricte de contournement anti-bot selon AGENTS §8.1.
> - Fonctionnement offline sur fixture Bronze reproductible et rejouable.
> - H5 non réalisé (revue golden set par annotateur tiers).

- **Propriétaire / licence / attribution :** World Food Programme (WFP) / OCHA HDX. Licence : CC BY-IGO. Attribution obligatoire : "World Food Programme (WFP)".
- **Famille de source (`source_family`) :** `un_wfp` (famille Programme Alimentaire Mondial, strictement isolée de `world_bank` pour prévenir toute double comptabilisation de prix imputés selon C3).
- **Statut opérationnel dans `registry/sources.yaml` :** `disabled` (incident B-R009, levée systématique de `PolicyStop` si tentative réseau live).
- **URL vérifiées (date, code HTTP) :**
  - https://data.humdata.org/dataset/wfp-food-prices-for-madagascar (historique 2026-10-06, actuellement HTTP 403 Cloudflare sur HDX en direct).
  - https://data.humdata.org/dataset/02b28c05-b076-4d0c-a9f4-279262e3d368/resource/b8c3fdfb-59d8-4f81-a64b-14dcf7d6be2f/download/wfp_food_prices_mdg.csv (téléchargement direct).
- **robots.txt (extrait pertinent, date) :** `User-agent: * Allow: /` (historique vérifié 2026-10-06).
- **CGU & Qualification légale (C1 / R1.1) :** https://data.humdata.org/terms. Utilisation libre avec attribution et mention de la source. Statut opérationnel `status: disabled` conformément à B-R009 et AGENTS §8.1. Aucune tentative de contournement CAPTCHA / 403. Aucune PII directe (`pii_class: none`).
- **Format(s) et structure (avec exemples réels, pages, colonnes) :** CSV structuré avec en-tête standard et ligne de balisage HXL (`#date`, `#adm1+name`, `#adm2+name`, `#loc+market+name`, etc.). Colonnes : `date`, `admin1`, `admin2`, `market`, `latitude`, `longitude`, `category`, `commodity`, `unit`, `priceflag`, `pricetype`, `currency`, `price`, `usdprice`.
- **Cadences distinctes (R1.1) :**
  - Collecte technique (`collection_cadence`) : `monthly`
  - Observation sous-jacente (`observation_cadence`) : `monthly`
  - Publication éditeur (`publication_cadence`) : `monthly`
- **Cadence constatée :** Mensuelle. Données consolidées par le WFP VAM.
- **Couverture géographique et produits :** Madagascar, principaux marchés urbains et ruraux. Produits : riz (local et importé), maïs, manioc, légumineuses, huile, sucre.
- **Règles de parsing et normalisation strictes (R1.7) :**
  - Élimination déterministe de la ligne de balises HXL sans bruit ni crash.
  - Dérivation `actor_level` : `Retail` -> `retail`, `Wholesale` -> `wholesale`.
  - Dérivation `observed_or_imputed` : `actual` -> `observed` (confiance 1.0), `forecast` / `imputed` / `estimated` -> `imputed` (confiance 0.8).
  - Préservation intégrale des valeurs brutes : `unit_raw` (ex: `"KG"`, `"L"`), `price_raw`, `currency_raw`, `product_raw`, `location_raw`.
  - Résolution des marchés : si le marché est absent ou non résolu, génération d'une issue `unresolved_market_needs_review` vers la file de revue humaine. **Interdiction absolue** d'assigner arbitrairement un marché manquant à la région parente ou d'inventer un P-code.
  - Garde-fou réseau : si `status: disabled` dans le registre, toute tentative d'accès réseau direct hors mode offline lève immédiatement un `PolicyStop`.
- **Échantillons et golden set :**
  - Fixture authentique : `backend/tests/fixtures/wfp_hdx_mdg/wfp_food_prices_mdg_sample.csv` (36 observations valides).
  - Golden set : `backend/tests/golden/wfp_hdx_mdg/wfp_sample.expected.json` (36 enregistrements, 252 champs vérifiés).
  - Précision des champs : 100% (seuil >= 99%).
  - Rappel : 100% (seuil >= 98%).
  - Tests unitaires : `backend/tests/unit/test_wfp_hdx_mdg.py` (6 tests verts, couverture 88%).
- **Statut et incidents :**
  - Connecteur : `qualified` (règles et parsing validés).
  - Collecte live : `BLOCKED` (incident B-R009 documenté dans `docs/plan/BLOCKERS.md`).
