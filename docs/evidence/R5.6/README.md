# Dossier de Preuve — R5.6 : Bilan d'Offre sans Double Comptage et Conservation de Masse

## 1. Contexte & Périmètre de Qualification

- **Tâche :** R5.6 (MUST — Construire un bilan d'offre sans double comptage).
- **Date d'exécution :** 2026-10-17T10:55:00Z.
- **Environnement :** Conteneurs Docker isolés `ketrika-backend:dev`, worktree `/home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep`, branche `work/r1-sources-prep`.
- **Référence normative :** `AGENTS.md` §1, §3, §4 (Règles 1 provenance totale, 8 brut conservé, 9 observé ≠ imputé ≠ prévu), §10 ; `MARKET_INTELLIGENCE_EXECUTION_PLAN.md` §10 (R5.6) ; `SPECS.md` §27 ; `ADR-092`.
- **Objectif :**
  1. Modéliser l'équation physique de conservation de masse du bilan d'approvisionnement :
     $$\text{Stock}_{\text{fin}} = \text{Stock}_{\text{début}} + \text{Entrées} - \text{Sorties} - \text{Ventes} - \text{Pertes}$$
  2. Empêcher formellement le double comptage entre statistiques douanières nationales (`trade_flow` au port) et arrivages physiques de marché (`inflow_arrival` en gros).
  3. Isoler rigoureusement les stocks statiques d'inventaire (`stock_inventory`) qui ne doivent jamais s'additionner aux flux d'arrivages périodiques.
  4. Appliquer le principe métrologique d'honnêteté : **un composant inconnu reste inconnu** (si les pertes ou les ventes informelles au détail ne sont pas observées, elles restent `None`, interdisant de présenter un bilan partiel comme un fait complet).
  5. Distinguer formellement le **Bilan Observé Partiel** (`observed_partial`) fondé à 100% sur des faits vérifiés et le **Scénario de Simulation** (`scenario_simulation`) paramétré avec des hypothèses explicites versionnées.

---

## 2. Synthèse d'Exécution des Critères d'Acceptation R5.6 (`test_supply_balance_engine.py`)

| Critère | Périmètre Qualifié | Résultat du Test | Constat Métrologique |
|---|---|---|---|
| **C1 : Conservation de Masse sur Cas Analytique** | Simulation bilan 10 jours (stock initial 100t, arrivages 300t, ventes 250t, pertes 15t) | **PASSED** | Conservation exacte : stock final théorique 135t, écart = 0.0 kg (`mass_conservation_holds=True`). |
| **C2 : Honnêteté Métrologique (Inconnu = Inconnu)** | Bilan Anosibe sans enquête sur les ventes de détail ni les pertes | **PASSED** | Ventes et pertes restent strictement `None` (`is_observed=False`). Statut `has_unobserved_terms=True`, type `observed_partial`. Zéro chiffre inventé. |
| **C3 : Prévention Collision Douanes vs Marché** | Tentative de sommation simultanée d'imports portuaires (25 000 t) et arrivages Anosibe (50 t) | **PASSED** | Alerte `DOUBLE_COUNT_HAZARD` levée. Les flux portuaires ne sont pas sommés dans les entrées du marché urbain (arrivages maintenus à 50 t). |
| **C4 : Séparation Stricte Stocks vs Flux** | Relevé mixte stock 200 t + arrivage 30 t à Anosibe | **PASSED** | Arrivages périodiques = 30 t. Le stock d'inventaire de 200 t n'est jamais additionné aux entrées. |
| **C5 : Validation sur Corpus Réel ODR Anosibe 2024** | Données authentiques ODR mai 2024 (semaine 1 et semaine 2 riz vary gasy) | **PASSED** | Semaine 1 : arrivages 180 t, stock fin 450 t. Semaine 2 : stock initial 450 t, arrivages 210 t, stock fin 520 t ($\Delta \text{Stock} = +70\text{ t}$). Bilan empirique cohérent. |

---

## 3. Résultats Chiffrés et Couverture Globale

- **Suite de tests dédiée :** 5/5 tests passés en 19.65s (exit code 0).
- **Suite cumulée R5 :** 30/30 tests passés (100% verts).
- **Couverture de code sur le lot :**
  - `src/ketrika/supply/balance.py` : **95 %**
  - Total package `ketrika.supply` : **92 %** (largement supérieur aux 80% requis).
- **Contrôles statiques backend :**
  - Ruff check : All checks passed (0 warning).
  - Mypy strict check : Success: no issues found in 2 source files.
- **Livrables d'architecture et de code :**
  - `ADR-092` dans `docs/plan/DECISIONS.md` ;
  - Module `backend/src/ketrika/supply/balance.py` ;
  - Export dans `backend/src/ketrika/supply/__init__.py`.

---

## 4. Décision de Clôture de la Tâche R5.6

Tous les critères d'acceptation de la tâche R5.6 sont **entièrement validés**.  
Le statut de la tâche R5.6 est déclaré **DONE**.
