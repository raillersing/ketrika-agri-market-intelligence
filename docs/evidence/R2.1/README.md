# Preuve de qualification R2.1 — Formalisation des contrats temps, origine et macroéconomie

**Date :** 2026-10-15  
**Tâche :** R2.1 — Formaliser les contrats temps, origine et macroéconomie  
**Statut :** **DONE** (ADR-069, SPECS §8/§19, MacroObservation, C1–C4, migration 0011, API /v1/macro, 6/6 tests verts, couverture 98%, 0 régression)

---

## 1. Contexte et objectifs de la qualification

La tâche **R2.1** ouvre la **Phase R2 (Qualité et observatoire marché/économie)** en formalisant les règles d'intégrité temporelle, la traçabilité d'origine et l'intégration des agrégats macroéconomiques nécessaires à l'aide à la décision :
1. **Séparation des grains et table macroéconomique additive :**
   - Interdiction formelle de détourner `obs.price_observation` ou `obs.cpi_observation` pour y stocker des variables macroéconomiques générales (PIB, taux de change BCM, agrégats monétaires, balances commerciales).
   - Création de la table additive `obs.macro_observation` (ADR-069, SPECS §8) avec indicateur, granularité, unité, vintage, base de référence et périmètre géographique.
2. **Contrats C1–C4 unifiés :**
   - **C1 (Acquisition & Authenticité) :** chaque objet Bronze et observation conserve son URL source, son sha256 vérifié et son niveau d'authenticité (`authentic | synthetic | unverified`).
   - **C2 (Temps, Disponibilité & Révisions) :** distinction obligatoire entre la période observée (`period_start`, `period_end`), la date de publication (`published_at`), et la date de première disponibilité prouvée (`first_available_at`).
   - **Anti-leakage ML :** interdiction absolue d'antidater la disponibilité sur la simple date affichée dans un document ; en l'absence de preuve corroborée indépendante (log immuable ou archive externe), `first_available_at` prend conservativement la date de première collecte UTC (`fetched_at`).
   - **C3 (Sens métier & Famille de sources) :** distinction de `source_family` pour interdire la confirmation trompeuse d'indépendance entre sources dérivées (ex: RTFP et WFP) et préservation stricte de `observed_or_imputed`.
   - **C4 (Modèle & Évaluation) :** tout dataset de modélisation ou backtest est borné à `first_available_at <= evaluation_as_of`.
3. **Idempotence et append-only :**
   - Les révisions d'estimations macroéconomiques et météorologiques s'opèrent par insertion de nouvelle ligne et chaînage `superseded_by`, protégées par le trigger PostgreSQL `obs.check_obs_superseded_only()`.

---

## 2. Implémentations techniques

- **Décision d'architecture :** `ADR-069` enregistré dans `docs/plan/DECISIONS.md`.
- **Spécifications techniques :** Mise à jour de `docs/plan/SPECS.md` (§8 pour `obs.macro_observation` et §19 pour la route `GET /v1/macro`).
- **Modèles de données :**
  - Record Pydantic : `MacroRecord` dans `backend/src/ketrika/connectors/records.py`.
  - Modèle ORM SQLAlchemy : `MacroObservation` dans `backend/src/ketrika/core/models/db.py`.
  - Dispatcher et chargeur avec supersession : `load_macro_record_with_supersession` dans `backend/src/ketrika/connectors/runner.py`.
- **API REST :**
  - Schéma : `MacroItem` dans `backend/src/ketrika/api/schemas.py`.
  - Routeur : `backend/src/ketrika/api/routers/macro.py` (`GET /v1/macro`).
  - Enregistrement dans `backend/src/ketrika/api/main.py`.
- **Migration de base de données :**
  - `backend/alembic/versions/0011_macro_observation_and_time_contracts.py` avec trigger d'immuabilité et privilèges `ketrika_app` (R/W) et `copilot_ro` (SELECT).
