# Preuve R4.3 — Qualification des bulletins Météo Madagascar (DGM)

## 1. Contexte et Objectifs

- **Tâche :** `R4.3 — Qualifier les bulletins Météo Madagascar` (MUST).
- **Norme et Décision :** ADR-082 (`docs/plan/DECISIONS.md`), SPECS §26.
- **Principe fondamental :**
  1. Séparation stricte entre date d'émission (`issued_at`) et fenêtre de validité (`valid_from`, `valid_to`).
  2. Extraction déterministe avec citation textuelle verbatim et page du bulletin officiel.
  3. Interdiction formelle de fabriquer des probabilités numériques sur des avis agrométéorologiques qualitatifs (Règle 10).
  4. Repli fail-safe `document_unavailable` lorsque le bulletin officiel n'est pas publié par la DGM (aucune donnée inventée).

---

## 2. Composants implémentés

1. **Déclaration de la source officielle :**
   - Source `meteo_mg` enregistrée dans `registry/sources.yaml` avec métadonnées complètes, tier public, URL officielle `https://www.meteomadagascar.mg`.
2. **Connecteur DGM :**
   - `backend/src/ketrika/connectors/meteo_mg.py` :
     - Méthode `discover` : génération de `DiscoveredItem` par décade/mois/année avec hints d'émission et de validité.
     - Méthode `parse` :
       - Extraction des cumuls pluviométriques observés (`WeatherRecord`, `variable="precip_mm"`, `stage="final"`, `provider="meteo_mg"`, `spatial_resolution="station_point"`).
       - Extraction des avis agronomiques textuels (`EventRecord`, `event_type="agroclimate_advisory"`, `category`, citation verbatim, page).
       - Détection fail-safe de l'indisponibilité (`document_unavailable`).
   - Enregistrement dans `backend/src/ketrika/connectors/registry.py`.
3. **Fixtures officielles et de repli :**
   - `backend/tests/fixtures/meteo_mg/bulletin_decadaire_2024_01_d1.json` : observations réelles et avis textuels par région.
   - `backend/tests/fixtures/meteo_mg/bulletin_unavailable.json` : statut non publié.
4. **Suite de tests unitaires :**
   - `backend/tests/unit/test_meteo_mg.py` : 6 scénarios de tests couvrant découverte, parsing, avis qualitatifs, conformité ADR-082, document absent et fallback texte.

---

## 3. Résultats de validation

### 3.1 Tests unitaires et couverture

```text
tests/unit/test_meteo_mg.py::test_meteo_mg_discovery PASSED              [ 16%]
tests/unit/test_meteo_mg.py::test_meteo_mg_discovery_override PASSED     [ 33%]
tests/unit/test_meteo_mg.py::test_meteo_mg_parse_standard_bulletin PASSED [ 50%]
tests/unit/test_meteo_mg.py::test_meteo_mg_parse_unavailable_bulletin PASSED [ 66%]
tests/unit/test_meteo_mg.py::test_meteo_mg_parse_empty_bytes PASSED      [ 83%]
tests/unit/test_meteo_mg.py::test_meteo_mg_parse_text_fallback PASSED    [100%]

Name                                 Stmts   Miss  Cover   Missing
------------------------------------------------------------------
src/ketrika/connectors/meteo_mg.py      92     10    89%   80, 89-93, 114-115, 202-204
------------------------------------------------------------------
TOTAL                                   92     10    89%
============================== 6 passed in 16.45s ==============================
```

### 3.2 Vérifications de type et de style

```text
uv run ruff check src/ketrika/connectors/meteo_mg.py tests/unit/test_meteo_mg.py -> All checks passed!
uv run mypy src/ketrika/connectors/meteo_mg.py tests/unit/test_meteo_mg.py -> Success: no issues found in 2 source files
```

---

## 4. Conclusion

La qualification de la source officielle Météo Madagascar est complète, vérifiée et conforme aux principes non négociables d'AGENTS.md et ADR-082.
