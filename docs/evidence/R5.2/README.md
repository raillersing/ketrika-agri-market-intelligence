# Dossier de Preuve — R5.2 : Import des Quantités Physiques Légales et Arrivages de Marché

## 1. Contexte & Périmètre de Qualification

- **Tâche :** R5.2 (MUST — Importer les quantités légalement disponibles).
- **Date d'exécution :** 2026-10-17T02:11:00Z.
- **Environnement :** Conteneurs Docker isolés `ketrika-backend:dev`, worktree `/home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep`, branche `work/r1-sources-prep`. Base PostgreSQL active (`aiagent-db-1`) avec schéma migré (Alembic 0016).
- **Référence normative :** `AGENTS.md` §1, §3, §4 (Provenance totale, Bronze immuable, Ajout seul, Rejouabilité), §8.3 (Anti-PII), §10 ; `MARKET_INTELLIGENCE_EXECUTION_PLAN.md` §10 (R5.2) ; `SPECS.md` §27 ; `ADR-089`.
- **Objectif :**
  1. Ingestion des données physiques officielles d'arrivages et de stocks depuis des sources institutionnelles (ODR Madagascar, ministères, enquêtes de marché).
  2. Respect de la disjonction formelle entre flux d'arrivages (`inflow_arrival`), production récoltée (`harvest_volume`) et stocks résiduels (`stock_inventory`).
  3. Enrichissement de la table `obs.stock_observation` avec les dimensions métrologiques `target`, `measurement_mode`, `market_type`, `market_code`.
  4. Migration PostgreSQL Alembic `0016_supply_arrival_and_stock_targets.py` avec contrainte unique partielle sur `(natural_key, target)` évitant les collisions.
  5. Implémentation du connecteur `MarketSupplyConnector` (`source_id="market_supply"`) conforme à `BaseConnector` avec conversions métriques en kg et détection précoce anti-PII.
  6. Support de la non-destructivité et de la supersession via `load_stock_record_with_supersession`.

---

## 2. Synthèse d'Exécution des Critères d'Acceptation R5.2

| Critère | Périmètre Qualifié | Résultat du Test | Constat Métrologique |
|---|---|---|---|
| **C1 : Découverte des sources physiques** | Découverte standard (Anosibe, Ambatondrazaka) et support d'overrides de métadonnées | **PASSED** | Deux drops ODR par défaut découverts ; partitionnement explicite par marché et année. |
| **C2 : Parsing Arrivages & Stocks Anosibe** | Parsing CSV officiel Anosibe 2024 (tonnes, sacs 50kg -> kg standardisés) | **PASSED** | 7 enregistrements extraits (4 arrivages, 3 stocks) avec conversion métrique exacte (180 t -> 180 000 kg, 600 sacs 50kg -> 30 000 kg). |
| **C3 : Parsing Récolte Ambatondrazaka** | Parsing CSV collecte bassin Alaotra (`harvest_volume`, arrivages collecteurs) | **PASSED** | Extraction certifiée de 8 500 tonnes (8 500 000 kg) de récolte rizicole et arrivages associés. |
| **C4 : Rejet Absolu PII en Amont** | Détection et rejet précoce d'un fichier corrompu contenant des colonnes PII privées | **PASSED** | 0 enregistrement extrait, génération d'une anomalie `PII_REJECTION` explicite. Conforme à AGENTS.md §8.3. |
| **C5 : Parsing Structuré JSON** | Parsing de flux d'arrivages au format JSON structuré | **PASSED** | Extraction et conversion métrique validée (`50 tonnes` -> `50 000 kg`). |
| **C6 : Insertion, Idempotence & Supersession** | Chargement avec `load_stock_record_with_supersession` | **PASSED** | Premier passage : `inserted` ; Rejeu identique : `idempotent_skipped` ; Révision de quantité : `superseded` avec préservation de l'ancien état via `superseded_by`. |

---

## 3. Résultats Chiffrés et Couverture Globale

- **Suite de tests dédiée :** 13/13 tests passés en 11.86s (exit code 0) :
  - `tests/unit/test_connector_market_supply.py` : 6/6 tests passés.
  - `tests/unit/test_supply_survey_contracts.py` : 7/7 tests passés.
- **Couverture de code :**
  - `src/ketrika/connectors/market_supply.py` : **84 %**
  - `src/ketrika/supply/contracts.py` : **94 %**
  - Moyenne globale du lot : **89 %** (au-dessus du seuil requis de 80%).
- **Contrôles statiques backend :**
  - Ruff check : All checks passed (0 warning).
  - Mypy strict check : Success: no issues found in 4 source files.
- **Base de données :**
  - Migration Alembic `0016_supply_arrival_and_stock_targets.py` appliquée avec succès sur `obs.stock_observation`.
- **Livrables documentaires & d'architecture :**
  - `ADR-089` consigné dans `docs/plan/DECISIONS.md` ;
  - Fixtures authentiques dans `backend/tests/fixtures/market_supply/` ;
  - Connecteur enregistré dans `backend/src/ketrika/connectors/registry.py`.

---

## 4. Décision de Clôture de la Tâche R5.2

Tous les critères d'acceptation de la tâche R5.2 sont **entièrement validés**.  
Le statut de la tâche R5.2 est déclaré **DONE**.
