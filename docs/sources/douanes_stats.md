# douanes_stats : Douanes Malagasy – Statistiques du Commerce Extérieur

> Audit indépendant2026-10-25 : registre `active`, SQL `active`. Pas de réception live actuelle déduite de la présence du code. Les dates/HTTP/droits/annotations ci-dessous sont des descriptions historiques, non revérifiées par cet audit. Réception à suivre dans [la matrice](../audits/2026-10-25/TASK_CAPABILITY_MATRIX.md) et le [plan correctif](../audits/2026-10-25/CORRECTIVE_EXECUTION_PLAN.md).

- **Propriétaire / licence / attribution :** Direction Générale des Douanes de Madagascar (DGD) / Ministère de l'Économie et des Finances. Licence : Données publiques officielles gouvernementales. Attribution : "Direction Générale des Douanes, Madagascar".
- **Famille de source (`source_family`) :** `madagascar_gov` (famille gouvernementale malgache officielle, isolée des sources d'aide internationale).
- **URL vérifiées (date, code HTTP) :**
  - https://www.douanes.gov.mg (2026-10-06, HTTP 200, verified: true).
- **robots.txt (extrait pertinent, date) :** `User-agent: * Allow: /`
- **CGU & Qualification légale (C1 / R1.1) :** https://www.douanes.gov.mg/mentions-legales. Publications statistiques officielles du commerce extérieur malagasy issues de SYDONIAWorld. Données statistiques agrégées sans secret commercial nominatif ni PII directe (`pii_class: none`).
- **Format(s) et structure (avec exemples réels, pages, colonnes) :**
  - Fichiers mensuels tabulaires CSV / XLSX structurés par flux déclarés au cordon douanier.
  - Colonnes principales :
    - `annee`, `mois` : Période calendaire de la déclaration douanière.
    - `flux` : Type de flux (`import` pour importations / mises à la consommation, `export` pour exportations).
    - `code_sh` : Nomenclature tarifaire SH (Système Harmonisé à 6 ou 8 chiffres, ex: `10063000` pour riz blanchi, `15119000` pour huile de palme, `17019900` pour sucre raffiné, `11010000` pour farine de froment, `07133300` pour haricots secs, `10059000` pour maïs).
    - `designation_produit` : Libellé officiel du produit PPN.
    - `pays_partenaire`, `code_iso3_pays` : Pays d'origine ou de destination (ex: Inde `IND`, Pakistan `PAK`, Malaisie `MYS`, Maurice `MUS`, Turquie `TUR`).
    - `poids_net_kg` : Poids net en kilogrammes.
    - `valeur_caf_fob_mga` : Valeur statistique en Francs Malgaches/Ariary (valeur CAF à l'importation, valeur FOB à l'exportation).
    - `valeur_usd` : Contre-valeur statistique en USD.
- **Cadences distinctes (R1.1) :**
  - Collecte technique (`collection_cadence`) : `monthly`
  - Observation sous-jacente (`observation_cadence`) : `monthly`
  - Publication éditeur (`publication_cadence`) : `monthly`
- **Cadence constatée :** Mensuelle avec consolidations trimestrielles et annuelles.
- **Gestion des révisions (SPECS §8.1) :**
  - Les apurements des déclarations SYDONIAWorld entraînent des révisions rétroactives des tonnages et valeurs déclarés.
  - Le connecteur ré-interroge une fenêtre glissante des 12 derniers mois.
  - Clé naturelle : `sha256(source_id|flow|product_raw|partner_raw|period_start|period_end)`.
  - En cas de révision, l'enregistrement existant dans `obs.trade_flow` est marqué avec `superseded_by = <nouvel_id>`, et le nouvel enregistrement est inséré avec `superseded_by = NULL`.
- **Couverture géographique :** Nationale (ensemble des bureaux des douanes malagasy : Toamasina, Mahajanga, Ivato, Antsiranana, Toliara).
- **Stratégie d'extraction & Qualification R1.6 :**
  - **Découverte dynamique :** `CatalogDiscoveryEngine` avec validation anti-SSRF stricte, domaine borné (`douanes.gov.mg`), pagination limitée à 20 pages.
  - **Distinction des totaux annuels (anti-double comptage) :** Séparation formelle entre flux mensuels (`aggregation_level="monthly"`) et totaux annuels officiels (`aggregation_level="annual_total"`, `period_start=YYYY-01-01`, `period_end=YYYY-12-31`). Clés naturelles strictement disjointes interdisant toute collision ou double comptage en agrégation. Concordance arithmétique vérifiée (somme des flux mensuels égale au total annuel dans la tolérance des arrondis).
  - **Indicateur de valeur unitaire importée :** Le ratio valeur CAF / poids net (`Ar/kg`) est un indicateur calculé de commerce extérieur, conservé dans `TradeFlowRecord` (`obs.trade_flow`) et jamais confondu avec un prix de marché de détail (`obs.price_observation`).
  - **Validation de nomenclature SH :** Validation stricte du format (6 ou 8 chiffres) et des chapitres agricoles PPN (07 légumes/racines/légumineuses, 10 céréales/riz/maïs, 11 meunerie/farine, 12 graines oléagineuses/arachides, 15 huiles végétales, 17 sucres). Codes hors chapitres ou malformés isolés avec issue `unverified_hs_code` sans mapping fallacieux.
  - **Gestion des révisions :** Cycle de révision testé (v1 vs v2) avec conservation d'immuabilité et traçabilité par `superseded_by`.
- **Mapping vers les tables cibles :** `obs.trade_flow` avec rattachement aux codes SH, partenaires ISO3 et niveaux d'agrégation.
- **Fixtures et Corpus Authentique CC-R :**
  - `backend/tests/fixtures/douanes_stats/douanes_stats_2024.csv` (36 flux mensuels PPN).
  - `backend/tests/fixtures/douanes_stats/douanes_stats_2023.csv` (38 flux dont 36 mensuels et 2 totaux annuels officiels).
  - `backend/tests/fixtures/douanes_stats/douanes_stats_invalid_codes.csv` (corpus négatif pour validation SH et dérives de dates).
  - `backend/tests/fixtures/douanes_stats/douanes_snapshot_v1.csv` & `douanes_snapshot_v2.csv` (cycle de révision).
  - `backend/tests/golden/douanes_stats/douanes_authentic.expected.json` (74 observations annotées de référence, 100 % exactitude, 100 % rappel).
- **Statut et incidents :** Actif (`status: active`). Qualifié R1.6.

