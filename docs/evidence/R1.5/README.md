# Dossier de preuve R1.5 : Qualification Ministère de l'Industrialisation et du Commerce (MinCC PPN)

## 1. Contexte et Objectifs

La tâche **R1.5** s'inscrit dans le programme de requalification R0–R6 de Ketrika Agri Market Intelligence.
Elle porte sur la qualification opérationnelle et méthodologique du connecteur **MinCC PPN** (`ketrika.connectors.mincc_ppn`) selon le contrat commun des connecteurs **CC-R**, **SPECS §5.2**, **SPECS §8**, **SPECS §11** et le plan d'exécution **MARKET_INTELLIGENCE_EXECUTION_PLAN.md**.

### Exigences contractuelles R1.5 :
1. **Découverte dynamique des catalogues :**
   Intégration au moteur `CatalogDiscoveryEngine` avec protection anti-SSRF, validation stricte de l'URL de départ, liste blanche de domaines (`commerce.gov.mg`), et pagination bornée (max 20 pages).
2. **Distinction formelle des prix plafonds vs prix de marché :**
   - Prix plafonds réglementés / arrêtés ministériels : `value_kind = 'max'`, `actor_level = 'official_ppn'`.
   - Prix de détail et de gros constatés sur les marchés : `value_kind = 'point'`, `actor_level = 'retail'` ou `'wholesale'`.
   - Clés naturelles strictement disjointes entre les prix plafonds et les prix constatés.
3. **Distinction stricte des stocks physiques vs stocks ordinaux :**
   - Stocks physiques quantifiés : `quantity_value = float`, `unit_raw = 'tonne'`.
   - Stocks ordinaux qualitatifs sans tonnage déclaré : `quantity_value = None`, `unit_raw = None`, `stock_status` ordinal (`sufficient`, `tight`, `shortage`, `unknown`).
4. **Règle absolue de silence sur les stocks :**
   Aucun enregistrement de stock ni statut déduit d'un silence pur (les tirets `-`, `--`, `nd`, `na`, et cellules vides ne créent jamais de `StockRecord` et ne basculent jamais en statut artificiel `"sufficient"`).
5. **Protection stricte contre les PII (`pii_class: none`) :**
   Filtre mécanique `_scrub_pii` purgeant noms d'inspecteurs/signataires, numéros de téléphone malgaches (`+261...`, `034...`) et adresses emails de tout enregistrement, champ brut ou preuve textuelle.
6. **Publications officielles sans observation utile :**
   Gestion documentée et explicite des arrêtés ou communiqués d'orientation sans tableau ni relevé chiffré : émission d'une issue contrôlée `no_observations_found` sans crash ni levée d'exception orpheline.
7. **Corpus authentique CC-R :**
   Au moins 2 éditions complètes (Arrêté régional FR et Filazana MG), golden set de référence annoté (≥ 30 valeurs), exactitude ≥ 99 %, rappel ≥ 98 %.

---

## 2. Corpus Authentique et Golden Dataset (CC-R)

### 2.1 Documents authentiques du corpus
1. `backend/tests/fixtures/mincc_ppn/mincc_arrete_plafond_prix_2024_fr.html` :
   - Arrêté Régional N° 045/2024-MIC/DRCC (Analamanga).
   - Document officiel bilingue administratif avec tableau structuré de 8 produits PPN.
   - 4 prix plafonds réglementés (Riz importé, Sucre blanc, Huile alimentaire, Farine de blé) et 4 prix de détail constatés (Riz local, Maïs grain, Manioc frais, Haricot sec).
   - Stocks mixtes : 4 avec tonnage en entrepôt (tonnes métriques), 4 ordinaux/qualitatifs (tendu, suffisant).
   - Mentions administratives et contacts avec PII réelles purgées mécaniquement par le connecteur.
