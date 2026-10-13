# Répartition des travaux restants — 2026-10-13

Document préparatoire, sans qualification produit ni changement des statuts.
Références : AGENTS §3.3, PROGRESS, BLOCKERS, EXECUTION_METHOD et plan R.
La complexité ci-dessous mesure le couplage et le risque, pas une durée promise.

## Priorité et état vérifiés

R0.1–R0.5 sont DONE ; R0.6 est IN_PROGRESS. R0.7 exige R0.6,
R0.8 exige notamment R0.7 et R0.9 exige R0.1–R0.8. Les phases suivantes
ne peuvent pas être commencées pour contourner ces dépendances.
Les sous-travaux simples de R0.6 peuvent néanmoins avancer en parallèle.

Dernière réception applicative consignée : b139c90, incrément 13 ; check Windows
3975 FINAL 0, 1236 tests backend et 35 frontend, build vert. C'est la preuve
historique du contenu reçu, pas celle des futurs raccordements.

## Matrice immédiate de délégation

| Sous-travail R0.6 | Complexité | Responsable conseillé | Chemins / livrable | Réception et dépendances |
|---|---|---|---|---|
| Comparer critères lot A et preuves disponibles | Faible | Agent documentaire indépendant | Ce fichier ; lecture `docs/evidence/R0.6/`, tests et PROGRESS | Distinguer reçu/prototype/manquant ; aucun nouveau test global ni statut DONE |
| Documenter reprise native sûre | Faible après contrat arrêté | Agent documentaire | Proposition dédiée de runbook ; lire `connectors/durable_runs.py`, `durable_phases.py`, `batch_ledger.py` | Expliquer préconditions, refus, identité, preuves et limites ; aucune commande de réactivation SQL, purge ou rebuild actif ; attendre contrat de reprise du principal avant instructions exécutables |
| Compléter cas unitaires d'une interface stabilisée | Faible à moyenne | Agent tests, worktree séparé | Fichier de tests neuf, périmètre convenu ; lire `tests/unit/test_durable_phases.py`, `test_batch_ledger.py`, `test_durable_factory.py` | Tests nouveaux seulement, lint/types ciblés Docker ; définir les assertions avant code ; ne pas modifier en parallèle les fixtures/fichiers du principal ; pas de suite SQL/S3 ni full check autonome |
| Inventaire assets/checks/schedules | Faible, essentiellement déjà couvert | Agent documentaire, pas réimplémentation | `pipelines/source_definitions.py`, `definitions.py`, `tests/unit/test_source_definitions.py` | Conserver la régression existante : 15 assets, 12 checks bloquants, 6 schedules pour le registre courant ; ces nombres ne prouvent pas six sources live qualifiées ; recalculer seulement si registre ou contrat change |
| Raccorder consommation au lot enregistré | Moyenne, noyau du lot A | Principal | `connectors/durable_phases.py`, `batch_ledger.py`, tests ciblés | Registre absent/divergent refusé avant parse ; aucun refetch ; prototype ADR-056 non reçu sur main, adopter contrats avant transfert |
| Tentatives durables, document/version, partitions, crash/reprise | Élevée | Principal | Modèles, migration additive, `durable_runs.py`, `stages.py`, `pipelines/factory.py`, tests SQL/S3 | ADR/SPECS avant code ; succès/échec/concurrence/crash/reprise explicite, retry sans doublon ; SQL/S3 QA sérialisés, check complet du lot A stabilisé |
| Garde publication SQL/CLI et identité | Élevée | Principal, lot B | `gold/refresh.py`, audits/schema, normalisation et tests publication | Même refus que Dagster sur provenance/schema_drift ; révisions append-only ; BL-016 et contrat R2.1 respectés, aucun type inventé pour 764 prix historiques |
| Robots/redirections/retries raccordés | Moyenne à élevée | Agent implémentation dédié possible, lot C | `core/http.py`, `policy.py`, tests HTTP locaux | Contrat fixé avec principal avant code ; zéro requête interdite, refus/challenge explicites ; serveur local seulement, aucun fetch institutionnel ; pas de modification des fichiers lot A |
| Budgets persistants et comportement au redémarrage | Élevée | Principal ou agent lot C après contrat | Politique HTTP, stockage des budgets, migration si requise | ADR/SPECS avant extension ; quotas/restart/concurrence testés, pas seulement primitives unitaires ; isolement QA réservé par principal |

