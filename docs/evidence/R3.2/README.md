# Dossier de Preuve — R3.2 : Datasets historiques as-of (C2/C4, traçabilité temporelle et partitionnement sans fuite)

## 1. Contexte & Périmètre

- **Tâche :** R3.2 (Phase R3 — Prévisions de prix évaluées et honnêtes).
- **Date d'exécution :** 2026-10-16T16:15:00Z.
- **Environnement :** Conteneurs Docker isolés `ketrika-backend:dev` et `ketrika-web:dev`, worktree `/home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep`, branche `work/r1-sources-prep`.
- **Référence normative :** `AGENTS.md`, `MARKET_INTELLIGENCE_EXECUTION_PLAN.md` §8 (R3.2), `SPECS.md` §17.2, `ADR-004`, `ADR-074`.
- **Objectif :** Implémenter le constructeur de datasets d'évaluation et d'apprentissage selon la sémantique as-of (C2/C4), garantir la traçabilité temporelle stricte et l'absence totale de fuite vers le futur (data leakage), résoudre les versions d'enregistrements en point-in-time avec gestion des révisions (`superseded_by`), calculer l'empreinte SHA-256 canonique immuable de chaque split, et cloisonner les splits train/calibration/test sur des fenêtres calendaires disjointes sans duplication ni chevauchement d'identifiants.

---

## 2. Décisions d'Architecture & Règles Normatives (ADR-074)

1. **Intégrité temporelle stricte (C2/C4) :**
   Un enregistrement n'est éligible à un instant $T$ (`as_of`) que si et seulement si toutes les conditions de disponibilité temporelle sont vérifiées :
   $$\text{ingested\_at} \le T \quad \land \quad (\text{published\_at} \text{ is None} \lor \text{published\_at} \le T) \quad \land \quad (\text{first\_available\_at} \text{ is None} \lor \text{first\_available\_at} \le T)$$
   Toute observation publiée après `as_of` (même si la période observée $t$ est antérieure) est strictement inaccessible à l'instant $T$.

2. **Résolution des révisions en Point-in-Time :**
   Les observations révisées disposent d'un pointeur `superseded_by`.
   - Si la révision n'existait pas encore à l'instant $T$ ($\text{ingested\_at}_{\text{revision}} > T$), la version initiale reste active et visible à cet instant.
   - Dès que $\text{ingested\_at}_{\text{revision}} \le T$, la nouvelle version supplante la version précédente qui devient obsolète.
   - Une chaîne de révisions est résolue de manière déterministe en sélectionnant la dernière version ingérée avant ou à $T$.

3. **Partitionnement sans fuite (train / calibration / test) :**
   - Les données sont partitionnées selon des bornes calendaires temporelles strictes :
     - `train` : $t < T_{\text{train\_end}}$
     - `calibration` : $T_{\text{train\_end}} \le t < T_{\text{test\_start}}$
     - `test` : $T_{\text{test\_start}} \le t \le T_{\text{test\_end}}$
   - L'intersection des identifiants d'enregistrements entre chaque split est rigoureusement vide :
     $$\text{ids}(\text{train}) \cap \text{ids}(\text{calibration}) = \emptyset, \quad \text{ids}(\text{train}) \cap \text{ids}(\text{test}) = \emptyset, \quad \text{ids}(\text{calibration}) \cap \text{ids}(\text{test}) = \emptyset$$

4. **Empreinte SHA-256 Canonique :**
   Chaque split dispose d'une empreinte cryptographique unique et déterministe basée sur le tuple trié de ses identifiants d'observations canoniques :
   $$\text{fingerprint} = \text{SHA-256}\left(\sum_{i} \text{record\_id}_i + \text{period}_i + \text{price}_i\right)$$
   Deux générations avec les mêmes paramètres temporels et les mêmes données sources produisent rigoureusement la même empreinte.

5. **Exclusion des séries non qualifiées :**
   Intégration native avec `SeriesEligibilityReport` (R3.1) : seules les séries validées sont incluses dans les splits d'évaluation.

---

## 3. Résultats et Preuves d'Exécution

### 3.1 Tests Unitaires Dédiés R3.2 (`test_ml_as_of_dataset.py`)

- **Commande :** `uv run pytest tests/unit/test_ml_as_of_dataset.py tests/unit/test_ml_series_eligibility.py tests/unit/test_ml_forecast.py tests/unit/test_ml_anomalies.py -m "not integration" -v --cov=ketrika.ml --cov-report=term-missing`
- **Résultat :** 29/29 tests passés en 41.80s (exit code 0).
- **Couverture de code sur `ketrika.ml.dataset` :** **92%** (185 statements, 14 missed).
- **Couverture globale `ketrika.ml` :** **84%** (770 statements, 120 missed).

Détail des 8 cas d'acceptation validés pour R3.2 :
1. `test_anti_leakage_future_publication_excluded` : exclusion stricte des publications futures (prix de janvier publié en mars absent du dataset de février).
2. `test_historical_revision_exclusion_and_point_in_time_preservation` : résolution point-in-time des révisions (révision d'avril exclue en mars, version historique conservée).
3. `test_deterministic_recomputation_identical_fingerprint` : recalcul déterministe avec calcul d'empreinte SHA-256 canonique identique sous permutation.
4. `test_no_unknown_uuids_and_artefacts_lineage` : zéro UUID inconnu, lignée d'artefacts et provenance vérifiée.
5. `test_exogenous_variables_aligned_as_of` : alignement temporel as-of strict pour les variables exogènes (aucune variable future accessible).
6. `test_leak_free_partitioning_splits` : partitionnement sans fuite (train, calibration, test disjoints temporellement, intersection des IDs vide).
7. `test_cohort_filtering_pure_observed_vs_mixed` : séparation étanche des cohortes observées pures vs mixtes.
8. `test_as_of_dataset_with_mock_session_sql` : extraction as-of SQL complète via `extract_as_of_observations`.

### 3.2 Contrôle de Qualité Statique (Linter & Types)

- **Ruff :** `uv run ruff check src/ketrika/ml/dataset.py tests/unit/test_ml_as_of_dataset.py` -> 0 erreur, 0 avertissement.
- **Mypy :** `uv run mypy src/ketrika/ml/dataset.py tests/unit/test_ml_as_of_dataset.py` -> Success: no issues found in 2 source files.

---

## 4. Conclusion & Qualification R3.2

La tâche R3.2 est intégralement complétée, testée et documentée en conformité stricte avec `AGENTS.md` et `MARKET_INTELLIGENCE_EXECUTION_PLAN.md`.
