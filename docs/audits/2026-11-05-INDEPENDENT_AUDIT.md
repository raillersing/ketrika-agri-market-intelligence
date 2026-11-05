# Audit indépendant du projet — 5 novembre 2026

## Conclusion et portée

Le programme reste PARTIAL. Le registre canonique contient 74 tâches R : 8 MUST DONE, 61 MUST IN_PROGRESS et 5 SHOULD IN_PROGRESS. Aucun pourcentage de fonctionnalités opérationnelles ne peut être déduit de ces statuts. Les huit DONE sont R0.1–R0.8 ; les sept premières réceptions sont explicitement historiques. R0.9 est la prochaine tâche MUST selon HANDOFF.

Audit documentaire et statique du checkout main à partir de a9af221, incluant les changements locaux visibles. Aucun code applicatif, statut, base, objet Bronze ou service modifié par cet audit. Le seul ajout est ce rapport. Pas de nouvelle réception logicielle : Docker est indisponible dans cette session WSL (`docker compose ps --all`, code 1, intégration Docker Desktop absente). Pas de sondage HTTP, SQL, S3, scan de vulnérabilités ou vérification distante GitHub. Les résultats CI mentionnés ci-dessous sont des preuves consignées dans le dépôt, pas des exécutions reproduites aujourd'hui. Les changements concurrents peuvent évoluer après la lecture.

## Constats prioritaires

### C1 — Critique : fabrication de valeurs publiables sous identité officielle

Le commit c0fc8fefef3dfad998ab4f1beca9d177e27e71f9 ajoute `backend/scripts/populate_secondary_modules.py`. Son contenu contredit sa description de peuplement authentique :

- Commerce : valeurs de base codées en dur, multipliées par une variation périodique (lignes 154–254, formule ligne 204), puis INSERT accepté sous extraction `deterministic_csv`. Aucun décodage des octets douaniers ne produit ces chiffres.
- Météo : tableaux de précipitations et températures et facteur annuel arbitraire (lignes 256–357, notamment 281 et 316), enregistrés comme NASA POWER, extraction `deterministic_api`, stage `final`.
- Macro : change linéaire, carburants constants/par paliers, inflation linéaire et croissance fixée à 4,2 (lignes 360–454, notamment 385), stockés explicitement `observed`, `accepted`, confiance 1.
- Le script rafraîchit les vues Gold (lignes 456–486). Les compteurs incrémentent même si ON CONFLICT n'insère rien : le nombre affiché ne mesure pas les nouvelles lignes.

La présence d'un source_record ne prouve pas que sa source contient la valeur. Défaut confirmé dans le code ; exécution et contamination actuelle à mesurer. PROGRESS lignes 12–23 affirme une exécution et des données réelles, mais aucune vérification SQL actuelle n'a été possible.

Action préalable à toute nouvelle qualification : empêcher l'utilisation de ce chemin pour publier ; inventorier son impact en lecture seule ; conserver les preuves et traiter les lignes concernées par quarantaine append-only. Aucun effacement ni fabrication rétroactive de Bronze.

### C2 — Critique : traçabilité créée sans acquisition correspondante

Dans ce même script, lignes 35–148 : sélection du premier source_record Douanes/NASA disponible, UUID de repli constants, fixtures BFM/OMH enregistrées avec `retrieved_via='direct'` et `http_status=200` sans requête HTTP, repli BFM/OMH vers un record Douanes. Le record INSTAT peut être créé avec une clé et un hash codés en dur sans `BronzeStore.put` correspondant. Le chemin ne démontre donc ni correspondance cellule/valeur ni même existence de l'objet INSTAT.

L'entrée météo est également écrite sous NASA alors que `registry/sources.yaml` déclare cette source disabled. Ce script SQL ne passe pas par le contrôle de collecte du connecteur. Il ne faut pas assimiler ce constat à la preuve d'une nouvelle requête interdite : aucune requête publique n'est réalisée ici.

