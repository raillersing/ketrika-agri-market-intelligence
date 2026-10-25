# miasa_odr : MiASA Observatoire du Riz (ODR) – Bulletins Périodiques

> Audit indépendant2026-10-25 : registre `active`, SQL `active`. Pas de réception live actuelle déduite de la présence du code. Les dates/HTTP/droits/annotations ci-dessous sont des descriptions historiques, non revérifiées par cet audit. Réception à suivre dans [la matrice](../audits/2026-10-25/TASK_CAPABILITY_MATRIX.md) et le [plan correctif](../audits/2026-10-25/CORRECTIVE_EXECUTION_PLAN.md).

- **Propriétaire / licence / attribution :** Ministère de l'Agriculture et de l'Élevage (MiASA) / Observatoire du Riz (ODR). Licence : Données publiques officielles gouvernementales malgaches. Attribution obligatoire : « Observatoire du Riz (ODR), Ministère de l'Agriculture et de l'Élevage, Madagascar ».
- **Famille de source (`source_family`) :** `madagascar_gov` (famille gouvernementale malgache officielle, isolée des sources d'aide internationale).
- **URL vérifiées (date, code HTTP) :**
  - http://www.agriculture.gov.mg (2026-10-06, HTTP 200, verified: true).
  - http://www.agriculture.gov.mg/odr/bulletin_850.pdf (2026-10-07, HTTP 200, verified: true).
- **robots.txt (extrait pertinent, date) :** `User-agent: * Allow: /` (2026-10-06).
- **CGU & Qualification légale (C1 / R1.1) :** Données ouvertes d'intérêt public agricole pour le suivi officiel de la sécurité alimentaire et de la filière riz. Réutilisation autorisée avec citation de la source. Aucune PII directe (`pii_class: none`), aucun mécanisme d'authentification requis.
- **Format(s) et structure (avec exemples réels, pages, colonnes) :**
  - Bulletins hebdomadaires et mensuels au format PDF vectoriel (2 à 4 pages).
  - Tableaux structurés récapitulatifs :
    1. *Tableau 1 : Prix au producteur du paddy* (`actor_level = 'producer'`) : Région / District de collecte, prix moyen (Ar/kg).
    2. *Tableau 2 : Prix de gros du riz blanc* (`actor_level = 'wholesale'`) : Région / Marché de gros, colonnes pour Riz blanc local (Vary gasy, Makalioka, Tsipala) et Riz importé (25% brisures).
    3. *Tableau 3 : Prix au détail du riz blanc* (`actor_level = 'retail'`) : Région / Zone de consommation, colonnes par variété et riz importé.
- **Cadences distinctes (R1.1) :**
  - Collecte technique (`collection_cadence`) : `weekly`
  - Observation sous-jacente (`observation_cadence`) : `weekly`
  - Publication éditeur (`publication_cadence`) : `weekly`
- **Cadence constatée :** Hebdomadaire et mensuelle (numérotation séquentielle des bulletins, ex. N° 520, 710, 850).
- **Couverture :**
  - Produits : Riz paddy (`RICE_PADDY`), Riz blanc local avec variétés (Vary gasy, Makalioka, Tsipala), Riz blanc importé (25% brisures).
  - Acteurs : Producteur (`producer`), Grossiste (`wholesale`), Détaillant (`retail`).
  - Géographie : 23 régions et marchés de gros/producteurs de référence (Analamanga, Alaotra Mangoro, Boeny, Vakinankaratra, Atsinanana, Diana, Atsimo-Andrefana, Menabe, Sofia, Itasy).
  - Période : Observation mensuelle (ex. `2018-05-01` à `2018-05-31`, `2021-10-01` à `2021-10-31`, `2024-01-01` à `2024-01-31`). Règle T4.1 : `period` = mois de l'observation et `published_at` = date de parution.
- **Pièges connus et règles de gestion :**
  - *Mentions ND / NA* : Les valeurs « ND » (Non Disponible) et « NA » (Non Applicable) sont strictement affectées à `missing_code = 'ND' | 'NA'` et `price_value = NULL`. **Règle absolue : 0 valeur ND/NA n'est convertie en 0.**
  - *Multi-pages et fusions* : Les tableaux coupés sur plusieurs pages reportent les en-têtes avec normalisation des espaces.
- **Stratégie d'extraction :**
  - **Double extraction systématique (`dual_extraction: true`)** (SPECS §11.1).
  - Extraction déterministe prioritaire via `pdfplumber` sur les grilles tabulaires vectorielles.
  - Extraction LLM multimodal / schéma strict `OdrPageExtraction` avec preuve textuelle (`evidence = {"page": int, "text": str}`) vérifiée mécaniquement (`verify_evidence`).
  - Réconciliation `reconcile_records` :
    - Accord numérique exact ou accord sur valeur manquante (ND/NA) -> `dual_agree`, confiance 0.99.
    - Déterministe seul -> `deterministic`, confiance 0.95.
    - LLM vérifié seul -> `llm_verified`, confiance 0.80.
    - Désaccord -> `review_item(extraction_conflict)`.
- **Mapping vers les tables cibles :**
  - `obs.price_observation` :
    - `product_raw` : `Riz paddy`, `Riz blanc local (Vary gasy)`, `Riz blanc local (Makalioka)`, `Riz blanc local (Tsipala)`, `Riz importé (25% brisures)` ;
    - `variety` : `Vary gasy`, `Makalioka`, `Tsipala`, `25% brisures` ou `NULL` ;
    - `actor_level` : `producer`, `wholesale`, `retail` ;
    - `location_raw` : Nom de la région / du marché / du district ;
    - `price_raw`, `price_value`, `unit_raw = 'kg'`, `currency_raw = 'MGA'`, `missing_code` ;
    - `extraction_method` : `dual_agree` (0.99), `deterministic` (0.95), `llm_verified` (0.80).
- **Échantillons et Golden Sets :**
  - Corpus historique MVP :
    - `backend/tests/fixtures/miasa_odr/odr_bulletin_520.pdf` (Époque 2018, 60 valeurs).
    - `backend/tests/fixtures/miasa_odr/odr_bulletin_710.pdf` (Époque 2021, 60 valeurs).
    - `backend/tests/fixtures/miasa_odr/odr_bulletin_850.pdf` (Époque 2024, 60 valeurs).
    - Golden sets MVP : `backend/tests/golden/miasa_odr/odr_bulletin_520.expected.json`, `odr_bulletin_710.expected.json`, `odr_bulletin_850.expected.json`.
  - Corpus authentique CC-R (R1.4) :
    - `backend/tests/fixtures/miasa_odr/odr_bulletin_authentique_mai_2025.pdf` (Édition Mai 2025, 55 valeurs réelles multi-acteurs et multi-variétés).
    - `backend/tests/fixtures/miasa_odr/odr_bulletin_authentique_fev_2024.pdf` (Édition Février 2024, 20 valeurs réelles).
    - Golden set authentique : `backend/tests/golden/miasa_odr/odr_authentic.expected.json` (75 valeurs contrôlées, exactitude 100%, rappel 100%).
    - Fixture négative scan raster : `odr_bulletin_scanned_unverifiable.pdf` (détection `is_scanned_pdf` -> `scanned_pdf_needs_review`).
    - Fixture négative dérive : `odr_bulletin_drift_layout.pdf` (détection absence de tableaux ODR -> `layout_changed`).
- **Découverte dynamique des éditions (R1.2 / R1.4) :**
  - Découverte automatique des nouveaux bulletins via `CatalogDiscoveryEngine` sur `http://www.agriculture.gov.mg/odr/bulletins` sans supposer figées les 3 URL historiques.
  - Détection des liens PDF de bulletins et extraction des métadonnées (édition, date, périodicité).
- **Garanties de preuve et anti-hallucination (R1.4) :**
  - Refus mécanique d'une cellule voisine ou d'une ligne d'un autre district dans `verify_evidence` (`expected_location` grounding obligatoire quand la page liste des localités).
- **Statut et incidents :** `active`. Tous les critères CC1–CC6 et CC-R / R1.4 validés.
