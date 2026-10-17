# Preuve R4.4 — Intégration des événements et perspectives FEWS NET et IPC Madagascar

## 1. Contexte et Objectifs

- **Tâche :** `R4.4 — Intégrer événements et perspectives FEWS NET/IPC` (MUST).
- **Norme et Décision :** ADR-083 (`docs/plan/DECISIONS.md`), SPECS §26.
- **Principes cardinaux :**
  1. **Disjonction formelle et étanche entre situation courante et perspective projetée :**
     - Le drapeau `is_projected` (False pour la situation actuelle, True pour la projection future) et des périodes temporelles distinctes (`valid_from`, `valid_to`) interdisent toute fusion entre état observé et état anticipé.
  2. **Intégrité métrologique et fidélité textuelle :**
     - Extraction déterministe des phases officielles IPC (1 à 5), des hypothèses clés (`assumptions`), des facteurs de bascule (`key_drivers`), avec numéro de page et citations verbatim.
     - Interdiction stricte de générer des scores synthétiques continus ou de fabriquer des chiffres non documentés (Règle 10).
  3. **Ancrage géographique et chargement unifié :**
     - Résolution spatiale vers les zones de Madagascar (Androy, Atsimo-Andrefana, Grand Sud, etc.).
     - Support complet de `EventRecord` dans `load_record_with_supersession` pour persister fidèlement dans la table `obs.event`.
  4. **Comportement fail-safe :**
     - En cas de publication absente ou non parue, étiquetage formel `document_unavailable` sans fabrication de fausses données de remplacement.

---

## 2. Composants implémentés

1. **Déclarations officielles dans le registre :**
   - `fewsnet_mdg` (USAID / FEWS NET Madagascar) et `ipc_mdg` (Cadre Intégré de Classification IPC Madagascar) enregistrés dans `registry/sources.yaml` et `backend/src/ketrika/connectors/registry.py`.
2. **Connecteurs spécialisés :**
   - `backend/src/ketrika/connectors/fewsnet_ipc.py` :
     - `FewsnetConnector` (`source_id='fewsnet_mdg'`) et `IpcConnector` (`source_id='ipc_mdg'`).
     - Séparation étanche de la découverte par cycles périodiques (tri-annuel pour FEWS NET, semestriel pour IPC).
     - Extraction des analyses avec citations exactes et attributs `is_projected`.
3. **Extension du modèle et du chargeur :**
   - `EventRecord` dans `backend/src/ketrika/connectors/records.py` enrichi avec `location_raw`, `product_raw`, `is_projected`, `published_at`, et clé naturelle étendue à 6 composantes.
   - `load_event_record_with_supersession` implémenté dans `backend/src/ketrika/connectors/runner.py` et intégré à `load_record_with_supersession`.
4. **Fixtures officielles :**
   - `backend/tests/fixtures/fewsnet_ipc/fewsnet_mdg_outlook_2024_02.json`
   - `backend/tests/fixtures/fewsnet_ipc/ipc_mdg_analysis_2024.json`
   - `backend/tests/fixtures/fewsnet_ipc/fewsnet_unavailable.json`
5. **Suite de tests unitaires et d'intégration de modèle :**
   - `backend/tests/unit/test_fewsnet_ipc.py` : 8 tests couvrant découverte, non-chevauchement des fenêtres temporelles, citations, indisponibilité, fallback texte, insertion et idempotence en base.

---

## 3. Résultats de validation

### 3.1 Tests unitaires et couverture

```text
tests/unit/test_fewsnet_ipc.py::test_fewsnet_ipc_discovery PASSED        [ 12%]
tests/unit/test_fewsnet_ipc.py::test_fewsnet_ipc_discovery_override PASSED [ 25%]
tests/unit/test_fewsnet_ipc.py::test_fewsnet_parse_outlook_strict_disjunction PASSED [ 37%]
tests/unit/test_fewsnet_ipc.py::test_ipc_parse_analysis PASSED           [ 50%]
tests/unit/test_fewsnet_ipc.py::test_fewsnet_parse_unavailable PASSED    [ 62%]
tests/unit/test_fewsnet_ipc.py::test_fewsnet_parse_empty_bytes PASSED    [ 75%]
tests/unit/test_fewsnet_ipc.py::test_fewsnet_parse_text_fallback PASSED  [ 87%]
tests/unit/test_fewsnet_ipc.py::test_fewsnet_ipc_loader_insertion_and_idempotence PASSED [100%]

Name                                    Stmts   Miss  Cover   Missing
---------------------------------------------------------------------
src/ketrika/connectors/fewsnet_ipc.py      90      8    91%   77, 86-90, 208-210
---------------------------------------------------------------------
TOTAL                                      90      8    91%
============================== 8 passed in 15.81s ==============================
```

### 3.2 Contrôles statiques

```text
uv run ruff check -> All checks passed!
uv run mypy -> Success: no issues found in 5 source files
```

---

## 4. Conclusion

La tâche R4.4 est complètement réalisée et qualifiée. Les perspectives et classifications de sécurité alimentaire sont intégrées dans le respect absolu de la disjonction entre observations courantes et projections futures.
