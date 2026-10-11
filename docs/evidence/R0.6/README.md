# R0.6 — lignée Bronze → Silver

État : IN_PROGRESS. Base fonctionnelle R0.5 reçue
9559e755877475c72a027051e0a0e08f0627292b ; clôture 90b2eb4.

Premier incrément : ADR-032/SPECS avant code ; lot immuable avec UUID SQL exacts,
collecte et consommation séparées, entrée Bronze réelle de l'asset Silver.
Référence SQL/source/parser/run et octets SHA contrôlés avant parse ; contexte
Silver offline copié et store borné à l'objet déjà vérifié, sans écriture.
Ces contrôles ne qualifient pas encore un inventaire persistant des artefacts
par run, la normalisation, les checks mesurés/durables, les définitions et partitions.
R0.6 ne devient pas DONE au premier incrément transport.

Source publique disabled/forbidden refusée avant discover. ADR-033 : acquisitions
NASA/WFP des tests locaux sous identités fixture distinctes, avec résolution
de rejeu limitée à l'environnement QA validé ; statut public inchangé, aucun
nouveau droit/source live ni mutation d'ancien Bronze. Robots et sélection
exhaustive d'assets/schedules restent réception obligatoire R0.6/R1.2.

Résultats intermédiaires : 24 unités / 41,92 s code 0 ; types quatre fichiers code 0 ;
lint dix fichiers code 0 ; suite étendue/gouvernance 48 / 46,02 s code 0.
QA Windows 63105 en cours, minimum 53 / cinq intégrations ; typecheck étendu 4947
en cours. Check Windows complet, couvertures, préservation active, scan et commit
atomique encore requis. Software testé ≠ source live ≠ modèle validé ≠ usage humain.

QA initiale 63105 rouge : 48 passed / cinq failed / 65,81 s ; KeyError du lookup
des fixtures. Reçu 0b0b633cf544433a9f88c2ee75cc31df / 79,86 s conservé.
Correction limitée : identité de test/classe résolue et QA réellement validée ;
source réelle inconnue refusée, sans catch général. QA intermédiaire 39753 code 0 :
55 / 96,30 s / cinq intégrations, reçu 06a8975850664fadadf63027edae287e / 109,542 s.
QA défensive 78044 code 0 : 56 / 99,65 s / cinq intégrations,
reçu ec3ac25f0da84a9ebb171d32c19dc3b3 / 111,973 s ; alias enregistré ne contourne
plus la garde QA. Deux types et lint codes 0. Le lot reprend aussi URL/published_at
SQL relus et refuse leurs divergences : nouvelle QA 50007 minimum 58/5 en cours.
Ces reçus intermédiaires ne remplacent pas sa réception ni le check global.

Réception ciblée finale Windows 50007 code 0 : 58 / 97,10 s / cinq intégrations,
zéro failure/error/skip ; reçu cf52e6c4d8ea4860b674fbfcaf16c7cb / 111,97 s,
rapports increment-1-qa-final exportés. Types 38569 et lint 97451 codes 0.
Check Windows global 41998 lancé à 2026-10-10T20:04:35Z sur code figé ;
backend/frontend/build/couvertures, préservation et commit encore requis.

BL-014 : identifiants courts appliqués aux trois mêmes cas de lecture du body,
dont le payload surdimensionné reste de 32 MiB + 1 ; aucun seuil ou cas retiré.
Les cinq XML historiques de 33 Mo et leur scan 50 min 54 s sont conservés.

Check intégral Windows 41998 code final 1 : 35 passed / une failure / 710,83 s,
cinq avertissements, 744 collectés ; format 202 et types 201 verts, frontend
non exécuté. Rapport increment-1-global-first-red.xml conservé. B-R029 / ADR-034 :
fixture d'échec enregistrée sous identité dummy dans QA, sans ouvrir les sources
inconnues ; le wrapper conserve l'UUID SQL d'une collecte échouée avant retour
du lot. Classe d'erreur uniquement en base/notification, exception originale
propagée. Deux régressions supplémentaires : identité réelle et refus sans
modifier un ancien run. Transaction du caller, aucune durabilité après rollback
revendiquée. QA renouvelée 27578, minimum 63 / huit intégrations ; check complet
à renouveler seulement après ses résultats. Aucun commit fonctionnel ni DONE.

QA corrigée 27578 code final 0 : 63 / 126,77 s / huit intégrations,
zéro failure/error/skip ; reçu c178755c3f714e1e8250f62fdfcfe40d / 140,324 s,
increment-1-qa-observability.json/xml. Types quatre fichiers, lint et diffcheck
codes 0. Les assertions SQL/API/Mailpit d'observabilité restent effectives.
Réception intégrale renouvelée requise avant commit ; R0.6 IN_PROGRESS.

Préparation des rapports : espaces de fin de ligne retirés uniquement dans les
deux XML rouges ; nombres, assertions, erreurs et traces conservés. Diff 6102
code 0. Scan non configuré 81465/76933 codes 1 : un faux positif generic-api-key
sur l'identifiant Dagster exact dummy_dagster_f1196e09722e43719f44a7cb10249ff2__bronze
(QA rouge, ligne 140), produit par le test et non une clé d'accès. Exception
littérale documentée dans .gitleaks.toml, aucun wildcard ni nouveau fichier exempté ;
scan configuré et contrôle final du snapshot staged restent requis.

