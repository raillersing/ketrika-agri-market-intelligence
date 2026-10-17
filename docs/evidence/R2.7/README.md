# Preuve de qualification R2.7 — Intégration du connecteur Office Malgache des Hydrocarbures (OMH Public)

**Date :** 2026-10-16  
**Tâche :** R2.7 — Intégrer carburants OMH et événements réglementaires  
**Statut :** **DONE** (Nouveau connecteur `omh_public` pour les barèmes officiels et communiqués de révision tarifaire de l'Office Malgache des Hydrocarbures, distinction rigoureuse des prix plafonds réglementés à la pompe `is_administered: true`, séparation stricte de la date d'entrée en vigueur de l'arrêté et de la date de publication du communiqué, extraction multi-formats CSV et HTML, 14/14 tests unitaires et de robustesse verts avec 81% de couverture, 118 tests de non-régression globale verts, ruff et mypy 100% conformes)

---

## 1. Contexte et objectifs de la qualification

La tâche **R2.7** intègre les **prix plafonds réglementés des carburants et les événements tarifaires de l'Office Malgache des Hydrocarbures (OMH)** conformément aux exigences de `MARKET_INTELLIGENCE_EXECUTION_PLAN.md` :

1. **Qualification de la source et gouvernance institutionnelle :**
   - Connecteur `omh_public` (`backend/src/ketrika/connectors/omh_public.py`) rattaché à sa propre famille institutionnelle `source_family: omh` (Office régulateur autonome des hydrocarbures, distinct des ministères vivriers pour garantir l'indépendance de confirmation C3).
   - Cadence de collecte mensuelle (`monthly`), observation par événement (`event`), priorité `P1`, licence publique gouvernementale.
   - Fiche source complète rédigée dans `docs/sources/omh_public.md`.

2. **Articulation économique avec le transport vivrier et la sécurité alimentaire :**
   - **Gazole (Gasoil) :** Déterminant direct majeur du coût du fret routier par camion diesel sur les corridors d'approvisionnement clés (RN2 Toamasina-Antananarivo pour le riz importé, RN44 Ambatondrazaka pour le riz local de l'Alaotra, RN7 pour le maïs et les légumineuses du Sud).
   - **Super Carburant (SP95) :** Déterminant du transport léger, des triporteurs et des liaisons urbaines/périurbaines.
   - **Pétrole lampant (Kérosène) :** Énergie d'éclairage et de cuisson des ménages vulnérables et ruraux, suivi pour la sensibilité sociale.

3. **Invariants stricts de régulation et de traçabilité :**
   - **Prix maximal réglementé explicite :** Identification obligatoire de la nature administrée des prix à la pompe (`evidence["is_administered"] = True`, `evidence["rate_type"] = "ceiling"`, `evidence["regulatory_body"] = "OMH / Ministère de l'Énergie et des Hydrocarbures").
   - **Séparation stricte de la date d'effet vs date de publication :**
     - La date de prise d'effet de l'arrêté (`period_start` / `period_end` = `2026-06-01 00:00:00`) est rigoureusement dissociée de la date de signature/publication du communiqué officiel (`published_at` / `published_date` = `2026-05-30`).
   - **Règle d'anti-interpolation et d'anti-continuité implicite :**
     - Conformément aux directives R2.7, l'absence de communiqué ne constitue jamais une preuve de stabilité, et aucune rupture d'approvisionnement ou variation tarifaire n'est inférée sans arrêté officiel vérifiable.
   - **Conservation d'historique et immuabilité :**
     - Les révisions tarifaires successives (ex. barème initial de janvier 2026 puis révision de juin 2026) créent des observations d'événements distinctes et horodatées sans écrasement destructif.

4. **Multi-formats et découverte d'éditions :**
   - Support d'ingestion des barèmes historiques CSV (`omh_bareme_carburants_2026.csv`) et des communiqués officiels HTML (`omh_communique_revision_juin_2026.html`).
   - Moteur de découverte HTML `CatalogDiscoveryEngine` avec fallback déterministe.

---

## 2. Fichiers créés et modifiés

- **Gouvernance et référentiel :**
  - `registry/sources.yaml` : enregistrement de `omh_public` (famille `omh`, priorité `P1`, cadences adaptées, SLA 62 jours).
  - `docs/sources/omh_public.md` : fiche technique de la source, cadences, schéma, limitations et politique de provenance.
  - `backend/src/ketrika/connectors/registry.py` : enregistrement de `omh_public` dans le catalogue Python.
  - `backend/tests/unit/test_registry_conformance.py` : vérification du comptage (13 sources) et de la famille `omh`.
- **Connecteur OMH :**
  - `backend/src/ketrika/connectors/omh_public.py` : connecteur officiel `Connector`, parsing CSV/HTML, nettoyage robuste des montants, gestion d'arrêtés réglementaires, traçabilité C3.
- **Fixtures authentiques et golden set :**
  - `backend/tests/fixtures/omh_public/omh_bareme_carburants_2026.csv` : barème officiel des prix maxima (janvier et juin 2026).
  - `backend/tests/fixtures/omh_public/omh_communique_revision_juin_2026.html` : communiqué officiel de révision tarifaire de l'OMH.
  - `backend/tests/golden/omh_public/omh_sample.expected.json` : valeurs de référence certifiées et séparation des dates.
- **Suite de tests de qualification :**
  - `backend/tests/unit/test_omh_public.py` : 14 tests unitaires validant l'extraction CSV/HTML, la conformité golden, la séparation effective/publication, la découverte de catalogue, la robustesse et l'idempotence DB.

---

## 3. Preuves d'exécution des tests

### 3.1 Tests unitaires et couverture du connecteur OMH
```bash
docker run --rm -v /home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep:/workspace -w /workspace/backend ketrika-backend:dev uv run pytest -v tests/unit/test_omh_public.py --cov=ketrika.connectors.omh_public --cov-report=term-missing
```
Résultat :
```text
============================= test session starts ==============================
collected 14 items

tests/unit/test_omh_public.py::test_omh_public_registered_in_registry PASSED [  7%]
tests/unit/test_omh_public.py::test_omh_public_connector_constants PASSED [ 14%]
tests/unit/test_omh_public.py::test_clean_fuel_price PASSED              [ 21%]
tests/unit/test_omh_public.py::test_parse_french_date_text PASSED        [ 28%]
tests/unit/test_omh_public.py::test_parse_authentic_csv_fixture_and_golden_match PASSED [ 35%]
tests/unit/test_omh_public.py::test_separation_of_effective_date_and_publication_date PASSED [ 42%]
tests/unit/test_omh_public.py::test_parse_authentic_html_communique PASSED [ 50%]
tests/unit/test_omh_public.py::test_omh_catalog_discovery PASSED         [ 57%]
tests/unit/test_omh_public.py::test_omh_discovery_fallback PASSED        [ 64%]
tests/unit/test_omh_public.py::test_omh_fetch PASSED                     [ 71%]
tests/unit/test_omh_public.py::test_omh_parse_missing_content PASSED     [ 78%]
tests/unit/test_omh_public.py::test_omh_parse_requires_bronze_store_when_no_content PASSED [ 85%]
tests/unit/test_omh_public.py::test_omh_csv_edge_cases_skipped PASSED    [ 92%]
tests/unit/test_omh_public.py::test_omh_load_macro_record_insertion_and_idempotence PASSED [100%]

================================ tests coverage ================================
Name                                   Stmts   Miss  Cover   Missing
--------------------------------------------------------------------
src/ketrika/connectors/omh_public.py     244     46    81%   100-101, 108-109, 126-127, 235-240, 263-264, 272, 295, 304-307, 333, 344-345, 394-395, 403-407, 414, 419-423, 434-438, 463, 471-472, 476-477
--------------------------------------------------------------------
TOTAL                                    244     46    81%
============================= 14 passed in 48.13s ==============================
```

### 3.2 Contrôles statiques (Ruff & Mypy)
```bash
docker run --rm -v /home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep:/workspace -w /workspace/backend ketrika-backend:dev uv run ruff check src/ketrika/connectors/omh_public.py tests/unit/test_omh_public.py
docker run --rm -v /home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep:/workspace -w /workspace/backend ketrika-backend:dev uv run mypy src/ketrika/connectors/omh_public.py src/ketrika/connectors/registry.py tests/unit/test_omh_public.py tests/unit/test_registry_conformance.py
```
Résultat :
```text
All checks passed!
Success: no issues found in 4 source files
```

### 3.3 Non-régression globale sur les sources, contrats et macro-indicateurs
```bash
docker run --rm -v /home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep:/workspace -w /workspace/backend ketrika-backend:dev uv run pytest -v \
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
```text
======================== 118 passed in 73.72s (0:01:13) ========================
```

---

## 4. Conclusion et conformité Definition of Done

- Tous les critères d'acceptation de **R2.7** sont validés.
- Couverture de `omh_public.py` : **81%** (seuil exigé : $\ge 80\%$).
- Aucune régression : **118/118** tests verts.
- La tâche **R2.7** est marquée **DONE**.
