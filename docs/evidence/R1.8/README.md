# Preuve de qualification R1.8 — Banque mondiale RTFP

**Date :** 2026-10-15  
**Tâche :** R1.8 — Qualifier Banque mondiale RTFP  
**Statut :** **DONE** (Logiciel, règles C3, extraction déterministe, traçabilité et rejouabilité Bronze)  

---

## 1. Contexte et objectifs de la qualification

Le jeu de données **Real-Time Food Prices (RTFP) Madagascar** de la Banque Mondiale (`wb_rtfp_mdg`) fournit un historique de suivi des prix vivriers mensuels (riz, blé, maïs, manioc).
Selon les exigences de la tâche **R1.8** et les contrats transversaux **C1** et **C3** de `MARKET_INTELLIGENCE_EXECUTION_PLAN.md` :
1. **Contrat C3 (Dépendance des sources et non-duplication) :**
   - RTFP utilise en amont des données primaires issues du Programme Alimentaire Mondial (PAM/WFP) et de la FAO.
   - Le connecteur doit obligatoirement expliciter la famille `source_family="world_bank"` et la dépendance `source_dependency="wfp_fao"`.
   - Tout consensus de prix WFP + RTFP ne doit pas être comptabilisé par défaut comme deux confirmations indépendantes.
2. **Principe d'intégrité observé vs imputé (AGENTS §4.9, §8.9) :**
   - Toute valeur imputée porte obligatoirement `observed_or_imputed="imputed"` et `is_forecast_or_estimated=True`.
   - Tout mois ou observation imputé est exclu de la vérité terrain servant à évaluer la précision des modèles de prévision de prix (R3).
   - Tout flag inconnu ne doit **jamais** être promu en `observed` mais routé vers la file de revue humaine (`unknown_value_kind_needs_review`).
3. **Résolution géographique rigoureuse :**
   - Si ni le marché ni la région ne sont fournis, une anomalie documentée `unresolved_location_needs_review` est émise sans inventer de P-code ni affecter arbitrairement un point par défaut.
4. **Calcul explicite du dénominateur :**
   - Part d'imputé calculée avec dénominateur strict sur le total traité.
5. **Découverte dynamique et rejouabilité Bronze :**
   - Découverte flexible (métadonnées, catalogue `CatalogDiscoveryEngine` avec expression régulière, fallback direct).
   - Mode offline supporté avec injection déterministe dans le `BronzeStore`.

---

## 2. Implémentation technique

- **Connecteur :** `backend/src/ketrika/connectors/wb_rtfp_mdg.py` (version `1.1.0`).
- **Découverte dynamique :** `CatalogDiscoveryEngine` avec domaine autorisé `ALLOWED_WB_DOMAINS = ["microdata.worldbank.org", "worldbank.org"]` et validation anti-SSRF.
- **Règles métier :**
  - Flags observés / imputés stricts : détection des mentions `null`, `none`, `nd`, `na`, `nan` dans `price_observed` pour forcer le statut `imputed`.
  - Confiance : `1.0` pour les observations constatées, `0.8` pour les imputations statistiques.
  - Données brutes préservées : `price_raw`, `unit_raw`, `currency_raw`, `product_raw`, `location_raw`.

---

## 3. Résultats des tests et métriques de validation

Exécution dans le conteneur Docker `ketrika-backend:dev` :

```bash
docker run --rm -v /home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep:/workspace -w /workspace/backend ketrika-backend:dev uv run pytest -v tests/unit/test_wb_rtfp_mdg.py
```

### Résultats d'exécution (10/10 tests passés) :
1. `test_wb_rtfp_parse_fixture` : **PASSED** (36 enregistrements, 24 observés, 12 imputés, part d'imputés = 33,33 %, riz/maïs/manioc/blé sur 4 marchés).
2. `test_wb_rtfp_golden_test` : **PASSED** (Golden test sur 36 enregistrements, 288 champs vérifiés, Exactitude = 100 %, Rappel = 100 %).
3. `test_wb_rtfp_unknown_flag_never_promoted_to_observed` : **PASSED** (flag `estimated_trend` -> issue `unknown_value_kind_needs_review`, 0 PriceRecord créé).
4. `test_wb_rtfp_unresolved_location_needs_review` : **PASSED** (absence marché + adm1 -> issue `unresolved_location_needs_review`, aucun repli fictif vers "Madagascar").
5. `test_wb_rtfp_evidence_schema_c3_traceability` : **PASSED** (`source_family="world_bank"`, `source_dependency="wfp_fao"`, `is_forecast_or_estimated` vérifié).
6. `test_wb_rtfp_fetch_offline_into_bronze` : **PASSED** (stockage déterministe dans BronzeStore en mode hors-ligne).
7. `test_wb_rtfp_discover_flexible_targets` : **PASSED** (résolution URL par défaut et cibles explicites dans metadata).
8. `test_wb_rtfp_dynamic_catalog_discovery` : **PASSED** (découverte dynamique regex via `CatalogDiscoveryEngine`).
9. `test_wb_rtfp_market_missing_falls_back_to_adm1` : **PASSED** (fallback légitime vers niveau régional adm1 lorsque seul ce niveau est disponible).
10. `test_wb_rtfp_parse_ignores_empty_and_corrupt_lines` : **PASSED** (gestion robuste des lignes vides, commentaires et prix non numériques).

### Couverture du code :
- Fichier : `backend/src/ketrika/connectors/wb_rtfp_mdg.py`
- Statements : 130
- Miss : 6
- **Couverture de code : 95 %** (largement supérieure au seuil normatif de 80 %).

### Contrôles de style et de types :
- `ruff check` : 0 erreur.
- `mypy` : 0 erreur (type checking strict).

---

## 4. Statut et suite

- **Statut R1.8 :** **DONE**.
- **Prochaine tâche éligible du plan R :** **R1.9 — Qualifier FAOSTAT** (`connectors/faostat.py`).
