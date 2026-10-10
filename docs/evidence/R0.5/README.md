# R0.5 — provenance mesurée

État : DONE, qualification logicielle source-cell uniquement.
Commit final fonctionnel : 9559e755877475c72a027051e0a0e08f0627292b.
Check Windows 21289 code final 0 ; QA 327/20 ; diff staged final code 0 ;
gitleaks staged Docker code 0 / 168416452 octets / 50 min 54 s / aucune fuite.
Les mentions « encore requis » ci-dessous décrivent les étapes intermédiaires,
pas le statut final. Matrice de réception : ACCEPTANCE.md.
Base reçue : R0.4 commit 8f8f1d15d8dce4dc4acc84e4dda7a30e77b41482,
clôture documentaire cd89d17 ; incrément pur reçu et commité :
30d0a837bf666336ee802ecdf843dc810f75d639, ADR-016 avant implémentation.

## Incrément 8 en qualification : publication source-cell

ADR-023–027/SPECS avant transfert. Lecture Bronze bornée, groupement sans cache
cumulatif, fixtures nouvelles source-backed, init non peuplée et refresh atomique.
113 tests ciblés / 76,67 s, lint et types sept fichiers codes 0 ; format complet
196 fichiers code 0 après correction du cache temporaire du diagnostic read-only.
Migration Windows 99199 code 0 ; SQL et Bronze préservés selon les deux reçus
increment-8-migration-*. PostgreSQL/MinIO réel Windows 57268 code 0 : 1 test /
111,64 s, publication positive, refus de dommage simulé en mémoire, rollback
partiel et DQ relus. Aucun objet réel endommagé.
QA complète Windows 19891 code 1 : 304 passed / 1 failed / 164,37 s ; reçu
2636387056d54746b5b92d782514af3d archivé increment-8-qa-first-red.
NASA historique sans cellules doit désormais refuser Gold tout en conservant
les contrôles réels de rejeu Silver (ADR-029). Clôture des dépendances Gold
adoptée avant code (ADR-028), avec régression SQL de fraîcheur des ancêtres.
Réception corrigée Windows 9804 code 0 : 308 passed / 162,63 s, dix intégrations,
zéro failure/error/skip ; reçu b818375d307d41798c7bc956ceff4cb0 / 176,614 s,
rapports increment-8-qa archivés. Types 27059 code 0 / sept fichiers.
Check complet Windows 18162 code 1 : 709 collectés, 6 passed / 1 failed /
189,15 s ; ancien test d'alertes sur vues non peuplées, frontend non exécuté.
Run rouge archivé increment-8-global-first-red. Cible corrigée Windows 45625
code 0 : 2 passed / 88,28 s, candidats high/medium effectivement requis.
ADR-030 avant code : statistiques Silver attachées au refus Gold toujours propagé,
jamais transformé en succès. Quatre unités du helper / 39,73 s ; anciens parseurs
non qualifiés gardent leurs comptes/valeurs de rejeu et exigent le refus Gold.
CSV positif source_id borné, sans revendication de rebuild complet R0.8.
QA courante élargie Windows 15540 lancée à 2026-10-10T16:18:02Z,
minimum 322 tests / 20 intégrations ; nouveau check global obligatoire.
Cette réception élargie est rouge : 318 passed / 4 failed / 322,97 s,
reçu 0071f5289e2a44c0a531354c4bb565fa, rapports increment-8-qa-expanded-red.
Quatre sources prix n'ont aucune observation éligible Gold ; la normalisation
du loader brut manque (BL-013, R0.6/R2.1). ADR-031 distingue empty 0/0/taux NULL
d'un refus ou de cells_verified, avec contrôle réel des onze vues numériques.
Neuf unités / 41,70 s vertes ; cible Windows 27459 code 0 : cinq tests /
91,97 s. Types 27667 code 0 / quatre fichiers. Les assertions
Silver restent inchangées et le CSV vérifie trois preuves natives séparément
du Gold vide. Nouveau minimum 327/20 ; aucune certification d'ensemble vide.
QA courante Windows 94546 code final 0 : 327 passed / 332,67 s, quatre
avertissements, vingt intégrations, zéro failure/error/skip ; reçu
95241682d1be4234990838e307335fbc / 347,085 s, rapports increment-8-qa-final.
Check complet Windows 21289 lancé à 2026-10-10T16:43:57Z, code figé ;
backend/frontend/build/couvertures, préservation finale et commit encore requis.
Backend courant reçu : 718 passed / 2223,69 s, cinq avertissements, aucun
failure/error/skip ; intégrations 40 par dossier / 40 par marqueur / union 44.
Couvertures core 93,59968968192398 %, extraction 86,3768115942029 %,
normalize 84,85523385300668 % ; rapports increment-8-backend-check-* exportés.
Frontend/build et code final Windows reçus à 2026-10-10T17:27:54Z : session
21289 code 0 ; 35 tests / quatre suites / 7,13 s, reçu
84bc6869-c602-4f04-95c9-c82e3408bdc4. Lint 15292 ms, types 24086 ms,
tests 14338 ms, build 214764 ms, chaque étape code 0 sans timeout/signal/erreur.
Préservation active finale SQL/Bronze codes 0 : mêmes effectifs/empreintes que
l'incrément 7, reçu increment-8-active-preservation-final. Scan et commit restent requis.
Les trois XML rouges ont uniquement leurs espaces de fin de ligne supprimés
pour le contrôle git ; assertions, résultats, traces et reçus restent conservés.
Check global, préservation active finale et commit encore requis ; aucune
qualification de source live, conversion, lignée historique de modèle ou usage humain.

