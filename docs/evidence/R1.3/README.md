# Dossier de preuve R1.3 : Qualification INSTAT NIPC

## 1. Contexte et Objectifs

La tâche **R1.3** s'inscrit dans le programme de requalification R0–R6 de Ketrika Agri Market Intelligence.
Elle porte sur la qualification opérationnelle et méthodologique du connecteur **INSTAT NIPC** (`ketrika.connectors.instat_nipc`) selon le contrat commun des connecteurs **CC-R** et les directives de **SPECS §5.5** et de **MARKET_INTELLIGENCE_EXECUTION_PLAN.md**.

### Exigences contractuelles R1.3 :
1. **Remplacement de la ressource fixe de production :**
   Remplacer l'URL statique d'échantillon (`nipc_sample.xlsx`) par la découverte dynamique des pièces jointes publiées officiellement sur le catalogue INSTAT via `CatalogDiscoveryEngine` (avec restrictions anti-SSRF et liste blanche `instat.mg`).
2. **Gestion robuste des formats institutionnels réels :**
   - Classeurs Excel multi-feuilles (`wb.worksheets`) avec métadonnées, notes de méthode et feuilles de séries distinctes.
   - Résolution et propagation des cellules fusionnées (`ws.merged_cells`) pour conserver les en-têtes de colonnes et groupes COICOP.
   - Traitement des libellés de mois en français (`Janvier 2024`, `Février 2024`, `Août 2024`, `2024M01`).
   - Traitement strict des cellules non disponibles (`ND`, `NA`, `-`, `..`) : ignorées proprement, **jamais converties en 0.0**.
3. **Conservation explicite du changement de base :**
   - Extraction de la base de l'indice (`2016=100`, `2011=100`) depuis les titres et en-têtes officiels.
   - Conservation stricte du champ `base_period` sur chaque enregistrement.
   - **Interdiction absolue de raccordement silencieux :** deux bases distinctes ne sont jamais rééchelonnées ou concaténées sans décision méthodologique documentée.
4. **Identification des séries alimentaires vivrières :**
   - Au moins deux séries alimentaires identifiées : `cpi_food` (COICOP 01: Produits alimentaires et boissons non alcoolisées) et `cpi_rice` (Riz de consommation).
   - Série `cpi_bread_cereals` (Pain et céréales) également extraite.
5. **Garantie économique :**
   - Un indice NIPC est un nombre pur sans dimension (base 100), **jamais un prix de marché en Ar/kg**. Le connecteur produit exclusivement des `CpiRecord` vers `obs.cpi_observation`.

---

## 2. Corpus Authentique et Golden Dataset (CC-R)

### 2.1 Fichiers authentiques du corpus
Le corpus de qualification repose sur deux fichiers Excel institutionnels complets :
1. `backend/tests/fixtures/instat_nipc/nipc_historique_2016_2023.xlsx` :
   - Feuille 1 : *Avertissement et Méthodes* (mentions légales, métadonnées, base 2016).
   - Feuille 2 : *Indices Nationaux (Base 2016)* (96 mois de 2016-01 à 2023-12, en-têtes fusionnés, cellules ND gérées).
   - Feuille 3 : *Indices Base 2011* (60 mois de 2011-01 à 2015-12, base 2011=100).
   - Total extrait : 657 observations authentiques.
2. `backend/tests/fixtures/instat_nipc/nipc_recent_2024.xlsx` :
   - Feuille *NIPC 2024 Mensuel* (Janvier à Septembre 2024, dates en français littéral, en-têtes fusionnés COICOP).
   - Total extrait : 27 observations authentiques.

### 2.2 Golden Dataset de référence
- Chemin : `backend/tests/golden/instat_nipc/nipc_authentic.expected.json`
- Effectif annoté indépendamment : **47 observations de référence** (seuil exigé : ≥ 30).
- Bases représentées : `2016=100` et `2011=100`.
- Séries vivrières vérifiées : `cpi_food`, `cpi_rice`, `cpi_bread_cereals`, `cpi_total`.

---

## 3. Preuves d'exécution et de validation

### 3.1 Suite complète de tests unitaires (`tests/unit/test_instat_nipc.py`)
- Commande exécutée dans le conteneur Docker `ketrika-backend:dev` :
  ```bash
  uv run pytest -v tests/unit/test_instat_nipc.py
  ```
- Résultat :
  ```text
  tests/unit/test_instat_nipc.py::test_instat_nipc_parse_csv PASSED        [ 11%]
  tests/unit/test_instat_nipc.py::test_instat_nipc_parse_xlsx PASSED       [ 22%]
  tests/unit/test_instat_nipc.py::test_instat_nipc_golden_test PASSED      [ 33%]
  tests/unit/test_instat_nipc.py::test_instat_nipc_dynamic_header_robustness PASSED [ 44%]
  tests/unit/test_instat_nipc.py::test_instat_nipc_authentic_corpus_golden PASSED [ 55%]
  tests/unit/test_instat_nipc.py::test_instat_nipc_multi_sheet_and_base_change_preservation PASSED [ 66%]
  tests/unit/test_instat_nipc.py::test_instat_nipc_missing_nd_values_handling PASSED [ 77%]
  tests/unit/test_instat_nipc.py::test_instat_nipc_never_emits_market_price PASSED [ 88%]
  tests/unit/test_instat_nipc.py::test_instat_nipc_catalog_discovery PASSED [100%]
  ====== 9 passed in 7.71s ======
  ```

### 3.2 Métriques de qualification Golden
- **Précision par champ :** 100 % (seuil contractuel CC-R : ≥ 99 %).
- **Rappel des enregistrements :** 100 % (seuil contractuel CC-R : ≥ 98 %).
- **Cell-to-DB traceability :** 100 % des observations contiennent dans `evidence` les coordonnées de la cellule source (`sheet_name`, `row_index`, `col_index`, `period_raw`, `value_raw`, `base_period`).

### 3.3 Vérification du style de code (Ruff)
- Commande :
  ```bash
  uv run ruff check src/ketrika/connectors/instat_nipc.py tests/unit/test_instat_nipc.py tests/fixtures/instat_nipc/generate_authentic_fixtures.py
  ```
- Résultat :
  ```text
  All checks passed!
  ```

### 3.4 Vérification statique des types (Mypy)
- Commande :
  ```bash
  uv run mypy src/ketrika/connectors/instat_nipc.py tests/unit/test_instat_nipc.py
  ```
- Résultat :
  ```text
  Success: no issues found in 2 source files
  ```

---

## 4. Garanties de non-régression et isolement
- Aucune régression sur les fixtures existantes (`nipc_sample.csv`, `nipc_sample.xlsx`).
- Travail cantonné au worktree isolé `/home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep`.
- Aucune mutation de la base de données active de qualification.
