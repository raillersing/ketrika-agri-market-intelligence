# Preuve de qualification R2.6 — Intégration du connecteur Banky Foiben'i Madagasikara (BFM Public)

**Date :** 2026-10-16  
**Tâche :** R2.6 — Intégrer change et contexte monétaire BFM  
**Statut :** **DONE** (Nouveau connecteur `bfm_public` pour les cours officiels du Marché Interbancaire de Devises de Banky Foiben'i Madagasikara, extraction déterministe des cours USD/MGA et EUR/MGA en achat/vente/moyen, respect absolu des jours ouvrés sans interpolation silencieuse de week-ends ou jours fériés, certification documentaire des taux inverses, support multi-formats CSV et bulletin HTML, 17/17 tests unitaires et de robustesse verts avec 85% de couverture, 104 tests de non-régression verts, ruff et mypy 100% conformes)

---

## 1. Contexte et objectifs de la qualification

La tâche **R2.6** intègre les **cours de change officiels et le contexte monétaire de Banky Foiben'i Madagasikara (BFM)** conformément aux directives de `MARKET_INTELLIGENCE_EXECUTION_PLAN.md` :

1. **Qualification de la source et gouvernance institutionnelle :**
   - Connecteur `bfm_public` (`backend/src/ketrika/connectors/bfm_public.py`) rattaché à sa propre famille institutionnelle `source_family: bfm` (Banque Centrale, distincte des ministères gouvernementaux `madagascar_gov` pour une traçabilité C3 indépendante).
   - Cadence journalière (`daily`), priorité `P1`, licence publique officielle de la Banque Centrale.
   - Fiche technique rédigée dans `docs/sources/bfm_public.md`.

2. **Périmètre des séries extraites (Devises clés vivrières) :**
   - **Dollar américain (USD) :** Devise clé de facturation des importations de riz vivrier (Vary Tsinjo).
     - `EXCHANGE_RATE_USD_MGA` : Cours moyen pondéré MID (référence officielle).
     - `EXCHANGE_RATE_USD_MGA_BUY` : Cours acheteur indicatif bancaire.
     - `EXCHANGE_RATE_USD_MGA_SELL` : Cours vendeur indicatif bancaire.
   - **Euro (EUR) :** Devise de référence régionale et des échanges avec les partenaires de l'Océan Indien.
     - `EXCHANGE_RATE_EUR_MGA` : Cours moyen pondéré MID.
     - `EXCHANGE_RATE_EUR_MGA_BUY` : Cours acheteur indicatif.
     - `EXCHANGE_RATE_EUR_MGA_SELL` : Cours vendeur indicatif.

3. **Invariants stricts de cotation et anti-interpolation :**
   - **Jours ouvrés stricts :** Seuls les jours où le MID a réellement opéré (lundi à vendredi, hors jours fériés bancaires) portent des observations.
   - **Interdiction formelle du forward-fill :** Aucun remplissage automatique des week-ends (samedis/dimanches) ou jours fériés (1er mai, Ascension 14 mai). Les jours chômés demeurent rigoureusement absents de la base.
   - **Distinction stricte des taux :** Achat, vente et moyen restent séparés et ne sont jamais intervertis. Aucun taux douanier administratif (taux de liquidation) n'est substitué au cours de change de marché BFM.

4. **Convention inverse vérifiée mécaniquement :**
   - Stockage normatif en Ariary par unité de devise (`MGA`), unité de base officielle.
   - Calcul et traçabilité de la parité inverse dans `evidence["inverse_rate_usd_per_mga"]` avec invariant strict :
     $$\text{rate} \times \text{inverse} = 1.0 \pm 10^{-5}$$

5. **Multi-formats et découverte d'éditions :**
   - Support d'ingestion des séries historiques CSV (`bfm_cours_de_change_2026_mai.csv`) et des bulletins quotidiens HTML (`bfm_bulletin_journalier_2026_05_18.html`).
   - Moteur de découverte HTML `CatalogDiscoveryEngine` avec fallback déterministe.

---

## 2. Fichiers créés et modifiés

- **Gouvernance et référentiel :**
  - `registry/sources.yaml` : enregistrement de `bfm_public` (famille `bfm`, priorité `P1`, cadence `daily`).
  - `docs/sources/bfm_public.md` : fiche technique de la source, cadences, schéma, limitations et politique de provenance.
  - `backend/src/ketrika/connectors/registry.py` : enregistrement de `bfm_public` dans le registre Python.
  - `backend/tests/unit/test_registry_conformance.py` : vérification du comptage (12 sources) et de la famille `bfm`.
- **Connecteur BFM :**
  - `backend/src/ketrika/connectors/bfm_public.py` : connecteur officiel `Connector`, parsing CSV/HTML, calcul de taux inverse, vérification de jours ouvrés, gestion d'erreurs robuste.
- **Fixtures authentiques et golden set :**
  - `backend/tests/fixtures/bfm_public/bfm_cours_de_change_2026_mai.csv` : séries journalières authentiques mai 2026 (hors week-ends et jours fériés).
  - `backend/tests/fixtures/bfm_public/bfm_bulletin_journalier_2026_05_18.html` : bulletin quotidien de séance HTML.
  - `backend/tests/golden/bfm_public/bfm_sample.expected.json` : valeurs de référence certifiées et dates de contrôle négatif (week-ends).
- **Suite de tests de qualification :**
  - `backend/tests/unit/test_bfm_public.py` : 17 tests unitaires, validation des jours ouvrés, calcul d'inverse, golden matching, anti-interpolation des week-ends, découverte de catalogue, robustesse et supersession DB.

---

## 3. Résultats des tests et métriques de validation

### 3.1 Suite unitaire et de robustesse R2.6 (17/17 passés, couverture 85%)

Commande exécutée dans Docker :
```bash
docker run --rm -v /home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep:/workspace -w /workspace/backend ketrika-backend:dev uv run pytest -v tests/unit/test_bfm_public.py --cov=ketrika.connectors.bfm_public --cov-report=term-missing
```

Résultats :
```text
============================= test session starts ==============================
platform linux -- Python 3.12.13, pytest-9.1.1, pluggy-1.6.0
collected 17 items

tests/unit/test_bfm_public.py::test_bfm_public_registered_in_registry PASSED [  5%]
tests/unit/test_bfm_public.py::test_bfm_public_connector_constants PASSED [ 11%]
tests/unit/test_bfm_public.py::test_is_business_trading_day PASSED       [ 17%]
tests/unit/test_bfm_public.py::test_clean_rate_number PASSED             [ 23%]
tests/unit/test_bfm_public.py::test_compute_inverse_exchange_rate PASSED [ 29%]
tests/unit/test_bfm_public.py::test_parse_french_date_text PASSED        [ 35%]
tests/unit/test_bfm_public.py::test_parse_authentic_csv_fixture_and_golden_match PASSED [ 41%]
tests/unit/test_bfm_public.py::test_inverse_rate_calculation_in_parsed_records PASSED [ 47%]
tests/unit/test_bfm_public.py::test_parse_authentic_html_daily_bulletin PASSED [ 52%]
tests/unit/test_bfm_public.py::test_bfm_catalog_discovery PASSED         [ 58%]
tests/unit/test_bfm_public.py::test_bfm_discovery_fallback PASSED        [ 64%]
tests/unit/test_bfm_public.py::test_bfm_fetch PASSED                     [ 70%]
tests/unit/test_bfm_public.py::test_bfm_parse_missing_content PASSED     [ 76%]
tests/unit/test_bfm_public.py::test_bfm_load_macro_record_insertion_and_idempotence PASSED [ 82%]
tests/unit/test_bfm_public.py::test_bfm_parse_requires_bronze_store_when_no_content PASSED [ 88%]
tests/unit/test_bfm_public.py::test_bfm_csv_parsing_weekend_and_unsupported_currency_skipped PASSED [ 94%]
tests/unit/test_bfm_public.py::test_bfm_html_parsing_weekend_and_empty PASSED [100%]

================================ tests coverage ================================
Name                                   Stmts   Miss  Cover   Missing
--------------------------------------------------------------------
src/ketrika/connectors/bfm_public.py     220     32    85%   87-88, 95-96, 112-113, 223-228, 251-252, 260, 285, 350-351, 410-411, 424-425, 454, 463-465, 494-495, 522-523, 550-551
--------------------------------------------------------------------
TOTAL                                    220     32    85%
============================= 17 passed in 58.28s ==============================
```

### 3.2 Contrôles de qualité statique (Ruff et Mypy)

```bash
docker run --rm -v /home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep:/workspace -w /workspace/backend ketrika-backend:dev uv run ruff check src/ketrika/connectors/bfm_public.py src/ketrika/connectors/registry.py tests/unit/test_bfm_public.py tests/unit/test_registry_conformance.py
# Output: All checks passed!

docker run --rm -v /home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep:/workspace -w /workspace/backend ketrika-backend:dev uv run mypy src/ketrika/connectors/bfm_public.py src/ketrika/connectors/registry.py tests/unit/test_bfm_public.py tests/unit/test_registry_conformance.py
# Output: Success: no issues found in 4 source files
```

### 3.3 Suite de non-régression (104/104 passés)

```bash
docker run --rm -v /home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep:/workspace -w /workspace/backend ketrika-backend:dev uv run pytest -v tests/unit/test_bfm_public.py tests/unit/test_instat_tbe.py tests/unit/test_instat_nipc.py tests/unit/test_registry.py tests/unit/test_registry_conformance.py tests/unit/test_source_definitions.py tests/unit/test_contracts_time_origin_macro.py tests/unit/test_market_coverage_and_pilot.py
# Output: ============================= 104 passed in 43.81s =============================
```

---

## 4. Conclusion de conformité

La tâche **R2.6** satisfait l'ensemble des critères d'acceptation énoncés dans `MARKET_INTELLIGENCE_EXECUTION_PLAN.md` :
- Connecteur `bfm_public` opérationnel sur les cours de référence officiels du MID.
- Séparation explicite cours moyen, cours achat et cours vendeur.
- Jours ouvrés stricts préservés sans interpolation silencieuse des jours chômés.
- Taux inverses documentés et vérifiés.
- Chaîne de provenance C3 assignée à `Banky Foiben'i Madagasikara`.
