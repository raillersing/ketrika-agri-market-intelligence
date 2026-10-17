# Preuve de qualification R1.9 — FAOSTAT

**Date :** 2026-10-15  
**Tâche :** R1.9 — Qualifier FAOSTAT  
**Statut :** **DONE** (Logiciel, règles C3, extraction déterministe, distinction paddy/blanchi, validation des flags, rejouabilité Bronze)  

---

## 1. Contexte et objectifs de la qualification

Le connecteur **FAOSTAT** (`faostat`) ingère les statistiques officielles de la FAO pour Madagascar :
- Production agricole, superficies et rendements (`DomainCode=QCL`).
- Flux du commerce international de produits agroalimentaires (`DomainCode=TM`).

Selon les directives de la tâche **R1.9** et du contrat commun **CC-R** :
1. **Validation et classification stricte des drapeaux statistiques FAO :**
   - Drapeaux officiels vérifiés (`A`, `P`, `X`, `""`) -> `observed_or_imputed="observed"` avec confiance `1.0`.
   - Drapeaux d'estimation / imputation (`E`, `I`, `F`, `T`, `M`, `Q`) -> `observed_or_imputed="imputed"` avec confiance `0.8`.
   - **Interdiction absolue** de promouvoir un drapeau inconnu ou non répertorié en donnée officielle : émission obligatoire d'une anomalie `unknown_faostat_flag_needs_review` et classification conservative en `imputed` avec confiance réduite (`0.7`).
2. **Distinction rigoureuse Paddy vs Riz blanchi / usiné :**
   - Aucune conversion implicite ni application arbitraire de ratio d'usinage (ex: 0.67) sans source officielle documentée.
   - Conservation intégrale de l'intitulé source exact dans `product_raw` (`"Rice, paddy"` vs `"Rice, milled"`).
3. **Couverture historique paddy sur 20 années :**
   - Vérification de la continuité chronologique sur 20 années consécutives (2004–2023) pour la production de riz à Madagascar.
4. **Découverte dynamique et support multi-domaines :**
   - Support des domaines `QCL`, `TM`, `FBS`, configuration d'URLs directes via métadonnées (`api_urls`, `api_url`), et point d'entrée par défaut.
5. **Rejouabilité Bronze 100% offline :**
   - Rechargement déterministe de la fixture `faostat_sample.json` dans le `BronzeStore`.

---

## 2. Implémentation technique

- **Connecteur :** `backend/src/ketrika/connectors/faostat.py` (version `1.1.0`).
- **Records typés :**
  - `ProductionRecord` pour `obs.production_observation` (`element = 'production_t'`, `'area_harvested_ha'`, `'yield_kg_ha'`).
  - `TradeFlowRecord` pour `obs.trade_flow` (`flow = 'import' | 'export'`, conversion unitaire `t -> kg`).
- **Traçabilité :** `source_family="un_fao"`, `is_forecast_or_estimated` renseigné dans `evidence`.

---

## 3. Résultats des tests et métriques de validation

Exécution dans le conteneur Docker `ketrika-backend:dev` :

```bash
docker run --rm -v /home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep:/workspace -w /workspace/backend ketrika-backend:dev uv run pytest -v tests/unit/test_faostat.py
```

### Résultats d'exécution (7/7 tests passés) :
1. `test_faostat_parse_fixture` : **PASSED** (36 enregistrements parsés, 28 production, 8 commerce extérieur, série riz paddy sur 20 années consécutives 2004–2023 vérifiée, min=2004, max=2023).
2. `test_faostat_golden_test` : **PASSED** (Golden test sur 36 enregistrements, 260 champs vérifiés, Exactitude = 100 %, Rappel = 100 %).
3. `test_faostat_paddy_vs_milled_never_converted_without_proof` : **PASSED** (distinction stricte de `"Rice, paddy"` et `"Rice, milled"`, aucune conversion de libellé ni de quantité).
4. `test_faostat_unknown_flag_never_promoted_to_observed` : **PASSED** (drapeau `"Z"` -> issue `unknown_faostat_flag_needs_review`, marqué `imputed` avec confiance 0.7, non promu en observed).
5. `test_faostat_fetch_offline_into_bronze` : **PASSED** (stockage déterministe dans le `BronzeStore`).
6. `test_faostat_discover_flexible_endpoints` : **PASSED** (résolution par domaine `QCL`, `TM` et liste `api_urls`).
7. `test_faostat_evidence_schema_c3` : **PASSED** (traçabilité `source_family="un_fao"` et flag d'exclusion de prévision `is_forecast_or_estimated`).

### Couverture du code :
- Fichier : `backend/src/ketrika/connectors/faostat.py`
- Statements : 139
- Miss : 27
- **Couverture de code : 81 %** (conforme au seuil normatif >= 80 %).

### Contrôles de style et de types :
- `ruff check` : 0 erreur.
- `mypy` : 0 erreur (type checking strict).

---

## 4. Statut et suite

- **Statut R1.9 :** **DONE**.
- **Prochaine tâche éligible du plan R :** **R1.10 — Requalifier géographie et résolution** (`geo/`, `core/geo.py`, `ref.location`).
