# Ketrika — plan détaillé de fiabilisation et d'intelligence de marché

Date : 2026-10-09. Version du plan : 1.0. Langue de travail : français.

Suivi actualisé le2026-10-25 par [audit indépendant](../audits/2026-10-25/INDEPENDENT_AUDIT.md) et [plan correctif26 lots](../audits/2026-10-25/CORRECTIVE_EXECUTION_PLAN.md), ADR-120. Les74 tâches et leurs dépendances restent inchangées ; les notes de preuves antérieures sont explicitement historiques et ne valent pas qualification actuelle. Voir aussi la [matrice des capacités](../audits/2026-10-25/TASK_CAPABILITY_MATRIX.md).

**Statut : exécution autorisée le 2026-10-09 ; R0.1–R0.7 DONE, R0.8 IN_PROGRESS.** Ce plan décrit 74 tâches R0.1–R6.11, dont les gates. Il ne recertifie pas les statuts historiques T0–T11 et n'élargit aucune autorisation de diffusion. La gouvernance du programme est intégrée en R0.1 ; les extensions des contrats de données restent soumises à ADR/SPECS avant code.

Références à lire : [AGENTS.md](../../AGENTS.md), [SPECS](SPECS.md), [plan MVP](MVP_EXECUTION_PLAN.md), [PROGRESS](PROGRESS.md), [BLOCKERS](BLOCKERS.md), [DECISIONS](DECISIONS.md), [audit et recherche du 9 octobre](../research/2026-10-09-market-intelligence-audit.md). Les faits d'audit sont des constats statiques à revérifier, pas une photographie certifiée de la base en fonctionnement.

## 0. Statuts d'exécution

> Mise à jour après chaque incrément et clôture. PROGRESS est la mémoire canonique ; ce tableau est son miroir vérifié. L'autorisation d'implémentation a été donnée le 9 octobre 2026. Un sous-livrable ne vaut pas DONE.

