# Dossier de Preuve — R5.7 : Prévision des Fenêtres d'Approvisionnement et des Pics d'Arrivages

## 1. Contexte & Périmètre de Qualification

- **Tâche :** R5.7 (MUST — Prévoir les fenêtres d'approvisionnement et leurs pics).
- **Date d'exécution :** 2026-10-17T11:15:00Z.
- **Environnement :** Conteneurs Docker isolés `ketrika-backend:dev`, worktree `/home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep`, branche `work/r1-sources-prep`.
- **Référence normative :** `AGENTS.md` §1, §3, §4 (Règles 1 provenance totale, 8 brut conservé, 9 observé ≠ imputé ≠ prévu, 10 intégrité des faits), §10 ; `MARKET_INTELLIGENCE_EXECUTION_PLAN.md` §10 (R5.7) ; `SPECS.md` §27 ; `ADR-093`.
- **Objectif :**
  1. Modéliser la prévision des fenêtres d'approvisionnement et des pics d'arrivages sur les marchés vivriers de gros (ex: Anosibe, Antananarivo).
  2. Imposer un découpage temporel décadaire agronomique rigoureux (D1: 1-10, D2: 11-20, D3: 21-fin de mois).
  3. Intégrer le décalage logistique $\tau_{\text{logistique}} \in [1, 2]$ décades entre la récolte dans le bassin de production (Alaotra, Marovoay, Vakinankaratra) et les arrivages physiques sur le marché terminal de gros (séchage, usinage paddy $\to$ riz blanc, chargement et transport).
  4. Réutiliser les contrôles temporels as-of stricts (cloisonnement chronologique, aucune fuite du futur).
  5. Appliquer la règle métrologique d'honnêteté sur les données insuffisantes : **au moins deux cycles complets d'arrivages réels observés sont exigés pour calibrer un modèle saisonnier empirique**. Si l'historique d'observations réelles couvre moins de deux cycles complets, le système refuse de simuler de fausses années d'entraînement et classe obligatoirement la prévision en `experimental_baseline` ou `abstained_insufficient_history` avec note d'incertitude qualitative explicite.
  6. Déduire les labels de pics d'offre **exclusivement des tonnages physiques réels**, jamais d'un minimum sur la courbe de prix (décorrélation fréquente en raison des stocks spéculatifs ou coûts de transport).
  7. Évaluer la prévision de manière indépendante sur les arrivages réels ODR Anosibe mai 2024 (erreur de calage en décades/jours et taux de couverture du volume de campagne).
  8. Exposer l'API `/v1/supply/peak-forecast` et `/v1/supply/sufficiency`.

---

## 2. Synthèse d'Exécution des Critères d'Acceptation R5.7 (`test_supply_peak_forecast.py`)

| Critère | Périmètre Qualifié | Résultat du Test | Constat Métrologique |
|---|---|---|---|
| **C1 : Arithmétique & Résolution Décadaire** | Fonctions `parse_dekad_label`, `date_to_dekad_label`, `dekad_difference` | **PASSED** | Résolution décadaire agronomique certifiée. Zéro date fictive au jour près inventée. |
| **C2 : Décalage Logistique Récolte $\to$ Marché** | Projection riz Alaotra $\to$ Anosibe avec $\tau_{\text{logistique}} = +1$ décade | **PASSED** | Fenêtre nominale (mai D1 - juin D3, pic mai D2) translatée exactement en fenêtre de marché (mai D2 - juillet D1, pic prévu mai D3). Dates limites exactes. |
| **C3 : Critère d'Historique Suffisant ($\ge 2$ cycles)** | Évaluation du nombre de cycles complets couverts par les relevés | **PASSED** | Échantillon pilote 45j (< 1 cycle) $\implies$ `is_sufficient=False`, abstention documentée. Échantillon 800j (2.19 cycles) $\implies$ `is_sufficient=True`. |
| **C4 : Cloisonnement As-Of & Abstention Honnête** | Coupure temporelle stricte à la date d'as-of `2024-05-01` | **PASSED** | Relevé ultérieur du 20 mai exclu du calcul d'as-of. Qualification `experimental_baseline` et note d'abstention explicite. Zéro fuite de données futures. |
| **C5 : Pic Dérivé Exclusivement des Quantités Physiques** | Détection de pic sur série Anosibe avec corrélation inverse de prix | **PASSED** | Pic détecté au 15 mai (250 t) où le prix était élevé (3 400 MGA), et non au 28 mai (20 t) où le prix était au plus bas (2 800 MGA). Zéro inférence trompeuse prix/volume. |
| **C6 : Confrontation Empirique Indépendante ODR 2024** | Évaluation de la prévision contre les flux réels d'arrivages ODR Anosibe mai 2024 | **PASSED** | Pic prévu en mai D3 coïncide exactement avec le pic observé (280 t le 23 mai, D3) : erreur = 0 décade (`exact_match`). 100% du volume observé (610 t) couvert par la fenêtre. |
| **C7 : Endpoints API `/v1/supply`** | Routes `/v1/supply/peak-forecast` et `/v1/supply/sufficiency` | **PASSED** | Requêtes HTTP GET fonctionnelles, réponse JSON conforme au schéma Pydantic, isolation complète avec mock DB. |

---

## 3. Résultats Chiffrés et Couverture Globale

- **Suite de tests dédiée :** 7/7 tests passés en 32.71s (exit code 0).
- **Suite cumulée R5 :** 37/37 tests passés (100% verts).
- **Couverture de code sur le lot :**
  - `src/ketrika/supply/peak_forecast.py` : **90 %**
  - `src/ketrika/api/routers/supply.py` : **77 %**
  - Total package `ketrika.supply` : **92 %** (largement supérieur aux 80% requis).
- **Contrôles statiques backend :**
  - Ruff check : All checks passed (0 warning).
  - Mypy strict check : Success: no issues found in 2 source files.
- **Livrables d'architecture et de code :**
  - `ADR-093` dans `docs/plan/DECISIONS.md` ;
  - Module `backend/src/ketrika/supply/peak_forecast.py` ;
  - Router API `backend/src/ketrika/api/routers/supply.py` et intégration dans `main.py` ;
  - Export dans `backend/src/ketrika/supply/__init__.py`.

---

## 4. Décision de Clôture de la Tâche R5.7

Tous les critères d'acceptation de la tâche R5.7 sont **entièrement validés**.  
Le statut de la tâche R5.7 est déclaré **DONE**.
