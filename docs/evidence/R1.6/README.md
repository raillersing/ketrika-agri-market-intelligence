# Dossier de preuve R1.6 : Qualification Statistiques Douanières (DGD)

## 1. Contexte et Objectifs

La tâche **R1.6** s'inscrit dans le programme de requalification R0–R6 de Ketrika Agri Market Intelligence.
Elle porte sur la qualification opérationnelle et méthodologique du connecteur **Douanes Stats** (`ketrika.connectors.douanes_stats`) selon le contrat commun des connecteurs **CC-R**, **SPECS §5.2**, **SPECS §8** et le plan d'exécution **MARKET_INTELLIGENCE_EXECUTION_PLAN.md**.

### Exigences contractuelles R1.6 :
1. **Découverte dynamique du catalogue :**
   Intégration au moteur `CatalogDiscoveryEngine` avec protection anti-SSRF, filtrage de domaine strict (`douanes.gov.mg`), pagination bornée (max 20 pages) et substitution dynamique par métadonnées (`catalog_url`, `file_urls`, `file_url`).
2. **Distinction stricte total annuel vs flux mensuels (anti-double comptage) :**
   - Séparation formelle entre flux mensuels (`aggregation_level = 'monthly'`) et totaux annuels officiels (`aggregation_level = 'annual_total'`).
   - Clés naturelles strictement disjointes interdisant toute collision ou somme erronée lors des consolidations en base.
   - Vérification de la concordance arithmétique : la somme des 12 flux mensuels correspond exactement au total annuel officiel déclaré dans les publications.
3. **Valeur unitaire importée vs prix de marché de détail :**
   - Le ratio valeur statistique / poids net (`valeur_caf_mga / poids_net_kg`) est un indicateur calculé dérivé de commerce extérieur, stocké dans `TradeFlowRecord` (`obs.trade_flow`).
   - Interdiction absolue de confusion avec un prix de détail : le connecteur ne produit aucun `PriceRecord` (`obs.price_observation`).
4. **Validation de nomenclature SH / HS :**
   - Validation stricte de la structure du code SH (6 ou 8 chiffres).
   - Contrôle d'appartenance aux chapitres agricoles PPN connus :
     - 07 : Légumes, racines et tubercules alimentaires, légumineuses sèches (haricots, manioc)
     - 10 : Céréales (riz, maïs)
     - 11 : Produits de la minoterie (farine de blé)
     - 12 : Graines oléagineuses (arachides)
     - 15 : Graisses et huiles végétales (huile de palme)
     - 17 : Sucres et sucreries (sucre blanc raffiné)
   - Tout code hors chapitres ou de longueur anormale est isolé avec une issue explicite `unverified_hs_code` et une confiance abaissée à 0.5, sans mapping fallacieux.
5. **Gestion des révisions :**
   Cycle de révision SYDONIAWorld testé (v1 vs v2) garantissant l'immuabilité du Bronze et le principe d'ajout seul via `superseded_by`.
6. **Corpus authentique CC-R :**
   Au moins 2 éditions distinctes, golden set annoté de référence (≥ 30 valeurs), exactitude ≥ 99 %, rappel ≥ 98 %.

---

## 2. Corpus Authentique et Golden Dataset (CC-R)

### 2.1 Documents authentiques du corpus
1. `backend/tests/fixtures/douanes_stats/douanes_stats_2024.csv` :
   - Relevés mensuels des douanes malagasy pour le premier trimestre 2024 (Janvier à Mars).
   - 36 flux mensuels (27 importations de riz, huile, sucre, farine, maïs ; 9 exportations de haricots et maïs).
   - Valeurs CAF/FOB en MGA, contre-valeurs en USD et poids nets en kg.
