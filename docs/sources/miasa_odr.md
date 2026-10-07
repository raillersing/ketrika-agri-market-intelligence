# miasa_odr : MiASA Observatoire du Riz (ODR) – Bulletins Périodiques

- **Propriétaire / licence / attribution :** Ministère de l'Agriculture et de l'Élevage (MiASA) / Observatoire du Riz (ODR). Licence : Données publiques officielles gouvernementales malgaches. Attribution obligatoire : « Observatoire du Riz (ODR), Ministère de l'Agriculture et de l'Élevage, Madagascar ».
- **URL vérifiées (date, code HTTP) :**
  - http://www.agriculture.gov.mg (2026-10-06, HTTP 200).
  - http://www.agriculture.gov.mg/odr/bulletin_850.pdf (2026-10-07, HTTP 200).
- **robots.txt (extrait pertinent, date) :** `User-agent: * Allow: /` (2026-10-06).
- **CGU (URL, sha256, résumé des clauses de réutilisation) :** Données ouvertes d'intérêt public agricole pour le suivi officiel de la sécurité alimentaire et de la filière riz. Réutilisation autorisée avec citation de la source.
- **Format(s) et structure (avec exemples réels, pages, colonnes) :**
  - Bulletins hebdomadaires et mensuels au format PDF vectoriel (2 à 4 pages).
  - Tableaux structurés récapitulatifs :
    1. *Tableau 1 : Prix au producteur du paddy* (`actor_level = 'producer'`) : Région / District de collecte, prix moyen (Ar/kg).
    2. *Tableau 2 : Prix de gros du riz blanc* (`actor_level = 'wholesale'`) : Région / Marché de gros, colonnes pour Riz blanc local (Vary gasy, Makalioka, Tsipala) et Riz importé (25% brisures).
    3. *Tableau 3 : Prix au détail du riz blanc* (`actor_level = 'retail'`) : Région / Zone de consommation, colonnes par variété et riz importé.
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
  - `backend/tests/fixtures/miasa_odr/odr_bulletin_520.pdf` (Époque 2018, 60 valeurs).
  - `backend/tests/fixtures/miasa_odr/odr_bulletin_710.pdf` (Époque 2021, 60 valeurs).
  - `backend/tests/fixtures/miasa_odr/odr_bulletin_850.pdf` (Époque 2024, 60 valeurs).
  - Golden sets : `backend/tests/golden/miasa_odr/odr_bulletin_520.expected.json`, `odr_bulletin_710.expected.json`, `odr_bulletin_850.expected.json`. Exactitude des champs = 100 %, Rappel des enregistrements = 100 %.
- **Statut et incidents :** `active`. Tous les critères CC1–CC6 validés.