Une attribution proposée n'est pas une tâche déjà démarrée. Chaque mission
effective doit nommer son agent, son worktree, ses fichiers exclusifs, son contrat
d'entrée et sa preuve de sortie. Le principal conserve l'intégration, la cohérence
PROGRESS/plan et la réception ; les agents ne modifient pas ces registres en parallèle.

## Lot A : acquis, préparé, à produire

| Critère | État documentaire actuel | Travail utile restant |
|---|---|---|
| Références Bronze exactes, registre immuable et retry identique | Reçu incrément 13 ; `test_batch_ledger.py` couvre persistance, rollback, mutation SQL refusée et second writer | Réutiliser preuve du contenu identique ; ne pas refaire le même lot autonome |
| Transactions natives et reçu d'échec indépendant | Reçu ; `test_durable_phases.py` couvre rollback puis reçu | Étendre au contrat de tentative/reprise, pas confondre erreurs ordinaires et crash |
| Silver compare effectivement son entrée au registre durable | Prototype séparé seulement ; principal importe encore uniquement `persist_bronze_batch` | Raccorder puis conserver cas registre absent, parser/flag divergent, refus avant parse |
| Inventaire explicite, source disabled exclue et construction invalide visible | Implémentation et tests existants `test_source_definitions.py` | Vérifier inclusion de ces cas dans le JUnit final, aucune réimplémentation nécessaire |
| Identité document/version et partitions | Non qualifié | Définir identité et liens durables, intégrer Dagster et tester révision/retry |
| Tentative persistante, crash et reprise explicite sans refetch | Non qualifié | Contrat puis implémentation et tests réels ; reprise ne doit pas simplement remettre un run terminal à running |
| Double rejeu sans doublon, révision avec supersession, zéro HTTP Silver | Critères de lot à démontrer sur nouveau contenu complet | Scénarios intégrés et compteurs/assertions exacts ; mocks unitaires seuls insuffisants |

## Programme ultérieur : comparaison sans démarrage prématuré

| Étape | Complexité dominante | Sous-livrables simples délégables quand éligibles | Prérequis à conserver |
|---|---|---|---|
| R0.7 qualification mesurée | Moyenne à élevée : lier preuves, commit et environnement | Format des rapports, cas preuve absente/périmée après interface fixée | R0.3, R0.5, R0.6 |
| R0.8 puis R0.9 | Élevée : rejeu réel, empreintes métier et gate | Runbook, cartographie des champs comparés, lecture des rapports | R0.8 : R0.2/R0.4/R0.6/R0.7 ; R0.9 : tous R0.1–R0.8 |
| R1 collecte authentique | Moyenne à élevée : droits, formats, acquisitions et reprises | Fiches sources fondées sur preuves, annotation des corpus autorisés | R1.1 exige R0.9 ; R1.2 exige R1.1 ; respecter ensuite chaque fiche CC-R |
| R2 observatoire économique | Élevée : contrats additifs, grains et calculs | Documentation unités/grains, tests sur contrat validé, libellés UI | R2.1 exige R0.1/R0.2/R1.1 ; autres dépendances de chaque fiche |
| R3 prévisions | Élevée : as-of, anti-fuite, calibration et validation réelle | Description des protocoles, lecture des rapports, cas d'abstention | Dépendances de chaque fiche ; aucun gain modèle inféré d'une fixture |
| R4 agroclimat | Élevée : géospatial, versions et résolution | Fiches de métadonnées/qualité, tests nodata sur contrat arrêté | R4.1 exige R2.1/R1.10 ; autres dépendances de chaque fiche |
| R5 disponibilité/abondance | Élevée : quantités authentiques, couverture et double comptage | Dictionnaire stock/flux, formulaires anonymes et brouillons non envoyés | R5.1 exige R2.1/R2.4/R4.7 ; aucun contact H7 ou donnée personnelle |
| R6 décision et exploitation | Élevée : sécurité, provenance des réponses et réception | Runbooks, exemples métier, cartographie des assertions existantes | R6.1 exige R0.2/R2.9 ; suivre chaque fiche jusqu'à R6.11 |

## Validation sans redondance

Les agents rendent leurs diffs et preuves ciblées ; un seul pilote réserve DB/S3.
Le principal reçoit chaque lot fonctionnel figé avec son check complet unique.
Si le JUnit global contient réellement les fichiers/cas et minima attendus,
ne pas refaire automatiquement la suite QA cumulée juste avant. Un échec ou
changement invalidant une preuve impose une nouvelle réception, pas une réutilisation.
Cette matrice ne déclenche aucune suite et ne qualifie aucune source, aucun modèle,
aucun déploiement ou usage humain.