- **Tests unitaires et de contrats :**
  - `backend/tests/unit/test_contracts_time_origin_macro.py`.

---

## 3. Résultats des tests et métriques de validation

### 3.1 Tests unitaires et de contrats R2.1 (6/6 passés)

Commande exécutée dans le conteneur Docker `ketrika-backend:dev` :
```bash
docker run --rm -v /home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep:/workspace -w /workspace/backend ketrika-backend:dev uv run pytest -v tests/unit/test_contracts_time_origin_macro.py --cov=ketrika.connectors.records --cov=ketrika.core.models.db --cov=ketrika.api.routers.macro --cov-report=term-missing
```

Résultats :
```text
tests/unit/test_contracts_time_origin_macro.py::test_macro_record_natural_key_determinism PASSED [ 16%]
tests/unit/test_contracts_time_origin_macro.py::test_macro_record_loader_insertion_and_idempotence PASSED [ 33%]
tests/unit/test_contract_c2_time_availability_conservative_fallback PASSED [ 50%]
tests/unit/test_macro_supersession_on_revised_value PASSED [ 66%]
tests/unit/test_non_regression_raw_price_and_weather_models PASSED [ 83%]
tests/unit/test_api_v1_macro_route_contract PASSED [100%]

Name                                Stmts   Miss  Cover
-------------------------------------------------------
src/ketrika/api/routers/macro.py       34      6    82%
src/ketrika/connectors/records.py     119      5    96%
src/ketrika/core/models/db.py         413      0   100%
-------------------------------------------------------
TOTAL                                 566     11    98%
============================== 6 passed in 37.32s ==============================
```

### 3.2 Tests de non-régression (58/58 passés)

Exécution des suites `test_weather_provenance.py`, `test_weather_migration.py`, `test_price_loader.py` et `test_instat_nipc.py` :
- **58 tests exécutés et réussis** en 10.13s.
- Préservation absolue des champs bruts (`price_raw`, `unit_raw`, `currency_raw`, `value_raw`).
- Aucune régression sur les tables `obs.price_observation`, `obs.weather_observation` et `obs.cpi_observation`.

### 3.3 Contrôles statiques et frontend

- **Ruff :** 0 erreur, 0 avertissement.
- **Mypy :** Succès sur les 6 fichiers modifiés (`Success: no issues found in 6 source files`).
- **TypeScript Web :** `tsc --noEmit` exécuté avec code 0 (0 erreur de compilation).

---

## 4. Synthèse des critères d'acceptation de la tâche R2.1

| Exigence R2.1 | Validation | Preuve |
|---|---|---|
| **ADR & SPECS avant code** | Conforme | ADR-069 consigné dans `DECISIONS.md` ; `SPECS.md` §8 et §19 mis à jour |
| **Contrats C1–C4 formalisés** | Conforme | Traçabilité source, non-antidatage de disponibilité, distinction de familles |
| **Extension additive Macro** | Conforme | Table `obs.macro_observation`, `MacroRecord`, `MacroObservation`, migration 0011 |
| **Non-régression des prix bruts** | Conforme | Historique et champs bruts `price_raw`, `currency_raw` 100% inchangés |
| **Idempotence & révisions météo** | Conforme | `superseded_by` sans mise à jour destructive ; 58 tests de non-régression verts |
| **Contrat API REST validé** | Conforme | `GET /v1/macro` avec filtres `indicator`, `geo_scope`, `vintage`, dates |
| **Rôles DB compatibles** | Conforme | Privilèges `ketrika_app` (R/W) et `copilot_ro` (SELECT seul) dans la migration |

---

## 5. Statut de qualification

- **Contrats temps et disponibilité C2 :** **QUALIFIED**
- **Schéma et modèle macroéconomique :** **QUALIFIED**
- **Intégrité et non-régression :** **QUALIFIED**
- **Statut global R2.1 :** **DONE**
