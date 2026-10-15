# Preuve de qualification R1.13 — Gate de fin de phase R1 (Collecte réelle et qualification du socle)

**Date :** 2026-10-15  
**Tâche :** R1.13 — Gate de collecte réelle (Gate de fin de phase R1)  
**Statut :** **QUALIFIED & ACCEPTÉ AVEC LIMITES PUBLIÉES**  
**Tag associé :** `mi-r1-qualified`

---

## 1. Synthèse de validation du Gate R1

Conformément à la constitution [`AGENTS.md`](../../AGENTS.md) (§1, §3, §4, §8), à [`SPECS.md`](../plan/SPECS.md) et au programme [`MARKET_INTELLIGENCE_EXECUTION_PLAN.md`](../plan/MARKET_INTELLIGENCE_EXECUTION_PLAN.md) (§6), le **Gate de fin de phase R1** vérifie l'ensemble des 12 tâches préalables (R1.1 à R1.12) et établit la qualification formelle de l'infrastructure d'ingestion et des **9 sources du socle**.

### 1.1 Règle de transparence opérationnelle (AGENTS.md §8 & R1.13)
> **Avertissement normatif :** Conformément aux directives strictes de R1.13 et d'AGENTS.md §8.1 (« Ne jamais prétendre neuf opérationnelles lorsque certaines sont hors ligne ») :
> - **7 sources sont pleinement opérationnelles et actives** pour l'ingestion de données de marché.
> - **2 sources sont formellement désactivées en collecte live réseau (`status: disabled`)** en raison de politiques d'accès externes strictes (incident **B-R009** : blocage 403 Cloudflare sur HDX ; incident **B-R010** : directive officielle `robots.txt Disallow: /api/` sur NASA POWER).
> - Pour ces 2 sources, tout contournement est strictement interdit (AGENTS §8.1). Leurs connecteurs logiciels, contrôles de cohérence physique, détection d'imputation et pipelines de réhydratation Bronze sont **100 % qualifiés en mode rejeu offline**.

---

## 2. Matrice complète des 9 sources du socle

| # | Source ID | Nom & Famille | Capacité & Périmètre | Volume & Période | Produits / Indicateurs | Zones géographiques | Statut opérationnel | Crawl Permission & Licence | Preuve |
|---|---|---|---|---|---|---|---|---|---|
| **1** | `ocha_codab_mdg` | OCHA COD-AB / BNGRC (`un_ocha`) | Référentiel spatial pivot, 23 régions officielles (Loi 2021-010), 119 districts | Admin 0, 1, 2, 3 (annuel/statique) | Polygones GeoJSON, centroïdes, P-codes ISO | Madagascar national (23 régions, 119 districts) | **QUALIFIED (Active)** | `public_open_data`<br>CC BY-IGO | [R1.10](../evidence/R1.10/README.md) |
| **2** | `instat_nipc` | INSTAT NIPC (`national_stats`) | Indices des prix à la consommation (IPC / NIPC) mensuels | 108 mois (2016–2024), 7 agglomérations | Indice global, alimentation, riz, énergie | 7 grands centres urbains | **QUALIFIED (Active)** | `public_open_data`<br>INSTAT Open | [R1.3](../evidence/R1.3/README.md) |
| **3** | `miasa_odr` | Observatoire du Riz (`madagascar_gov`) | Bulletins hebdomadaires des prix au kg (détail, gros, paddy) | Hebdomadaire (2020–2024), bulletins 520, 710, 850 | Riz blanc local (Vary Gasy, Makalioka, Tsipala), importé, paddy | 23 régions de Madagascar | **QUALIFIED (Active)** | `public_open_data`<br>Public Open Data | [R1.4](../evidence/R1.4/README.md) |
| **4** | `mincc_ppn` | Min. Industrialisation & Commerce (`madagascar_gov`) | Prix plafonds vs observés, alertes de disponibilité PPN | 10 communiqués authentiques (2021–2024) | Riz, huile de table, sucre blanc/roux, farine | Régions & districts de Madagascar | **QUALIFIED (Active)** | `public_open_data`<br>Public Open Data (anti-PII) | [R1.5](../evidence/R1.5/README.md) |
| **5** | `douanes_stats` | Direction Générale des Douanes (`madagascar_gov`) | Commerce extérieur : importations et exportations mensuelles/annuelles | 2020–2024, flux vs totaux annuels | Riz (SH 1006), Huiles (SH 1511), Sucre (SH 1701), Farine (SH 1101) | Bureaux douaniers (Toamasina, etc.) | **QUALIFIED (Active)** | `public_open_data`<br>Public Open Data | [R1.6](../evidence/R1.6/README.md) |
| **6** | `wfp_hdx_mdg` | WFP Food Prices HDX (`un_wfp`) | Prix mensuels historiques des marchés vivriers locaux | 2010–2023 (~40 marchés de district) | Riz, maïs, manioc, haricots, huile | Marchés ruraux et urbains | **QUALIFIED (Offline Replay)**<br>**BLOCKED Live (B-R009)** | `public_open_data`<br>CC BY-IGO | [R1.7](../evidence/R1.7/README.md) |
| **7** | `wb_rtfp_mdg` | Banque mondiale RTFP (`world_bank`) | Real-Time Food Prices haute fréquence | 2020–2024 mensuel, traçabilité C3 | Prix vivriers réels, inflation vivrière | Régions de Madagascar | **QUALIFIED (Active)** | `public_open_data`<br>CC BY 4.0 | [R1.8](../evidence/R1.8/README.md) |
| **8** | `faostat` | FAOSTAT QCL/TM (`un_fao`) | Bilans annuels de production vivrière et commerce | 20 années continues (2004–2023) | Riz paddy, maïs, manioc, légumineuses | Madagascar national (ISO3 MDG) | **QUALIFIED (Active)** | `public_open_data`<br>CC BY-NC-SA 3.0 IGO | [R1.9](../evidence/R1.9/README.md) |
| **9** | `nasa_power` | NASA POWER Agroclimatology (`us_nasa`) | Réanalyse agroclimatique MERRA-2 (pluie, T°, humidité) | Quotidien 1991–2024, grille 0.5°x0.5° | Précipitations (PRECTOTCORR), Tmin/Tmax (T2M), RH2M | Centroïdes de districts Madagascar | **QUALIFIED (Offline Replay)**<br>**BLOCKED Live (B-R010)** | `public_open_data`<br>NASA Public Data | [R1.11](../evidence/R1.11/README.md) |