## Incrément 7 reçu : preuves natives CSV/JSON

Commit ca4e33f27da2fad6d9328a4731b1cfa1112acd86 ; diff staged check et gitleaks codes 0,
348309 octets / aucune fuite ; base et Bronze actifs inchangés.

ADR-022/SPECS avant transfert ; lexème numérique JSON original explicite, refus des
clés dupliquées et profondeur bornée ; coordonnées natives du CSV de test 1.0.1.
Pas de nouveau connecteur public ni de réactivation de source interdite.
QA Windows 31083 code 0 : 258 / 94,82 s / neuf intégrations, zéro failure/error/skip ;
reçu 47ef2fcaecf94630b8c40affa0a636fc / 104,384 s, rapports increment-7-qa archivés.
SQL/MinIO : JSON et CSV 1/1 valides, brut divergent/ligne étrangère 0/1 chacun,
résultats DQ relus dans nouvelle session. Tests synthétiques seulement.
Types 94244 code 0 / cinq fichiers ; lint 14692 code 0 ; format 17447 code 0.
Check Windows 23511 lancé à 2026-10-10T14:26:11Z, code final 0 reçu à 15:22:32Z :
659 backend / 2649,23 s, cinq avertissements, zéro failure/error/skip ; intégrations
39 par dossier/marqueur, union 43. Couvertures core 93,5217903416 %,
extraction 86,3768115942 %, normalize 84,8552338530 % ; lint/format 185, types 184 verts.
Frontend 35 tests / quatre suites / 5,17 s ; reçu 567fb9cb-202a-4811-b026-c537890968ff,
lint 17088 ms, types 19912 ms, tests 11438 ms, build 246537 ms, toutes étapes code 0.
Rapports increment-7-backend-check/frontend-check archivés. Préservation renouvelée :
482 sources/764 prix et mêmes MD5 ; 674 versions/objets Bronze, zéro delete marker,
1377481 octets, SHA 83ae4ee1b5a8b3c8c957a50dde479f3def170b8ec42257995a340f65294c265c inchangé.
Pas de qualification de source live, conversion économique ou modèle de marché.

## Incrément 6 reçu : brut production

Commit 41822c8ea7db91f0eda7f17c273daf47786d7459 ; diff staged check et gitleaks codes 0,
337596 octets / aucune fuite ; DB et Bronze actifs inchangés.

