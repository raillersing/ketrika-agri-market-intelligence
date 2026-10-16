# Qualification Evidence — R2.10 : Livrer les vues marché et économie

## 1. Contexte et Objectifs

La tâche **R2.10** (« Livrer les vues marché et économie ») concrétise l'interface utilisateur pour la restitution des données de marché et de conjoncture macroéconomique conformément à **ADR-070**, **ADR-072** et **SPECS §22** :
1. Mise en place de l'**Observatoire Économique & Conjoncture** (`web/src/app/economy/page.tsx`, route `/economy`) articulé autour de 5 dimensions autonomes sans score synthétique global inventé.
2. Intégration des **14 fiches métriques normatives** (définition, formule, lag de publication, limitations).
3. Panneau de **contexte de transmission sur le pilote rizicole** (mise en regard de l'inflation alimentaire NIPC, de la variation des prix vivriers au kilo, du coût unitaire CAF d'importation et du ratio de dépendance).
4. Enrichissement de l'**Explorateur des prix** (`web/src/app/prices/page.tsx`) avec un panneau d'audit de complétude et de lacunes calendaires (`/v1/market/coverage/gaps`).
5. Présence systématique des badges de nature (`ValueKindBadge`), des badges de source (`SourceBadge`) et des liens de provenance (`ProvenanceLink` vers `/observations/[id]`).
6. Conformité mobile responsive (largeur $\ge 390\text{ px}$) et accessibilité WCAG AA.

---

## 2. Décisions Architecturales (ADR-072)

- **ADR-072** adopté et consigné dans `docs/plan/DECISIONS.md`.
- Spécifications §22 mises à jour dans `docs/plan/SPECS.md`.
- Lien de navigation ajouté dans `web/src/components/layout/Sidebar.tsx` sous la section « Marché & Cours ».

---

## 3. Résultats et Métriques de Qualification

### A. Typage statique et linting frontend

Commandes exécutées :
```bash
docker run --rm -v ... -w /app ketrika-web:dev npm run typecheck
docker run --rm -v ... -w /app ketrika-web:dev npm run lint
docker run --rm -v ... -w /app ketrika-web:dev npm run build
```

Résultats :
- **TypeScript (`tsc --noEmit`)** : Exit 0, 0 erreur.
- **ESLint (`next lint`)** : Exit 0 (`✔ No ESLint warnings or errors`).
- **Next.js Production Build (`next build`)** : Exit 0, 16/16 routes générées avec succès dont `/economy` (5.94 kB).

### B. Tests unitaires frontend (Vitest)

Commande exécutée :
```bash
docker run --rm -v ... -w /app ketrika-web:dev npm run test
```

Résultat :
```
Test Files  5 passed (5)
     Tests  39 passed (39)
```

Fichiers de tests passés :
- `src/smoke.test.ts` (1 test)
- `src/lib/formatters.test.ts` (14 tests)
- `src/qa-runner.test.js` (15 tests)
- `src/proxy.test.ts` (5 tests)
- `src/economy.test.ts` (4 tests)

### C. Extension E2E Playwright et Responsive 390px

- Script `scripts/qa-e2e.py` étendu avec :
  - Navigation authentifiée vers `/economy`
  - Validation du rendu de l'Observatoire Économique et de l'indicateur ADR-070
  - Capture d'écran desktop `economy.png`
  - Validation du viewport mobile 390px (`economy_mobile_390px.png`)
  - Capture d'écran et validation de l'explorateur des prix (`prices.png`)

### D. Suite de non-régression globale backend

Commande exécutée :
```bash
docker run --rm -v ... -w /workspace/backend ketrika-backend:dev uv run pytest -v \
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
============================= 143 passed in 49.46s =============================
```

---

## 4. Bilan fonctionnel des vues livrées

| Vue | Route | Contenu & Gardes R2.10 | Rôle |
|---|---|---|---|
| **Observatoire Économique** | `/economy` | 5 dimensions étanches (inflation, devises, carburants administrés, commerce, activité réelle), 14 fiches métriques normatives repliables, contexte pilote rizicole, bouton d'export CSV, gestion explicite des raisons nulles | client |
| **Explorateur des Prix** | `/prices` | Séries temporelles, dispersion, tableau, export CSV, panneau d'audit de couverture (`coverage_ratio`, continuité mois, mois manquants, familles de sources indépendantes) | client |
| **Barre de Navigation** | Global | Intégration de l'Observatoire Économique dans la section « Marché & Cours » avec icône `BarChart3` | client |
