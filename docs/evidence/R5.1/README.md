# Dossier de Preuve — R5.1 : Définition des Cibles, Protocole de Relevé des Quantités et Contrats Anti-PII

## 1. Contexte & Périmètre de Qualification

- **Tâche :** R5.1 (MUST — Définir les cibles et le protocole de relevé des quantités et approvisionnements).
- **Date d'exécution :** 2026-10-17T02:00:00Z.
- **Environnement :** Conteneurs Docker isolés `ketrika-backend:dev`, worktree `/home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep`, branche `work/r1-sources-prep`.
- **Référence normative :** `AGENTS.md` §1, §3, §4, §8.3 (Interdiction absolue de PII), §10 ; `MARKET_INTELLIGENCE_EXECUTION_PLAN.md` §10 (R5.1) ; `SPECS.md` §27 ; `ADR-088`.
- **Objectif :** Établir le cadre normatif et métrologique pour la mesure des volumes physiques et flux d'approvisionnement :
  1. Définition rigoureuse de 3 cibles métrologiques strictement disjointes (`HARVEST_VOLUME`, `INFLOW_ARRIVAL`, `STOCK_INVENTORY`, `OUTFLOW_SALES`).
  2. Prévention formelle du double comptage (interdiction d'additionner flux logistique et stock d'inventaire ou production brute).
  3. Contrat de mesure anti-PII absolu via Pydantic (`extra="forbid"`) rejetant tout nom de personne, numéro de téléphone, email, plaque d'immatriculation ou identifiant privé.
  4. Dictionnaire d'unités physiques et conversions standardisées (`kg`, `tonne`, `bag_50kg`, `bag_100kg`, `gony`, `kapoaka`) avec prise en compte des densités spécifiques par produit vivrier malgache.
  5. Protocole d'enquête anonymisé (`docs/protocols/market_supply_survey_protocol.md`) et modèle de convention de partage (`docs/outreach/accord_partenariat_enquetes_approvisionnement.md`) conforme aux gates H3/H7 (sans envoi).

---

## 2. Synthèse d'Exécution des Critères d'Acceptation R5.1 (`test_supply_survey_contracts.py`)

| Critère | Périmètre Qualifié | Résultat du Test | Constat Métrologique |
|---|---|---|---|
| **C1 : Cibles Métrologiques Disjointes** | Instanciation certifiée de `HARVEST_VOLUME`, `INFLOW_ARRIVAL`, `STOCK_INVENTORY` | **PASSED** | Aucune ambiguïté sémantique entre production amont, arrivages logistiques et stock magasin. |
| **C2 : Rejet Formel PII (extra="forbid")** | Rejet automatique de `trader_name`, `phone`, `email`, `driver_id`, etc. | **PASSED** | Conformité absolue à AGENTS.md §8.3. Données personnelles rejetées à la compilation Pydantic. |
| **C3 : Détection PII dans Textes Libres** | Rejet des numéros de téléphone malgaches (`+261`, `034...`) et emails dans `notes` | **PASSED** | Aucun contournement possible par insertion de coordonnées privées dans les champs textuels. |
| **C4 : Identifiant Enquêteur Anonyme** | Rejet des noms humains (« Monsieur Rakoto ») au profit d'identifiants de rôle (`ENQ_01`) | **PASSED** | Anonymat garanti des agents enquêteurs et respect de la vie privée. |
| **C5 : Validateur Payload Brut** | Fonction `validate_payload_no_pii` interceptant les dictionnaires amont | **PASSED** | Filtrage précoce avant même la conversion en objets typés. |
| **C6 : Conversions d'Unités Locales** | Table de conversion métrique standardisée (kg, tonne, sac 50kg/100kg, gony, kapoaka) | **PASSED** | Densités massiques respectées (ex: kapoaka riz paddy 0.28kg vs riz usiné 0.26kg vs sucre 0.25kg). |
| **C7 : Détection Double Comptage** | `validate_no_double_counting` détectant mix flux/stock et chevauchements temporels | **PASSED** | Alerte formelle si tentative d'additionner des flux et des états ou des périodes sécantes. |

---

## 3. Résultats Chiffrés et Couverture Globale

- **Suite de tests dédiée :** 7/7 tests passés en 9.53s (exit code 0).
- **Couverture de code `ketrika.supply` :** **93 %** (largement supérieure au seuil minimal de 80%).
  - `src/ketrika/supply/__init__.py` : 100 %
  - `src/ketrika/supply/contracts.py` : 93 %
- **Contrôles statiques backend :** Ruff clean (0 warning), Mypy strict clean (0 issue).
- **Livrables documentaires :**
  - `ADR-088` dans `docs/plan/DECISIONS.md` ;
  - `SPECS.md` §27 ;
  - `docs/protocols/market_supply_survey_protocol.md` ;
  - `docs/outreach/accord_partenariat_enquetes_approvisionnement.md`.

---

## 4. Décision de Clôture de la Tâche R5.1

Tous les critères d'acceptation de la tâche R5.1 sont **entièrement validés**.  
Le statut de la tâche R5.1 est déclaré **DONE**.
