# R0.5 — provenance mesurée

État : IN_PROGRESS. Quatre incréments reçus ; pas de tâche DONE ni de garde Gold livrée.
Base reçue : R0.4 commit 8f8f1d15d8dce4dc4acc84e4dda7a30e77b41482,
clôture documentaire cd89d17 ; incrément pur reçu et commité :
30d0a837bf666336ee802ecdf843dc810f75d639, ADR-016 avant implémentation.

## Incrément 4 reçu : preuve LLM mécanique

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
