# market_supply : Enquêtes d'Approvisionnement et Stocks des Marchés Vivriers

> Audit indépendant2026-10-25 : registre `active`, SQL `absent`. Pas de réception live actuelle déduite de la présence du code. Les dates/HTTP/droits/annotations ci-dessous sont des descriptions historiques, non revérifiées par cet audit. Réception à suivre dans [la matrice](../audits/2026-10-25/TASK_CAPABILITY_MATRIX.md) et le [plan correctif](../audits/2026-10-25/CORRECTIVE_EXECUTION_PLAN.md).

- **Propriétaire / licence / attribution :** Observatoire du Riz (ODR) / Direction Régionale du Commerce et de la Consommation (DRCC). Licence : Protocole d'enquête partenariale et relevés officiels (R5.1, ADR-088). Attribution obligatoire : « Observatoire du Riz (ODR) / Direction Régionale du Commerce, Madagascar ».
- **Famille de source (`source_family`) :** `madagascar_gov` (famille institutionnelle malgache, données de flux physiques et stocks).
- **URL vérifiées (date, code HTTP) :**
  - `file:///data/supply` (2026-10-16, verified: true).
- **robots.txt / CGU :** Protocole d'enquête d'intérêt public. Réutilisation autorisée avec citation de la source.
- **Politique PII & Confidentialité :**
  - `pii_class: none`.
  - Anonymisation stricte : aucun nom d'opérateur, aucun contact, aucun numéro de téléphone ni immatriculation de véhicule. Les données agrégées ne contiennent que les flux (tonnages entrants, stocks estimés, origines régionales).
- **Format(s) et structure :**
  - Fichiers tabulaires CSV / relevés hebdomadaires d'enquêtes de marché (marchés de gros d'Anosibe, marchés collecteurs de l'Alaotra / Ambatondrazaka).
  - Colonnes standards : `date_releve`, `marche`, `region_origine`, `produit`, `variete`, `volume_entrant_tonnes`, `stock_disponible_tonnes`, `niveau_approvisionnement`.
- **Cadences distinctes (R1.1) :**
  - Collecte technique (`collection_cadence`) : `weekly`
  - Observation sous-jacente (`observation_cadence`) : `weekly`
  - Publication éditeur (`publication_cadence`) : `weekly`
- **Couverture :**
  - Produits : Riz blanc local, Riz paddy, Maïs grain, Manioc sec / frais, Huile alimentaire, Sucre roux / blanc.
  - Géographie : Principaux corridors et marchés de gros (Analamanga / Anosibe, Alaotra Mangoro / Ambatondrazaka, Atsinanana / Toamasina).
- **Stratégie d'extraction :**
  - Déterministe : `MarketSupplyConnector` (`ketrika.connectors.market_supply`).
  - Validation anti-PII à l'ingestion (`rejet_pii_interdit`).
- **Mapping vers les tables cibles :**
  - `obs.market_supply_observation` / `obs.stock_observation` :
    - `market_name` : Nom du marché de gros / plateforme logistique ;
    - `commodity` : Libellé standardisé du produit vivrier ;
    - `volume_inflow_t`, `stock_level_t` ;
    - `provenance_id` : Référence immuable vers le fichier source Bronze.