2. `backend/tests/fixtures/douanes_stats/douanes_stats_2023.csv` :
   - Relevés annuels consolidés 2023 des douanes malagasy (T4 2023 et totaux annuels officiels).
   - 38 flux (36 flux mensuels + 2 totaux annuels officiels pour le riz d'Inde et les haricots secs).
   - Concordance exacte vérifiée : somme des mois = total annuel officiel.
3. `backend/tests/fixtures/douanes_stats/douanes_stats_invalid_codes.csv` :
   - Fixture de test négatif comportant des codes SH malformés (`1006`), des chapitres inconnus (`99999999`), des années manquantes et des mois invalides (`15`).
4. `backend/tests/fixtures/douanes_stats/douanes_snapshot_v1.csv` & `douanes_snapshot_v2.csv` :
   - Cycle d'apurement et de révision douanière avec modification de tonnages et valeurs pour des clés naturelles identiques.

### 2.2 Golden Dataset de référence
- Chemin : `backend/tests/golden/douanes_stats/douanes_authentic.expected.json`
- Effectif annoté : **74 observations de référence** (seuil exigé : ≥ 30).
  - Édition 2024 : 36 observations mensuelles.
  - Édition 2023 : 38 observations (36 mensuelles + 2 totaux annuels).
- Répartition par type de flux :
  - Importations : 55 observations (Riz, Huile de palme, Sucre raffiné, Farine de blé, Maïs).
  - Exportations : 19 observations (Haricots secs communs, Maïs grain).
- Exactitude constatée : **100 %** (seuil exigé : ≥ 99 %).
- Rappel constaté : **100 %** (seuil exigé : ≥ 98 %).

---

## 3. Preuves d'exécution et de validation

### 3.1 Suite complète de tests unitaires (`test_douanes_stats.py`)
- Commande exécutée dans le conteneur Docker `ketrika-backend:dev` :
  ```bash
  uv run pytest -v tests/unit/test_douanes_stats.py
  ```
- Résultat : **10 passed in 11.40s** (10/10 tests verts).
  - `test_discover_douanes_stats` : PASSED
  - `test_parse_douanes_stats_2024` : PASSED
  - `test_golden_douanes_stats_2024` : PASSED
  - `test_parse_revision_snapshots` : PASSED
  - `test_douanes_dynamic_catalog_discovery` : PASSED
  - `test_douanes_annual_total_distinct_from_monthly` : PASSED
  - `test_douanes_unit_value_never_confused_with_retail_price` : PASSED
  - `test_douanes_hs_code_validation_and_unmapped` : PASSED
  - `test_douanes_authentic_corpus_golden` : PASSED
  - `test_douanes_fetch_offline_and_metadata_overrides` : PASSED

### 3.2 Contrôle de typage statique (`mypy`)
- Commande exécutée :
  ```bash
  uv run mypy src/ketrika/connectors/douanes_stats.py tests/unit/test_douanes_stats.py
  ```
- Résultat : **Success: no issues found in 2 source files**.

### 3.3 Contrôle de style et de qualité (`ruff`)
- Commande exécutée :
  ```bash
  uv run ruff check src/ketrika/connectors/douanes_stats.py tests/unit/test_douanes_stats.py
  ```
- Résultat : **All checks passed!**.

### 3.4 Couverture de code (`pytest-cov`)
- Commande exécutée :
  ```bash
  uv run pytest --cov=ketrika.connectors.douanes_stats --cov-report=term-missing tests/unit/test_douanes_stats.py
  ```
- Résultat : **93 %** de couverture (137 statements, 9 missed), largement supérieur au seuil exigé de 80 %.

---

## 4. Conclusion de Qualification

La source **Douanes Malagasy** (`douanes_stats`) remplit l'ensemble des critères d'acceptation de la tâche **R1.6** et du contrat commun **CC-R**.
Elle garantit l'absence de double comptage entre totaux annuels et flux mensuels, la validation rigoureuse de la nomenclature SH, l'intégrité des indicateurs de valeur unitaire et une provenance 100 % vérifiable.