Scan configuré préparatoire 48174 code final 0 : 139 194 octets / 8,88 s,
aucune fuite détectée avec l'exception littérale déclarée ; nouveaux reçus/états
à scanner à nouveau après réception globale, pas de commit anticipé.

Réception complète 91048 code final Windows 0 : 746 backend / 2332,14 s,
42 intégrations par layout/marker et 46 union, cinq avertissements, zéro
failure/error/skip. Core 93,83242823894491 %, extraction 86,3768115942029 %,
normalisation 84,85523385300668 %. Lint/format 202 et types 201 verts.
Frontend 35 tests / quatre suites / 4,95 s ; reçu
85c30b58-b24d-43de-99c4-4bfc04d7e759, quatre étapes codes 0,
build 233684 ms. Rapports backend/frontend et reçu agrégé conservés.
B-R028/029 résolus sur cette réception, pas R0.6 entière ; le ledger,
normalisation, checks mesurés, durabilité, inventaire et partitions restent ouverts.
Préservation et scan du snapshot final encore requis avant commit.

Préservation finale reçue après check : SQL 77284 et Bronze 56901 codes 0,
482 références et 764 prix, empreintes MD5 identiques ; 674 versions/current,
zéro marqueur, 1 377 481 octets, SHA identique au précheck/R0.5.
Reçu increment-1-active-preservation-final.json ; aucun schéma actif ou usage
humain qualifié. Diff/scan du snapshot final et commit encore requis.

Incrément transport reçu et committé
c63fe222832f76cc55feeba4f97def4ec296884d (41 fichiers, 1917 ajouts,
136 suppressions). Diff staged 47800 code 0 ; scan configuré final 10594 code 0,
440 194 octets / 7,04 s / aucune fuite, exception exacte de step UUID documentée.
R0.6 reste IN_PROGRESS ; suite : définitions/inventaire/schedules désactivés,
puis checks mesurés, ledger, normalisation, partitions et durabilité.

Deuxième incrément en réalisation après ADR-035/SPECS : inventaire explicite,
erreurs de résolution/construction expurgées plutôt qu'ignorées, exclusions
planned/disabled/forbidden/fixtures, cadences sans repli implicite et timezone
business. Unités 42059 code final 0 : 53 / 63,10 s, dont 24 nouvelles ; repository
Dagster réellement chargé, 15 assets / six checks / six schedules vérifiés.
NASA/WFP désactivées ne sont plus planifiées ; aucune acquisition effectuée.
Format 18169/lint 85433 codes 0 ; types 48096 en cours. QA portée à 90/huit
intégrations, réception complète et commit encore requis. Checks numériques,
normalisation, ledger, partitions et durabilité restent non qualifiés.

Revue défensive : classe de connecteur obligatoire, discover/fetch/parse callable ;
quatre tests de refus supplémentaires. Unités renouvelées 18533 code final 0 :
57 / 68,29 s, dont 28 source_definitions ; format 12397 et lint 45009 codes 0.
Mypy 10054 encore en cours. QA minimum désormais 94/huit intégrations ; code
de l'incrément 2 non committé, aucune qualification globale ou source live.

Types finals 10054 code 0 / quatre fichiers. QA Windows 13568 code final 0 :
94 / 115,84 s / huit intégrations / zéro failure/error/skip ; reçu
2693c4c0de6a45fc8ad68f6431f70dd5 / 128,224 s, increment-2-qa-final.json/xml.
Code figé pour réception intégrale renouvelée ; aucun commit ou DONE de cet
incrément avant check complet, préservation active, diff et scan.

Réception intégrale incrément 2, Windows 18002 code final 0 :
774 backend / 2365,63 s / cinq avertissements / zéro failure/error/skip,
42 intégrations par layout/marker et 46 union ; core 93,83242823894491 %,
extraction 86,3768115942029 %, normalize 84,85523385300668 %.
Frontend 35 tests / quatre suites / 11,58 s, reçu
9ad7f99c-026b-4d0b-90e2-ae3c910d67ed, quatre codes 0,
build 234840 ms. Rapports backend/frontend et agrégat final conservés.
Inventaire 15/six/six testé, exclusions et erreurs explicites ; aucune collecte
publique ou qualification de checks numériques revendiquée. Préservation
finale et scan du lot complet encore requis avant commit, R0.6 IN_PROGRESS.

Préservation finale renouvelée reçue le 2026-10-11 : SQL chunk 9958e6 et
Bronze session 58622 codes 0, mêmes comptes et empreintes que le précheck.
Reçu increment-2-active-preservation-final.json ; snapshot applicatif testé
comparé au worktree (session 4324 code 0), quatre fichiers identiques.
Diff/scan final et commit restent requis ; aucune qualification live.

Commit fonctionnel reçu b873f44ec71c8fcb04677983423f48a1ba17ab2f :
20 fichiers / 647 ajouts / 27 retraits. Diff staged 51497 code 0, scan
configuré final 75483 code 0 / 339921 octets / 8,67 s / aucune fuite.
R0.6 reste IN_PROGRESS ; aucune qualification source/modèle/usage humain.