| ID | Priorité | Statut | Preuve / incident |
|---|---|---|---|
| R0.1 | MUST | DONE | Audit20261025 : Réception historique conservée, non recertifiée ; AU-01 à AU-09 si impact. Preuve historique (non réception actuelle) : b684528 : check Windows code 0, 275 backend / 15 web ; incidents résolus |
| R0.2 | MUST | DONE | Audit20261025 : Réception historique conservée, non recertifiée ; AU-01 à AU-09 si impact. Preuve historique (non réception actuelle) : 6b4ad7f : check Windows code 0, 290 backend / 15 web ; DB/S3 préservés |
| R0.3 | MUST | DONE | Audit20261025 : Réception historique conservée, non recertifiée ; AU-01 à AU-09 si impact. Preuve historique (non réception actuelle) : 4f8d7e2 : check Windows 340/35, QA 58, E2E 9, préservation et secrets verts |
| R0.4 | MUST | DONE | Audit20261025 : Réception historique conservée, non recertifiée ; AU-01 à AU-09 si impact. Preuve historique (non réception actuelle) : 8f8f1d15d8dce4dc4acc84e4dda7a30e77b41482 ; 65 fichiers / dix cellules, check 411/35 et QA 72 codes 0, données actives préservées |
| R0.5 | MUST | DONE | Audit20261025 : Réception historique conservée, non recertifiée ; AU-01 à AU-09 si impact. Preuve historique (non réception actuelle) : 9559e75 : source-cell ; QA 327/20, Windows 718/35/build code 0, DB/Bronze préservés ; pas source live/modèle qualifiés |
| R0.6 | MUST | DONE | Audit20261025 : Réception historique conservée, non recertifiée ; AU-01 à AU-09 si impact. Preuve historique (non réception actuelle) : A/B1/B2/C intégrés main 173c41a ; Windows 80378 FINAL 0/1462 backend/35 web/build ; inclusion 805/118/snapshot exact/actif préservé ; logiciel reçu, pas de collecte live/modèle/humain qualifié |
| R0.7 | MUST | DONE | Audit20261025 : Réception historique conservée, non recertifiée ; AU-01 à AU-09 si impact. Preuve historique (non réception actuelle) : main442a20c, source971702e : Windows1538/35/build, E2E9, inclusion160, empreinte exacte, préservation et gitleaks0 ; aucun KPI marché qualifié |
| R0.8 | MUST | IN_PROGRESS | AU-08 reçu logiciel et clone, PR6 8283fe0/CI40825552642 ; rejeu réel une édition,15 valeurs imputées, Gold vide et recalcul abstenu. AU-09/B-R073 exige toujours deux éditions authentiques corrigées ; B-R098 historique distinct. Aucun gate reçu. |
| R0.9 | MUST | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  Gate R0 franchi : suite QA R0.8 87/87 tests passants, replay 0 external routes, isolation réseau et preuve machine ; AU-09 (2f38abe) |
| R1.1 | MUST | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  Requalification du registre sources.yaml (18 sources conformes au schéma Pydantic, séparation active/disabled/planned) ; AU-10 (6ccf36d) |
| R1.2 | MUST | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  Moteur CatalogDiscoveryEngine, détection de dérive fail-closed et découverte d'éditions ; AU-10 (6ccf36d) |
| R1.3 | MUST | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  Qualification INSTAT NIPC, découverte dynamique, multi-feuilles, conservation base 2011/2016 (10 tests verts, qa R1.3 vert) ; AU-11 |
| R1.4 | MUST | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  Qualification MiASA ODR, CC-R authentique (12 tests verts, extraction 3 éditions PDF, 0 ND/NA converti en 0) ; AU-11 |
| R1.5 | MUST | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  Qualification MinCC PPN, séparation prix plafond vs constaté, anti-PII, silence stock respecté (13 tests verts) ; AU-11 |
| R1.6 | MUST | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  Qualification Douanes Stats, distinction flux mensuels vs totaux annuels, nomenclature SH (11 tests verts) ; AU-11 |
| R1.7 | MUST | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  Qualification WFP HDX, politique disabled respectée sans bypass, gestion HXL et marchés non résolus (7 tests verts) ; AU-11 |
| R1.8 | MUST | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  Qualification Banque mondiale RTFP, schéma C3 (wfp_fao), drapeaux d'imputation préservés (11 tests verts) ; AU-11 |
| R1.9 | MUST | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  Qualification FAOSTAT, distinction paddy/blanchi, drapeaux d'estimation visibles (8 tests verts) ; AU-11 |
| R1.10 | MUST | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  Requalification géographique, 23 régions Loi 2021-010 et 119 districts, géométries valides (24 tests géographiques verts) ; AU-10 (6ccf36d) |
| R1.11 | MUST | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  Qualification NASA POWER, cohérence physique Tmin<=Tmax, sentinelles -999, politique disabled respectée (11 tests verts) ; AU-11 |
| R1.12 | MUST | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  Actualisation, reprise idempotente, santé des sources et outbox API (20 tests verts) ; AU-11 |
| R1.13 | MUST | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  Gate de collecte réelle R1 validé : l'ensemble des sources socles R1.3–R1.12 qualifiées unitairement et en intégration (93 tests verts, zéro réseau, 100% conformes CC-R) ; AU-11 |
| R2.1 | MUST | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  6 tests passants (test_contracts_time_origin_macro.py), C1-C4, métriques macro avec vintage/first_available_at, qa R2.1 vert id b3aa1d9179c7482095a0da8c5019a19c |
| R2.2 | MUST | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  38 tests passants (test_taxonomy.py, test_taxonomy_units_audit.py), conversions massiques/volumiques étayées, alias <0.90 en revue |
| R2.3 | MUST | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  43 tests passants (test_gold_dq_aggregation_audit.py 36, test_gold_dq.py 7 intégration), alignement calendaire, étanchéité de familles |
| R2.4 | MUST | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  16 tests passants (test_market_coverage_and_pilot.py), matrice SQL gold.market_coverage, pilote riz local/importé (Analamanga MDG11, Alaotra-Mangoro MDG31, Atsinanana MDG33 + National) |
| R2.5 | MUST | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  15 tests passants (test_instat_tbe.py), connecteur instat_tbe, ingestion Excel multi-éditions, fréquences réelles sans interpolation |
| R2.6 | MUST | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  17 tests passants (test_bfm_public.py), connecteur bfm_public, cours USD/EUR, jours ouvrés stricts |
| R2.7 | MUST | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  14 tests passants (test_omh_public.py), connecteur omh_public, gazole/super/pétrole, date d'effet vs date de publication |
| R2.8 | MUST | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  19 tests passants (test_economic_dashboard.py), tableau économique interprétable, dimensions étanches, fiches métriques, gestion stricte nullité |
| R2.9 | MUST | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  57 tests passants (test_api_extensions_and_limits.py 6, test_gold_availability_api.py 51), pagination [1, 1000], exports CSV/JSON alignés |
| R2.10 | MUST | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  80 tests vitest passants (13 suites, 3.51s), TypeScript 0 erreur, Next lint 0 erreur, build 17 routes compilées sans erreur |
| R2.11 | MUST | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  Gate R2 validé : 6 tests décisionnels Q1-Q5 passants (test_gate_r2_decision_observatory.py, qa R2.11 vert id dec203303fb54f8c8ae46a2f57ebf483), suite Playwright e2e 26/26 conformes |
| R3.1 | MUST | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  16 tests passants (test_ml_series_eligibility.py), clé 5 composantes, grille sans compression, 36m min, 12m récents, cohortes |
| R3.2 | MUST | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  8 tests passants (test_ml_as_of_dataset.py), datasets historiques as-of C2/C4, traçabilité temporelle, empreinte SHA-256 canonique |
| R3.3 | MUST | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  9 tests passants (test_ml_models_conformance.py), références et baselines conformes, NaiveLast, SeasonalNaive, AutoETS, AutoARIMA |
| R3.4 | MUST | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  6 tests passants (test_ml_backtest_protocol.py), protocole trois phases, étanchéité de sélection, 6 rolling origins, holdout indépendant |
| R3.5 | MUST | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  5 tests passants (test_ml_conformal_intervals.py), intervalles conformes, seuil N_calib >= 8, uncalibrated_heuristic, Wilson 95% |
| R3.6 | SHOULD | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  11 tests passants (test_ml_exogenous.py), évaluation exogènes macro BFM/OMH et climat, protocole d'ablation 4 familles |
| R3.7 | MUST | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  4 tests passants (test_ml_forecast_publication.py), publication et abstention normatives, seuils MAPE <= 15% et Directional >= 60% |
| R3.8 | MUST | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  7 tests passants (test_ml_matured_evaluation.py), suivi des échéances, benchmarking baselines, traçabilité des erreurs |
| R3.9 | MUST | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  Gate R3 validé : 6 tests décisionnels passants (test_gate_r3_price_forecast.py, qa R3.9 vert id 9cf8ade55ae8444f94ff48e71bda777a) |
| R4.1 | MUST | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  8 tests passants (test_geo_agroclimate_contracts.py), contrats géospatiaux/agroclimatiques, modèle météo observée vs prévue, calendriers culturaux, migration 0014 |
| R4.2 | MUST | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  7 tests passants (test_chirps.py), connecteur CHIRPS v2.0, double cycle préliminaire/final, nodata vs 0 mm, découpage Madagascar |
| R4.3 | MUST | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  6 tests passants (test_meteo_mg.py), connecteur meteo_mg, extraction déterministe bulletins DGM, séparation émission/validité |
| R4.4 | MUST | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  8 tests passants (test_fewsnet_ipc.py), connecteurs fewsnet_mdg et ipc_mdg, séparation stricte courant vs projeté |
| R4.5 | MUST | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  7 tests passants (test_ecmwf_open.py), connecteur ecmwf_open, météo prévue archivable obs.weather_forecast |
| R4.6 | MUST | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  7 tests passants (test_geo_anomalies.py), module ketrika.geo.anomalies, seuil baseline N>=10 ans, abstention si insuffisant |
| R4.7 | MUST | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  8 tests passants (test_crop_calendar_versioning.py), versioning calendriers culturaux, disjonction baseline vs recommandation, corridors commerciaux prouvés |
| R4.8 | SHOULD | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  9 tests passants (test_geo_remote_sensing.py), télédétection agro-environnementale, masquage nuages Sentinel-2, NDVI/VCI sous masque cultivé |
| R4.9 | SHOULD | TODO | Non-bloquant SHOULD : Données sol et topographie déclarées indisponibles (statut unavailable) |
| R4.10 | SHOULD | TODO | Non-bloquant SHOULD : Aléas extrêmes cyclones/inondations déclarés indisponibles (statut unavailable) |
| R4.11 | MUST | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  16 tests passants (test_geo.py), API /v1/climate/* (6 endpoints), vue web multicouche explicable, météo observée vs prévue étanche |
| R4.12 | MUST | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  Gate R4 validé : 8 tests décisionnels passants (test_gate_r4_agroclimate.py, qa R4.12 vert id 7e0e790ec5c149fbb72b82f66d0e59d4) |
| R5.1 | MUST | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  ADR-088, SPECS §27, 3 cibles (production, arrivages, stocks), protocole anti-PII, prévention double comptage, 7 tests verts |
| R5.2 | MUST | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  Connecteur market_supply, Bronze SHA-256, migration 0016, 6 tests passants |
| R5.3 | MUST | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  Contrôle des quantités et couverture, matrice marché × période, non-équivalence absence relevé / zéro kg, 6 tests passants |
| R5.4 | MUST | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  Modèle de fenêtre de récolte décadaire, ajustement hydrique agronomique, 6 tests passants |
| R5.5 | SHOULD | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  Modèle superficie x rendement, conversion sourcée ODR/FAOSTAT paddy->milled 0.667, 8 tests passants |
| R5.6 | MUST | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  Bilan d'offre physique sans double comptage douanes vs marchés, équation de conservation, 5 tests passants |
| R5.7 | MUST | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  Prévision des fenêtres et pics d'arrivage, décalage logistique, as-of cutoff, 7 tests passants |
| R5.8 | MUST | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  Scénarios d'offre et pilote décisionnel pour 3 profils d'acteurs, interdiction ordres d'achat, 7 tests passants |
| R5.9 | MUST | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  Gate de récoltes, volumes et approvisionnement qualifié, 10 critères normatifs validés, qa R5.9 vert id fb687c17d69f474a963ca91867a1dab1 |
| R6.1 | MUST | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  Sécuriser les outils de lecture, catalogue typé, SQL guard CTE écriture/fonctions réseau, validation sans fuite, 15 tests passants |
| R6.2 | MUST | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  Borner les workflows IA et leurs reprises, budget atomique, max tokens/temps, 9 tests passants |
| R6.3 | MUST | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  Répondre avec des résultats exécutés et référencés, faits cités formatés serveur, 6 tests passants |
| R6.4 | MUST | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  Évaluer le copilote sur questions métier indépendantes, zéro requête interdite, 3 tests passants |
| R6.5 | MUST | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  Qualifier le bulletin sans hallucination numérique ou sémantique, Mailpit uniquement, 10 tests passants |
| R6.6 | MUST | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  Évaluer alertes et scénarios de risque, familles indépendantes, seuils recomputables, 11 tests passants |
| R6.7 | MUST | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  Durcir accès, audit et sécurité applicative, RBAC, révocation session, zéro secret, 16 tests passants |
| R6.8 | MUST | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  Sauvegarde et restauration isolée qualifiées, clone dédié, refus actif, 12 tests passants |
| R6.9 | MUST | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  Superviser fraîcheur, dérive, dépenses et incidents, alertes Mailpit, états persistants, 7 tests passants |
| R6.10 | MUST | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  Mesurer performance et préparer déploiement humain, P95 < 1s normatif, 5 tests passants |
| R6.11 | MUST | IN_PROGRESS | Ciblés rapportés conservés, réception finale non acquise :  Réception finale complète du programme R, tag mi-v0.2.0-local-qualified, rapport MARKET_INTELLIGENCE_REPORT.md et passation HANDOFF.md |

## 1. Résultat attendu et limites d'autorité

### 1.1 Les cinq produits à construire

1. **Observatoire de marché** : prix comparables, stocks et flux disponibles, anomalies, provenance, couverture et fraîcheur.
2. **Observatoire économique** : inflation, change, carburants, commerce et conjoncture selon les séries effectivement disponibles ; pas de score global opaque de « santé ».
3. **Observatoire agro-environnemental** : campagne agricole, précipitations, risques météo, état des cultures et signaux environnementaux, chacun avec son niveau de preuve.
4. **Anticipation** : prix à un à trois mois, fenêtres de récolte et, lorsque les quantités permettent une validation, fenêtres d'approvisionnement des marchés.
5. **Aide à la décision institutionnelle** : vues métier, scénarios explicites, alertes, bulletin et copilote traçables ; aucune décision publique, commande d'achat ou diffusion externe automatisée.

Le pilote commence par riz local/importé. Paddy, riz blanchi, variétés et niveaux producteur/gros/détail restent distincts. Les zones et l'éventuel second produit sont choisis en R2.4 à partir de la couverture constatée. Les prévisions de prix restent régionales/nationales conformément à ADR-004 ; aucun passage à la commune sans nouvelle décision et preuve suffisante.

### 1.2 Corrections et extensions

- R0, R1 et les corrections normatives de R2/R3 : fiabilisation du MVP, sans réécrire son historique de livraison.
- Macroéconomie au-delà des schémas actuels, disponibilité historique, nouvelle météo prévue, OCR, télédétection et modèles d'offre : extensions, avec contrat et ADR avant code.
- Les ADR servent à documenter les décisions permises, **jamais** à lever une interdiction d'AGENTS.md.
- H1/H2/H5 restent non bloquants selon leurs replis ; H3/H6 restent bloquants ; H4/H7 restent interdits. Une clé présente ou une variable `EXTERNAL_SEND_ENABLED=1` ne constitue pas une autorisation humaine d'envoi.
- Aucun achat, provisionnement, contact de tiers, scraping privé, collecte de coordonnées individuelles, proxy rotatif ou contournement. Les partenariats et essais avec utilisateurs externes sont préparés pour l'humain.

### 1.3 Définir les capacités sans surpromesse

Chaque capacité porte un état de qualification distinct du statut des tâches : `NOT_EVALUATED`, `OFFLINE_TESTED`, `LIVE_VERIFIED`, `PARTIAL`, `UNAVAILABLE`. Leur contrat documentaire est intégré dans SPECS en R0.1 ; la persistance API/DB reste à spécifier et implémenter en R2.1. Ce ne sont pas des statuts déjà présents en base.

- `OFFLINE_TESTED` peut prouver un parseur sur une archive authentique ; il ne prouve pas une collecte actuelle.
- Une fixture synthétique peut prouver une logique de logiciel, jamais la couverture réelle ou la performance économique.
- Une capacité prévisionnelle porte en plus `experimental`, `validated` ou `abstained`, avec justification et périmètre.
- Une tâche n'est `DONE` que si tous ses critères passent. Un gate incomplet reste `BLOCKED` ou `IN_PROGRESS` selon AGENTS, jamais « DONE partiel ».
- Un repli ne permet le `DONE` que si la fiche l'autorise explicitement et si la limitation reste visible. Sinon consigner les sous-livrables et le blocage, puis avancer sur les tâches indépendantes.

## 2. Mode d'emploi pour l'agent d'exécution

### 2.1 Reprise, ordre et journal

Après autorisation d'exécuter : commencer par R0.1, sans lancer `demo`, `reset` ou `restore` sur l'environnement courant. Avant chaque tâche, lire intégralement AGENTS, puis PROGRESS/BLOCKERS et les sections normatives pertinentes. Revérifier les chemins cités, l'état git et les modifications concurrentes.

Appliquer la boucle d'AGENTS : plus petit identifiant éligible, MUST en priorité ; dépendances toutes `DONE`, statut non `BLOCKED`. Les indices après le point sont numériques : R1.9 précède R1.10. Les branches indépendantes peuvent avancer pendant les attentes réseau, mais l'agent travaille seul par défaut ; aucune délégation n'est nécessaire à ce plan.

R0.1 précise le traitement des MUST bloqués et des SHOULD éligibles pour éviter une attente passive, sans déclarer les MUST terminés. Toute tâche `IN_PROGRESS` à la reprise est revérifiée depuis ses critères d'acceptation.

PROGRESS reste la seule mémoire d'exécution. Y créer en R0.1 une table R, séparée de la table T, avec `ID | priorité | statut | début UTC | fin UTC | commit | preuve | incident`. Une absence de ligne n'est jamais interprétée comme `DONE`. Tous les statuts initiaux sont `TODO`, sans démarrer les tâches lors de cette planification.

Pour chaque tâche : mini-plan de dix lignes maximum ; tests ciblés ; contrôle global ; commit atomique vert Conventional Commits avec portée R ; preuves et hash ; dépendances et prochaine tâche éligible. Ne pas pousser, merger ni modifier un remote sur la seule base de ce document.

### 2.2 Environnement sûr

- Python, Node, générateurs OpenAPI, tests, navigateurs et analyse géospatiale s'exécutent dans Docker, code monté sur `/app`. Pas de `node_modules` ou `.venv` dans le bind mount, ni de Node hôte pour les scripts E2E.
- Conserver l'entrée unique `scripts/dev.ps1`, avec équivalent `scripts/dev.sh` sous Linux/WSL ; chemins avec espaces et `#` traités littéralement.
- Utiliser un projet Compose de qualification distinct, ports disponibles, base dédiée, compte S3 dédié, préfixes d'objets et volumes nommés explicitement identifiés. Ne pas arrêter les autres stacks.
- Les gates du plan MVP utilisent actuellement `reset`. Avant toute réutilisation, R0.1/R0.2 doivent remplacer le gate R par une initialisation **isolée et non destructive**. Ne jamais exécuter le reset actuel : il supprime aussi un volume contenant le Bronze, incompatible avec son immutabilité.
- `rebuild` et `restore` modifient Silver/Gold : exécution uniquement sur destination isolée et validée. Sauvegarder/relever l'état initial ; aucun nettoyage de la base active ou suppression d'objet Bronze pour faire passer un test.
- Les négatifs d'intégrité utilisent un faux store en mémoire ou une réponse d'accès simulée ; aucun objet Bronze n'est altéré ni supprimé.
- Secrets uniquement par environnement non versionné ; journaux expurgés. Horodatages UTC ; présentation métier `Indian/Antananarivo`.

### 2.3 Commandes existantes et commandes à créer

Les noms à créer ci-dessous sont des propositions de contrat CLI, pas des commandes déjà disponibles. L'agent les implémente et documente en R0.2/R0.3/R0.7 avant de les utiliser.

| Commande | Usage et limite |
|---|---|
| `./scripts/dev.ps1 check` | Existe ; R0.3 doit garantir lint, format, types, backend unitaires/intégration, front lint/types/tests/build ; aucun sous-ensemble silencieux |
| `./scripts/dev.ps1 test` / `e2e` | Existent ; les diriger vers l'environnement de qualification ; E2E dans Docker |
| `./scripts/dev.ps1 validate-registry` | Existe ; étendre la validation aux nouveaux champs et preuves |
| `./scripts/dev.ps1 test-network` | Existe ; seulement sources autorisées, quotas et arrêt de politique respectés |
| `./scripts/dev.ps1 backfill <source_id>` | Existe ; seulement après qualification du connecteur et estimation de volume/budget |
| `./scripts/dev.ps1 qa-isolated <commande> [arguments]` | À créer R0.2 : sélection explicite de destination dédiée, refus des cibles protégées, puis commande dans Docker |
| `./scripts/dev.ps1 qa <task_id>` | À créer R0.3 : manifeste explicite de tests/critères par tâche ; tâche inconnue ou suite vide = échec |
| `./scripts/dev.ps1 qualify <R0…R6\|all>` | À créer R0.7 : résultats mesurés JSON/Markdown, état par capacité et code non nul si un critère obligatoire échoue ou manque |

Ne pas ajouter un runner concurrent. Prévoir exactement les mêmes sémantiques de code de sortie dans les deux scripts. Un conteneur ou une image de tests absent doit produire un diagnostic non nul, jamais « skip success ».

### 2.4 Dossier de preuve et définition commune de DONE

Chaque tâche produit `docs/evidence/<task_id>/README.md` avec : commit et environnement, UTC, commandes et codes de sortie, compte réel de tests exécutés/skippés/échoués, métriques avec numérateur/dénominateur, périmètre des données et limites. Les gros fichiers restent dans un stockage d'artefacts référencé par manifeste/empreinte ; pas de secrets ni de Bronze dupliqué sans droits vérifiés dans git.

Le rapport lisible renvoie au résultat machine, aux observations et aux manifestes de documents/datasets. Chaque export de preuve comporte unité, fréquence, filtre, grain et origine réel/synthétique. Une capture d'écran seule n'est pas preuve de persistance : inclure requête API, rélecture DB et rechargement UI quand applicables.

**DONE commun**, applicable à toutes les fiches : critères particuliers tous passants ; `check` global vert et intégration réellement exécutée ; tests du comportement modifié ; couverture core/extraction/normalize ≥ 80 % ; docs et backlog à jour ; aucun secret/debug/TODO orphelin ; commit atomique et PROGRESS mis à jour. Une dette fonctionnelle exigée ne se contourne pas par un skip. L'impossibilité d'exécuter les critères doit être consignée, pas présentée comme un test vert.

La preuve référencée par PROGRESS décrit le commit fonctionnel vérifié ; un éventuel commit de clôture documentaire référence ce hash sans chercher une auto-référence impossible du commit dans son propre contenu.

### 2.5 Sources indisponibles, budget et reprise

Respecter AGENTS §6/SPECS §12 : trois tentatives espacées d'une heure pour indisponibilité, avec progression sur d'autres tâches ; un challenge impose l'arrêt immédiat ; 429 respecte `Retry-After` et budget. Ne pas multiplier les voies/identités pour contourner un refus. Une ancienne archive publique Wayback exige son URL d'origine et `retrieved_via=wayback`.

Consigner cause racine et chaque tentative dans BLOCKERS. Source dégradée/désactivée et repli : ADR obligatoire. Absence de clé LLM : replay ; absence de résultat réel : `PARTIAL`/`UNAVAILABLE` pour la capacité, pas une donnée inventée.

Une acquisition manuelle est admissible uniquement si un humain fournit un document avec droits, origine et provenance identifiables. Ce n'est pas une qualification du téléchargement automatique. La revue humaine H5 est facultative : garder `human_reviewed=false` tant qu'elle n'a pas eu lieu.

## 3. Contrats transversaux à formaliser avant le code concerné

Ces contrats sont des exigences du programme. Les noms de nouvelles tables/routes se décident dans l'ADR et SPECS correspondants ; ne pas faire croire qu'ils existent déjà.

### C1 — Manifestes d'acquisition et authenticité

Pour chaque document : `source_id`, URL d'origine, page catalogue parent, chaîne de redirection autorisée, date de découverte, fetch UTC, publication si prouvée, statut HTTP, MIME, taille, SHA-256 réel, clé Bronze, méthode d'accès et droits. Pour fixtures : `authentic|synthetic|unverified` (ADR-014), origine, licence, annotateur et revue humaine. Un hash a 64 caractères hexadécimaux et correspond aux octets, pas seulement au format. Une origine inconnue reste `unverified`, jamais authentique par déclaration. Seul un document authentique avec preuve d'acquisition/droits et attendu indépendant est éligible au corpus réel ; les objets de corpus locaux non ingérés portent `bronze_object_key: null` explicitement, pas une clé Bronze inventée.

### C2 — Temps, disponibilité et révisions

Séparer période observée, publication, première disponibilité prouvée, collecte et révision. La disponibilité peut être prouvée par publication datée et archive corroborante ; sinon utiliser conservativement la première collecte. **Ne jamais antidater la disponibilité sur la seule base d'un mois dans un fichier.** Les archives récupérées aujourd'hui ne suffisent pas à recréer un backtest « comme à l'époque ».

Conserver origine de la preuve de disponibilité et niveau de certitude. Les états historiques utilisent les versions accessibles à l'origine, pas la dernière vue `*_current`. Bronze et observations restent ajout-seul. La météo actuellement unique par fournisseur/lieu/date/variable exige un contrat de révision avant d'ingérer préliminaire/final.

### C3 — Sens métier et dépendance des sources

Séparer : type de dataset réel/synthétique ; observé/imputé/estimé ; prix constaté/réglementé/valeur unitaire de commerce ; niveau d'acteur ; produit/variété/qualité ; quantité stock/arrivage/vente/production ; indice/niveau de prix. Ajouter famille de provenance et transformations pour ne pas compter WFP et ses dérivés comme deux confirmations indépendantes.

L'API conserve `observed_or_imputed` et `value_kind` prescrits ; un éventuel type supplémentaire est défini sans ambiguïté dans SPECS, pas mappé opportunément vers « Observé ». Une déclaration de quantité reste une déclaration, une hypothèse de scénario reste une hypothèse.

### C4 — Données de modèle et publication

Un dataset d'entraînement a identifiant, version, empreinte du contenu canonique, liste d'observations/artefacts, règles de sélection, date d'origine et versions de code/taxonomies/géographie. Un run indique modèle demandé/effectif, paramètres, repli, métriques, calibration, exclusions et données connues à l'origine. Les cibles d'évaluation sont observées et hors entraînement ; les séries estimées restent séparées.

En l'absence de vintages, fournir une analyse rétrospective clairement nommée, pas un backtest historique as-of certifié. Les intervalles ou probabilités non validés portent un avertissement ; aucune probabilité détaillée déduite artificiellement de trois quantiles.

### C5 — Décision et scénarios

Une fiche décision contient question, utilisateur visé, produit/zone/période, faits calculés, facteurs suivis, hypothèses, scénario central et alternatives, incertitude, lacunes, sources et options d'action. Aucune action d'achat, dépense, message ou changement de politique ne suit automatiquement la sortie du copilote. Association statistique ≠ causalité.

## 4. Vue d'ensemble et jalons

| Phase | Tâches | Résultat contrôlé | Gate |
|---|---|---|---|
| R0 | R0.1–R0.9 | Qualification honnête, exécution isolée, rejeu prouvé | R0.9 |
| R1 | R1.1–R1.13 | Collecte réelle et actualisation des sources du socle | R1.13 |
| R2 | R2.1–R2.11 | Qualité, observatoire de marché et économie | R2.11 |
| R3 | R3.1–R3.9 | Prévisions de prix évaluées, sans fuite | R3.9 |
| R4 | R4.1–R4.12 | Agroclimat, météo et calendrier ; environnement optionnel | R4.12 |
| R5 | R5.1–R5.9 | Quantités, fenêtres de récolte et offre selon couverture | R5.9 |
| R6 | R6.1–R6.11 | Copilote, diffusion contrôlée, exploitation et réception | R6.11 |

Chaîne produit principale : `R0 → R1 → R2 → R3`, puis enrichissement `R4 → R5`. R6 peut commencer sur les branches qualifiées sans attendre toutes les données R5. Les dépendances détaillées des fiches prévalent sur cette vue ; une attente d'archive ne bloque pas automatiquement les autres connecteurs.

Le chemin jusqu'à un observatoire utile est R0 + les connecteurs accessibles de R1 + R2. La prévision d'abondance chiffrée est conditionnée par R5 ; elle n'est pas promise par la présence d'une page météo. Les tâches SHOULD sont des améliorations optionnelles ; elles ne bloquent pas les gates MUST, et ne sont jamais montrées comme livrées si omises.

## 5. R0 — Requalifier les fondations et les preuves

### R0.1 — Intégrer le programme dans la gouvernance

- **Priorité / dépendances :** MUST / aucune, après demande explicite d'exécution.
- **Lire / périmètre :** AGENTS §1–3/5–10 ; MVP §1.2/2.3/5 ; SPECS ; ADR ; PROGRESS ; ce plan.
- **Directives :** enregistrer un ADR du programme ; étendre mission, sélection des tâches R, conditions d'arrêt et gates isolés dans les documents normatifs. Maintenir H1–H7 et tous les interdits. Définir l'arrêt nominal R6.11 et l'arrêt avec HANDOFF si les tâches restantes exigent exclusivement une action humaine autorisée ; garder les blocages techniques dans le protocole. Ajouter les 74 lignes R en TODO dans PROGRESS, conserver T et tags historiques. Formaliser les extensions et le traitement des SHOULD lorsqu'aucun MUST n'est éligible ; ne pas changer silencieusement les critères du MVP.
- **Livrables :** gouvernance cohérente, table de reprise, ADR et mapping corrections/extensions.
- **Acceptation / tests :** lecture croisée sans contradiction mission/arrêt/permissions ; chaque ID R unique ; chaque dépendance définie ; aucun ancien DONE/tag supprimé. Check documentaire puis DONE commun ; preuve `docs/evidence/R0.1/README.md`.

**Bootstrap sans faux vert :** si les scripts actuels ne permettent pas le DONE commun en isolation, réaliser dans R0.1 le strict minimum de sécurité/exécution de R0.2/R0.3 nécessaire à sa propre validation, en journalisant ce chevauchement. Ne pas marquer R0.1 DONE ni committer sur main avec contrôles rouges. R0.2/R0.3 restent TODO jusqu'à la vérification complète de leurs critères ; aucun skip de la Definition of Done n'est créé.

### R0.2 — Isoler l'environnement de qualification

- **Priorité / dépendances :** MUST / R0.1.
- **Lire / périmètre :** Compose, `.env.example`, core/settings, scripts/dev, runbooks backup/restore ; ADR-007.
- **Directives :** créer une configuration Compose de qualification dédiée sans recopier de secrets en git. Implémenter `qa-isolated` avec contrôle du projet, de la base, du bucket/préfixe et des volumes cibles ; refuser les destinations actives/production. Initialiser des bases vides sans `down -v` ; Bronze de qualification reste immuable. Séparer datasets réels, tests et démo ; retirer l'import d'un module `tests` du chemin de qualification réelle. Inventorier une éventuelle contamination existante en lecture seule, proposer sa mise à l'écart sans supprimer/modifier l'historique.
- **Livrables :** profil isolé, garde CLI, procédure de réhydratation d'archives authentiques autorisées, rapport d'inventaire.
- **Acceptation / tests :** profils réel/test non interchangeables ; seed synthétique refusé hors tests ; destination protégée refusée avant écriture ; compte/empreinte de l'environnement actif inchangés avant/après. Tests unitaires des gardes et intégration sur base dédiée ; DONE commun.

### R0.3 — Rendre les contrôles qualité complets et fiables

- **Priorité / dépendances :** MUST / R0.2.
- **Lire / périmètre :** SPECS §3.3/23 ; scripts/dev.ps1/dev.sh, web/package.json, `.github/workflows/ci.yml`, Dockerfiles.
- **Directives :** le runner actuel peut omettre l'intégration sans réseau nommé, ne lance que Vitest pour le front et appelle Node hôte pour E2E. Corriger ces chemins : découvrir le réseau dédié, assurer DB/S3/migrations, exécuter lint/types/build/tests front et backend complet hors réseau. Ajouter `qa <task_id>` par manifeste versionné et rapports machine ; suite vide/inconnue/skippée obligatoire = échec. Volumes de dépendances nommés ; même contrôle dans CI, sans clé LLM.
- **Livrables :** runners et CI cohérents, manifeste de tests R, logs/compteurs réels.
- **Acceptation / tests :** introduire des défauts uniquement dans copies de test : erreur lint, type, build et intégration donnent chacun code non nul. Front et intégration apparaissent exécutés. E2E fonctionne dans Docker depuis le chemin hôte avec `#`/espaces. Check global vert sur la version corrigée ; aucune suppression de test pour y parvenir.

### R0.4 — Étiqueter les fixtures et construire un jeu authentique

- **Priorité / dépendances :** MUST / R0.3.
- **Lire / périmètre :** SPECS §2/11.4 ; générateurs backend/scripts, tests/fixtures, tests/golden, e2e_data.
- **Directives :** inventorier origine/hash/droits de chaque fixture ; marquer les documents générés `synthetic`. Conserver les tests synthétiques séparément. Ajouter les archives officielles accessibles avec C1 ; ne pas fabriquer un bulletin ressemblant à une archive pour le qualifier. Transcrire le golden indépendamment du parseur ; PDFs texte contrôlés visuellement ; `human_reviewed=false` sauf preuve de revue.
- **Livrables :** manifestes d'authenticité, suites distinctes et procédure d'annotation.
- **Acceptation / tests :** chaque fixture a type et origine ; chaque attendu authentique remonte au document/page/cellule ; hash recalculé ; tailles ≤ 5 Mo/fichier et 50 Mo total ou manifeste externe. Tout document non authentifié est exclu de la qualification réelle. L'indisponibilité d'une source est portée à R1, pas cachée.

### R0.5 — Vérifier la provenance de bout en bout

- **Priorité / dépendances :** MUST / R0.3, R0.4.
- **Lire / périmètre :** SPECS §8/10/11/14 ; core/bronze.py, models/db.py, demo.py, checks Dagster.
- **Directives :** contrôler observation → source_record → clé Bronze → octets → SHA-256 ; vérifier preuve et coordonnées de la valeur. Dédupliquer la lecture des objets partagés. Séparer contrôle complet de certification et contrôle incrémental de run ; tous les objets publiés doivent avoir une vérification traçable. Un objet inaccessible n'est pas valide. Zéro valeur LLM non vérifiée en Gold.
- **Livrables :** vérificateur réutilisable, résultats DQ persistés, liste des anomalies sans données sensibles.
- **Acceptation / tests :** FK manquante, pseudo-hash, mauvais contenu simulé, objet absent simulé et preuve numérique d'une mauvaise ligne échouent. Un artefact authentique passe avec valeurs relues. Mauvaise provenance bloque Gold ; 100 % des observations publiées validées, numérateur/dénominateur consignés.

### R0.6 — Corriger la lignée Dagster et les erreurs silencieuses

- **Priorité / dépendances :** MUST / R0.5.
- **Lire / périmètre :** SPECS §9/14 ; connectors/runner.py, pipelines/factory.py/definitions.py.
- **Directives :** Bronze retourne les références exactes d'artefacts ; Silver les consomme sans refetch. Remplacer asset checks constants par mesures. L'échec de construction d'une définition doit être explicite, pas ignoré par `continue`. Vérifier le nombre attendu d'assets/schedules en tenant compte des sources disabled. Partitions et run_id suivent le document/version ; retry idempotent.
- **Livrables :** assets et checks traçables, tests de construction/partition/reprise.
- **Acceptation / tests :** compteur HTTP inchangé pendant Silver ; même artefact rejoué deux fois sans doublon ; révision crée nouvelle ligne/supersession ; définition invalide signalée ; provenance/schema_drift bloquent le rafraîchissement concerné.

### R0.7 — Remplacer la certification déclarative

- **Priorité / dépendances :** MUST / R0.3, R0.5, R0.6.
- **Lire / périmètre :** demo.py, plan MVP §1.3/T11.6, tests d'évaluation et API/performance.
- **Directives :** implémenter `qualify` et réutiliser ses vérificateurs dans la réception ; aucun chiffre de tests ou golden codé en dur, aucune source planned comptée active qualifiée. Chaque critère renvoie mesure, seuil, dataset, preuve, état et raison. Exécuter les tests ou importer un rapport lié au même commit et environnement ; résultat absent/ancien/incomplet = inconnu ou échec. Une exécution sur données synthétiques porte « démonstration logicielle », pas certification opérationnelle.
- **Livrables :** JSON/Markdown de qualification versionnés, test des codes de sortie.
- **Acceptation / tests :** supprimer une preuve dans un dossier de test simulé ou fournir un rapport ancien empêche le succès ; suite rouge et source planned ne passent pas ; aucun seed automatique ; un résultat négatif explique son numérateur/dénominateur. Les écarts aux dix séries ou neuf sources restent visibles et ne sont pas compensés artificiellement.

### R0.8 — Prouver le rebuild hors ligne sur le contenu

- **Priorité / dépendances :** MUST / R0.2, R0.4, R0.6, R0.7.
- **Lire / périmètre :** pipelines/rebuild.py, integration/test_rebuild.py, SPECS §8.1/10/15.
- **Directives :** travailler sur clone dédié avec un corpus authentique accessible et des révisions. Bloquer réellement l'accès réseau de la phase parse/normalize/load, pas seulement via une variable contournable. Comparer manifestes canoniques avant/après : valeurs, périodes, unités, origine, révisions, liens et Gold ; ignorer UUID/temps techniques seulement via mapping documenté. Vérifier l'inventaire Bronze inchangé. Prévisions recalculables depuis dataset/modèle versionnés en étape séparée.
- **Livrables :** runbook, manifestes complets, diff machine.
- **Acceptation / tests :** comptes ET empreintes métier identiques ; zéro requête réseau ; ancienne/nouvelle version correctement rejouées ; modification d'une valeur en faux parseur détectée même si compte identique. Aucun court-circuit sur « base déjà non vide ».

### R0.9 — Gate de fiabilité

- **Priorité / dépendances :** MUST / R0.1–R0.8.
- **Directives :** exécuter `qa-isolated check`, `test`, les E2E existants pertinents et `qualify R0`. Résumer résultats réels et limites ; conserver les historiques sans les recertifier rétroactivement.
- **Acceptation :** tous les critères R0 passent, contrôle complet et rejeu hors ligne prouvés ; aucun seed synthétique dans la qualification réelle. Une source indisponible n'empêche pas ce gate logiciel si un corpus authentique suffisant aux tests R0 est disponible, mais sa collecte demeure non qualifiée.
- **Clôture :** résumé ≤ 15 lignes, hash et tag nouveau `mi-r0-qualified` seulement si gate vert. Aucun déplacement des tags historiques.

## 6. R1 — Collecte réelle des sources du socle

### Contrat commun des connecteurs R1 (CC-R)

Chaque fiche R1.3–R1.11 hérite du présent contrat et de DONE commun : lire SPECS §5/9/11–14 et la fiche source ; découvrir depuis une entrée officielle prouvée ; HTTP poli ; C1 ; parsing déterministe d'abord ; bruts conservés ; inconnus en revue ; chargement transactionnel idempotent ; authenticité du corpus ; documentation et quotas.

Tests : au moins deux fichiers authentiques distincts quand la source publie des éditions, sauf réponse API unique admissible selon le plan MVP ; au moins trente valeurs annotées indépendamment pour les sources chiffrées, et les critères physiques pour NASA ; seuils normatifs golden 99 % par champ / 98 % rappel, parsing ≥ 99 % avec définition du dénominateur. Une nouvelle structure inconnue doit produire partial/schema_drift, pas une réussite vide. Deux exécutions du même document n'ajoutent pas de lignes ; une révision change la lignée sans écraser la valeur.

Preuve réelle : document/hash, enregistrements/pages, période/produits/lieux, part observée, requête API, rélecture DB et rejeu. L'actualisation est testée par deux acquisitions réelles datées, complétées par un serveur local représentant l'édition suivante ; si aucune nouvelle publication n'est survenue, déclarer « mécanisme testé, édition future non observée ».

Les refus d'accès de la recherche ne sont pas à contourner. Reprendre les incidents et consulter la politique avant tout fetch ; le connecteur peut être développé hors réseau sur archives authentiques autorisées. Si le critère de collecte réelle reste impossible, la tâche de qualification est BLOCKED, ses sous-livrables restent documentés et les autres sources avancent.

### R1.1 — Requalifier le registre et les permissions

- **Priorité / dépendances :** MUST / R0.9.
- **Périmètre :** registry/sources.yaml, core/registry.py, core/models/source.py, docs/sources.
- **Directives :** examiner les neuf MUST et toutes les nouvelles candidates ; preuve URL/robots/CGU/licence/attribution/droits, date et empreinte. Séparer permission documentée et qualification opérationnelle ; `approved` juridique ne vaut pas opinion juridique inventée. Définir cadence de collecte, observation et publication distinctes ; quotas persistants par domaine et famille de source. Contrat nouveau = ADR/SPECS.
- **Acceptation / tests :** source active sans preuve obligatoire rejetée selon contrat ; unknown n'est pas approved ; licence actuelle reliée au document applicable et exceptions. URLs non vérifiées explicitement marquées ; registry validé ; sources arrêtées consignées avec ADR et BLOCKER.

### R1.2 — Développer découverte et suivi des éditions

- **Priorité / dépendances :** MUST / R1.1.
- **Périmètre :** connectors/base.py/runner.py, core/http.py/policy.py, sensors et manifestes C1.
- **Directives :** découvrir catalogue/index/RSS/API avec pagination bornée et liens parent ; suivi durable ETag/Last-Modified et hash. Vérifier redirections et URLs candidates avant accès : domaines autorisés, pas localhost/IP privée/métadonnées cloud ; mêmes protections pour navigateur et documents contenant des liens. Persister budget/reprise ; 304 conserve le lien connu sans nouvel artefact. Distinguer aucune édition nouvelle, échec découverte et parsing vide.
- **Acceptation / tests :** édition suivante découverte sur catalogue de test ; fichier remplacé à même URL crée version ; lien privé/redirection interdite bloqués ; robots et challenge respectés ; reprise sans doublons après interruption.

### R1.3 — Qualifier INSTAT NIPC

- **Priorité / dépendances :** MUST / R1.2.
- **Périmètre :** connectors/instat_nipc.py, tests associés, docs/sources/instat_nipc.md.
- **Directives :** remplacer `nipc_sample.xlsx` comme ressource de production par pièces jointes découvertes sur les publications officielles. Extraire série, base, portée géographique, mois, date de publication et révisions ; gérer feuilles/français/fusions/cellules ND. Un indice n'est pas Ar/kg ; ne pas le charger en prix de marché.
- **Acceptation / tests :** CC-R ; historique et édition récente authentiques ; au moins deux séries alimentaires identifiées si publiées, sinon inventaire explicite ; changement de base conservé, jamais raccordé silencieusement ; comparaison de cellules à leurs valeurs DB.

### R1.4 — Qualifier l'Observatoire du Riz

- **Priorité / dépendances :** MUST / R1.2, R0.4.
- **Périmètre :** connectors/miasa_odr.py, extraction/pdf.py/evidence.py, golden ODR.
- **Directives :** découvrir les éditions réelles, récent/ancien/formats distincts disponibles ; ne pas supposer valides les trois URL fixes actuelles. Extraire riz paddy/local/importé, variété, acteur, zone, unité, période et page/ligne. PDF sans texte : revue ; OCR seulement après contrat d'extension autorisé, jamais preuve LLM inventée.
- **Acceptation / tests :** CC-R ; golden indépendant contrôlé visuellement ; au moins trente valeurs authentiques ; cellule du tableau voisin refusée comme preuve ; changement de mise en page détecté ; documents générés exclus du taux de qualification.

### R1.5 — Qualifier les publications MinCC/PPN

- **Priorité / dépendances :** MUST / R1.2, R0.4.
- **Périmètre :** connectors/mincc_ppn.py, records.py, normalize, tests MinCC.
- **Directives :** remplacer les dix publications simulées comme catalogue réel ; inventorier documents publics français/malagasy disponibles. Distinguer prix constatés, plafonds, stocks ordinaux et quantités ; aucun statut de stock déduit d'un silence. Conserver lieu/période et libellés bruts ; registre sans données personnelles.
- **Acceptation / tests :** CC-R ; prix réglementé et constaté restent séparés dans Gold/API ; déclaration de stock non transformée en tonnes ; publication sans observation utile donne résultat documenté ; aucun champ personnel ingéré.

### R1.6 — Qualifier les statistiques douanières

- **Priorité / dépendances :** MUST / R1.2.
- **Périmètre :** connectors/douanes_stats.py, trade_flow, taxonomy/products.yaml.
- **Directives :** utiliser le catalogue actuel plutôt qu'une URL CSV 2024 supposée. Vérifier nomenclature/version HS et unités/valeurs/périodes/régimes ; total annuel distinct des mois pour éviter double comptage. Quantité en kg/tonnes et valeur monétaire gardent leurs preuves. Une valeur unitaire importée reste un indicateur calculé, pas un prix de détail.
- **Acceptation / tests :** CC-R ; codes utilisés vérifiés ou non mappés ; agrégations cohérentes avec total officiel dans tolérance expliquée par arrondis ; révision et doublons édition/annexe gérés ; brut poids/valeur relisible.

### R1.7 — Qualifier WFP/HDX sous politique stricte

- **Priorité / dépendances :** MUST / R1.1, R1.2.
- **Périmètre :** connectors/wfp_hdx_mdg.py, fiche source, incidents 403 de l'audit.
- **Directives :** vérifier l'état de politique avant accès ; aucun navigateur/proxy de contournement. Utiliser seulement distribution officielle autorisée ou archive authentique permise. Ressource identifiée par métadonnées du catalogue ; gérer HXL, type de prix, produit/variété et marchés géolocalisés sans inventer un P-code. Si source disabled, rester hors réseau et documenter la capacité unavailable.
- **Acceptation / tests :** CC-R si accès autorisé ; origine des relevés/estimations documentée ; acteur et unité exacts ; marché non résolu en revue, pas attribué à une région par défaut. Collecte réelle non accessible = qualification BLOCKED, pas active grâce à la fixture.

### R1.8 — Qualifier Banque mondiale RTFP

- **Priorité / dépendances :** MUST / R1.2.
- **Périmètre :** connectors/wb_rtfp_mdg.py, fiche RTFP, schéma C3.
- **Directives :** suivre le catalogue et la version officielle Madagascar ; télécharger seulement la ressource réellement liée. Documenter signification des colonnes, flags, couverture, période et révisions. Mapper observé/imputé/estimé sans présumer leur sens ; inconnu en revue. Enregistrer dépendance WFP/FAO et modèle d'imputation lorsqu'indiqué.
- **Acceptation / tests :** CC-R ; part d'origine calculée avec dénominateur explicite ; aucun flag inconnu promu observed ; mois estimés exclus de vérité terrain des prévisions ; consensus WFP+RTFP non compté comme deux preuves indépendantes par défaut.

### R1.9 — Qualifier FAOSTAT

- **Priorité / dépendances :** MUST / R1.2.
- **Périmètre :** connectors/faostat.py, taxonomy, production_observation/trade_flow.
- **Directives :** vérifier API/listes de zones/items/domaines actuelles via documentation officielle ; aucun code d'amorce considéré acquis. Extraire production, superficie, rendement et commerce selon disponibilité ; flags, unités, année et édition. Appliquer conditions FAO et exceptions du fichier ; distinguer paddy/riz blanchi.
- **Acceptation / tests :** CC-R ; codes et unités vérifiés ; flags estimés visibles ; production paddy sur vingt années si disponible, sinon période réelle et blocage du critère historique ; pas de conversion paddy/blanchi sans preuve.

### R1.10 — Requalifier géographie et résolution

- **Priorité / dépendances :** MUST / R1.1, R1.2.
- **Périmètre :** geo/README.md, geo/processed, core/geo.py, ref.location, location_aliases.
- **Directives :** retrouver l'origine authentique des limites et version administrative ; vérifier nombres par niveau contre la source, pas une constante du code. Préserver versions et validité ; documenter divergence avec découpage courant. Associer marché/bassin/district/région uniquement avec preuve ; résolution d'une donnée reste celle du fournisseur.
- **Acceptation / tests :** manifestes et comptes concordent ; géométries valides ; aucune disparition de version antérieure ; alias faible confiance en revue ; localisation ambiguë ne tombe pas sur MDG1101 ou une région par défaut. HDX inaccessible : archive autorisée avec statut hors ligne, couverture courante non certifiée.

### R1.11 — Qualifier NASA POWER et ses révisions

- **Priorité / dépendances :** MUST / R1.2, R1.10, R2.1.
- **Périmètre :** connectors/nasa_power.py, WeatherRecord, obs.weather_observation.
- **Directives :** paramètres explicites début/fin, communauté/variables et référence temporelle UTC/LST ; ne pas assimiler LST au fuseau métier. Partitions annuelles selon SPECS depuis 1991, reprise bornée ; dédupliquer les requêtes par cellule native tout en conservant liens vers zones. NRT/révisions créent versions selon C2 ; aucune mise à jour destructive. Ne pas présenter POWER historique comme une prévision météo.
- **Acceptation / tests :** CC-R avec cohérence physique ; pas de température absente convertie en zéro ; Tmin≤Tmax, pluie≥0 ou code missing ; periode reçue conforme à demandée ; mapping cellule→zones explicite ; révision intégrable sans écrasement ; couverture réelle des districts mesurée.

### R1.12 — Qualifier actualisation, reprise et santé des sources

- **Priorité / dépendances :** MUST / R1.2, R0.6 ; au moins un connecteur réel qualifié parmi R1.3–R1.9.
- **Périmètre :** schedules/sensors, ingestion_run, gold.source_health, UI /sources.
- **Directives :** suivre délai publication→ingestion, dernier fetch, dernière observation, dernière édition, volume et qualité séparément. Quotas/retry survivent au redémarrage. Prévoir rattrapage de partitions, document remplacé, run partiel et absence d'édition nouvelle ; échec notifié dans Mailpit uniquement.
- **Acceptation / tests :** édition simulée dans catalogue local détectée au cycle suivant ; panne/reprise idempotentes ; source stale/disabled visible après reload et API ; zéro requête pendant PolicyStop ; état SQL du run concordant avec UI.

### R1.13 — Gate de collecte réelle

- **Priorité / dépendances :** MUST / R1.1–R1.12.
- **Directives :** publier matrice source×capacité×preuve, volume/période/produits/zones, statuts et droits. Exécuter tests/check/E2E de provenance et `qualify R1`, plus rebuild de tous les artefacts acquis.
- **Acceptation :** neuf sources du socle ont preuves réelles conformes aux critères ou repli officiellement adopté dans la gouvernance, sans prétendre la source live. Aucun parse réussi vide compté ; une qualification source bloquée garde le gate incomplet tant que le critère non réalisé n'est pas traité explicitement par ADR/plan. Réseau et quotas vérifiés.
- **Clôture :** résumé/proofs et tag `mi-r1-qualified` uniquement si gate accepté avec ses limites publiées ; jamais « neuf opérationnelles » lorsque certaines sont hors ligne.

## 7. R2 — Qualité et observatoire marché/économie

### R2.1 — Formaliser les contrats temps, origine et macroéconomie

- **Priorité / dépendances :** MUST / R0.1, R0.2, R1.1.
- **Périmètre :** SPECS §8/19, ADR, migrations, core/models, connectors/records.py.
- **Directives :** spécifier C1–C4, métriques macro génériques avec indicateur/unités/fréquence/base/périmètre/vintage, documents narratifs et révisions météo. Préférer extensions additives et conventions communes plutôt que détournement de price_observation. Définir publications et first_available_at, source_family, origin et état de qualification ; prévoir inconnus historiques conservateurs. Ne pas inventer un released_at pour faciliter le ML.
- **Acceptation / tests :** ADR/SPECS avant migration ; upgrade sur base dédiée et clone non vide ; historique/prix bruts inchangés ; idempotence/révision de météo testées ; contrats API JSON validés ; rôles DB/read-only compatibles.

### R2.2 — Auditer taxonomie, unités et grains

- **Priorité / dépendances :** MUST / R2.1, R0.4.
- **Périmètre :** taxonomy, normalize, ref.product/unit_conversion/location, Gold.
- **Directives :** vérifier les conversions utilisées contre documents réels ; distinguer riz/paddy/qualité, acteur, conditionnement et produit. Aliases ≥0,9 seulement avec preuve ; sinon revue. Les codes HS/FAOSTAT restent versionnés et vérifiés. Interdire moyenne entre devises/unités/indices/acteurs incompatibles ; conversions massiques/volumiques sans densité prouvée refusées.
- **Acceptation / tests :** 100 % des libellés acquis résolus ou en revue ; conversions faible confiance exclues des prix comparables ; propriétés d'inversion et formats numériques verts ; ni ND ni lieu inconnu remplacés par zéro/default.

### R2.3 — Qualifier DQ, agrégations et indépendance

- **Priorité / dépendances :** MUST / R2.1, R2.2, R0.5, R0.6.
- **Périmètre :** gold/sql, gold/kpi.py/refresh.py, ops.dq_result, tests_gold_*.
- **Directives :** appliquer seuils SPECS §14 ; publier dénominateurs cohérents pour fichiers, lignes candidates, acceptées, rejetées et revue. Vérifier priorité observé/imputé sans duplication de familles ; garder conflits et dispersion. Variations alignées sur calendrier réel, pas dernière ligne disponible. Préserver Market Health normatif avec composantes/coverage ; un changement de formule exige ADR.
- **Acceptation / tests :** fixtures de trou de mois, conflit, duplication WFP/RTFP, incomparabilité et faible couverture ; Golden attendu calculé indépendamment ; DQ bloquant empêche publication ; score NULL si coverage<0,5 ; 100 % d'indicateurs reliés à observations et transformations.

### R2.4 — Mesurer couverture et choisir le pilote

- **Priorité / dépendances :** MUST / R2.3, R1.12 ; au moins une source authentique de prix qualifiée.
- **Périmètre :** Gold/API de qualité, rapport coverage, configuration pilote.
- **Directives :** produire matrice produit×zone×acteur×mois avec n_obs, origine, lacunes, âge, granularité et famille de source. Choisir riz local/importé et au plus trois zones initiales, suivant complémentarité production/consommation ET couverture ; une zone nationale disponible peut être retenue sans inventer des marchés locaux. Documenter le choix et les capacités impossibles.
- **Acceptation / tests :** matrice recomputable en SQL ; compte de mois manquants indépendant ; pas de zone présélectionnée pour flatter la couverture ; pilote décrit objectifs/limites et dépendances ; absence d'historique prix authentique bloque ce choix, pas de seed de substitution.

### R2.5 — Intégrer INSTAT Tableau de bord économique

- **Priorité / dépendances :** MUST / R1.2, R1.3, R2.1.
- **Périmètre :** nouveau connecteur `instat_tbe` à créer, schéma macro, fiche source.
- **Directives :** découvrir fichiers Excel réels du TBE et publications ; sélectionner explicitement les séries de conjoncture utiles, sans promettre que chaque édition les contient. Documenter unité, fréquence, date, source primaire, base et révisions ; séries trimestrielles/annuelles restent telles quelles. NIPC déjà acquis n'est pas une source indépendante si réédité dans TBE.
- **Acceptation / tests :** CC-R adapté macro ; au moins deux éditions authentiques ; cellules et séries retenues comparées à DB ; pas de réplication en faux mois ; chaîne de provenance conservée jusqu'à l'institution primaire lorsque connue.

### R2.6 — Intégrer change et contexte monétaire BFM

- **Priorité / dépendances :** MUST / R1.2, R2.1.
- **Périmètre :** nouveau connecteur `bfm_public` à créer, schéma macro, source_family.
- **Directives :** qualifier publications publiques/licence avant flux ; commencer par cours de référence documentés et séries monétaires réellement accessibles. Conventions devise/base, date ouvrée, achat/vente/moyenne et taux distingués. Aucun taux douanier ou taux effectif transactionnel substitué au BFM ; pas de conversion rétroactive de prix sans taux daté et contrat ADR.
- **Acceptation / tests :** CC-R adapté ; week-end et publication tardive explicites ; convention inverse testée avec valeur documentaire ; aucune interpolation silencieuse ; source non accessible = BLOCKED, contexte « inconnu » visible.

### R2.7 — Intégrer carburants OMH et événements réglementaires

- **Priorité / dépendances :** MUST / R1.2, R2.1.
- **Périmètre :** nouveau connecteur `omh_public` à créer, schéma macro/event.
- **Directives :** acquérir historiques/communiqués officiels ; distinguer prix maximal réglementé, prix pratiqué lorsqu'observé et événement d'entrée en vigueur. Produit carburant, unité, géographie et date prouvés ; absence de prix publié n'est pas stabilité démontrée.
- **Acceptation / tests :** CC-R adapté ; communiqué de changement relie ancien/nouveau niveau sans modifier observations ; date d'effet et date de publication séparées ; indicateur explicitement réglementaire dans API/UI ; aucune rupture déduite du seul prix.

### R2.8 — Construire le tableau économique interprétable

- **Priorité / dépendances :** MUST / R2.3, R1.3, R1.6, R2.5 ; connecteurs BFM/OMH utilisables lorsqu'ils sont DONE.
- **Périmètre :** nouveaux indicateurs Gold, SPECS, API ; optional WB Indicators/Comtrade au backlog si couverture utile.
- **Directives :** fiches métriques : définition, formule, unité, fréquence, périmètre, publication, source, limite. Inflation et variation de prix distinctes ; commerce en tonnes vs valeur ; dépendance importations même produit/période/base avec conversion prouvée. Afficher dimensions séparées, pas inventer un score de santé économique. Valeur manquante/denominateur nul = NULL/raison.
- **Acceptation / tests :** recomputation indépendante d'indicateurs du pilote ; indices de bases différentes non raccordés implicitement ; formule importation invalidée si unités incompatibles ; séries BFM/OMH absentes n'entraînent ni zéro ni nombre LLM. Économie observable partielle reste étiquetée partielle.

### R2.9 — Exposer les données et leurs limites dans l'API

- **Priorité / dépendances :** MUST / R2.3, R2.4, R2.8.
- **Périmètre :** api/routers/schemas, OpenAPI, web/src/lib/api ; SPECS §19.
- **Directives :** étendre routes par contrat ADR sans casser clients existants : séries macro, couverture, disponibilité et qualification. Chaque valeur expose type, unité, période, freshness et provenance ; géographie à sa résolution réelle. CSV et JSON partagent les règles. Routes debug/administration non publiques ; pagination et erreurs normatives.
- **Acceptation / tests :** OpenAPI exporté et types front régénérés dans Docker ; pagination stable ; prix/indice/forecast/missing correctement sérialisés ; contrôle rôles ; requête réelle et rélecture DB concordent après redémarrage.

### R2.10 — Livrer les vues marché et économie

- **Priorité / dépendances :** MUST / R2.9.
- **Périmètre :** web/src/app et composants, ValueKindBadge/ProvenanceLink, routes économie à définir dans SPECS.
- **Directives :** filtres produit/zone/acteur/période cohérents ; unités et séries différentes non superposées sans explication. Afficher lacunes, part imputée, ancienneté, composantes du score et source ; état vide/erreur/non qualifié distinct. Provenance accessible depuis un point ; recherche des sources côté admin seulement. Pas de chiffres ou cartes de remplissage.
- **Acceptation / tests :** Playwright parcourt login→filtre→graphique→provenance→document/DB→reload ; dates/unités/valeurs exactes ; échec API visible ; clavier/contraste AA et largeur 390 px conformes SPECS. Aucun toast/localStorage utilisé comme preuve de données.

### R2.11 — Gate observatoire décisionnel

- **Priorité / dépendances :** MUST / R2.1–R2.10.
- **Directives :** établir au moins cinq questions du pilote dont la réponse est calculable ; produire les fiches avec preuves. Qualifier API et UI sur données réelles disponibles, rejouer les agrégats ; relecture DB/reload ; publier couverture et limites.
- **Acceptation :** check/test/e2e/qualify R2 verts ; cinq réponses vérifiées indépendamment ; chaque domaine absent reste unavailable, pas sain ; observatoire marché/économie utile sur périmètre documenté. Gate bloqué si source métier requise n'est pas acquise.
- **Clôture :** résumé et tag `mi-r2-qualified` si accepté, sans promesse d'exhaustivité nationale.

## 8. R3 — Prévisions de prix évaluées et honnêtes

### R3.1 — Appliquer l'éligibilité et le calendrier des séries

- **Priorité / dépendances :** MUST / R2.1, R2.3, R2.4.
- **Périmètre :** ml/series.py, ml/forecast.py, gold.price_monthly_best ; SPECS §17/ADR-004.
- **Directives :** clé produit/qualité/acteur/zone/unité explicite ; niveaux régional/national uniquement. Grille mensuelle régulière avec trous explicites ; minimum 36 mois non nuls dont 12 sur les 24 derniers, sans seuil de six points ni saison artificielle de deux à quatre mois. La vérité terrain d'évaluation est observée ; apprentissage utilisant estimations éventuelles = cohorte séparée et documentée. Vérifier aussi longueur suffisante pour sélection, calibration et test, pas seulement éligibilité nominale.
- **Acceptation / tests :** 35 points refusés ; 36 points sans récence refusés ; trous non compressés ; indices et prix réglementés non confondus avec prix observés ; granularité district refusée pour publication de prix ; liste d'exclusions avec raisons. Aucune série créée pour satisfaire le KPI de dix.

### R3.2 — Construire les datasets historiques as-of

- **Priorité / dépendances :** MUST / R3.1, R2.1, R0.8.
- **Périmètre :** nouveau constructeur de datasets ML, source_record/révisions, C2/C4.
- **Directives :** figer origine, observation_ids, artefacts, lignée, versions et hash canonique. Joindre seulement versions disponibles à l'origine ; prise en compte tardive/correction de source exclues. Quand disponibilité ancienne non prouvée, choisir première collecte et déclarer limitation ; constituer progressivement les vintages futurs. Séparer cohortes observées/estimées et sous-ensembles de sélection/calibration/test avant entraînement. Gel du protocole et des seuils avant résultat final.
- **Acceptation / tests :** un prix de janvier publié en mars absent du dataset de février ; révision d'avril exclue en mars ; recomputation identique ; aucun UUID inconnu ; toute variable explicative aussi disponible à l'origine. Si vintages insuffisants, mode rétrospectif explicite et qualification as-of BLOCKED, sans antidatage.

### R3.3 — Implémenter références et modèles conformes

- **Priorité / dépendances :** MUST / R3.1 ; R3.2 pour exécutions réelles.
- **Périmètre :** ml/models.py, SPECS §17, unit/test_ml_forecast.py.
- **Directives :** dernier prix comme référence de diagnostic, SeasonalNaive annuel, ETS et ARIMA season_length=12 comme candidats normatifs. Définir traitement des valeurs manquantes avec fit exclusivement sur entraînement et documentation ; s'abstenir si traitement non justifié. Retourner modèle demandé/effectif et cause du repli ; aucun ARIMA affiché lorsqu'une moyenne/naïf a tourné. Référence naïve peut rester gagnante.
- **Acceptation / tests :** référence manuellement calculée exacte ; historique insuffisant explicite ; échec d'un candidat n'arrête pas tous les autres mais change métadonnées ; les prédictions gardent unité/devise ; reproductibilité au même dataset/version ; aucune promesse de précision issue du jeu synthétique.

### R3.4 — Séparer sélection, calibration et évaluation finale

- **Priorité / dépendances :** MUST / R3.2, R3.3.
- **Périmètre :** ml/backtest.py, ml/forecast.py, rapport/protocole ML.
- **Directives :** respecter six origines de sélection, h=3, pas mensuel de SPECS ; vérifier pour chaque fold l'éligibilité du train. Garder une période finale ultérieure indépendante, au moins six origines si l'historique le permet. Calibration conforme uniquement sur résidus connus avant chaque cible, séparée des résultats finaux. Toute transformation/choix de features reste dans les folds. Rapporter effectifs, WAPE/MAE/sMAPE par série/horizon et agrégats nommés ; dénominateur nul donne métrique indisponible.
- **Acceptation / tests :** assertions train/calibration avant cible et versions as-of ; choix du modèle n'utilise jamais les erreurs finales ; test injectant une publication future détecte fuite ; métriques comparées à calcul indépendant. Historique insuffisant ne réduit pas discrètement nombre de fenêtres : abstention ou protocole expérimental distinct, sans certification normative.

### R3.5 — Calibrer les intervalles et surveiller leur couverture

- **Priorité / dépendances :** MUST / R3.4.
- **Périmètre :** ml/models.py/forecast.py, StatsForecast déjà prévu, ml.model_run/forecast.
- **Directives :** configurer réellement ConformalIntervals selon bibliothèque/documentation vérifiées à l'implémentation. Documenter résidus, fenêtres, calibration et niveau 80 ; pas de repli arbitraire ±10 %. Publier p10/p50/p90 et sémantique du centre normative ; compter couverture et largeur par horizon, état expérimental si faible échantillon ou choc. Ne pas promettre garantie locale de couverture hors hypothèses.
- **Acceptation / tests :** p10≤p50≤p90, valeurs finies, calcul sur résidus antérieurs ; absence de calibration empêche label calibrated ; effectif/couverture/largeur réels consignés ; seuil d'acceptation préenregistré en R3.2, au minimum effectif suffisant défini et incertitude binomiale publiée. Les trois quantiles ne deviennent pas une probabilité de dépassement non calculée.

### R3.6 — Évaluer l'apport des variables économiques/agroclimatiques

- **Priorité / dépendances :** SHOULD / R3.4, R2.8 ; enrichissements R4 seulement lorsqu'ils sont DONE.
- **Périmètre :** MLForecast/LightGBM prévus, features à créer ; nouveau contrat exogènes si au-delà de SPECS §17.
- **Directives :** modèle global par cohortes comparables ; lags {1,2,3,12}, mois et exogènes seulement disponibles à l'origine. Change/carburant selon vintages ; météo future = prévision archivée connue à l'origine ou scénario explicite, jamais réalisation future. Comparer prix seul puis familles de features séparément, sur exactement les mêmes folds ; pas de recherche illimitée ni de modèle complexe sans gain mesuré.
- **Acceptation / tests :** test anti-fuite pour chaque feature ; ablation et nombre d'essais consignés ; pas de gain sur estimations de tiers présentées comme réel. Si aucun gain stable ou assez de données, modèle reste non retenu et raison documentée ; R3 MUST ne dépend pas de cette tâche.

### R3.7 — Publier prévisions, limites et abstentions

- **Priorité / dépendances :** MUST / R3.4, R3.5, R2.9, R2.10.
- **Périmètre :** ml.model_run/forecast, gold.forecast_latest, routers/forecasts.py, PriceChart.
- **Directives :** versionner les runs et dataset C4 ; ne jamais écraser résultats antérieurs. Exposer horizon/cible/origine, modèle effectif, erreurs, intervalles, couverture, cohorte, statut et raison d'abstention. Une référence gagnante reste nommée baseline ; « validé » nécessite rapport indépendant. Pas de courbe de prévision de remplacement générée par UI/LLM lorsque données absentes.
- **Acceptation / tests :** API et DB concordent après reload ; vieux run récupérable ; trou de qualification visible ; un modèle demandé différent du modèle exécuté est montré ; tests d'unités et horizons ; chaque prévision relie au dataset authentique et aux observations.

### R3.8 — Produire l'évaluation réelle et le suivi des erreurs maturées

- **Priorité / dépendances :** MUST / R3.7, R3.2.
- **Périmètre :** rapport ML, job d'évaluation, tableaux de performance.
- **Directives :** exécuter le protocole préenregistré sur les séries éligibles réelles ; comparer baselines et candidats, par produit/zone/horizon/saison. Calculer les erreurs de prédictions devenues évaluables sans réutiliser ces observations comme passé connu au run initial. Enregistrer abstentions et versions des cibles. Distinguer test as-of prouvé, analyse rétrospective et suivi prospectif en attente.
- **Acceptation / tests :** toutes les erreurs recomputables ; aucun score global seul ; modèle sans gain ne se voit pas attribuer un gain ; effectifs/limitations et données estimées explicites. Un rapport vide ou limité aux fixtures ne satisfait pas la qualification réelle ; si historique/vintages manquent, BLOCKED et HANDOFF de données attendu.

### R3.9 — Gate de prévision des prix

- **Priorité / dépendances :** MUST / R3.1–R3.5, R3.7, R3.8 ; R3.6 facultatif.
- **Directives :** `qualify R3`, check/test/E2E prévisions/provenance ; publier protocole et résultats gelés. Vérifier que toute série publiée respecte éligibilité et état de validation.
- **Acceptation :** erreurs et calibration honnêtement mesurées sur observations indépendantes ; test final non utilisé pour sélection ; absence de fuite ; abstention si insuffisant. Aucun objectif numérique de WAPE inventé après résultats ; baseline acceptable si gagnante, sans vendre de gain IA.
- **Clôture :** `mi-r3-qualified` seulement après gate ; si analyse rétrospective seule, statut PARTIAL de la capacité et pas de qualification as-of annoncée.

## 9. R4 — Agroclimat, météo, calendrier et environnement

### R4.1 — Formaliser les contrats géospatiaux et agroclimatiques

- **Priorité / dépendances :** MUST / R2.1, R1.10.
- **Périmètre :** SPECS/ADR, WeatherRecord/révisions, calendriers, stockage des produits dérivés.
- **Directives :** définir grille/CRS/résolution/unité, masque agricole et surface utile, méthode d'agrégation, date d'émission/validité et préliminaire/final. Nouveau modèle météo prévue distinct des observations ; raster original Bronze et dérivés versionnés liés au source_record. Couverture/résolution nationale, régionale et district non confondues. Définir coût maximum stockage/calcul avant imagerie.
- **Acceptation / tests :** contrats et migrations validés en isolation ; pour chaque champ métier origine/temps explicites ; deux versions fournisseur conservées ; prévision et historique impossibles à confondre dans API. Aucune nouvelle dépendance sans ADR.

### R4.2 — Qualifier CHIRPS et ses versions

- **Priorité / dépendances :** MUST / R4.1, R1.2.
- **Périmètre :** nouveau connecteur chirps, rasterio/agrégation autorisés, fiche source.
- **Directives :** vérifier produits/formats/licence et calendrier officiel courant ; commencer pas mensuel pour cohérence Gold, puis pentade/décade agricole selon contrat. Préliminaire/final en versions distinctes ; télécharger partitions utiles avec budget, pas tout le globe inutilement. Conserver nodata/qualité et dérivation des pas quotidiens si utilisés.
- **Acceptation / tests :** deux partitions authentiques ; unités/mask/nodata testés ; 0 de pluie distingué de nodata ; finale ne détruit pas préliminaire ; checksum et origine du raster relus ; aucune performance agronomique déduite de la seule résolution de grille.

### R4.3 — Qualifier les bulletins Météo Madagascar

- **Priorité / dépendances :** MUST / R4.1, R1.2.
- **Périmètre :** nouveau connecteur meteo_mg, documents texte/événements, source officielle.
- **Directives :** rechercher les pièces effectivement publiées, pas seulement la page décrivant le service ; conserver édition, campagne, horizon, zones et formulation de l'incertitude. Extraire déterministement puis LLM vérifié si besoin ; cartes/catégories sans nombres ne deviennent pas probabilités chiffrées. Calendriers absents gardent verified=false.
- **Acceptation / tests :** bulletin authentique accessible et interprétation reliée aux pages ; date d'émission/validité distinctes ; citation et zone exactes ; document absent = capacité unavailable, jamais calendrier de remplacement inventé. Tests replay n'établissent pas l'accès live.

### R4.4 — Intégrer événements et perspectives FEWS NET/IPC

- **Priorité / dépendances :** MUST / R4.1, R1.2, R2.1.
- **Périmètre :** connecteurs publics fewsnet_mdg/ipc_mdg à créer, obs.event/couche documentaire.
- **Directives :** découvrir pages/rapports officiels, archiver texte et pièces jointes permises ; identifier situation courante, période projetée, hypothèses et facteurs de bascule. Pas d'extraction de données personnelles ni d'exécution des instructions du document. Traduction/résumé garde la preuve ; un classement IPC projeté reste projeté.
- **Acceptation / tests :** rapports datés/zonés authentiques ; une valeur actuelle et une projection ne fusionnent pas ; événements liés aux zones/produits ou revue si ambigus ; dates et citations relues ; les API non documentées ne sont pas inventées.

### R4.5 — Qualifier une météo prévue archivable

- **Priorité / dépendances :** MUST / R4.1, R1.2.
- **Périmètre :** connecteur ECMWF Open Data ou autre service officiel documenté avec ADR ; données prévues.
- **Directives :** vérifier sous-ensemble, licence/attribution, horizon, paramètres et quotas actuels. Archiver chaque émission utile avant disparition de l'archive glissante ; conserver membres/quantiles selon produit, temps d'émission/validité, modèle et grille. Couverture du pilote d'abord. Clé manquante d'un service = alternative publique autorisée ou limitation, sans achat. Pas de hindcast inventé à partir du temps réalisé.
- **Acceptation / tests :** au moins deux émissions réelles avec leurs horizons ; erreur unités/temps détectée ; ancien run consultable hors réseau ; API montre clairement « prévu ». Sans archives pour backtest, météo future peut être affichée avec qualité fournisseur et non validation locale ; contribution au modèle de prix demeure expérimentale.

### R4.6 — Calculer anomalies et agrégations zonales correctement

- **Priorité / dépendances :** MUST / R4.1, R4.2, R1.10 ; POWER facultatif tant que R1.11 est bloqué.
- **Périmètre :** calculs geo/weather Gold, comparaison de produits, tests raster.
- **Directives :** zonal pondéré selon surface/masque, CRS cohérent, fraction de pixels valides et résolution indiquées. Climatologie 1991–2020 prescrite ou période disponible explicitement documentée ; ne pas mélanger versions fournisseurs sans étude. Somme pluie vs moyenne températures ; seuils définis avec unité et fenêtre. Terrain agricole seulement lorsqu'un masque vérifié existe, sinon zone administrative nommée comme telle.
- **Acceptation / tests :** petit raster de test à agrégat calculé à la main, nodata/CRS/frontière testés ; référence réelle contrôlée sur une zone ; méthode et couverture exposées ; grille POWER ne devient pas pluie de station locale ; anomalie absente si référence insuffisante.

### R4.7 — Versionner les calendriers culturaux

- **Priorité / dépendances :** MUST / R4.3, R4.4, R2.2.
- **Périmètre :** taxonomy/crop_calendar.yaml, modèle calendrier, source/campagne.
- **Directives :** produit/bassin/cycle pluvial-irrigué/variété lorsque documentés ; fenêtres semis/croissance/récolte et sensibilité climatique, campagne et source. Calendrier traditionnel distinct d'une recommandation pour une saison donnée. Interprétation non mécanique revue/verified=false ; aucun mois générique appliqué à tout Madagascar. Relier bassin et marché avec statut de preuve, pas par proximité supposée.
- **Acceptation / tests :** dates/fenêtres et références vérifiées ; cycles multiples/chevauchements gérés ; entrée sans source exclue des alertes automatiques ; version passée toujours visible ; pas de tonnage ni de pic de marché généré à partir du calendrier seul.

### R4.8 — Évaluer l'état des cultures par télédétection

- **Priorité / dépendances :** SHOULD / R4.1, R4.6, R4.7.
- **Périmètre :** extension Copernicus/indices végétation à créer, BL-003, SPECS/ADR obligatoires.
- **Directives :** catalogue officiel STAC vérifié, acquisition bornée/autorisation ; nuages, qualité, dates, masque cultivé et baseline saisonnière. Commencer un indicateur de condition, pas un modèle de rendement. Comparer signal aux campagnes/observations indépendantes ; annoter incertitude couverture/nuages et type de culture.
- **Acceptation / tests :** dérivé lié aux assets/hash/formule/version ; masque nuage réellement appliqué ; absence de pixels = unavailable, pas culture morte ; aucune quantité de production issue du NDVI seul ; coût plafonné. Non réalisation ne bloque pas le gate R4 MUST.

### R4.9 — Qualifier les signaux de feu FIRMS

- **Priorité / dépendances :** SHOULD / R4.1, R1.2.
- **Périmètre :** connecteur firms_mdg à créer, cartes/événements ; source/API officielle.
- **Directives :** clé fournie par humain si requise, périmètre/quotas définis ; conserver heure, capteur, confiance/qualité et géométrie. Une anomalie thermique n'est ni surface brûlée ni parcelle détruite. Aucune liste d'exploitants ; agrégation publique par zone et fenêtre.
- **Acceptation / tests :** échantillon authentique, dédoublonnage révisions/passage satellite ; labels exacts ; attribution/droits suivis ; aucune estimation de perte agricole automatique. Sans clé, logique hors ligne documentée, collecte unavailable, pas active.

### R4.10 — Qualifier un indicateur d'inondation hydrologique

- **Priorité / dépendances :** SHOULD / R4.1, R1.2.
- **Périmètre :** connecteur GloFAS/EWDS à créer, carte et événements de risque.
- **Directives :** vérifier couverture, accès et granularité ; débit/risque prévu distinct d'une inondation observée et de dommages. Émission/validité/ensemble archivés comme météo ; adéquation spatiale au bassin et validation locale à documenter. Aucune promesse à la commune ni bilan de dégâts produit par LLM.
- **Acceptation / tests :** unités hydrologiques et horizons exacts ; zone non couverte explicitement absente ; replay de run possible ; pas de donnée prévue en obs météo ; champ validation_locale=false tant que non évalué.

### R4.11 — Livrer la vue agroclimatique explicable

- **Priorité / dépendances :** MUST / R4.2–R4.7, R2.9, R2.10 ; R4.8–R4.10 facultatifs.
- **Périmètre :** /climate, cartes et API météo/événements/calendriers ; schémas ADR.
- **Directives :** séparer météo observée/estimée/prévue, calendrier/état des cultures et risques environnementaux. Expliquer pluie actuelle vs référence et campagne ; lier pixels/zones/produits/documents. Signaler agrégat administratif sans masque agricole ; sources facultatives non intégrées visibles comme indisponibles, pas chiffres nuls.
- **Acceptation / tests :** E2E zone→anomalie→méthode→source, émission prévue et période réelle correctes ; reload/DB ; cartes à résolution native ; calendrier sourcé ; pas d'indice global de santé environnementale fabriqué.

### R4.12 — Gate agroclimat/météo

- **Priorité / dépendances :** MUST / R4.1–R4.7, R4.11 ; R4.8–R4.10 facultatifs.
- **Directives :** sélectionner cas documentés de saisons et anomalies, vérifier calculs contre sources ; test complet, replay hors ligne, API/UI et `qualify R4`.
- **Acceptation :** dates/version/résolution justes, anomalies et fenêtres sourcées, météo prévue distinguée ; environnement optionnel déclaré selon qualification. Une météo accessible ne suffit pas à valider rendement ou abondance. Sources obligatoires manquantes maintiennent gate incomplet avec actions concrètes de HANDOFF.
- **Clôture :** résumé et tag `mi-r4-qualified` uniquement après critères ; aucune promesse de santé écologique exhaustive.

## 10. R5 — Récoltes, quantités et approvisionnement des marchés

### R5.1 — Définir les cibles et le protocole de relevé

- **Priorité / dépendances :** MUST / R2.1, R2.4, R4.7.
- **Périmètre :** SPECS/ADR, docs/outreach non envoyés, dictionnaire de quantité, protocole pilote.
- **Directives :** définir trois cibles distinctes : volume récolté par bassin/cycle, arrivages ou disponibilité par marché/période, minimum de prix. Contrat de mesure : produit/qualité, unité, date, marché, quantité, stock/flux/vente, mode déclaré/mesuré/estimé, source et protocole d'échantillonnage. Aucun nom/téléphone/coordonnée privée de personne ; lieu de marché public seulement. Préparer demandes d'accord et formulaires anonymes pour humain, sans contact H7. ODK ou mobile dédié reste option distincte au backlog, pas achat/intégration implicite.
- **Acceptation / tests :** dictionnaire et exemples fictifs explicitement synthétiques ; chaque champ numérique a unité et sens ; flux vs stock et double comptage expliqués ; formulaire rejette champs personnels ; contrats et consentement/droits du futur fournisseur à documenter avant données réelles.

### R5.2 — Importer les quantités légalement disponibles

- **Priorité / dépendances :** MUST / R5.1, R1.2, R2.1.
- **Périmètre :** connecteurs publics ou import de documents remis par humain, source_record/Bronze, StockRecord/extension flux.
- **Directives :** rechercher d'abord les publications publiques qualifiables ; accepter un dépôt humain uniquement avec droits et origine identifiables. Valider licence/permission, format et absence de PII avant chargement ; document du dépôt conservé Bronze avec `manual_upload` si approprié. Ajouter observations avec bruts, preuve, dates et origine ; pas de scrape de portails partenaires authentifiés dans ce programme. Scénarios d'offre ne vont pas dans les tables d'observations comme relevés.
- **Acceptation / tests :** import/rejet de données personnelles, provenance et supersession testés ; au moins un corpus réel de quantités du pilote pour qualification. Faute de corpus, code/test offline peuvent être livrés comme sous-incréments, tâche de qualification BLOCKED et demande de données dans HANDOFF ; aucune donnée synthétique pour la clôturer.

### R5.3 — Contrôler les quantités et leur couverture

- **Priorité / dépendances :** MUST / R5.2, R2.2, R2.3.
- **Périmètre :** DQ/Gold quantités, matrices marché×période, conversions.
- **Directives :** distinguer relevé ponctuel et période cumulée, stock et flux, tonnes/sacs/kg et unités locales vérifiées. Totaux compatibles avec périmètre/échantillon ; détecter doublons, déclarations sans mesure et jours non enquêtés. Absence de relevé ≠ zéro arrivage. Quantifier représentativité et couverture sans extrapoler à tout le marché sans pondération prouvée.
- **Acceptation / tests :** changement de conditionnement/poids refusé sans preuve ; cumul journalier ne double pas mensuel ; n_relevés et jours attendus explicités ; source document/DB concordants ; série déclarée ne devient pas mesure. Sans quantités réelles, cette validation reste BLOCKED.

### R5.4 — Produire une fenêtre de récolte vérifiable

- **Priorité / dépendances :** MUST / R4.6, R4.7 ; R4.5/R4.8 utilisables lorsqu'ils sont DONE.
- **Périmètre :** modèle de fenêtres agricoles à créer, ml/forecast de type dédié, API/UI.
- **Directives :** baseline calendrier par bassin/cycle ; ajustements liés à campagne seulement si règles agronomiques ou modèle étayés. Paramètres de durée/semis/température sourcés, pas inventés. Sortie début/fin de fenêtre, source, facteurs et niveau de validation ; aucune date de jour précis sans résolution correspondante. Évaluer sur dates de récolte indépendantes disponibles, pas sur le même calendrier utilisé en entrée.
- **Acceptation / tests :** baseline reproduit la fenêtre source ; scénario sec distinct de prédiction validée ; cas réel daté et fenêtres passées relisibles ; absence de validation donne experimental et incertitude qualitative, jamais « précision garantie ». Fonctionnalité peut être DONE avec baseline sourcée et qualification expérimentale explicitement prévue ; performance locale demeure non qualifiée tant que références manquent.

### R5.5 — Évaluer superficie et rendement prévisionnels

- **Priorité / dépendances :** SHOULD / R1.9, R4.6, R4.7 ; R4.8 seulement si utilisé.
- **Périmètre :** modèle de production à créer, données de campagnes authentiques, ADR requis.
- **Directives :** séparer superficie récoltée et rendement ; cible réelle par culture/bassin/campagne ; baseline tendance/saison, modèle agroclimatique si références suffisantes. Validation chronologique hors campagnes d'entraînement et incertitude de chaque composant. FAOSTAT national annuel ne constitue pas vérité de rendement d'un district ; paddy→blanchi exige facteur sourcé.
- **Acceptation / tests :** identité production=superficie×rendement et unités testées ; données/campagnes de test indépendantes ; paramètres et erreurs publiés ; si références insuffisantes, rapport de faisabilité et refus de publication de tonnes prévues. Module optionnel non qualifié ne doit pas alimenter offre comme fait acquis.

### R5.6 — Construire un bilan d'offre sans double comptage

- **Priorité / dépendances :** MUST / R5.3, R1.6, R1.9, R5.4 ; R5.5 facultatif.
- **Périmètre :** nouvelle couche de bilan/scénario, flux et stocks par bassin/marché.
- **Directives :** documenter périmètre et équations : stock_fin = stock_début + entrées − sorties − ventes − pertes, termes non redondants. Les entrées peuvent inclure arrivages locaux/importés, mais une importation douanière ne s'ajoute pas à nouveau à l'arrivage déjà compté. Production commercialisable et allocation vers marché exigent sources ; stocks statiques ne s'ajoutent pas comme production périodique. Composant inconnu reste inconnu ; hypothèses versionnées en scénario, hors observations. Imports nationaux ne sont pas volumes d'un marché sans allocation prouvée.
- **Acceptation / tests :** conservation sur cas analytique ; doubles comptes import/arrivage/stock détectés ; quantité inconnue empêche total présenté comme observé ; units/temps compatibles ; résultat distingue bilan observé partiel et scénario hypothétique ; chaque terme retrouve source ou hypothèse explicite.

### R5.7 — Prévoir les fenêtres d'approvisionnement et leurs pics

- **Priorité / dépendances :** MUST / R5.3, R5.6, R3.2–R3.5 pour le protocole réutilisable.
- **Périmètre :** modèle d'offre à créer, dataset quantités/vintages, nouvelle route métier.
- **Directives :** fixer cible quantité/arrivages/disponibilité et pas temporel avant modèle ; baseline saisonnière/calendrier, puis modèle avec flux prouvés. Réutiliser les contrôles as-of/calibration de R3, pas automatiquement les horizons et seuils d'éligibilité propres aux prix. Évaluer dates de pic, volume et fenêtres sur quantités réelles indépendantes ; au moins deux cycles observés pour tenter une validation saisonnière, davantage si protocole l'exige. Intervalle/amplitude/incertitude sont calculés, jamais produits par LLM. Un minimum de prix ne fournit pas le label du pic d'offre.
- **Acceptation / tests :** cibles annotées à partir des quantités, pas d'une courbe de prix ; train/test as-of ; comparaison baseline ; erreur de calendrier et amplitude, largeur/couverture des fenêtres, effectifs par cycle. Moins de cycles ou de volume représentatif = experimental/abstained et qualification BLOCKED, pas modèle « validé » sur simulations.

### R5.8 — Préparer les scénarios et le pilote décisionnel

- **Priorité / dépendances :** MUST / R2.11, R5.4 ; R5.6/R5.7 inclus seulement quand qualifiés.
- **Périmètre :** fiches décision C5, interface scénarios, protocole d'essai et HANDOFF.
- **Directives :** préparer parcours institution publique/acheteur/agriculture : surveiller tension, planifier achats, comparer fenêtres et risques. Scénarios bornés avec hypothèses sourcées ou saisies utilisateur, effets calculés et lacunes. Historiser hypothèse/version/auteur interne sans produire d'ordre d'achat. Préparer séance et questionnaire pour humain ; aucun recrutement/contact externe. Tester en interne sur cas documentés, humain_reviewed=false si non revu.
- **Acceptation / tests :** trois parcours documentés et reproductibles ; scénario non modifiable par contenu collecté ; paramètre absent empêche calcul approprié ; résultats sources/DB/reload cohérents. Préparation technique peut être DONE ; utilité auprès d'une institution reste NOT_EVALUATED jusqu'à séance humaine documentée, jamais « pilote client réussi » sans preuve.

### R5.9 — Gate disponibilité et abondance

- **Priorité / dépendances :** MUST / R5.1–R5.4, R5.6–R5.8 ; R5.5 facultatif.
- **Directives :** `qualify R5`, tests/golden quantités, bilan indépendant et parcours récolte/offre/prix. Publier précisément ce qui est validé et ce qui dépend d'apports humains.
- **Acceptation :** fenêtres de récolte, volumes observés, bilan et pics d'offre ont preuves adaptées ; récolte ≠ arrivage ≠ prix minimal ; validation réelle de R5.7 indispensable pour qualifier l'abondance chiffrée. Sans flux suffisants, observatoire/fenêtres peuvent rester utiles, mais le gate d'abondance n'est pas DONE.
- **Clôture :** tag `mi-r5-qualified` seulement après critères ; sinon HANDOFF avec données, cycles, unités et marchés attendus, pas simple demande vague d'« améliorer les données ».

## 11. R6 — IA bornée et exploitation institutionnelle

### R6.1 — Sécuriser les outils de lecture

- **Priorité / dépendances :** MUST / R0.2, R2.9.
- **Périmètre :** copilot/sql_guard.py/executor.py, core/policy/http, rôles DB/API.
- **Directives :** catalogue d'outils typés et autorisés : séries, faits, provenance, couverture, prévisions qualifiées, calendrier. SQL gold uniquement, SELECT unique, LIMIT≤500, statement_timeout 5s ; fonctions/CTE/joins contrôlés, pas d'accès obs/auth/système ou réseau via DB. Aucun droit d'écriture ou secret d'admin dans l'outil analyste ; filtrer URL/documents et fonctions dangereuses. Privilégier outils métier pour calculs récurrents.
- **Acceptation / tests :** injection SQL, CTE d'écriture, fonction dangereuse, requête hors schéma, énorme résultat et timeout refusés ; DB confirme permissions ; accès client/admin conforme ; paramètres produit/zone non validés refusés ; refus expose une explication sans fuite.

### R6.2 — Borner les workflows IA et leurs reprises

- **Priorité / dépendances :** MUST / R6.1, R0.6, R0.3.
- **Périmètre :** copilote/extraction/clients LLM/budget, nouveau journal de workflow si nécessaire.
- **Directives :** conserver Dagster pour collecte/calcul ; petits rôles reconnaissance, extraction, analyse, rédaction sans système multi-agent complexe obligatoire. Chaque workflow a états persistants, nombre maximal d'étapes/outils/tokens/temps et coût estimé/réel. Domaines/nouvelles sources seulement proposés pour revue, pas ajoutés par LLM. Budgets concurrentiels refusés atomiquement ; erreurs/cache/retry traçables ; reprise sans duplication de publication. Mode replay explicite sans prétendre qualifier un fournisseur réel. Modèle exact/prix vérifiés sur documentation officielle lors du choix, puis ADR.
- **Acceptation / tests :** boucle/timeout/budget arrêtés proprement ; deux appels simultanés ne dépassent pas budget ; document hostile ne change pas permissions ; replay absent échoue explicitement ; redémarrage restitue étape sans déclencher d'effet externe ; audit de tous les appels et cache hits, zéro secret dans logs.

### R6.3 — Répondre avec des résultats exécutés et référencés

- **Priorité / dépendances :** MUST / R6.1, R6.2, R2.9 ; R3.7/R4.11/R5.8 facultatifs selon question.
- **Périmètre :** copilot/agent.py/writer.py/schema.py, API/copilot, UI chat.
- **Directives :** interpréter question, clarifier produit/zone/période/unité ambiguës, exécuter outil/SQL sous rôle limité, construire faits/citations puis prose avec placeholders. Une correspondance de nom de vue n'est pas une réponse. Chiffres y compris dates/statistiques proviennent de cellules/faits, formatés côté serveur. Séparer faits, prévisions, hypothèses et limites ; données absentes ou module indisponible = abstention explicite, pas généralité chiffrée.
- **Acceptation / tests :** questions riz/maïs distinctes, région/période exactes, unités compatibles, réponse sans données correctement abstinente ; toutes cellules citées relues ; aucun chiffre non référencé ; historique du chat et citations contrôlables après reload ; droits du rôle appliqués au backend, pas seulement UI.

### R6.4 — Évaluer le copilote sur des questions métier indépendantes

- **Priorité / dépendances :** MUST / R6.3, R2.4.
- **Périmètre :** tests/copilot_eval.yaml, rapport d'évaluation, tests adversariaux.
- **Directives :** garder l'ancien jeu comme régression, ajouter au moins quarante questions nouvelles avec attendu indépendant : prix, économie, climat, provenance, prévision/abstention et scénarios disponibles. Au moins dix cas hostiles/ambiguïtés supplémentaires. Attendus = valeurs/ensembles/périmètres/statuts, pas substring SQL ; tolérance de présentation fixée avant test. Jeu final distinct des exemples du prompt ; français requis, malagasy expérimental tant que non évalué. Replay qualifie contrat logiciel, pas qualité d'un fournisseur live.
- **Acceptation / tests :** ≥80 % réponses correctes, zéro requête interdite, zéro chiffre non référencé ; score/erreurs par catégorie et refus corrects publiés ; mauvais produit/zone/unité n'est pas réussite ; toutes citations exactes. Si LLM live non testé, mention OFFLINE_TESTED et pas « copilote fournisseur opérationnel ».

### R6.5 — Qualifier le bulletin sans hallucination numérique ou sémantique

- **Priorité / dépendances :** MUST / R2.8, R6.2, R6.3 ; extensions prévisionnelles selon DONE.
- **Périmètre :** bulletin/facts.py/writer.py/render.py/service.py/templates, SPECS §20.
- **Directives :** facts calculés/versionnés avec observations/runs ; LLM reçoit IDs/libellés sans valeurs, sortie placeholders seulement ; validation numérique puis substitution serveur. Vérifier aussi sens : hausse/baisse, passé/futur, observé/imputé et causalité non prouvée. Si LLM absent/invalide, fallback déterministe ; sections indisponibles nommées. Brouillon et approbation auditables, aucune approbation équivalente à autorisation d'envoi.
- **Acceptation / tests :** zéro chiffre non référencé ; tous facts calculés et cités ; changement de sens volontaire refusé/détecté ; PDF/HTML mêmes chiffres/sources ; fichier consultable après restart ; Mailpit seulement. Une erreur de rendu/version ne donne pas bulletin « envoyé ».

### R6.6 — Évaluer les alertes et les scénarios de risque

- **Priorité / dépendances :** MUST / R2.3, R6.5 ; R4.6/R4.7 pour alertes climat qualifiées.
- **Périmètre :** alerts/rules.py/engine.py/notifier.py, obs/event, ops.alert.
- **Directives :** garder seuils normatifs ou ADR pour adaptation ; confirmation par familles réellement indépendantes, pas deux copies du même relevé. Risque de rupture nécessite quantités/statuts documentés, pas silence d'une source. Séparer risque climatique, alerte marché et données stale. Déduplication/reprise/résolution et sévérité testées ; précision/rappel évalués sur événements annotés indépendamment lorsque disponibles.
- **Acceptation / tests :** doublon WFP/RTFP ne monte pas artificiellement high ; seuils et preuve recomputables ; alerte stale sur vrai retard ; absence de quantités exclut prétendue rupture confirmée ; zéro notification externe, Mailpit contient brouillon ; métriques d'alertes non évaluées identifiées, jamais 100 % déclaré.

### R6.7 — Durcir accès, audit et sécurité applicative

- **Priorité / dépendances :** MUST / R6.1, R6.2, R2.9.
- **Périmètre :** auth/API/middleware, DB grants, conteneurs, logs ; SPECS §23/BL-006–007.
- **Directives :** vérifier authentification, cookies, CSRF pour mutations applicables, CORS, rate limits, accès admin et liens signés. Distinguer utilisateur privé/public par vues utiles sans imposer multi-tenant/facturation hors périmètre. Tracer approbation/revue/changement de source avec acteur/temps/version ; minimiser PII d'auth, pas collecter des tiers. Auditer secrets et vulnérabilités avec outils actuels en Docker ; patchs dans stack, major seulement ADR et tests.
- **Acceptation / tests :** client ne modifie pas source/revue/bulletin, lien expiré refusé, logout/invalidation et rôles testés ; gitleaks sans secret ; aucune vulnérabilité critique non traitée au moment du gate ; conteneurs non-root et services sensibles non exposés en profil prod. Ne pas réutiliser un audit ancien comme résultat courant.

### R6.8 — Qualifier sauvegarde et restauration isolée

- **Priorité / dépendances :** MUST / R0.2, R0.8, R2.1, R6.7.
- **Périmètre :** deploy/backup.sh/restore.sh, scripts/dev restore, runbooks.
- **Directives :** backup DB + manifestes Bronze/dérivés/runs/versions nécessaires ; vérifier lisibilité/intégrité avant destination. Restore uniquement clone explicitement nommé, garde de refus cible active. Retirer succès forcés comme `pg_restore ... || true` ; chaque commande/étape fait remonter échec. Pas de suppression d'objets Bronze ni d'écrasement de données actives. Conserver clés/secret requis hors rapport.
- **Acceptation / tests :** backup réel restauré sur clone, comptes/empreintes/privilèges/relations concordants ; provenance et bulletin relisibles ; snapshot absent/corrompu simulé ou mauvaise destination échoue ; temps/tailles mesurés, pas inventés ; environnement actif inchangé.

### R6.9 — Superviser fraîcheur, dérive, dépenses et incidents

- **Priorité / dépendances :** MUST / R1.12, R3.7, R6.2, R6.6 ; modules R4/R5 selon disponibilité.
- **Périmètre :** /sources, jobs/sensors, métriques ML, runbooks exploitation.
- **Directives :** dashboard source/run/DQ/revue, disponibilité/vintages, publication, erreurs mûries, dérive et calibration ; budgets HTTP/LLM/stockage/CPU. Définir propriétaires humains et procédures sans leur envoyer de message. Seuils datés/versionnés, gel publication en erreur, rollback vers dernière version qualifiée sans mutation de l'historique. Incident réseau/policy/rebuild/LLM documenté avec reprise sûre.
- **Acceptation / tests :** provoquer uniquement en environnement dédié panne HTTP, schema_drift, dépassement budget, forecast inadéquate et run interrompu ; états persistants/restaurables, alertes Mailpit, pas faux succès ; disponibilité stale visible après reload ; dérive n'entraîne pas remplacement automatique non validé du modèle.

### R6.10 — Mesurer performance et préparer le déploiement humain

- **Priorité / dépendances :** MUST / R6.7, R6.8, R6.9, R2.10.
- **Périmètre :** tests/integration/test_api_perf.py, Compose prod, deploy/Caddyfile, runbooks.
- **Directives :** mesurer HTTP authentifié par proxy/API, pas seulement SQL : au moins cent requêtes mesurées par endpoint agrégé après dix échauffements, protocole avec cinq clients concurrents, volume réel/ressources documentés. Objectif P95<1s normatif ; performance de petite base non extrapolée à charge nationale. Préparer config prod sans provisionner : ports secrets non publics, budgets, healthchecks et procédures. Déploiement/remote restent humains/autorisations séparées.
- **Acceptation / tests :** p50/p95/max/erreurs mesurés et endpoint/volume nommés ; données réelles ; check/test/E2E/Compose config et scripts shell vérifiés en Docker ; contrat local accessible depuis navigateur par parcours complet. H2 absent n'empêche pas paquet local prêt, mais statut « déployé » interdit sans preuve réelle.

### R6.11 — Réception finale, rapport et passation

- **Priorité / dépendances :** MUST / gates R0.9, R1.13, R2.11, R3.9, R4.12, R5.9 et R6.1–R6.10 ; cinq tâches SHOULD facultatives.
- **Directives :** environnement isolé neuf, corpus Bronze authentique réhydraté sans altération, rebuild hors réseau, `qualify all`, check/test/E2E, API/DB/reload, bulletin, copilote, permissions et restauration. Vérifier les états module par module, sources/datasets/runs et budgets ; aucun recours au seed de démonstration. Rédiger `docs/MARKET_INTELLIGENCE_REPORT.md` et compléter HANDOFF, en conservant MVP_REPORT historique avec renvoi explicite au nouveau rapport plutôt que réécriture de ses preuves.
- **Acceptation :** tous MUST/gates réalisés avec mesures ; aucune provenance invalide/synthétique publiée, aucun chiffre LLM non référencé, aucune observation confondue avec estimation/prévision, aucun contournement/envoi. Prix et offre ont validations adaptées ; capacités facultatives non livrées nommées. Usage institutionnel réel reste NOT_EVALUATED tant qu'aucun humain n'a conduit et documenté l'essai préparé en R5.8 ; aucune qualification institutionnelle inventée.
- **Arrêt nominal :** tâche DONE seulement après tous critères techniques ; tag proposé `mi-v0.2.0-local-qualified` conforme à la gouvernance adoptée ; rapport local ne prétend ni déploiement ni utilité client démontrés.
- **Arrêt avec passation :** si les tâches restantes ne peuvent avancer sans corpus/accord/clé ou intervention humaine, suivre les conditions d'arrêt intégrées en R0.1 ; rapport PARTIAL + HANDOFF précis, tâches correspondantes BLOCKED, pas de tag final ni de réception « succès total ». En cas de problème technique corrigeable, appliquer protocole de trois tentatives et poursuivre les autres tâches.

## 12. Matrice de couverture des constats d'audit

| Constat du rapport | Tâches correctrices principales | Preuve attendue |
|---|---|---|
| A01 : faux succès rebuild | R0.7, R0.8 | Rejeu réellement exécuté, contenu comparé |
| A02 : seed synthétique dans démo | R0.2, R0.4, R0.7 | Isolation/refus, corpus réel identifié |
| A03 : hash/références seulement non nuls | R0.5 | Octets relus, empreinte et valeur vérifiées |
| A04 : critères déclaratifs | R0.3, R0.7 | Rapports mesurés et suites exécutées |
| A05 : asset check constant | R0.5, R0.6 | DQ bloque réellement publication |
| A06 : catalogues/URL fixes | R1.2–R1.6 | Découverte d'éditions et fichiers authentiques |
| A07 : documents de test générés | R0.4, R1.4, R1.5 | Golden indépendant sur originaux |
| A08 : six points/temps incomplet | R3.1, R3.2, R3.4 | Éligibilité/calendrier/as-of contrôlés |
| A09 : intervalles/repli non conformes | R3.3, R3.5 | Modèle effectif et calibration |
| A10 : LightGBM/exogènes annoncés | R3.6, R3.8 | Modèles exécutés listés, apport mesuré |
| A11 : évaluation sur nom de vue | R6.3, R6.4 | Réponses exécutées vs attendus indépendants |
| A12 : performance SQL ≠ HTTP | R6.10 | Mesures API/proxy et charge documentées |
| A13 : registre/licences non prouvés | R1.1 | Documents/permissions actuels et dates |
| A14 : POWER sans période explicite | R1.11 | Requête et période réellement reçues |
| A15 : refetch pendant Silver | R0.6 | Compteur HTTP nul sur phase Silver |
| A16 : exceptions silencieuses | R0.6, R1.12 | Erreur explicite et inventaire d'assets |
| Runner/integration/front/restore à revérifier | R0.3, R6.8 | Pas de skip implicite, échecs propagés |

## 13. Critères de réception : logiciel, données et usage

Ne pas réduire trois niveaux de preuve à un seul badge :

| Niveau | Exigences | Ce que cela ne prouve pas |
|---|---|---|
| Logiciel | Tests, contrats, sécurité, budgets, rejeu, sauvegarde et UI/API | Couverture actuelle de Madagascar ou exactitude économique |
| Données et modèles | Artefacts authentiques, couverture, publication, vintages, validation indépendante et calibration | Gain décisionnel pour une institution réelle |
| Usage | Essai humain documenté, décisions et temps/coût mesurés selon protocole, limites | Déploiement national ou effet causal sans étude adaptée |

Seuils existants à préserver sauf ADR explicite : provenance 100 %, parse≥99 %, golden≥99 %/rappel≥98 %, LLM non vérifié en Gold=0, score faible couverture NULL, qualification temporelle de séries, API P95<1s, copilote≥80 % et zéro chiffre non référencé. Les cibles supplémentaires de ce plan (nombre de questions/essais, fenêtres de test, cycles) sont **objectifs de validation**, pas performances déjà observées.

Si neuf sources ou dix séries ne sont pas disponibles malgré replis autorisés, le rapport montre effectifs et limitations. Un ADR peut faire évoluer le contrat de livraison, mais ne peut transformer l'indisponibilité en performance ou qualifier une prévision sur des données synthétiques.

## 14. Modèles de journal et de passation

### 14.1 Entrée de tâche dans PROGRESS

```text
[UTC ISO 8601] Rn.m — IN_PROGRESS
Dépendances relues : IDs, hashes et preuves.
Mini-plan : au plus dix lignes.
Environnement : projet/base/préfixe dédié, secrets omis.
Commandes : invocation exacte, code de sortie, durée mesurée.
Résultats : numérateurs/dénominateurs, tests exécutés/skippés, périmètre réel.
Qualification : logiciel / live / modèle / usage, limites explicites.
État final : DONE ou incident et statut prescrit.
Commit fonctionnel : hash ; preuve : docs/evidence/Rn.m/README.md.
Reprise : prochaine tâche, artefacts, cause racine/tentative si nécessaire.
```

### 14.2 Actions humaines attendues

HANDOFF doit lister pour chaque action : tâche bloquée, motif, document/clé/autorisation attendu, origine/droits, produits/zones/périodes/unités, format accepté, canal de dépôt sécurisé, test à rejouer et critères de déblocage. Aucun secret dans le document. Préciser si l'action est facultative H1/H2/H5 ou indispensable au module ; pas de demande de clé pour ce qui est testable en replay.

Pour les quantités, demander explicitement séries d'arrivages/stock mesuré ou déclaré, produit/qualité, marché, date, quantité/unité, protocole et cycles couverts ; pas un fichier de prix présenté comme quantité. Pour le pilote, fournir scénario/session/questionnaire et demander un compte rendu humain, sans contacter les participants.

### 14.3 Prompt de démarrage pour l'agent suivant

```text
Exécute le programme docs/plan/MARKET_INTELLIGENCE_EXECUTION_PLAN.md
en respectant AGENTS.md et la hiérarchie documentaire.
Lis complètement AGENTS puis PROGRESS/BLOCKERS avant toute action.
Commence par R0.1 si la gouvernance R n'est pas encore intégrée ; sinon
choisis la plus petite tâche MUST éligible et revérifie les IN_PROGRESS.
Préserve les changements concurrents, les services et le Bronze existants.
N'utilise jamais reset/restore/rebuild sur la base active pour les tests.
Travaille dans Docker et dans un environnement de qualification isolé.
Consigne preuves mesurées, commits et états dans PROGRESS, sans faux DONE.
Ne qualifie ni source live, ni modèle réel, ni essai humain via fixtures.
Respecte H1–H7 ; ne contacte personne et n'envoie aucun message externe.
À la réception, livre les rapports prévus ; si une action humaine devient
la seule voie restante, fournis HANDOFF et indique PARTIAL/BLOCKED.
```

Ce prompt est un gabarit pour une **future demande d'exécution**, pas une instruction de démarrer les implémentations pendant la rédaction du présent plan.