ADR-021/SPECS avant code ; migration nullable sans backfill, brut/evidence conservés
aux deux insertions, idempotence décimale et révisions de source/preuve/brut/statut.
Précision NUMERIC(20,4) inchangée, arrondis implicites/non-finis refusés.
Préparation Windows 31319 code 0, ancienne ligne QA inchangée ; reçu dédié.
Unités 13411 code 0 / 13 / 43,84 s ; types 41956 / cinq et 84247 / deux fichiers
codes 0, lint 5645/1941/93148 codes 0.
QA Windows 93155 code 0 : 228 / 128,94 s / sept intégrations,
zéro failure/error/skip, reçu 78d3547273b1421abd1df401b1e245fa / 144,65 s.
SQL/MinIO : ancienne/nouvelle version conservées, brut divergent refusé par audit
(1/2 valide, résultat failed), pas de qualification marché ou live.
Check Windows 6321 lancé 2026-10-10T06:45:39Z, code fonctionnel figé.
Code final Windows 0 reçu le 2026-10-10T08:06:02Z : 629 backend / 3893,46 s,
cinq avertissements, zéro failure/error/skip ; intégrations union 41 (dossier/marqueur 37).
Couvertures core 93,4747798239 %, extraction 86,3768115942 %, normalize 84,8552338530 %.
Frontend 35 tests / quatre suites / 13,13 s ; reçu 159c8012-17d8-48ea-910b-bd09feb9da1b,
lint 21882 ms, types 29603 ms, tests 24574 ms, build 357406 ms, toutes étapes code 0.
Rapports increment-6-backend-check/frontend-check archivés ; pas de qualification live.
API active de nouveau HTTP 200 et Docker healthy après reloads ; BL-011 documenté,
aucune migration active et aucun workflow production actif qualifié.

## Incrément 5 reçu : provenance/historique météo

Commit ea6466accf8d51d9fb3394b632f6cb33cd15b1e5 ; diff staged check et gitleaks
codes 0 / 341345 octets / aucune fuite. Empreintes actives SQL/Bronze inchangées.

ADR-020/SPECS avant transfert. Migration 0003 QA prépare cinq colonnes nullable,
sans backfill, remplace l'unicité globale par celle des courantes et ajoute le trigger
append-only. Loader conserve les preuves et le brut fourni, refuse un arrondi implicite,
révision par nouvelle ligne ; Gold météo exclut les supersessions. Cela ne fournit pas
encore la garde de publication Gold ni les adaptateurs natifs NASA.

Windows prepare 81104 code 0 : QA 0002 -> 0003, huit anciennes lignes météo et
287 source_record inchangés, hashes des anciennes colonnes/références identiques ;
cinq nouveaux champs tous NULL. Reçu increment-5-migration-preservation.json.
Ce MD5 diagnostique prouve une égalité, pas l'authenticité/provenance de ces anciennes lignes.
Aucune migration active ; sa route de santé HTTP 200 après transfert, workflow météo
actif non qualifié et schéma actif distinct. Types 35861 code 0 / huit fichiers,
lint 22998 code 0, format Docker 29965 code 0 / neuf fichiers inchangés.

QA R0.5 82330 code 0 : 212 / 95,59 s / six intégrations, zéro failure/error/skip ;
reçu cfc2e48e46f84402aa9286c6c858f954 / 105,284 s, rapports increment-5-qa exportés.
Révision SQL, unicité, trigger, refus de downgrade en lecture seule, relecture DQ et
Gold sans double compte vérifiés ; NASA test uniquement local/fixtures, jamais live.
Check Windows complet 7616 lancé 2026-10-10T04:20:12Z, code final 0 reçu
2026-10-10T06:30:58Z : 613 backend / 1610,71 s / cinq avertissements,
zéro failure/error/skip, intégrations union 40 (dossier/marqueur 36).
Couvertures core 93,4721665999 %, extraction 86,3768115942 %, normalize 84,8552338530 %.
Frontend 35 / quatre suites / 11,42 s ; reçu f320be59-3759-4a69-9d1c-e2085a04280a :
lint/types/tests/build codes 0, build 278980 ms, aucun signal/timeout/erreur.
Rapports increment-5-backend-check/frontend-check archivés. L'heure de réception
n'est pas la durée d'exécution. Aucun déploiement météo actif qualifié.

