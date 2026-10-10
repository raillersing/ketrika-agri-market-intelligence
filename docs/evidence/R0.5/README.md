# R0.5 — provenance mesurée

État : IN_PROGRESS. Premier incrément pur, pas de tâche DONE ni de garde Gold livrée.
Base reçue : R0.4 commit 8f8f1d15d8dce4dc4acc84e4dda7a30e77b41482,
clôture documentaire cd89d17 ; incrément pur reçu et commité :
30d0a837bf666336ee802ecdf843dc810f75d639, ADR-016 avant implémentation.

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
