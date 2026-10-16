# Qualification Evidence — R2.9 : Exposer les données et leurs limites dans l'API

## 1. Contexte et Objectifs

La tâche **R2.9** (« Exposer les données et leurs limites dans l'API ») complète les endpoints de l'API de marché et macroéconomique selon **ADR-071** et **SPECS §19** :
1. Exposition exhaustive des métadonnées de qualité et de traçabilité (`observed_or_imputed`, `value_kind`, `first_available_at`, `published_at`, `sources`, `vintage`).
2. Pagination systématique (`limit` par défaut 100, borné à [1, 1000], `offset` par défaut 0, $\ge 0$).
3. Support de l'export CSV structuré (`format=json|csv`) pour `/v1/macro`, `/v1/market/coverage`, et `/v1/economic/indicators`.
4. Cohérence et synchronisation OpenAPI / TypeScript des contrats d'interface.
5. Protection stricte des routes d'administration `/v1/admin/*` contre les accès anonymes.

---

## 2. Décisions Architecturales (ADR-071)

- **ADR-071** consigné dans `docs/plan/DECISIONS.md`.
- Spécifications techniques documentées dans `docs/plan/SPECS.md` §19.
- Maintien strict de la conformité REST et des codes d'erreur RFC 7807 (422 en cas de borne de pagination hors limites).

---

## 3. Résultats et Métriques de Qualification

### A. Couverture des tests unitaires et de contrats API

Commande exécutée :
```bash
docker run --rm -v /home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep:/workspace -w /workspace/backend ketrika-backend:dev uv run pytest -v tests/unit/test_api_extensions_and_limits.py tests/unit/test_economic_dashboard.py --cov=ketrika.api.routers.macro --cov=ketrika.api.routers.coverage --cov=ketrika.api.routers.economic --cov-report=term-missing
```

Résultats :
```
Name                                  Stmts   Miss  Cover   Missing
-------------------------------------------------------------------
src/ketrika/api/routers/coverage.py      28      5    82%   92-98, 121-124
src/ketrika/api/routers/economic.py      87      4    95%   142-144, 156
src/ketrika/api/routers/macro.py         40      0   100%
-------------------------------------------------------------------
TOTAL                                   155      9    94%
============================= 25 passed in 29.01s ==============================
```

### B. Contrôles statiques et typage

- **Ruff** : `docker run --rm -v ... uv run ruff check src/ketrika/api/routers/ tests/unit/test_api_extensions_and_limits.py`
  - Résultat : `All checks passed!`
- **Mypy** : `docker run --rm -v ... uv run mypy src/ketrika/api/routers/macro.py src/ketrika/api/routers/coverage.py src/ketrika/api/routers/economic.py tests/unit/test_api_extensions_and_limits.py`
  - Résultat : `Success: no issues found in 4 source files`
- **TypeScript Web Frontend** : `docker run --rm -v .../web/src:/app/src -w /app ketrika-web:dev npm run typecheck`
  - Résultat : `tsc --noEmit` -> Code 0 (0 erreur de typage).

### C. Suite de non-régression

Commande exécutée :
```bash
docker run --rm -v /home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep:/workspace -w /workspace/backend ketrika-backend:dev uv run pytest -v \
  tests/unit/test_api_extensions_and_limits.py \
  tests/unit/test_economic_dashboard.py \
  tests/unit/test_omh_public.py \
  tests/unit/test_bfm_public.py \
  tests/unit/test_instat_tbe.py \
  tests/unit/test_instat_nipc.py \
  tests/unit/test_registry.py \
  tests/unit/test_registry_conformance.py \
  tests/unit/test_source_definitions.py \
  tests/unit/test_contracts_time_origin_macro.py \
  tests/unit/test_market_coverage_and_pilot.py
```
Résultat :
```
======================= 143 passed in 122.18s (0:02:02) ========================
```

---

## 4. Endpoints qualifiés

| Endpoint | Méthode | Paramètres pagination | Format | Traçabilité & Gardes |
|---|---|---|---|---|
| `/v1/macro` | GET | `limit` (1-1000), `offset` ($\ge 0$) | `json`, `csv` | `observed_or_imputed`, `vintage`, `first_available_at`, `published_at`, `sources` |
| `/v1/market/coverage` | GET | `limit` (1-1000), `offset` ($\ge 0$) | `json`, `csv` | Matrice produit x région x mois, `n_sources`, `imputed_share`, `age_days` |
| `/v1/economic/indicators` | GET | `limit` (1-1000), `offset` ($\ge 0$) | `json`, `csv` | Catalogue normatif des 14 fiches ADR-070 avec formules et limites |
| `/v1/admin/*` | ALL | N/A | JSON | Non public, authentification requise (`require_role("admin")`) -> 401/403 |