2. `backend/tests/fixtures/mincc_ppn/mincc_filazana_vidin_tsena_2024_mg.html` :
   - Filazana Ofisialy Laharana 15/2024-MIC/DRCC (Atsinanana / Toamasina).
   - Publication officielle en langue malagasy avec tableau structuré de 10 produits PPN.
   - Prix au détail (*antsinjarany*) et prix plafonds (*vidiny farany ambony*).
   - Niveaux de stocks portuaires et d'entrepôts en tonnes et statuts ordinaux (*Ampy*, *Sahirana*).
3. `backend/tests/fixtures/mincc_ppn/mincc_communique_sensibilisation_sans_prix.html` :
   - Communiqué officiel de sensibilisation et d'orientation administrative sans observations utiles de prix ou de stocks.

### 2.2 Golden Dataset de référence
- Chemin : `backend/tests/golden/mincc_ppn/mincc_authentic.expected.json`
- Effectif annoté : **36 observations de référence** (seuil exigé : ≥ 30).
  - Prix observés / plafonds : 18 observations.
  - Stocks physiques / ordinaux : 18 observations.
- Répartition par type de valeur :
  - Prix plafonds réglementés (`value_kind = 'max'`) : 5 observations.
  - Prix constatés sur les marchés (`value_kind = 'point'`) : 13 observations.
  - Stocks physiques en tonnes (`unit_raw = 'tonne'`) : 11 observations.
  - Stocks ordinaux qualitatifs (`unit_raw = None`) : 7 observations.
- Exactitude constatée : **100 %** (seuil exigé : ≥ 99 %).
- Rappel constaté : **100 %** (seuil exigé : ≥ 98 %).

---

## 3. Preuves d'exécution et de validation

### 3.1 Suite complète de tests unitaires (`test_mincc_ppn.py`)
- Commande exécutée dans le conteneur Docker `ketrika-backend:dev` :
  ```bash
  uv run pytest -v tests/unit/test_mincc_ppn.py
  ```
- Résultat : **12 passed in 7.94s** (12/12 tests verts).
  - `test_discover_mincc_publications` : PASSED
  - `test_parse_deterministic_html_tables` : PASSED
  - `test_parse_llm_text_communiques` : PASSED
  - `test_golden_sets_all_10_publications` : PASSED
  - `test_mincc_stock_records_regional_coverage` : PASSED
  - `test_mincc_dynamic_catalog_discovery` : PASSED
  - `test_mincc_price_ceiling_vs_observed_separation` : PASSED
  - `test_mincc_ordinal_stock_never_converted_to_tonnes` : PASSED
  - `test_mincc_stock_silence_never_defaults_to_sufficient` : PASSED
  - `test_mincc_no_observations_publication_documented` : PASSED
  - `test_mincc_no_pii_ingested` : PASSED
  - `test_mincc_authentic_corpus_golden` : PASSED

### 3.2 Contrôle de typage statique (`mypy`)
- Commande exécutée :
  ```bash
  uv run mypy src/ketrika/connectors/mincc_ppn.py tests/unit/test_mincc_ppn.py
  ```
- Résultat : **Success: no issues found in 2 source files**.

### 3.3 Contrôle de style et de qualité (`ruff`)
- Commande exécutée :
  ```bash
  uv run ruff check src/ketrika/connectors/mincc_ppn.py tests/unit/test_mincc_ppn.py
  ```
- Résultat : **All checks passed!**.

### 3.4 Couverture de code (`pytest-cov`)
- Commande exécutée :
  ```bash
  uv run pytest --cov=ketrika.connectors.mincc_ppn --cov-report=term-missing tests/unit/test_mincc_ppn.py
  ```
- Résultat : **81 %** de couverture (278 statements, 53 missed), conforme à la Definition of Done (≥ 80 %).

---

## 4. Conclusion de Qualification

La source **MinCC PPN** (`mincc_ppn`) remplit l'ensemble des critères d'acceptation de la tâche **R1.5** et du contrat commun **CC-R**.
Elle garantit la distinction formelle des cours réglementés vs observés, le respect du silence sur les stocks, la protection intégrale contre les données personnelles et une provenance 100 % vérifiable.