## Incrément 4 reçu : preuve LLM mécanique

Commit c29acf2cffffabbabab9604e053a42abfe8d806b ; diff staged check code 0,
gitleaks staged Docker code 0 / 318571 octets / aucune fuite. Tâche IN_PROGRESS.

ADR-019/SPECS avant transfert par apply_patch depuis le prototype conservé.
Cellules et attentes SQL vérifiées avant page/extrait ; PDF page identique, HTML
page logique 1, ancrage normalisé §11.2 et tous les tokens valeur/identité exigés.
Ni arrondi float, préfixe numérique ni étiquette seule ne prouvent une valeur.
XLSX/CSV/JSON LLM restent non pris en charge ; human/inconnu refusés.
Pas d'appel fournisseur, de collecte live, d'OCR ni de nouvelle dépendance.

QA enregistrée : minimum 182 tests / quatre intégrations SQL-MinIO ; trois méthodes
deterministic/llm_verified/dual_agree, refus LLM incomplet persisté et relu depuis
une nouvelle session SQL. Objets réellement écrits uniquement au bucket QA,
synthétiques/manual_upload, URL verified=false et zéro HTTP acquis ; aucune mutation
Bronze négative réelle. QA Windows 65882 code 0 : 182 / 22,91 s / quatre intégrations,
zéro failure/error/skip, reçu e6e52eb0295e4d0da9d792af7032a0a0 / 31,479 s,
rapports increment-4-qa archivés. Mypy 95072 code 0 / six fichiers, lint 39249 code 0.
Check Windows intégral 55501 lancé 2026-10-10T03:25:28Z, code fonctionnel figé ;
code final 0 reçu 2026-10-10T04:02:14Z : 593 backend / 1849,68 s / cinq avertissements,
zéro failure/error/skip ; intégrations union 39 (dossier/marqueur 35).
Couvertures core 93,4590690209 %, extraction 86,3768115942 %, normalize 84,8552338530 % ;
preuve LLM 52/53 statements. Frontend 35 / quatre suites / 5,45 s, reçu
2f8726a5-b54f-4f2e-9c0d-aeb76ad91c26, lint/types/tests/build codes 0 ; build 195248 ms,
aucun signal/timeout/erreur. Rapports increment-4-backend-check/frontend-check archivés.
JUnit ciblé : complet 1/255 puis 2/258 puis 3/261, toujours failed ; deux refus LLM
incomplets 0/1 persistés/relus. Ces dénominateurs incluent les anciennes régressions
QA synthétiques, pas des observations du marché. Préservation active inchangée,
482 source_record / 764 prix / 674 Bronze, empreintes dans PROGRESS.
Garde Gold et adaptateurs métier restent obligatoires avant DONE.

## Incrément 3 reçu : formats et preuve SQL/MinIO

Commit c012c8a5de30cf020914ff183215184eda80d0e9 ; diff staged check code 0,
gitleaks staged Docker code 0 / 333808 octets / aucune fuite. Statut global IN_PROGRESS.

ADR-018/SPECS intégrés avant transfert. Nouveaux lecteurs et tests copiés par apply_patch
depuis le worktree, empreintes Git identiques ; répartiteur commun raccordé, source brute
PDF/XLSX non décodée en UTF-8 avant son lecteur. Documents et nombres bornés, aucune
formule/lien/macro exécuté. Ce lot ne fournit pas les adaptateurs métier ni la garde Gold.

Intégration positive : objet réellement créé dans le seul bucket QA après vérification
de destination, contenu synthétique/manual_upload, URL verified=false, zéro HTTP acquis.
Les tests négatifs d'objets restent simulés ; aucune suppression/mutation Bronze.
Effectifs DQ ajoutés comme propriétés JUnit, sans valeurs/extraits/URL ni exception,
après relecture SQL ; un UUID/hash contenant accidentellement les mêmes chiffres qu'un
prix ne doit pas provoquer un faux test de fuite (contrôle des clés de sortie à la place).