### C3 — Élevé : nouveaux travaux exogènes non reçus et risque de répétition

Changements locaux constatés : ADR-164/SPECS/PROGRESS indexés ; registre, registry.py et parity_pricing.py modifiés ; nouveaux connecteurs world_benchmarks/corridor_friction, modules Gold, fixtures et tests non suivis.

`backend/scripts/populate_alternative_data.py` charge des CSV depuis `tests/fixtures`, les enregistre sous des URL officielles avec HTTP 200/direct codés en dur et les insère comme observed/accepted. Aucune acquisition ni preuve de droits n'est démontrée par ce chemin. L'authenticité des fichiers reste à établir ; elle n'est pas prouvée par leur SHA-256. Les URL citées ne sont pas vérifiées par cet audit.

### C4 — Élevé : requêtes dites as-of insuffisantes

Dans les ajouts locaux de `gold/parity_pricing.py`, `get_macro_indicator_as_of` (ligne 304) filtre sur period_start et la version actuellement non supersédée. Il ne filtre pas published_at/first_available_at et ne reconstruit pas la version connue au cutoff. `gold/corridor_friction.py:get_macro_value_as_of` présente le même motif. Une correction publiée ultérieurement peut donc entrer dans un calcul historique. Contre-épreuve SQL requise sur clone.

`compute_authenticated_import_parity` utilise aussi des replis 4900 et 42000 et d'autres coefficients fixes ; sa liste de provenance ne couvre pas toutes les composantes. Sa qualification « entièrement authentifiée » n'est pas établie. Tester absence de chaque intrant, publication tardive, révision postérieure et provenance de chaque coefficient.

### C5 — Élevé : annonces de clôture contradictoires

HANDOFF et MARKET_INTELLIGENCE_REPORT maintiennent R0.9/R6.11 non reçus. PROGRESS contient néanmoins des annonces de qualification globale et ses dossiers historiques R3.4/R6.8 concluent DONE alors que la table canonique les maintient IN_PROGRESS. Les tests ciblés et HTTP 200 du 3–4 novembre ne satisfont pas les critères de corpus, fraîcheur, validation indépendante et usage.

Des tags locaux mi-r1-qualified à mi-r5-qualified et mi-v0.2.0-local-qualified existent. Ils ne constituent pas une qualification actuelle : le registre retire explicitement cette portée aux annonces historiques. Ne pas les déplacer ; préciser leur portée dans les communications et vérifier leurs refs avant publication.

### C6 — Élevé : réception récente non transférable au checkout présent

R0.8 est reçu selon PROGRESS lignes 2019 et 4898–4902 sur le candidat 3a974be, CI41769707448 : 2796 backend dont 301 intégrations, 113 frontend, 26 E2E ; couvertures consignées 92,18/87,77/88,96 %. Le corpus comprend deux ZIP WB, 664 cellules annotées dont 60 nombres, 163 lignes/81 révisions/82 courantes. Portée : riz national imputé depuis 2020 ; pas de qualification de prix observés régionaux ni de modèle de marché.

Le commit de peuplement secondaire et les ajouts locaux sont postérieurs/absents de cette source figée. Le check antérieur ne les reçoit pas. L'audit actuel n'a pas réinspecté les originaux CI compressés ni les volumes de corpus externes ; les effectifs restent ceux du reçu documentaire.

## Inventaire des travaux non terminés

