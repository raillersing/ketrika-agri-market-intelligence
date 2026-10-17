# Preuve de qualification R2.2 — Audit de la taxonomie, des unités, des grains et des gardes de comparabilité

**Date :** 2026-10-16  
**Tâche :** R2.2 — Auditer taxonomie, unités et grains  
**Statut :** **DONE** (Taxonomie auditée, conversions avec preuves empiriques, gardes physiques massique/volumique, gardes d'agrégation Gold, file de revue des alias < 0.90, 38/38 tests verts, 90% couverture core, 99 tests de non-régression verts)

---

## 1. Contexte et objectifs de la qualification

La tâche **R2.2** consolide l'intégrité taxonomique, physique et mathématique de la plateforme Ketrika Agri Market Intelligence :
1. **Audit des conversions contre documents réels :**
   - Vérification de toutes les unités contre documents empiriques (ODR, INSTAT, CIRAD, MiASA).
   - Calibrage des densités spécifiques par produit pour le *kapoaka* (riz blanc local: 285 g, riz blanc importé: 280 g, paddy: 220 g, maïs grain: 260 g, haricots secs: 280 g).
   - Statut `uncertain` et exclusion des prix comparables pour les conditionnements non calibrés (*gony* sac indéfini confiance 0.50, *daba* manioc confiance 0.70).
2. **Distinction stricte des grains, qualités et acteurs :**
   - Séparation absolue entre riz paddy (*akotry*, SH 1006.10, FAOSTAT 27), riz blanc local (*vary gasy*, SH 1006.30) et riz blanc importé (*vary vahiny*, SH 1006.30).
   - Les variétés botaniques (Makalioka, Tsipala, Vary mena, X265, Rojofotsy, Rojomena, Botry, Imported 25%) constituent des attributs qualitatifs (`variety`), sans collision avec les codes produits.
   - Les acteurs économiques (`retail`, `wholesale`, `farmgate`, `producer`, `official_ppn`, `listing`, `unknown`) et conditionnements (`sac_50kg`, `kapoaka`, `bouteille_1l`) sont rigoureusement distingués dans la clé naturelle et l'agrégation.
3. **Garde d'alias et file de revue (seuil >= 0.90) :**
   - Tout alias avec confiance >= 0.90 possède obligatoirement une preuve vérifiable (`evidence`).
   - Tout alias vernaculaire avec confiance < 0.90 est orienté vers la file de revue (`review_status = 'pending'`), et son prix comparable (`price_mga_per_base`) est exclu (NULL) tant qu'une validation humaine n'a pas eu lieu.
4. **Interdiction des conversions massiques/volumiques sans densité prouvée :**
   - Toute tentative de conversion d'un produit solide (ex: riz en litres) ou liquide (ex: huile en kg) sans densité spécifique explicite est systématiquement refusée (`status = 'uncertain'`, valeur `None`).
5. **Codes SH et FAOSTAT versionnés :**
   - Vérification que tous les codes SH6 (6 chiffres) et FAOSTAT (entiers > 0) sont valides et documentés.
6. **Gardes d'agrégation Gold :**
   - Interdiction absolue de moyenner des devises différentes (ex: MGA vs USD ou FMG) sans conversion préalable.
   - Interdiction de moyenner des unités physiques hétérogènes (ex: kg et l).
   - Interdiction de moyenner des indices (ex: NIPC INSTAT base 100) avec des prix nominaux en Ariary.
   - Interdiction de moyenner des niveaux d'acteurs économiques incompatibles (ex: bord champ *farmgate* et détail *retail*) sans partitionnement explicite.
   - Préservation stricte : ni `ND` ni valeur manquante ne sont remplacées par zéro ou une valeur par défaut.

---

## 2. Implémentations techniques

- **Taxonomie et alias :**
  - `taxonomy/aliases.yaml` : ajout de notes explicites de désambiguïsation contextuelle pour tous les alias vernaculaires à confiance < 0.90.
  - `backend/src/ketrika/core/taxonomy.py` : renforcement de `validate_taxonomy` avec validation stricte des unités de base (kg/l), codes SH6 (6 chiffres), FAOSTAT (> 0), séparation riz/paddy, intégrité des variétés et preuves d'alias.
- **Unités physiques et conversions :**
  - `backend/src/ketrika/core/units.py` : ajout dans `convert_to_base` et `convert_from_base` du contrôle de compatibilité entre la dimension de l'unité et la `base_unit` du produit (refus des conversions massiques/volumiques sans densité prouvée).
  - Renforcement de `validate_units` avec contrôles des cohérences massiques/volumiques, facteurs positifs et preuves obligatoires.
- **Pipeline de normalisation :**
  - `backend/src/ketrika/normalize/units.py` : sécurisation de `UnitConverter` contre les conversions cross-dimensionnelles non calibrées.
  - `backend/src/ketrika/normalize/price_loader.py` : émission systématique d'issues `unqualified_alias` et `unqualified_location_alias` pour toute résolution avec confiance < 0.90, marquant `review_status = 'pending'` et excluant le prix comparable.
- **Gardes d'agrégation Gold :**
  - `backend/src/ketrika/core/aggregation.py` : module dédié implémentant `IncompatibleAggregationError`, `ComparablePriceItem`, `validate_comparable_group`, `filter_comparable_items`, `compute_safe_arithmetic_average` et `compute_safe_weighted_average`.
- **Suite de tests d'audit :**
  - `backend/tests/unit/test_taxonomy_units_audit.py` : 24 tests unitaires et property-based tests (Hypothesis) couvrant l'ensemble des exigences de la tâche.

---

## 3. Résultats des tests et métriques de validation

### 3.1 Tests de la suite d'audit et couverture (38/38 passés)

Commande exécutée dans le conteneur Docker `ketrika-backend:dev` :
```bash
docker run --rm -v /home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep:/workspace -w /workspace/backend ketrika-backend:dev uv run pytest -v tests/unit/test_taxonomy_units_audit.py tests/unit/test_taxonomy.py tests/unit/test_units.py --cov=ketrika.core.taxonomy --cov=ketrika.core.units --cov=ketrika.core.aggregation --cov-report=term-missing
```

Résultats :
```text
tests/unit/test_taxonomy_units_audit.py::test_production_taxonomy_passes_strict_audit PASSED [  2%]
tests/unit/test_taxonomy_units_audit.py::test_core_ppn_catalog_conformance PASSED [  5%]
tests/unit/test_taxonomy_units_audit.py::test_strict_rice_vs_paddy_vs_variety_separation PASSED [  7%]
tests/unit/test_taxonomy_units_audit.py::test_alias_evidence_and_review_note_integrity PASSED [ 10%]
tests/unit/test_taxonomy_units_audit.py::test_validate_taxonomy_detects_defects PASSED [ 13%]
tests/unit/test_taxonomy_units_audit.py::test_production_units_pass_strict_audit PASSED [ 15%]
tests/unit/test_taxonomy_units_audit.py::test_mass_volume_cross_conversion_refused_without_density PASSED [ 18%]
tests/unit/test_taxonomy_units_audit.py::test_calibrated_density_kapoaka_conversions PASSED [ 21%]
tests/unit/test_taxonomy_units_audit.py::test_uncalibrated_units_excluded_from_comparable PASSED [ 23%]
tests/unit/test_taxonomy_units_audit.py::test_mass_inverse_conversions_exact PASSED [ 26%]
tests/unit/test_taxonomy_units_audit.py::test_volume_inverse_conversions_exact PASSED [ 28%]
tests/unit/test_taxonomy_units_audit.py::test_numeric_parsing_french_malagasy_formats PASSED [ 31%]
tests/unit/test_taxonomy_units_audit.py::test_missing_values_never_default_to_zero PASSED [ 34%]
tests/unit/test_taxonomy_units_audit.py::test_aggregation_guard_refuses_mixed_currencies PASSED [ 36%]
tests/unit/test_taxonomy_units_audit.py::test_aggregation_guard_refuses_mixed_base_units PASSED [ 39%]
tests/unit/test_taxonomy_units_audit.py::test_aggregation_guard_refuses_mixing_index_and_price PASSED [ 42%]
tests/unit/test_taxonomy_units_audit.py::test_aggregation_guard_refuses_unsegmented_actor_levels PASSED [ 44%]
tests/unit/test_taxonomy_units_audit.py::test_aggregation_safe_averaging_computations PASSED [ 47%]
tests/unit/test_taxonomy_units_audit.py::test_alias_below_90_directed_to_review_and_excluded_from_comparable PASSED [ 50%]
tests/unit/test_taxonomy_units_audit.py::test_canonical_product_with_high_confidence_is_accepted PASSED [ 52%]
tests/unit/test_taxonomy_units_audit.py::test_validate_taxonomy_catches_all_defects PASSED [ 55%]
tests/unit/test_taxonomy_units_audit.py::test_validate_units_catches_all_defects PASSED [ 57%]
tests/unit/test_taxonomy_units_audit.py::test_get_unit_and_conversion_exceptions PASSED [ 60%]
tests/unit/test_taxonomy_units_audit.py::test_aggregation_guards_additional_invariants PASSED [ 63%]
tests/unit/test_taxonomy.py::test_validate_taxonomy_has_no_errors PASSED [ 65%]
tests/unit/test_taxonomy.py::test_products_catalog_contains_core_ppn PASSED [ 68%]
tests/unit/test_taxonomy.py::test_get_product_success_and_failure PASSED [ 71%]
tests/unit/test_taxonomy.py::test_rice_varieties_loaded PASSED           [ 73%]
tests/unit/test_taxonomy.py::test_all_fixture_commodity_labels_are_resolved PASSED [ 76%]
tests/unit/test_taxonomy.py::test_resolve_canonical_product_codes_and_names PASSED [ 78%]
tests/unit/test_taxonomy.py::test_normalize_string_special_chars PASSED  [ 81%]
tests/unit/test_units.py::test_validate_units_has_no_errors PASSED       [ 84%]
tests/unit/test_units.py::test_no_conversion_ge_80_without_evidence PASSED [ 86%]
tests/unit/test_units.py::test_fixture_units_are_all_present PASSED      [ 89%]
tests/unit/test_units.py::test_kapoaka_conversions PASSED                [ 92%]
tests/unit/test_units.py::test_uncertain_conversions_return_none_value PASSED [ 94%]
tests/unit/test_units.py::test_inverse_conversions_are_consistent PASSED [ 97%]
tests/unit/test_units.py::test_product_specific_kapoaka_inverse_consistency PASSED [100%]

Name                              Stmts   Miss  Cover   Missing
---------------------------------------------------------------
src/ketrika/core/aggregation.py      89      5    94%   84, 157, 161, 165, 176
src/ketrika/core/taxonomy.py        138     18    87%   26, 41, 47, 57, 63, 73, 79, 111, 117-118, 145-146, 150-151, 155-156, 183, 235
src/ketrika/core/units.py           126     12    90%   59, 65, 123-124, 178-179, 183, 190, 193, 205-206, 240
---------------------------------------------------------------
TOTAL                               353     35    90%
============================= 38 passed in 56.45s ==============================
```

### 3.2 Tests de non-régression (99/99 passés)

Exécution conjointe des suites unitaires et de chargement :
- `tests/unit/test_taxonomy_units_audit.py`
- `tests/unit/test_taxonomy.py`
- `tests/unit/test_units.py`
- `tests/unit/test_price_loader.py`
- `tests/unit/test_contracts_time_origin_macro.py`
- `tests/unit/test_weather_provenance.py`
- `tests/unit/test_instat_nipc.py`
Résultat : **99 tests exécutés et réussis** en 34.06s (0 échec, 0 skip).

### 3.3 Contrôles statiques et frontend

- **Ruff :** 0 erreur, 0 avertissement (`Found 0 errors`).
- **Mypy :** Succès sur les 6 fichiers modifiés (`Success: no issues found in 6 source files`).
- **TypeScript Web :** `tsc --noEmit` exécuté avec code 0 (0 erreur de compilation).

---

## 4. Matrice de conformité aux critères d'acceptation R2.2

| Critère R2.2 | Résultat | Justification / Preuve |
|---|---|---|
| **Conversions vérifiées contre documents réels** | Conforme | Preuves documentées ODR/INSTAT/CIRAD/MiASA pour toutes les conversions >= 0.80 |
| **Distinction riz / paddy / qualité** | Conforme | Séparation stricte `RICE_PADDY` (1006.10), `RICE_WHITE_LOCAL` (1006.30), `RICE_WHITE_IMPORTED` (1006.30) et variétés dans `rice_varieties.yaml` |
| **Distinction acteur, conditionnement, produit** | Conforme | Dimensions autonomes dans la clé naturelle et gardes d'agrégation Gold |
| **Aliases >= 0.90 seulement avec preuve** | Conforme | Vérifié par `validate_taxonomy` ; absence de preuve interdite |
| **Aliases < 0.90 en file de revue** | Conforme | Émission d'issue `unqualified_alias` et exclusion de `price_mga_per_base` |
| **Codes HS6 et FAOSTAT vérifiés et versionnés** | Conforme | Formats validés (HS6 = 6 chiffres, FAOSTAT > 0) sur les 15 produits PPN |
| **Interdiction moyenne devises/unités/indices/acteurs** | Conforme | `validate_comparable_group` lève `IncompatibleAggregationError` |
| **Refus conversions massiques/volumiques sans densité** | Conforme | `convert_to_base` et `UnitConverter` renvoient `None` et statut `uncertain` |
| **Propriétés d'inversion mathématique vertes** | Conforme | Tests Hypothesis validés sur l'ensemble des plages d'unités de masse et volume |
| **Formats numériques et gestion ND** | Conforme | Formats français/malagasy parsés ; ND et inconnus renvoient `None`, jamais 0 |

---

## 5. Statut de qualification

- **Audit taxonomie et unités :** **QUALIFIED**
- **Gardes d'agrégation et comparabilité :** **QUALIFIED**
- **Intégrité et non-régression :** **QUALIFIED**
- **Statut global R2.2 :** **DONE**
