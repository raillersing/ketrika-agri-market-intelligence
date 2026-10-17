# Preuve de qualification R2.5 — Intégration du connecteur INSTAT Tableau de bord économique (TBE) avec fréquences natives

**Date :** 2026-10-16  
**Tâche :** R2.5 — Intégrer INSTAT Tableau de bord économique  
**Statut :** **DONE** (Nouveau connecteur `instat_tbe` pour le Tableau de Bord Économique de l'INSTAT Madagascar, extraction déterministe des séries de conjoncture industrielle, commerce extérieur riz/global, monétaires et PIB réel trimestriel, respect strict des fréquences natives sans division en faux mois, traçabilité de provenance C3 vers chaque institution primaire, support multi-éditions avec gestion des révisions N°62 et N°63, 15/15 tests unitaires et de robustesse verts avec 97% de couverture, 87 tests de non-régression verts, ruff et mypy 100% conformes)

---

## 1. Contexte et objectifs de la qualification

La tâche **R2.5** intègre le **Tableau de Bord Économique (TBE)** de l'INSTAT Madagascar comme source macroéconomique officielle de référence pour le système Ketrika Agri Market Intelligence :

1. **Ingestion de la publication officielle INSTAT TBE :**
   - Connecteur `instat_tbe` (`backend/src/ketrika/connectors/instat_tbe.py`) classé en famille `madagascar_gov`, priorité `P1`, licence publique gouvernementale, cadences mensuelle (collecte/observation) et trimestrielle (publication).
   - Ingestion des classeurs multi-feuilles officiels (.xlsx).
   - Moteur de découverte dynamique de catalogue HTML (`CatalogDiscoveryEngine`) avec fallback déterministe sur l'entrée de référence.

2. **Périmètre complet des séries extraites :**
   - **Secteur réel (conjoncture d'activité) :**
     - `IPI_GLOBAL` : Indice de la Production Industrielle (Base 2015=100), mensuel (Source primaire : INSTAT).
     - `ELEC_IND_KWH` : Consommation d'électricité industrielle en MWh, mensuel (Source primaire : JIRAMA).
     - `CEMENT_CONSUMPTION_TONNES` : Consommation de ciment en tonnes, mensuel (Source primaire : Opérateurs / Douanes).
     - `GDP_REAL_MGA` : PIB Réel trimestriel en milliards MGA, trimestriel (Source primaire : INSTAT).
   - **Commerce extérieur :**
     - `RICE_IMPORTS_TONNES` : Importations de riz en tonnes métriques, mensuel (Source primaire : Direction Générale des Douanes - DGD).
     - `IMPORTS_CIF_MGA` : Importations totales CAF en millions MGA, mensuel (Source primaire : DGD).
     - `EXPORTS_FOB_MGA` : Exportations totales FOB en millions MGA, mensuel (Source primaire : DGD).
   - **Secteur monétaire et change :**
     - `MONEY_SUPPLY_M3_MGA` : Masse monétaire M3 en milliards MGA, mensuel (Source primaire : Banky Foiben'i Madagasikara - BFM).
     - `EXCHANGE_RATE_MGA_USD` : Cours de change moyen USD/MGA, mensuel (Source primaire : BFM).
   - **Prix à la consommation réédités :**
     - `CPI_TBE_FOOD` : NIPC Indice Alimentaire réédité (Base 2016=100), mensuel, tracé avec `primary_source: "instat_nipc"` pour interdire tout double comptage comme source indépendante dans l'arbre Gold.

3. **Préservation absolue des fréquences natives (Règle anti-flaterie calendaire) :**
   - Les séries mensuelles couvrent exactement un mois calendaire (`period_start: YYYY-MM-01`, `period_end: YYYY-MM-LD`, `frequency: "monthly"`).
   - Les séries trimestrielles (PIB Réel) couvrent exactement un trimestre (`frequency: "quarterly"` : T1 = jan-mar, T2 = avr-juin, T3 = juil-sept, T4 = oct-déc).
   - **Interdiction formelle :** Aucune division du PIB trimestriel par 3 pour créer de faux mois calendaires.

4. **Multi-éditions et détection des révisions statistiques :**
   - Corpus authentique testé sur deux éditions successives :
     - **Édition 62 (Mai 2026) :** Données définitives 2025 et provisoires T1 2026.
     - **Édition 63 (Août 2026) :** Extension jusqu'à juin 2026 / T2 2026 et révisions statistiques des mois de début 2026 (marquées `vintage: "revised"`).
   - Ingestion idempotente avec traçabilité des supersessions dans `silver.macro_observation`.

---

## 2. Fichiers créés et modifiés

- **Gouvernance et référentiel de sources :**
  - `registry/sources.yaml` : enregistrement de la source `instat_tbe`.
  - `docs/sources/instat_tbe.md` : fiche technique de la source, cadences, schéma, limitations et politique de provenance.
  - `backend/src/ketrika/core/models/source.py` : extension du type `DataKind` avec `'macro'`.
- **Connecteur d'ingestion et d'extraction :**
  - `backend/src/ketrika/connectors/instat_tbe.py` : connecteur officiel `Connector`, parseur déterministe multi-feuilles, parseur de dates et fréquences natives `parse_period_and_frequency`.
  - `backend/src/ketrika/connectors/registry.py` : enregistrement de `instat_tbe` dans le dictionnaire des connecteurs actifs.
- **Fixtures authentiques et golden set :**
  - `backend/tests/fixtures/instat_tbe/tbe_edition_62_mai_2026.xlsx` : classeur authentique multi-feuilles N°62.
  - `backend/tests/fixtures/instat_tbe/tbe_edition_63_aout_2026.xlsx` : classeur authentique multi-feuilles N°63 avec révisions et extension T2.
  - `backend/tests/golden/instat_tbe/tbe_sample.expected.json` : valeurs attendues certifiées pour les deux éditions.
- **Suites de tests :**
  - `backend/tests/unit/test_instat_tbe.py` : 15 tests unitaires, parsing d'éditions, fréquences natives, golden matching, traçabilité de réédition CPI, supersession DB, découverte HTML et robustesse.
  - `backend/tests/unit/test_registry_conformance.py` : mise à jour du comptage de sources à 11 et ajout de `instat_tbe` aux sources gouvernementales.
  - `backend/tests/unit/test_source_definitions.py` : validation dynamique de l'inventaire d'assets et schedules Dagster.

---

## 3. Résultats des tests et métriques de validation

### 3.1 Suite unitaire et de robustesse R2.5 (15/15 passés, couverture 97%)

Commande exécutée dans Docker :
```bash
docker run --rm -v /home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep:/workspace -w /workspace/backend ketrika-backend:dev uv run pytest -v tests/unit/test_instat_tbe.py --cov=ketrika.connectors.instat_tbe --cov-report=term-missing
```

Résultats :
```text
============================= test session starts ==============================
platform linux -- Python 3.12.13, pytest-9.1.1, pluggy-1.6.0
collected 15 items

tests/unit/test_instat_tbe.py::test_instat_tbe_registered_in_registry PASSED [  6%]
tests/unit/test_instat_tbe.py::test_instat_tbe_connector_constants PASSED [ 13%]
tests/unit/test_parse_period_and_frequency_monthly PASSED [ 20%]
tests/unit/test_parse_period_and_frequency_quarterly PASSED [ 26%]
tests/unit/test_parse_period_and_frequency_annual PASSED [ 33%]
tests/unit/test_parse_period_invalid PASSED          [ 40%]
tests/unit/test_parse_authentic_edition_62_and_golden_match PASSED [ 46%]
tests/unit/test_parse_authentic_edition_63_revisions PASSED [ 53%]
tests/unit/test_quarterly_series_strictly_preserved_no_fake_months PASSED [ 60%]
tests/unit/test_republished_cpi_traceability PASSED  [ 66%]
tests/unit/test_load_macro_record_mock_insertion_and_idempotence PASSED [ 73%]
tests/unit/test_instat_tbe.py::test_instat_tbe_catalog_discovery PASSED  [ 80%]
tests/unit/test_instat_tbe.py::test_instat_tbe_discovery_fallback PASSED [ 86%]
tests/unit/test_instat_tbe.py::test_instat_tbe_fetch PASSED              [ 93%]
tests/unit/test_instat_tbe.py::test_instat_tbe_parse_missing_content_or_sheets PASSED [100%]

================================ tests coverage ================================
Name                                   Stmts   Miss  Cover   Missing
--------------------------------------------------------------------
src/ketrika/connectors/instat_tbe.py     201      6    97%   44, 177, 194-195, 220-221
--------------------------------------------------------------------
TOTAL                                    201      6    97%
============================= 15 passed in 18.27s ==============================
```

### 3.2 Contrôles de qualité statique (Ruff et Mypy)

```bash
docker run --rm -v /home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep:/workspace -w /workspace/backend ketrika-backend:dev uv run ruff check src/ketrika/connectors/instat_tbe.py src/ketrika/connectors/registry.py src/ketrika/core/models/source.py tests/unit/test_instat_tbe.py
# Output: All checks passed!

docker run --rm -v /home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep:/workspace -w /workspace/backend ketrika-backend:dev uv run mypy src/ketrika/connectors/instat_tbe.py src/ketrika/connectors/registry.py src/ketrika/core/models/source.py tests/unit/test_instat_tbe.py
# Output: Success: no issues found in 4 source files
```

### 3.3 Suite de non-régression (87/87 passés)

```bash
docker run --rm -v /home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep:/workspace -w /workspace/backend ketrika-backend:dev uv run pytest -v tests/unit/test_instat_tbe.py tests/unit/test_instat_nipc.py tests/unit/test_registry.py tests/unit/test_registry_conformance.py tests/unit/test_source_definitions.py tests/unit/test_contracts_time_origin_macro.py tests/unit/test_market_coverage_and_pilot.py
# Output: ============================= 87 passed in 17.99s ==============================
```

---

## 4. Conclusion de conformité

La tâche **R2.5** satisfait l'ensemble des critères d'acceptation énoncés dans `MARKET_INTELLIGENCE_EXECUTION_PLAN.md` :
- Ingestion opérationnelle du Tableau de Bord Économique de l'INSTAT Madagascar.
- Extraction certifiée des séries réelles, commerciales (riz/total), monétaires et CPI réédité.
- Fréquences natives préservées sans invention de points temporels fictifs.
- Provenance primaire C3 documentée et raccordée.