---

## 3. Capacités fonctionnelles et techniques vérifiées (R1.1 – R1.12)

1. **Registre des sources & conformité légale (R1.1) :**
   - Registre centralisé `registry/sources.yaml` définissant quotas quotidiens, `max_rps`, politique anti-PII, licences et statut de validation légale.
2. **Découverte dynamique & pagination bornée (R1.2) :**
   - Moteur `CatalogDiscoveryEngine` avec protection anti-SSRF, parsing d'hyperliens stricts et gestion des révisions.
3. **Extraction & Golden sets authentiques (R1.3 – R1.9) :**
   - Extraction déterministe prioritaire (HTML, PDF texte `pypdfium2`, Excel multi-feuilles `openpyxl`).
   - Évaluation sur Golden sets indépendants : **100 % d'exactitude et 100 % de rappel** sur les jeux de référence MiASA (bulletins 520, 710, 850), MinCC (10 communiqués), Douanes (2024), Banque mondiale RTFP et FAOSTAT.
   - Refus strict d'assimilation de prix plafonds à des prix observés (R1.5).
   - Distinction rigoureuse entre riz paddy et riz usiné sans ratio artificiel non prouvé (R1.9).
4. **Référentiel géographique pivot & 23 régions (R1.10) :**
   - Intégration du standard officiel Loi 2021-010 (23 régions administratives MDG11–MDG72).
   - Suppression définitive de tout fallback aveugle vers MDG1101 (émission systématique de l'issue `unresolved_location_needs_review`).
   - Vérification spatiale que 100 % des géométries se situent strictement dans la boîte englobante nationale de Madagascar.
5. **Validation physique & sentinelles (R1.11) :**
   - Contrôles physiques météorologiques stricts (`Tmin <= Tmax`, `pluie >= 0`, `0 <= RH <= 100`).
   - Filtrage intransigeant des sentinelles `-999.0` (jamais converties en `0.0`).
6. **Résilience opérationnelle & Cockpit DataOps (R1.12) :**
   - Détection automatique de nouvelles éditions de catalogue.
   - Idempotence garantie lors des reprises après panne et alertes capturées par Mailpit (H3).
   - Zéro requête HTTP envoyée sous PolicyStop.
   - Concordance SQL / API / UI validée dans `/sources`.

---

## 4. Résultats des tests et métriques d'acceptation du Gate

### 4.1 Suite complète de tests R1 (109/109 tests passés)

Exécution dans le conteneur Docker `ketrika-backend:dev` :
```bash
docker run --rm -v /home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep:/workspace -w /workspace/backend ketrika-backend:dev uv run pytest -v \
  tests/unit/test_registry.py \
  tests/unit/test_edition_discovery.py \
  tests/unit/test_instat_nipc.py \
  tests/unit/test_miasa_odr.py \
  tests/unit/test_mincc_ppn.py \
  tests/unit/test_douanes_stats.py \
  tests/unit/test_wfp_hdx_mdg.py \
  tests/unit/test_wb_rtfp_mdg.py \
  tests/unit/test_faostat.py \
  tests/unit/test_geo.py \
  tests/unit/test_nasa_power.py \
  tests/unit/test_source_health_and_refresh.py
```

Résultats :
- **Total collecté :** 109 tests
- **Statut :** **109 passed in 28.76s (0 failed, 0 error, 0 skipped)**
- **Taux de succès :** **100 %**

### 4.2 Contrôles statiques et frontend

- **Backend Ruff :** 0 avertissement, 0 erreur.
- **Backend Mypy :** Typage statique strict validé sans omission.
- **Frontend Typecheck (`tsc --noEmit`) :** Exit code 0, 0 erreur TypeScript.
- **Frontend Next.js Lint (`next lint`) :** Exit code 0, 0 avertissement ni erreur ESLint.

---

## 5. Décision de clôture de la Phase R1

Toutes les conditions normatives de clôture de phase de la tâche **R1.13** et d'**AGENTS.md** (§3, §8, §10) étant satisfaites :
1. Les 9 sources du socle possèdent des preuves formelles conformes ou un repli documenté dans la gouvernance (B-R009, B-R010).
2. Aucun parse vide ni extraction fictive n'est comptabilisé.
3. Le tag git `mi-r1-qualified` est apposé sur le commit stabilisé de clôture du gate.
4. Le programme est prêt pour la transition vers la **Phase R2 — Qualité et observatoire marché/économie** (tâche d'entrée R2.1).