QA initiale 2930 code 0 : 149 / 20,22 s / deux intégrations, rapports initial-qa conservés.
Mypy initial 19587 code 1, Optional du test annoté ; assertions non-null corrigées,
comptes SQL typés sans remplacer une absence par zéro, aucun changement runtime/ignore.
QA corrigée 21628 code 0 : 149 passed / 21,27 s / deux intégrations / zéro failure/error/skip,
reçu c1655be2579c4142b95f455a927f1beb / 30,21 s, rapports increment-3-qa exportés.
Mypy corrigé 65327 code 0 / quatre fichiers, lint 33721 code 0.
Check Windows global 28765 lancé 2026-10-10T02:42:43Z, code fonctionnel figé,
code final 0 reçu 2026-10-10T03:18:51Z : 560 backend / 1772,10 s,
zéro failure/error/skip, cinq avertissements ; intégrations union 37 (dossier/marqueur 33).
Lint/format 174 fichiers, mypy 173, gouvernance codes 0.
Couvertures core 93,3360756890 %, extraction 86,3768115942 %, normalize 84,8552338530 %.
Frontend 35 / quatre suites / 5,42 s, reçu 54b17cd3-0835-4ac7-9cf5-43e65ec2cad2 :
lint/types/tests/build codes 0 ; build 212689 ms, aucun signal/timeout/erreur.
Rapports increment-3-backend-check-* et increment-3-frontend-check-* archivés.
Préservation active contrôlée en lecture seule codes 0 : mêmes 482 source_record,
764 prix, 674 versions/objets Bronze / zéro delete marker / 1377481 octets et empreintes
décrites dans PROGRESS. Pas de qualification économique, source live, modèle ou usage humain.

## Incrément 2 reçu, sans garde Gold

Commit 180cc77c68185715689a6b69f6e98b7a68997489 ; tâche globale toujours IN_PROGRESS.

ADR-017/SPECS avant liaison SQL/DQ. Auditeur des six tables, sans filtre silencieux,
attentes issues des champs stockés, raw_expected lié au brut, résultat DQ transactionnel.
Sélection incrémentale explicite table/UUID ; observations absentes incluses dans les échecs.
Preuves météo absentes, formats non pris en charge et extractions LLM sans contrôle de
page/extrait restent invalides. Pas de garde Gold, d'adaptateurs complets ni de validation
des conversions économiques déjà livrés.

Première cible Windows 37147 code 0 : 94 passed / 9,71 s, deux intégrations SQL.
Mypy initial 6836 code 1 : MIME nullable dans SourceRecord ; corrigé en format vide
explicitement invalide, aucun MIME valide supposé. Ce run précède neuf nouveaux cas unitaires
et le scénario complet rendu indépendant des anciens enregistrements.
QA courante 76144 code 0 : 104 passed / 8,65 s, deux intégrations, zéro failure/error/skip ;
reçu 6a8f5c06d0264327a09e78cce151185f / 15,779 s, rapports increment-2-qa exportés.
Mypy courant 36134 code 0 / trois fichiers. Check Windows intégral 88450 lancé
le 2026-10-10T01:55:29Z, code final 0 reçu à 02:29:04Z : 515 backend / 1644,14 s,
cinq avertissements, zéro failure/error/skip ; intégrations 33 par dossier / 33 par marqueur,
union 37. Couvertures core 93,4887813462 %, extraction 86,3768115942 %,
normalize 84,8552338530 % ; provenance_audit 115/116 statements, provenance 221/226.
Lint/format 172 fichiers, types 171 et gouvernance codes 0.
Frontend 35 tests / quatre suites / 7,04 s ; reçu 2f0a5a36-b8a8-45d2-9671-86788351e5cd,
lint 11177 ms, types 15636 ms, tests 12165 ms, build 191499 ms, chaque étape code 0.
Rapports increment-2-backend-check-* et increment-2-frontend-check-* exportés.
Contrôle actif renouvelé à 02:27Z : DB/S3 codes 0, mêmes effectifs/empreintes que ci-dessous.

