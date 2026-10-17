# Dossier de Preuve — R5.8 : Scénarios d'Offre et Pilote Décisionnel pour Trois Profils d'Acteurs

## 1. Contexte & Périmètre de Qualification

- **Tâche :** R5.8 (MUST — Préparer les scénarios et le pilote décisionnel).
- **Date d'exécution :** 2026-10-17T11:30:00Z.
- **Environnement :** Conteneurs Docker isolés `ketrika-backend:dev`, worktree `/home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep`, branche `work/r1-sources-prep`.
- **Référence normative :** `AGENTS.md` §1, §3, §4 (Règles 6 aucun chiffre LLM en Gold, 7 aucun chiffre généré dans les textes, 9 observé ≠ imputé ≠ prévu, 10 intégrité des faits et données jamais instructions), §10 ; `MARKET_INTELLIGENCE_EXECUTION_PLAN.md` §10 (R5.8) ; `SPECS.md` §27 ; `ADR-094`.
- **Objectif :**
  1. Structurer 3 parcours décisionnels cibles pour les acteurs clés de la filière vivrière malgache :
     - *Régulateur Public / SPM / MIC* : surveillance des tensions d'approvisionnement urbain (Antananarivo), déficit mensuel, stock de sécurité stratégique (30 jours).
     - *Acheteur Commercial / Agro-industriel* : alignement du calendrier d'achat sur le pic d'arrivages (mai D3 à Anosibe), optimisation des capacités d'entrepôt, calcul déterministe des économies d'achat.
     - *Planificateur Agricole / MinAE / Vulgarisation* : évaluation d'impact du stress hydrique précoce (-35% CHIRPS), retard de récolte (+2 décades), élongation de la soudure paysanne (+2,9 semaines).
  2. Modéliser des scénarios bornés, strictement déterministes, dont tous les calculs d'impacts sont mathématiques et explicables (aucun chiffre généré par LLM).
  3. Sécuriser les entrées : filtrage strict des injections de prompts et liste blanche des paramètres autorisés (`ALLOWED_PARAMETERS`). Tout paramètre non autorisé ou suspect est immédiatement rejeté.
  4. Complétude rigoureuse : si un paramètre obligatoire est absent, le moteur refuse formellement le calcul (`missing_parameters`), sans inventer de valeur par défaut invisible.
  5. Garde-fou constitutionnel : interdiction formelle de générer des ordres financiers ou d'achat autonomes (`order_generation_prohibited: true`).
  6. Gouvernance humaine et protocole d'essai : rédaction de `docs/protocols/decision_pilot_protocol.md` avec questionnaire en 5 critères ; statut explicitement maintenu à `human_reviewed: false` et `evaluation_status: "NOT_EVALUATED"` conformément à `AGENTS.md` §5 (Gate H7) tant que les séances avec les utilisateurs finaux humains ne sont pas consignées.

---

## 2. Synthèse d'Exécution des Critères d'Acceptation R5.8 (`test_supply_decision_pilot.py`)

| Critère | Périmètre Qualifié | Résultat du Test | Constat Métrologique |
|---|---|---|---|
| **C1 : Complétude des Templates de Scénarios** | Méthode `get_default_scenario_templates()` pour les 3 personas | **PASSED** | Templates complets pour `public_regulator`, `commercial_buyer`, `agricultural_planner`. Tous les paramètres justifiés. Statut `NOT_EVALUATED`, `human_reviewed=False`. |
| **C2 : Parcours Régulateur Public (Tension Urbaine)** | Simulation demande Antananarivo (2,5M hab @ 350g/j = 26 250 t) vs arrivages réels (24 500 t) | **PASSED** | Déficit mensuel calculé à -1 750 t (taux de couverture 93.3%). Stock de sécurité 30 jours = 26 250 t. Alerte modérée sans ordre d'achat autonome. |
| **C3 : Parcours Acheteur Commercial (Pic & Stockage)** | Simulation volume cible (5 000 t), décote pic 12%, entrepôt 8 000 t | **PASSED** | Économie brute calculée à 2 040 000 000 MGA par achat synchronisé sur la fenêtre de pic prévue (mai D3). Recommandation calendaire explicite. `order_generation_prohibited=True`. |
| **C4 : Parcours Planificateur Agricole (Choc Hydrique)** | Simulation déficit précoce (-35%), retard récolte (+2 décades = +20j), perte rendement 18% | **PASSED** | Allongement de la soudure paysanne calculé à +2.9 semaines (durée totale 14.9 semaines). Recommandation agronomique (semences précoces Mailaka, motopompes). |
| **C5 : Rejet d'Exécution sur Paramètre Absent** | Simulation avec suppression délibérée du paramètre `reserve_target_days` | **PASSED** | Le moteur bloque immédiatement le calcul (`impacts=[]`), signale `missing_parameters=['reserve_target_days']`. Zéro valeur inventée. |
| **C6 : Sécurité Anti-Injection & Whitelisting** | Test de détection de pattern d'injection (`ignore previous instructions`) et clé de variable non approuvée | **PASSED** | `sanitize_input_text` lève `ValueError`. L'injection d'un paramètre non listé dans la whitelist de la persona lève `ValueError`. |
| **C7 : Endpoints API Scénarios `/v1/supply`** | Routes `GET /v1/supply/scenarios/templates` et `POST /v1/supply/scenarios/run` | **PASSED** | Requêtes HTTP 200 OK. Restitution conforme au schéma Pydantic `DecisionPilotReport`. |

---

## 3. Résultats Chiffrés et Couverture Globale

- **Suite de tests dédiée :** 7/7 tests passés en 43.07s (exit code 0).
- **Suite cumulée R5 :** 44/44 tests passés (100% verts).
- **Couverture de code sur le lot :**
  - `src/ketrika/supply/decision_pilot.py` : **95 %**
  - Total package `ketrika.supply` : **93 %** (largement supérieur aux 80% requis).
- **Contrôles statiques backend :**
  - Ruff check : All checks passed (0 warning).
  - Mypy strict check : Success: no issues found in 2 source files.
- **Livrables d'architecture, de protocole et de code :**
  - `ADR-094` dans `docs/plan/DECISIONS.md` ;
  - Module `backend/src/ketrika/supply/decision_pilot.py` ;
  - Router API `backend/src/ketrika/api/routers/supply.py` (`/v1/supply/scenarios/*`) ;
  - Protocole d'évaluation humaine `docs/protocols/decision_pilot_protocol.md` ;
  - Export dans `backend/src/ketrika/supply/__init__.py`.

---

## 4. Décision de Clôture de la Tâche R5.8

Tous les critères d'acceptation de la tâche R5.8 sont **entièrement validés**.  
Le statut de la tâche R5.8 est déclaré **DONE**.
