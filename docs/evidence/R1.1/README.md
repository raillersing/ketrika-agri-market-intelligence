# Dossier de preuve R1.1 : Requalification du registre et permissions

## 1. Contexte et Objectifs

La tâche **R1.1** s'inscrit dans le programme de requalification R0–R6 de Ketrika Agri Market Intelligence.
Elle porte sur la requalification formelle du registre des sources (`registry/sources.yaml`), des modèles Pydantic (`backend/src/ketrika/core/models/source.py`), de la documentation de chaque source (`docs/sources/*.md`) et des contrats de permissions / légalité selon les règles **C1**, **C3** et **AGENTS §8**.

### Règles appliquées :
- **Règle C1 (Permissions et légalité) :** Chaque source doit disposer d'un statut juridique vérifié (licence ouverte ou droit public d'accès), d'un robots.txt vérifié, d'une classe PII nulle (`none`), et d'un drapeau explicite `verified: bool` sur chaque URL d'entrée. Tout accès refusé (ex: 403 persistant sur HDX) entraîne l'arrêt sans contournement (`status: disabled` ou `degraded`).
- **Règle C3 (Ségrégation des familles de sources / anti-fuite) :** Pour empêcher qu'une source modélisée ou imputée (ex. World Bank RTFP) ne vienne confirmer artificiellement une source d'origine (ex. WFP HDX), chaque source déclare un champ obligatoire `source_family`. WFP HDX est assigné à `un_wfp` et World Bank RTFP est assignée à `world_bank`.
- **Règle Cadences distinctes (R1.1) :** La cadence unique ambiguë est décomposée en trois cadences explicites :
  - `collection_cadence` : fréquence d'exécution technique du robot collecteur.
  - `observation_cadence` : granularité temporelle des observations contenues dans les données.
  - `publication_cadence` : fréquence de mise à disposition des documents par l'émetteur.

---

## 2. Matrice de requalification des 10 sources du registre

| ID Source | Nom officiel | Famille (`source_family`) | Cadences (Col / Obs / Pub) | Statut | Verified | PII Class | Licence / Droits |
|---|---|---|---|---|---|---|---|
| `instat_nipc` | INSTAT Madagascar (NIPC) | `madagascar_gov` | monthly / monthly / monthly | active | True | none | Données publiques officielles gouvernementales |
| `miasa_odr` | MiASA Observatoire du Riz | `madagascar_gov` | weekly / weekly / weekly | active | True | none | Données publiques officielles gouvernementales |
| `mincc_ppn` | MinCC Relevés Prix & Stocks | `madagascar_gov` | weekly / daily / weekly | active | True | none | Données publiques officielles gouvernementales |
| `douanes_stats` | Douanes Malagasy Statistiques | `madagascar_gov` | monthly / monthly / monthly | active | True | none | Données publiques officielles gouvernementales |
| `faostat` | FAOSTAT Statistiques Madagascar | `un_fao` | monthly / annual / annual | active | True | none | CC BY-NC-SA 3.0 IGO |
| `wb_rtfp_mdg` | World Bank Real-Time Food Prices | `world_bank` | monthly / monthly / monthly | active | True | none | CC BY 4.0 |
| `wfp_hdx_mdg` | WFP Food Prices Madagascar | `un_wfp` | monthly / monthly / monthly | disabled | False | none | CC BY-IGO (403 Cloudflare persistant, B-R009) |
| `chc_chirps_dekad` | UCSB CHIRPS Dérivé Décadaire | `chc_ucsb` | monthly / monthly / monthly | planned | True | none | Public Domain / CC0 |
| `nasa_power_daily` | NASA POWER Daily Agroclimatology | `nasa` | daily / daily / daily | planned | False | none | US Public Domain (Robots.txt B-R010) |
| `ocha_codab_mdg` | OCHA Subnational Boundaries | `un_ocha` | static / static / static | active | False | none | CC BY-IGO (HDX direct 403, fixture éprouvée) |

---

## 3. Preuves d'exécution et de validation

### 3.1 Validation du registre (`validate_registry`)
- Commande :
  ```bash
  python -m ketrika.core.registry
  ```
- Résultat :
  ```text
  Ketrika Registry Validator
  --------------------------
  Registry is valid! Successfully verified 10 sources:
    - instat_nipc: INSTAT Madagascar - Indice des Prix à la Consommation (active, monthly)
    - miasa_odr: MiASA Observatoire du Riz (ODR) (active, weekly)
    - mincc_ppn: MinCC - Relevés Prix & Stocks PPN (active, weekly)
    - douanes_stats: Douanes Malagasy - Statistiques Commerce Extérieur (active, monthly)
    - faostat: FAOSTAT - Statistiques Agricoles Madagascar (active, monthly)
    - wb_rtfp_mdg: World Bank Real-Time Food Prices - Madagascar (active, monthly)
    - wfp_hdx_mdg: WFP Food Prices - Madagascar (disabled, monthly)
    - chc_chirps_dekad: UCSB CHIRPS - Précipitations décadaires (planned, monthly)
    - nasa_power_daily: NASA POWER - Agroclimatologie quotidienne (planned, daily)
    - ocha_codab_mdg: OCHA Madagascar - Découpage Administratif COD-AB (active, static)
  ```
- Statut : 0 erreur, 10/10 sources valides avec documentation et fixtures conformes.

### 3.2 Tests unitaires de conformité du registre
- Commande :
  ```bash
  pytest -v tests/unit/test_registry_conformance.py
  ```
- Résultat :
  ```text
  tests/unit/test_registry_conformance.py::test_registry_file_validates_without_errors PASSED [ 16%]
  tests/unit/test_registry_conformance.py::test_all_sources_define_source_family PASSED [ 33%]
  tests/unit/test_registry_conformance.py::test_all_sources_define_distinct_cadences PASSED [ 50%]
  tests/unit/test_registry_conformance.py::test_all_entrypoints_define_verified_flag PASSED [ 66%]
  tests/unit/test_registry_conformance.py::test_reject_forbidden_extra_fields PASSED [ 83%]
  tests/unit/test_registry_conformance.py::test_reject_direct_pii_in_registry PASSED [100%]
  ====== 6 passed in 28.85s ======
  ```

### 3.3 Linting & Type-checking strict
- Ruff :
  ```bash
  ruff check src/ketrika/core/models/source.py src/ketrika/core/registry.py tests/unit/test_registry_conformance.py
  # Output: All checks passed!
  ```
- Mypy :
  ```bash
  mypy src/ketrika/core/models/source.py src/ketrika/core/registry.py tests/unit/test_registry_conformance.py
  # Output: Success: no issues found in 3 source files
  ```

---

## 4. Garanties de non-régression et isolement
- Aucune mutation de la base de qualification active (`ketrika-qualification-*`).
- Travail cantonné au worktree isolé `/home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep`.
- Pas de modification de code partagé ou d'Alembic migrations.