| Périmètre | Statuts canoniques | Travail nécessaire avant réception |
|---|---|---|
| R0 | R0.1–R0.8 DONE ; R0.9 IN_PROGRESS | Brancher le manifeste authentique externe sur core.qualify, assembler les preuves et recevoir le gate R0. |
| R1 | R1.1–R1.13 IN_PROGRESS | Registre/droits/cadences, découverte réelle, corpus indépendants par source, reprise et santé ; gate de collecte réelle. WFP, NASA et INSTAT NIPC sont disabled dans le registre consulté ; CHIRPS/DGM planned. |
| R2 | R2.1–R2.11 IN_PROGRESS | Temps/origine, taxonomie/unités, DQ, couverture, BFM/OMH/TBE, économie, API et UI ; authentifier et vérifier les données avant les conclusions économiques. |
| R3 | R3.1–R3.9 IN_PROGRESS | Éligibilité, datasets as-of, baselines, sélection/calibration/holdout, publication et erreurs maturées sur séries authentiques ; distinguer exogènes facultatifs et performances validées. |
| R4 | R4.1–R4.12 IN_PROGRESS | Données météo/climat/géographiques authentiques, anomalies et calendriers justifiés, prévisions archivées ; facultatifs satellite/FIRMS/GloFAS explicitement indisponibles si nécessaire. |
| R5 | R5.1–R5.9 IN_PROGRESS | Quantités et unités réelles, couverture, récoltes et arrivages séparés, bilans, validation indépendante des pics, parcours préparés et essai humain distinct. |
| R6 | R6.1–R6.11 IN_PROGRESS | Réception des outils/IA/bulletins/alertes, sécurité actuelle, backup réellement restauré, supervision durable, performance HTTP sur données réelles, réception finale isolée. |

Les cinq SHOULD non reçus sont R3.6, R4.8, R4.9, R4.10 et R5.5. Les 61 MUST restants ont priorité ; IN_PROGRESS ne signifie pas qu'il faut tout réimplémenter. Auditer chaque preuve existante et reprendre au premier critère manquant.

Les tâches T sont historiques ; T9.3 CHIRPS reste TODO dans leur table. Le programme R porte la suite autorisée, sans double comptage d'avancement. BACKLOG contient aussi des dettes dont la clôture n'est pas démontrée ici : BL-019 upgrades historiques, BL-011 reload, BL-012 entraînement/replis ; plusieurs lignes anciennes peuvent être dépassées et exigent rapprochement avec les corrections récentes.

BLOCKERS conserve de nombreuses lignes INVESTIGATING malgré des corrections/réceptions ultérieures mentionnées ailleurs. Ce registre est un historique utile mais pas une file actuelle fiable sans consolidation. Ne pas déduire de son seul statut qu'un défaut est encore reproductible. HANDOFF distingue notamment les migrations 0022–0028 reçues sur clones de leur absence d'activation sur l'actif : vérifier cette situation avant toute migration, sans appliquer automatiquement les changements.

## Ordre de reprise recommandé

1. Préserver l'état Git concurrent ; rendre explicite la frontière entre source reçue et travaux locaux. Aucun reset ou déplacement de tags.
2. Traiter C1/C2 : inventaire readonly SQL/S3, origine de chaque série secondaire, impact Gold/API, protection de publication et quarantaine selon contrat reçu.
3. Revoir le lot ADR-164 avant ingestion : artefacts originaux et droits, coefficients sourcés, as-of et versions, absence d'intrant, validations indépendantes ; rattacher la portée aux tâches R autorisées.
4. Finaliser R0.9 avec le corpus externe déjà acquis ; ne pas recommencer la recherche des deux éditions WB désormais consignées comme reçues en R0.8.
5. Consolider un état documentaire unique par tâche et incident : preuve, commit, environnement, logiciel/données/modèle/usage. Conserver les journaux historiques avec portée explicite.
6. Recevoir R1 puis les lots indépendants R2–R6 suivant leurs dépendances ; compléter les corpus et validations manquantes, sans convertir un test unitaire en preuve de marché.
7. Sur contenu stabilisé, réception Docker complète isolée, SQL/S3/E2E, scans actuels et restauration sur clone. Puis seulement gates et éventuelle activation opérationnelle autorisée.

L'audit ne conclut ni à un déploiement sûr, ni à une performance prédictive validée, ni à une contamination SQL chiffrée actuelle. Il démontre des chemins de code incompatibles avec la provenance totale et établit l'inventaire des tâches encore non reçues.
