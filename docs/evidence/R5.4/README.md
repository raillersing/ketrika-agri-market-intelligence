# Dossier de Preuve — R5.4 : Modèle de Fenêtre de Récolte Vérifiable et Ajustements Agronomiques

## 1. Contexte & Périmètre de Qualification

- **Tâche :** R5.4 (MUST — Produire une fenêtre de récolte vérifiable).
- **Date d'exécution :** 2026-10-17T10:38:00Z.
- **Environnement :** Conteneurs Docker isolés `ketrika-backend:dev`, worktree `/home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep`, branche `work/r1-sources-prep`. Référentiels taxonomiques officiels montés (`taxonomy/crop_calendar.yaml`).
- **Référence normative :** `AGENTS.md` §1, §3, §4 (Règle 9 observé ≠ imputé ≠ prévu, Règle 10 intégrité des faits), §10 ; `MARKET_INTELLIGENCE_EXECUTION_PLAN.md` §10 (R5.4) ; `SPECS.md` §26, §27 ; `ADR-091`.
- **Objectif :**
  1. Reproduire fidèlement la fenêtre de récolte nominale issue des calendriers culturaux authentiques malgaches (MinAE, FAO GIEWS, FOFIFA, ODR).
  2. Implémenter des règles d'ajustement agronomiques déterministes sous contraintes hydriques réelles (anomalies pluviométriques précoces de début de saison CHIRPS) en distinguant les périmètres irrigués avec maîtrise d'eau (tamponnage du déficit) et les cultures pluviales (retard de semis/repiquage décalant la maturité).
  3. Imposer une résolution temporelle décadaire agronomique stricte (D1: 1-10, D2: 11-20, D3: 21-fin de mois), en interdisant formellement l'invention de dates fictives au jour précis sans instrumentation continue.
  4. Réaliser une confrontation empirique indépendante contre les volumes d'arrivages réels constatés par l'ODR (mai 2024).
  5. Expliciter l'incertitude qualitative et étiqueter les projections comme `experimental_unverified` ou `adjusted_campaign_rule` sans jamais alléguer une fausse précision garantie.

---

## 2. Synthèse d'Exécution des Critères d'Acceptation R5.4 (`test_harvest_window_model.py`)

| Critère | Périmètre Qualifié | Résultat du Test | Constat Métrologique |
|---|---|---|---|
| **C1 : Résolution Décadaire & Bornes Calendaires** | Fonctions `get_dekad_bounds` et `shift_dekad` (mai 31j, décades D1/D2/D3) | **PASSED** | Bornes temporelles conformes aux normes FAO/MinAE (ex: D1=1-10 mai, D2=11-20 mai, D3=21-31 mai). Zéro date journalière inventée. |
| **C2 : Reproduction Baseline du Calendrier Officiel** | Cycle rizicole irrigué du bassin du Lac Alaotra (`ZONE_ALAOTRA`, `RICE_PADDY`) | **PASSED** | Fenêtre nominale reproduite exactement : début mai D1 (`2024-05-D1`), fin juin D3 (`2024-06-D3`), pic mai D2 (`2024-05-D2`), `shift_dekads=0`, niveau `baseline_reference`. |
| **C3 : Tamponnage Hydrique en Régime Irrigué** | Bassin Alaotra irrigué sous déficit pluviométrique précoce modéré (-25%) | **PASSED** | Aucun décalage artificiel induit (`shift_dekads=0`). Motif documenté : « Irrigated regime with hydraulic control buffers rainfall deficit ». |
| **C4 : Translation Décadaire sous Sécheresse Pluviale** | Maïs pluvial des Hauts Plateaux (`crop_regime: rainfed`) sous sécheresse sévère (-38%) | **PASSED** | Retard agronomique de 2 décades (+20 jours) appliqué : début décalé de mars D1 à mars D3 (`2024-03-D3`), pic décalé d'avril D2 à mai D1 (`2024-05-D1`). Niveau `adjusted_campaign_rule`. |
| **C5 : Confrontation Empirique Indépendante ODR** | Confrontation de la fenêtre riz Alaotra 2024 contre les arrivages réels ODR Anosibe mai 2024 | **PASSED** | 100% des arrivages de riz observés (180 000 kg) tombent dans la fenêtre projetée ; pic observé le 2024-05-08 dans la fenêtre ; verdict `consistent`. |
| **C6 : Transparence & Note d'Incertitude Qualitative** | Audit des métadonnées du modèle sous scénario sec simulé | **PASSED** | Qualification `experimental` documentée ; aucune prétention trompeuse de « précision garantie » (conforme à AGENTS.md §8). |

---

## 3. Résultats Chiffrés et Couverture Globale

- **Suite de tests unifiée R5 :** 25/25 tests passés en 29.38s (exit code 0) :
  - `tests/unit/test_harvest_window_model.py` : 6/6 tests passés.
  - `tests/unit/test_supply_quality_and_coverage.py` : 6/6 tests passés.
  - `tests/unit/test_connector_market_supply.py` : 6/6 tests passés.
  - `tests/unit/test_supply_survey_contracts.py` : 7/7 tests passés.
- **Couverture de code sur le lot :**
  - `src/ketrika/supply/harvest_window.py` : **90 %**
  - `src/ketrika/supply/quality.py` : **96 %**
  - `src/ketrika/supply/contracts.py` : **94 %**
  - `src/ketrika/connectors/market_supply.py` : **84 %**
  - Total cumulé phase R5 : **91 %** (largement supérieur aux 80% requis).
- **Contrôles statiques backend :**
  - Ruff check : All checks passed (0 warning).
  - Mypy strict check : Success: no issues found in 2 source files.
- **Livrables d'architecture et de code :**
  - `ADR-091` dans `docs/plan/DECISIONS.md` ;
  - Module `backend/src/ketrika/supply/harvest_window.py` ;
  - Export dans `backend/src/ketrika/supply/__init__.py`.

---

## 4. Décision de Clôture de la Tâche R5.4

Tous les critères d'acceptation de la tâche R5.4 sont **entièrement validés**.  
Le statut de la tâche R5.4 est déclaré **DONE**.
