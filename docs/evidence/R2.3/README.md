# Preuve de qualification R2.3 — Qualification DQ, agrégations, alignement calendaire et indépendance des familles

**Date :** 2026-10-16  
**Tâche :** R2.3 — Qualifier DQ, agrégations et indépendance  
**Statut :** **DONE** (Vues Gold et moteur DQ mis en conformité, alignement calendaire exact sans LAG naïf, indépendance des familles C3 anti-fuite WFP/RTFP, gardes bloquants DQ, dénominateurs de publication avec invariant strict, 59/59 tests d'audit et couverture à 95%, 114 tests de non-régression verts, ruff, mypy et tsc 100% conformes)

---

## 1. Contexte et objectifs de la qualification

La tâche **R2.3** consolide la couche Gold analytique et le moteur de qualité des données (DQ) selon les exigences normatives de SPECS §14, §15, §16 et du contrat C3 :

1. **Alignement calendaire réel des variations de prix (élimination du LAG naïf) :**
   - Remplacement des fonctions de fenêtrage `LAG(median_price, 1/3/12)` dans `gold.price_changes` et `gold.cpi_food` par des jointures gauches sur dates calendaires exactes `(b.month - INTERVAL '1 month')::date`, `INTERVAL '3 months'`, et `INTERVAL '12 months'`.
   - En cas de trou de mois (gap historique), la variation est strictement `NULL`, interdisant tout calcul erroné de variation mensuelle sur un intervalle plurimensuel.
2. **Indépendance des familles et anti-corrobation fallacieuse (Contrat C3) :**
   - Intégration de `source_family` dans les vues `gold.price_obs_current`, `gold.price_monthly` et `gold.price_monthly_best`.
   - Traçabilité de la dérivation : la Banque mondiale (WB RTFP) s'appuyant sur les données primaires du PAM (WFP HDX), ces deux flux sont reconnus comme partageant la racine `un_wfp` et ne peuvent pas être comptabilisés comme deux corroborations indépendantes.
   - Exposition du nombre de familles distinctes `n_families` aux côtés du nombre de sources `n_sources`.
3. **Détection de conflit et préservation de la dispersion :**
   - Détection des conflits de prix entre sources concurrentes sur un même produit × lieu × mois (`has_conflict = true` dès lors que le ratio max/min dépasse 1.25).
   - Préservation des métriques de dispersion (`price_spread`, `stddev_price`, `group_spread`) pour ne jamais masquer les divergences réelles de marché.
4. **Arbitrage strict de priorité : observé > imputé :**
   - L'observation empirique prime systématiquement sur une valeur imputée ou estimée, quel que soit le niveau de priorité de la source (P0 observé > P1 observé > P0 imputé > P1 imputé > P2).
5. **Score Market Health normatif et seuil de couverture (SPECS §16) :**
   - Composantes de Stabilité (0.30), Abordabilité (0.25), Disponibilité (0.25), et Climat (0.20).
   - Si les données d'une composante sont absentes, son score est strictement `NULL` (jamais de remplacement par 0 ou 100).
   - Règle normative : si `coverage < 0.50`, le score composite `market_health_score` est obligatoirement `NULL`.
6. **Porte bloquante DQ et publication atomique (SPECS §14) :**
   - Implémentation de `check_blocking_dq_gate` : refus catégorique de publication (`GoldDqRejected`) si la provenance est incomplète (< 100%), si le taux d'extraction est dégradé (< 99%), ou si une observation LLM non vérifiée pénètre dans Gold (`llm_unverified_in_gold > 0`).
7. **Dénominateurs de publication cohérents et invariants mathématiques :**
   - Publication explicite des dénominateurs dans le bilan de rafraîchissement avec vérification de l'invariant strict :
     $$\text{candidate\_rows} = \text{accepted\_rows} + \text{rejected\_rows} + \text{review\_rows}$$
     $$\text{candidate\_files} = \text{parsed\_files} + \text{failed\_files} + \text{review\_files} + \text{pending\_files}$$

---

## 2. Fichiers modifiés et créés

- **Définitions SQL des vues Gold :**
  - `backend/src/ketrika/gold/sql/001_price_obs_current.sql` : ajout de la colonne `source_family`.
  - `backend/src/ketrika/gold/sql/002_price_monthly.sql` : ajout de `source_family`, métriques de dispersion `price_spread` et `stddev_price`.
  - `backend/src/ketrika/gold/sql/003_price_monthly_best.sql` : intégration de `group_stats`, calcul de `n_sources`, `n_families`, détection de divergence `has_conflict`, `group_spread`, et priorité absolue des données observées.
  - `backend/src/ketrika/gold/sql/004_price_changes.sql` : élimination des LAG naïfs, jointures gauches sur intervalles calendaires exacts `(month - INTERVAL '1/3/12 months')::date`.
  - `backend/src/ketrika/gold/sql/009_cpi_food.sql` : alignement calendaire exact sur mois $t-1$ et $t-12$ pour les indices alimentaires.
  - `backend/src/ketrika/gold/sql/010_market_health.sql` : scores de composantes strictement `NULL` en cas d'absence, respect du seuil normatif `coverage >= 0.50`.
- **Moteur KPI et contrôles Data Quality (Python) :**
  - `backend/src/ketrika/gold/kpi.py` : fonction `calculate_calendar_aligned_variation` et helper `audit_source_family_independence`.
  - `backend/src/ketrika/gold/dq.py` : ajout de `GoldDqRejected`, `PublicationDenominators` (avec validation d'invariant), `check_llm_unverified_in_gold`, `get_publication_denominators`, et `check_blocking_dq_gate`.
  - `backend/src/ketrika/gold/refresh.py` : appel systématique de `check_blocking_dq_gate` avant publication Gold et intégration des dénominateurs dans le rapport de publication.
  - `backend/src/ketrika/gold/__init__.py` : exportations des nouvelles fonctions et exceptions normatives.
  - `backend/tests/e2e_data/synthetic_gold_dataset.py` : enrichissement des définitions de sources avec `source_family`.
- **Suite de qualification dédiée :**
  - `backend/tests/unit/test_gold_dq_aggregation_audit.py` : 29 tests unitaires, scénarios de qualification et tests property-based (Hypothesis).

---

## 3. Résultats des tests et métriques de validation

### 3.1 Suite d'audit et couverture (59/59 passés, 95% de couverture)

Commande exécutée dans le conteneur Docker `ketrika-backend:dev` :
```bash
docker run --rm -v /home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep:/workspace -w /workspace/backend ketrika-backend:dev uv run pytest -v tests/unit/test_gold_dq_aggregation_audit.py tests/unit/test_gold_kpi.py tests/unit/test_taxonomy_units_audit.py --cov=ketrika.gold.kpi --cov=ketrika.gold.dq --cov=ketrika.core.aggregation --cov-report=term-missing
```

Résultats :
```text
================================ tests coverage ================================
Name                              Stmts   Miss  Cover   Missing
---------------------------------------------------------------
src/ketrika/core/aggregation.py      89      5    94%   84, 160, 164, 168, 179
src/ketrika/gold/dq.py              160      8    95%   184-191, 257-259, 268-270
src/ketrika/gold/kpi.py             149      8    95%   81-83, 116, 119-122
---------------------------------------------------------------
TOTAL                               398     21    95%
============================= 59 passed in 51.15s ==============================
```

### 3.2 Contrôles statiques et typage

- **Ruff linter :**
  ```bash
  docker run --rm -v /home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep:/workspace -w /workspace/backend ketrika-backend:dev uv run ruff check src/ketrika/gold tests/unit/test_gold_dq_aggregation_audit.py
  # Sortie : All checks passed! (code 0)
  ```
- **Mypy typechecker :**
  ```bash
  docker run --rm -v /home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep:/workspace -w /workspace/backend ketrika-backend:dev uv run mypy src/ketrika/gold/dq.py src/ketrika/gold/kpi.py src/ketrika/gold/refresh.py src/ketrika/gold/__init__.py tests/unit/test_gold_dq_aggregation_audit.py
  # Sortie : Success: no issues found in 5 source files (code 0)
  ```
- **TypeScript frontend :**
  ```bash
  docker exec aiagent-web-1 pnpm typecheck
  # Sortie : tsc --noEmit (code 0)
  ```

### 3.3 Suite de non-régression (114/114 passés)

Commande exécutée dans Docker :
```bash
docker run --rm -v /home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep:/workspace -w /workspace/backend ketrika-backend:dev uv run pytest -v tests/unit/test_gold_dq_aggregation_audit.py tests/unit/test_gold_kpi.py tests/unit/test_taxonomy_units_audit.py tests/unit/test_taxonomy.py tests/unit/test_units.py tests/unit/test_registry.py tests/unit/test_registry_conformance.py tests/unit/test_price_loader.py
# Sortie : 114 passed in 38.14s (code 0)
```

---

## 4. Bilan et critères d'acceptation R2.3

| Critère d'acceptation R2.3 | Statut | Preuve |
|---|---|---|
| Fixtures de trou de mois : variation MoM = NULL si mois manquant | **VALIDÉ** | `test_calendar_aligned_variation_returns_null_on_month_gap` |
| Fixture de duplication WFP / RTFP et indépendance des familles (C3) | **VALIDÉ** | `test_source_family_independence_wfp_and_rtfp_not_independent` |
| Conflit de prix et dispersion préservée (spread, ratio >= 1.25) | **VALIDÉ** | `test_price_conflict_detection_and_dispersion_metrics` |
| Arbitrage priorité : observé > imputé systématiquement | **VALIDÉ** | `test_priority_arbitration_observed_vs_imputed` |
| Incomparabilité (devises, unités, acteurs, indices) rejetée | **VALIDÉ** | `test_incomparable_aggregation_guards` |
| Market Health : composantes disponibles + coverage < 0.50 => NULL | **VALIDÉ** | `test_market_health_coverage_threshold_and_components` |
| DQ bloquant empêche publication (`GoldDqRejected`) | **VALIDÉ** | `test_blocking_dq_gate_refuses_when_*` |
| Dénominateurs cohérents : candidate = accepted + rejected + review | **VALIDÉ** | `test_publication_denominators_valid_invariant` |
| 100% indicateurs reliés à observations et transformations | **VALIDÉ** | Vues Gold matérialisées auditées et liées aux clés primaires |
| Couverture des modules Gold et Core >= 80 % | **VALIDÉ** | **95 %** (398 statements, 21 manquantes) |
