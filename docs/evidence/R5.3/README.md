# Dossier de Preuve — R5.3 : Contrôle Qualité des Quantités, Matrice Marché × Période et Taux de Couverture

## 1. Contexte & Périmètre de Qualification

- **Tâche :** R5.3 (MUST — Contrôler les quantités et leur couverture).
- **Date d'exécution :** 2026-10-17T02:17:00Z.
- **Environnement :** Conteneurs Docker isolés `ketrika-backend:dev`, worktree `/home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep`, branche `work/r1-sources-prep`.
- **Référence normative :** `AGENTS.md` §1, §3, §4 (Règles 8 brut conservé, 9 observé ≠ imputé), §10 ; `MARKET_INTELLIGENCE_EXECUTION_PLAN.md` §10 (R5.3) ; `SPECS.md` §27 ; `ADR-090`.
- **Objectif :**
  1. Valider métrologiquement la cohérence des séries de quantités physiques et flux d'approvisionnement des marchés vivriers.
  2. Construire la matrice marché × période distinguant formellement présence observée, zéro réel certifié et jours non enquêtés.
  3. Appliquer la règle impérative : **Absence de relevé ≠ zéro arrivage** (interdiction absolue d'imputer `0.0 kg` sur un jour non enquêté).
  4. Quantifier le taux de couverture d'échantillonnage réel ($N_{\text{observés}} / N_{\text{attendus}}$) et expliciter la part de pesée certifiée sur bascule (`measured_scale`) vs déclarations marchands (`declared_trader`), sans extrapolation artificielle non pondérée.
  5. Détecter mécaniquement les violations de double comptage temporel (ex: cumul mensuel subsumant des relevés journaliers).
  6. Auditer les facteurs de conversion vers le kilogramme métrique et rejeter toute altération arbitraire de conditionnement.

---

## 2. Synthèse d'Exécution des Critères d'Acceptation R5.3 (`test_supply_quality_and_coverage.py`)

| Critère | Périmètre Qualifié | Résultat du Test | Constat Métrologique |
|---|---|---|---|
| **C1 : Matrice Marché × Période & Jours Non Enquêtés** | Grille calendrier 5 jours à Anosibe avec relevés discontinus | **PASSED** | Jours enquêtés correctement typés `observed_arrival`. Jours non enquêtés marqués `missing_survey` avec `quantity_kg is None` (zéro faux zéro). |
| **C2 : Zéro Vérifié vs Absence d'Enquête** | Fermeture Bazar Be Toamasina (pesée 0 kg) vs jour suivant non enquêté | **PASSED** | Distinction nette entre `zero_arrival_verified` (0.0 kg) et `missing_survey` (None). Règle « absence ≠ zéro » respectée à 100%. |
| **C3 : Taux de Couverture & Ventilation Métrologique** | Série de 10 jours (6 enquêtés : 4 bascule, 2 déclaratif) | **PASSED** | Taux de couverture calculé exactement à `0.60` (60%). Ratio certifié mesuré à `0.6667` (66.7%). Somme observée sans extrapolation abusive. |
| **C4 : Détection Double Comptage Temporel** | Intervalle mensuel (1er-31 mai) subsumant des relevés quotidiens | **PASSED** | Violation `subsumed_interval_double_count` identifiée immédiatement avec sommation isolée des sous-périodes (`390 000 kg` dans `5 000 000 kg`). |
| **C5 : Audit des Conversions d'Unités Physiques** | Tonnes, sacs 50 kg conformes vs altération arbitraire à 5 000 kg pour 10 t | **PASSED** | Conversions légales validées. Écarts et unités locales non répertoriées sans table de conversion formellement rejetés. |
| **C6 : Audit Qualité Global sur Corpus Réel ODR 2024** | Corpus officiel d'arrivages Anosibe 2024 (riz, maïs) | **PASSED** | Rapport `SupplyDataQualityReport` complet généré, absence totale de violations ou de conversion corrompue, validité confirmée. |

---

## 3. Résultats Chiffrés et Couverture Globale

- **Suite de tests unifiée R5 :** 19/19 tests passés en 16.74s (exit code 0) :
  - `tests/unit/test_supply_quality_and_coverage.py` : 6/6 tests passés.
  - `tests/unit/test_connector_market_supply.py` : 6/6 tests passés.
  - `tests/unit/test_supply_survey_contracts.py` : 7/7 tests passés.
- **Couverture de code sur le lot supply :**
  - `src/ketrika/supply/quality.py` : **96 %**
  - `src/ketrika/supply/contracts.py` : **94 %**
  - `src/ketrika/connectors/market_supply.py` : **84 %**
  - Total package `ketrika.supply` : **92 %** (largement supérieur aux 80% requis).
- **Contrôles statiques backend :**
  - Ruff check : All checks passed (0 warning).
  - Mypy strict check : Success: no issues found in 3 source files.
- **Livrables d'architecture et de code :**
  - `ADR-090` dans `docs/plan/DECISIONS.md` ;
  - Module `backend/src/ketrika/supply/quality.py` ;
  - Export dans `backend/src/ketrika/supply/__init__.py`.

---

## 4. Décision de Clôture de la Tâche R5.3

Tous les critères d'acceptation de la tâche R5.3 sont **entièrement validés**.  
Le statut de la tâche R5.3 est déclaré **DONE**.