Prototype de formats non intégré : /tmp/ketrika-r05-formats.OQ2It5, ADR-018/SPECS
avant code dans ce worktree. Dernière cible 15285 : 113 passed / 12,86 s ; mypy 51746
code 0 / trois fichiers, ruff 42216 code 0. Ces résultats ne qualifient pas encore son
intégration dans le dépôt principal ni le prochain check Windows complet.

## Périmètre du premier incrément

- Vérificateur hors réseau : référence/UUID, clé relative content-addressed, SHA réel,
  lectures partagées dédupliquées et cache abandonné entre deux lots.
- Preuves CSV/JSON, cellule numérique et identité dans le même enregistrement,
  comparaison Decimal, refus des formats/coordonnées/attentes inconnus.
- Erreurs stables sans exception SDK, URL ni extrait collecté ; zéro observation
  ne devient pas 100 %. Le mode complete/incremental décrit le lot fourni par le caller,
  il ne prouve pas encore une sélection exhaustive de toutes les tables en base.
- Les attentes doivent être liées par le caller aux champs de l'observation.
  Le vérificateur pur ne fait pas encore cette liaison SQL, ni persistance DQ,
  contrôle LLM page/extrait ou blocage de publication Gold : critères restant obligatoires.
- WDI : valeurs originales et cellules du golden indépendant, sans créer de fausse
  observation GDP/prix ni prétendre avoir ingéré cet artefact dans Bronze/Silver.

## Vérifications intermédiaires

- Windows test initial code 0 : 60 passed / 3,14 s, couverture du module 96 %.
  Ce résultat précède corrections de types et huit régressions supplémentaires.
- Diagnostic mypy initial code 1 : variable bytes réutilisée pour bytes|None et
  dictionnaire de preuve inféré object ; annotations/nom de variable corrigés,
  sans retirer de comportement ou de test.
- Diagnostic ruff avec montage lecture seule code 2 avant lint : cache tenté sur
  ce montage. Relance avec --no-cache ; pas une erreur applicative interprétée comme verte.
- QA Windows courante 71961 code 0 : 68 passed / 2,26 s, zéro échec/erreur/skip,
  zéro intégration SQL ; reçu f954154f0daa422cbdfdba0957688bfc / 8,984 s,
  `increment-1-qa-*`. Lint ciblé --no-cache code 0, mypy courant code 0 / trois fichiers.
- Check Windows intégral session 7895 : code final 0 reçu le 2026-10-10,
  479 passed / 2208,18 s, cinq avertissements de dépendances, zéro échec/erreur/skip.
  Intégrations : 31 par dossier, 31 par marqueur, union dédoublonnée 35.
  Couvertures : core 93,1659693166 %, extraction 86,3768115942 %,
  normalize 84,8552338530 % ; nouveau module provenance 215/220 statements, 97,73 %.
  Lint/format 169 fichiers, mypy 168 fichiers et gouvernance codes 0.
- Frontend : 35 tests / quatre suites / 4,54 s ; reçu
  dc2ea94a-93df-4ba8-bf5a-363828b53435, lint 11267 ms, types 16313 ms,
  tests 9956 ms, build 168382 ms, chaque étape code 0 sans timeout/signal/erreur.
  Rapports courants `increment-1-backend-check-*` et `increment-1-frontend-check-*`.
- Préservation active : SQL read-only code 0, 482 références / empreinte
  47b4402859acc41e3ae91fdb128e56c6 ; 764 prix / empreinte
  4b2586cb8e422f11c4873ad513d66bc1. Lecture de chaque version Bronze code 0 :
  674 versions/objets, zéro delete marker, 1377481 octets,
  SHA 83ae4ee1b5a8b3c8c957a50dde479f3def170b8ec42257995a340f65294c265c.
  Empreintes identiques à R0.4, aucune écriture active de ce lot.
  Les snapshots précédents ne qualifient ni données actives, droits, collecte live,
  modèle de marché, revue humaine, déploiement ou CI distante.
