# faostat : FAOSTAT – Food and Agriculture Organization Statistics (Madagascar)

> **Statut de qualification R1.9 (2026-10-15) :**
> - Connecteur, découverte dynamique, règles de normalisation C3 et validation de flags : **QUALIFIÉ & VALIDÉ (DONE)**.
> - Distinction stricte entre riz paddy et riz blanchi/usiné : aucune conversion ni ratio implicite (ex: 0.67) appliqué sans justificatif officiel.
> - Validation rigoureuse des drapeaux statistiques FAO : interdiction absolue de promouvoir un drapeau inconnu en donnée officielle observée.
> - Couverture de 20 années consécutives (2004–2023) pour la production de riz paddy à Madagascar.
> - Rejouabilité 100% offline via BronzeStore.

- **Propriétaire / licence / attribution :** Food and Agriculture Organization of the United Nations (FAO). Licence : CC BY-NC-SA 3.0 IGO. Attribution : "FAOSTAT, Food and Agriculture Organization of the United Nations".
- **Famille de source (`source_family`) :** `un_fao` (famille d'agences onusiennes spécialisées agriculture et alimentation).
- **URL vérifiées (date, code HTTP) :**
  - https://www.fao.org/faostat/en/#data (2026-10-06, HTTP 200, verified: true).
  - https://fenixservices.fao.org/faostat/api/v1/en/data/QCL (2026-10-06, HTTP 200, verified: true).
- **robots.txt (extrait pertinent, date) :** `User-agent: * Allow: /` pour l'API et les données publiques.
- **CGU & Qualification légale (C1 / R1.1) :** https://www.fao.org/contact-us/terms/en/. Données ouvertes pour usage analytique et non commercial direct sans altération de l'intégrité statistique. Aucune PII directe (`pii_class: none`), pas d'authentification requise.
- **Format(s) et structure :** API REST JSON et CSV téléchargeables.
  - Domaines : `QCL` (Crops and livestock products), `FBS` (Food Balance Sheets), `TM` (Detailed trade matrix).
  - Champs : `AreaCode` (129 pour Madagascar), `Area`, `DomainCode`, `ItemCode`, `Item`, `ElementCode` (5510 Production, 5312/5110 Superficie, 5419 Rendement, 5610 Importations, 5910 Exportations), `Element`, `Year`, `Unit`, `Value`, `Flag`.
- **Règles de dérivation des flags (`observed_or_imputed`) :**
  - **Observé (`observed`, confidence=1.0)** : Drapeaux officiels et vérifiés `A` (Official figure), `P` (Provisional), `X` (International reliable source), ou absence de drapeau `""` (donnée officielle standard).
  - **Imputé (`imputed`, confidence=0.8)** : Drapeaux d'estimation ou d'imputation `E` (Estimated value), `I` (Imputed value), `F` (FAO estimate), `T` (Trend calculation), `M` (Data not available / proxy), `Q` (Suppressed).
  - **Drapeau inconnu (`imputed`, confidence=0.7, issue émise)** : Tout drapeau non répertorié est consigné sous `unknown_faostat_flag_needs_review` et n'est jamais promu en `observed`.
- **Distinction stricte Paddy vs Blanchi (R1.9) :**
  - Le libellé exact de la source (`Item`) est scrupuleusement conservé dans `product_raw` (ex. `"Rice, paddy"` vs `"Rice, milled"`).
  - Aucune conversion implicite de quantité ou de libellé sans source officielle.
- **Cadences distinctes (R1.1) :**
  - Collecte technique (`collection_cadence`) : `monthly`
  - Observation sous-jacente (`observation_cadence`) : `annual`
  - Publication éditeur (`publication_cadence`) : `annual`
- **Cadence constatée :** Annuelle avec révisions consolidées.
- **Couverture validée :**
  - Production agricole : ≥ 20 années consécutives (2004–2023) de production de riz paddy pour Madagascar, séries maïs et manioc.
  - Commerce international : flux d'importation de riz, farine de blé, sucre et huile de palme convertis en kilogrammes (`weight_kg = value_t * 1000.0`).
- **Stratégie d'extraction :** Déterministe via l'API JSON FAOSTAT (`FaostatConnector`, version 1.1.0).
- **Mapping vers les tables cibles :**
  - Production agricole (`ElementCode = 5510`) → `obs.production_observation` (`element = 'production_t'`).
  - Flux de commerce extérieur (`ElementCode = 5610` import, `5910` export) → `obs.trade_flow`.
- **Fixtures et Golden Dataset :**
  - Fixture authentique : `backend/tests/fixtures/faostat/faostat_sample.json` (36 enregistrements).
  - Golden set : `backend/tests/golden/faostat/faostat_sample.expected.json` (36 observations annotées).
  - Tests unitaires : `backend/tests/unit/test_faostat.py` (7 tests verts, couverture : 81 %).
  - Précision des champs : 100 % (seuil >= 99 %).
  - Rappel des enregistrements : 100 % (seuil >= 98 %).
- **Statut :** `qualified`, aucun incident bloquant.
