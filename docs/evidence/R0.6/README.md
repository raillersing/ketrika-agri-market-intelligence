# R0.6 — lignée Bronze → Silver

État courant 2026-10-12 : incréments 1–9 reçus, dernier fonctionnel a5ec413.
R0.6 IN_PROGRESS. Les points de reprise ci-dessous sont
historiques ; ils ne remplacent pas les réceptions consignées en fin de fichier.
Incrément 7 durable reçu après ADR-050 ; incrément HTTP 8 reçu.

Incrément 9 reçu après ADR-040/SPECS : deux primitives identité
artefact/manifeste, six fichiers source/tests. Ciblé 47180 code 0/43 unités/
8,07 s/types-lint-format six fichiers ; QA Windows 96902 code final 0/
426/39/zéro échec-erreur-skip/139,44 s, reçu
78c7750c6f174769b0998e9659e225bc/147,987 s, originaux conservés.
Check Windows complet 12952 code FINAL 0 : 1104/75 intégrations/1990,69 s,
zéro échec-erreur-skip ; core 94,3629 %, extraction 86,3768 %, normalize 88,2090 %.
Front 35/quatre suites/4,66 s, reçu fc2c6306-937f-42d7-b81d-54084d50a0fb :
quatre étapes code 0, build 112316 ms. Six fichiers identiques au snapshot,
gouvernance Windows 21397 code 0, SQL/toutes versions Bronze inchangés.
Commit a5ec41324bf761a01850de4a073ba18f33d97255/11187 code 0 ; diff 02a66a
code 0, scan final 17967 code 0/499911 octets/39,4 s/aucune fuite.
Aucun ledger/partition/reprise qualifié.
SQL readonly vérifie comptes/NUMERIC/NULL/clés/version, pas des octets ou
provenance de mappings. Archive Bronze, référentiel effectivement utilisé,
ledger/partition/reprise non livrés ; prix/robots/ND préparatoires séparés.

Incrément 8 (2026-10-12) : identité User-Agent imposée via HTTPX Headers,
dix tests de casse/doublons/retry/redirection/GET conditionnel/304/429.
Ciblé 29503 code 0/lint-format-types deux fichiers/dix tests/5,94 s.
QA Windows 2784 code final 0/378 tests/34 intégrations/zéro échec-erreur-skip,
169,81 s ; reçu 2359445214c24e8f92c0721208e8e9d4/183,143 s.
Check Windows complet 49133 code FINAL 0 : 1056 backend/70 intégrations/
1698,41 s/cinq warnings, zéro échec-erreur-skip ; core 94,2421 %,
extraction 86,3768 %, normalize 88,2090 %. Front 35/quatre suites/2,86 s,
reçu fb6c5a51-67be-4065-85d9-f06ea32bdc1c : quatre étapes code 0,
build 128964 ms. Deux fichiers identiques au snapshot, SQL/Bronze final
inchangés. Commit fonctionnel 4710a6f9ffaadeebc808f6c647951f5e2fd5804e.
Diff code 0 ; scan final 90864 code 0/455948 octets/3,96 s/sans fuite ;
gouvernance 81159 code 0. BL-018 résolu. Helpers/ADR de worktree non adoptés, robots runtime,
ledger/partitions/reprise/garde structure SQL directe encore requis.
Précheck actif dans increment-8-precheck-preservation.json ; probe readonly
legacy-statistical-kind-readonly.json ne qualifie pas les prix : 764 types
statistiques absents, aucune valeur point inférée ou observation réécrite.

Point de reprise incrément 4 (2026-10-11T11:48:18Z) : toujours non committé.
QA finale de comportement 45271 code Windows 0, 197 tests dont seize
intégrations, 192,75 s, zéro failure/error/skip ; reçu
fb298a810c7046c590d738397d45ef4b / 204,982 s conservé. Types 23865 code 0
pour les trois fichiers de fixture, lint 98221 code 0. Format final global
66933 code 0 / 214 fichiers ; AST MiASA inchangé après format 49303 code 0.
Check intégral actuel 99868 : résultat final backend/frontend/build encore
requis. Aucun résultat du worktree préparatoire API/Gold/schema n'est inclus
dans cette qualification principale.

B-R032 : alias source et lieux MiASA exclusivement synthétiques, origin depuis
golden existant/human_reviewed=false ; aucun P-code ou niveau administratif
déduit du rôle producteur, niveaux symboliques 9. Rejeu corrige seulement les
anciennes références de cette fixture exacte sous garde QA, aucune observation
ou Bronze réécrit. Météo exige explicitement son P-code ; NASA conserve trois
P-codes de son mapping préexistant sans remplacement implicite. Seuil 5 %,
180 observations, distributions, bruts, idempotence et refus de Gold historique
conservés ; source MiASA et géographie réelle R1.1/R1.3 non qualifiées.

Les refus précédents restent conservés : 89136 (MiASA), 81034 (interaction NASA),
75577 (météo), 26579 (format). XML rouges récents archivés gzip sans modification
d'octets, SHA de destination décompressée vérifié et original scanné avant
compression ; JSON d'archivage et reçus présents. Pas d'effacement de rapport
historique, de seuil abaissé ou de cache vide déclaré certifié.

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

Incrément 3 en cours après ADR-036 : provenance source-scopée mesurée sur les
six tables, incluant historique/revue ; vide échoue avec 0/0 et métrique NULL.
Check blocking ERROR, reçu SQL avant retour négatif. Unités 95502 code 0 :
70 / 84,65 s ; types 44427 code 0 / deux fichiers, lint 99135 code 0.
QA Windows 47407 en cours (107/douze intégrations). Test réel de blocage aval,
réception intégrale et commit restent requis ; Gold réel/schema_drift/normalisation/
ledger/partitions/durabilité non qualifiés par ce reçu.

QA finale renforcée 28400 code final 0 : 107 / 116,74 s / douze intégrations,
zéro failure/error/skip ; reçu 5536f1c478bf4f66b4ee516f9b3b0f89 / 130,296 s.
Check réel Dagster : 1/1 valide laisse exécuter le sentinel, trois cas 0/1
le bloquent ; chaque reçu négatif est relu en nouvelle session SQL. Aucun
refresh Gold ni corpus officiel qualifié. Code figé pour check Windows 83312,
réception intégrale/préservation/diff/scan/commit encore requis.

Backend intégral 83312 reçu vert : 787 / 2327,02 s / cinq avertissements /
zéro failure/error/skip ; intégrations 46 layout / 46 marker / 50 union.
Core 93,85088393543428 %, extraction 86,3768115942029 %, normalize
84,85523385300668 %. XML/coverage/receipt increment-3-backend-check conservés,
relecture Docker 97146 code 0 ; frontend/code final Windows encore requis.
Ces résultats ne qualifient pas le prototype séparé de normalisation.

Check Windows 83312 code final 0 : frontend 35/quatre suites/6,73 s,
reçu a0e167cf-3795-44c9-92d6-9a84ec69021a, quatre étapes code 0,
build 216184 ms. Rapports frontend et agrégat final conservés ; snapshot
82554 code 0, quatre fichiers identiques. Préservation/diff/scan/commit
finals restent requis ; R0.6 IN_PROGRESS, prototype non inclus.

Préservation finale reçue : SQL chunk ddf1f4/Bronze 15632 codes 0,
482 références/764 prix/674 versions/current, zéro marqueur/1377481 octets,
empreintes identiques au précheck ; reçu final conservé. Aucun schéma actif,
source live ou usage humain qualifié. Diff/scan/commit du lot complet requis.

Réception finale : commit 27d4e0e7b576de18515c8244d932674b41c91e36,
24 fichiers/676 ajouts/huit retraits ; diff staged 76641 code 0,
scan configuré 98284 code 0/369689 octets/4,46 s/aucune fuite.
QA 107/douze, check 787 backend/35 web/build et préservation reçus.
R0.6 reste IN_PROGRESS ; normalisation préparée hors snapshot, non livrée.

## Incrément 4 — normalisation (reçue, 47dc4a8)

ADR-037/SPECS acceptés avant transfert : Decimal exact, alias SQL source avant
global, conversion documentée compatible produit et revue d'ambiguïtés.
Silver route PriceRecord vers normalize→load ; autres types inchangés.
Bruts/provenance conservés, revue comptée sans duplication au retry, révisions
append-only. value_kind en métadonnées seulement, colonne/UI R2.1 non livrées.
SQL/S3 Windows 2301 code final 0 : deux tests / 21,12 s, FMG/USD, source alias,
retry/révision et deux preuves natives vérifiées ; scope synthétique seulement.
Pas de réception globale de cet incrément, aucun Gold réel/source live/modèle
qualifié. Manifeste élargi sans réduction, préservation active inchangée.

B-R030 reçu numériquement : 45 tests / 6,88 s, précision exacte as_tuple,
exposants extrêmes et contexte de faible précision refusés sans arrondi observé.
Ancien check 37430 interrompu explicitement (Windows 1/Docker 137), reçu conservé,
pas réception complète. QA précision 79315 rouge : 194/1 / 140,92 s,
JSON/XML conservés ; défaut préexistant cache source_health B-R031/BL-015.
Le scénario Mailpit/API prépare désormais seulement les métadonnées source_health,
avec 0/0/NULL et sans publier de prix. Cela ne corrige pas l'API sans cache ;
correction séparée requise avant DONE R0.6. Nouveau manifeste minimum 195/14.

QA corrigée 3441 code final 0 : 195/138,18 s/quatorze intégrations,
zéro failure/error/skip, reçu 40f45e447ade40dda714ad488a0f0d15/152,36 s.
Nouveau check Windows 89136 en cours : lint/format 213, types 212 verts,
875 tests collectés ; backend/frontend/build finaux non reçus.
XML rouge conservé en `.xml.gz` : SHA original/décompressé identique
7c25b64c65258ddeda0e20393b317b0af12a7fb236cbfe55da6a7462316c63c8,
archive/réception dans `increment-4-qa-precision-red-archive.json`.
Scan préparatoire XML brut inclus 73355 vert/184520 octets/7,16 s ;
diff avait espaces de traceback originaux, archive évite de les réécrire.
Nouveau diff/scan du lot final et commit encore requis.

Réception renouvelée après les refus MiASA, interaction NASA/météo et format :
les XML rouges sont conservés byte-identiques dans leurs archives gzip,
avec SHA original/décompressé et scans des originaux avant compression.
Les références MiASA sont uniquement synthétiques, source-scopées,
sans P-code officiel ; tous les lieux créés portent admin_level 9.
NASA et météo sélectionnent leurs références explicites sans P-code inventé.
Seuil de revue et assertions de valeurs originaux conservés.
QA finale 45271 code 0 : 197 tests/seize intégrations/192,75 s,
reçu fb298a810c7046c590d738397d45ef4b/204,982 s.
Backend complet 99868 reçu code 0 : 875 tests/2464,91 s/cinq avertissements,
48 intégrations dossier/marqueur, 52 union, zéro failure/error/skip.
Core 93,85088393543428 %, extraction 86,3768115942029 %, normalize
88,2089552238806 %. Relecture XML exporté 54010 code 0, 875/52.
Snapshot sept fichiers identiques 64912 code 0 ; frontend/build et code final
Windows encore requis à ce point, aucun commit incrément 4 ni DONE R0.6.

Check Windows 99868 code final 0 reçu à 2026-10-11T12:23:16Z : frontend
35 tests/quatre suites/10,27 s, quatre étapes code 0 et build 227055 ms.
Reçu 0ba956bf-d093-487c-bb53-e50e93a60f31 et vitest originaux exportés ;
agrégat final conservé. Aucun prototype API/schema/Gold/ledger/robots séparé
inclus ; R0.6 IN_PROGRESS. Préservation finale et scan/commit encore requis.

Préservation finale : SQL aa1db6/Bronze 91367 codes 0, 482 références/764 prix,
674 versions/current et zéro delete marker/1377481 octets ; empreintes identiques
au précheck, reçu conservé. Diff/scan du lot complet et commit encore requis.

Clôture : commit 47dc4a852d1df22c3b3935eca6b68e4fa4d6f38c,
59 fichiers/2112 ajouts/21 retraits. Diff staged 48495 code 0, scan configuré
23767 code final 0/915064 octets/15,7 s/aucune fuite, gouvernance 98674 code 0.
QA 197/16, contrôle complet 875/35/build et préservation reçus.
R0.6 reste IN_PROGRESS ; aucune source native/modèle/usage humain qualifié,
aucun prototype séparé inclus. BL-015 et autres critères de la matrice restent ouverts.

## Incrément 5 — API DataOps sans cache (en qualification)

ADR-039/SPECS acceptés avant transfert ciblé route et deux fichiers de tests.
Liste depuis meta quand cache absent/non peuplé, fraîcheur NULL ; dernier run
meta prioritaire sur cache ancien. Santé non publiée 503 RFC 7807, sans chiffres
fabriqués ni refresh implicite. Huit unités et deux scénarios SQL/API ajoutés,
manifest minimum 207/dix-huit intégrations, aucun ancien test retiré.
Réception principale ciblée/globale, signatures SQL/Bronze et commit requis ;
prototype préparatoire 7389 ne qualifie pas ce nouvel état du dépôt.

QA principale 83025 code final 0 : 207 tests/dix-huit intégrations/169,87 s,
zéro failure/error/skip, reçu d7fa51b094544607b8e6b325aa627f94/183,532 s.
Lint 77825, format 45237 et types 98066 codes 0 ; trois fichiers contrôlés.
Check Windows complet 44242 reçu code final 0 : 885 backend/54 intégrations,
35 frontend/quatre suites/7,88 s ; build 228639 ms, quatre étapes code 0.
Snapshot 98540 code 0/trois fichiers identiques ; SQL et toutes versions Bronze
actives inchangés après réception. Commit 2d5b8ae, diff 11737 code 0,
scan 56727 code 0/389525 octets/12,2 s/aucune fuite ; BL-015 RESOLVED_FIXED.
R0.6 reste IN_PROGRESS, aucun prototype indépendant ni source live qualifié.

## Incrément 6 — structure et Gold connecté (en qualification)

ADR-049/SPECS adoptés avant transfert des seuls helpers structurels, audit,
check natif et dépendances Gold. Contrats CSV/JSON explicitement déclarés,
aucun contrat public inféré ; absence = unknown/refus. Factory deux checks
blocking, inventaire 15 assets/12 checks/six schedules. Garde structure SQL
directe/CLI, ledger/durabilité/partitions et qualifications sources restent ouverts.
Unités principales 85042 code 0/134/120,22 s ; lint et format 15 fichiers verts.
QA élargie minimum 319/24, aucun test historique retiré. Ancien scénario
provenance doit fournir son contrat JSON synthétique explicite et vérifier
les deux évaluations, pas un sous-ensemble ; nouvelle réception obligatoire.
Préparation indépendante 83639 code 0/huit tests/55,23 s : six Gold et deux
helpers durables, ces derniers non transférés ni reçus dans cet incrément.

QA initiale 45059 code final 1 : 315 passed/4 failed/259,86 s, reçu
d927b84cf74340278955e7ba62038823/284,26 s et XML originaux conservés.
Le snapshot incluait un contrat intermédiaire location_raw au lieu du champ
period_start réel de la fixture ; les six nouveaux Gold passent. B-R035,
correction limitée au contrat synthétique, nouvelle QA 30895 requise.

QA renouvelée 30895 code final 0 : 319 tests/24 intégrations/199,56 s,
zéro failure/error/skip, reçu 1d8413a058984cc0b4efb71fa7f2d9f1/215,381 s.
Originaux increment-6-qa-final conservés ; code figé pour check Windows intégral,
préservation/diff/scan final/commit requis. R0.6 et B-R035 non clos par la QA seule.

Réception globale Windows 21370 code final 0 obtenue le 2026-10-11T16:24:50Z.
XML original : 997 tests, 2240,356 s, zéro échec/erreur/skip ; couvertures
core 94,2094 %, extraction 86,3768 %, normalize 88,2090 %. Frontend 35 tests,
quatre suites ; reçu 7180d33b-7642-40d8-baa4-78d889afad15, toutes étapes code 0,
build 140732 ms. Les seize fichiers du lot correspondent au snapshot testé.
SQL actif et toutes versions Bronze relus après réception : empreintes identiques
au précheck (482 références, 764 prix, 674 versions, 1377481 octets).
Commit 6f1a9b1f6dff9c6411435a012c96c6b6f8d48def. Diff staged 52385 code 0,
scan configuré 50898 code final 0 : 502123 octets/31,9 s/aucune fuite ;
gouvernance 26921 code 0/74 statuts cohérents. B-R035 résolu par correction
du seul contrat synthétique et réception globale renouvelée. R0.6 demeure
IN_PROGRESS ; aucune réception complète, source live, modèle ou usage humain.

## Incrément 7 — durabilité des phases (en qualification)

Préparation indépendante : dix tests SQL 22936 code final 0/78,63 s,
deux helpers et huit cas propriétaires/assets natifs, échec après artefact,
après parse, après insertion et succès ; SQL/S3 synthétiques, pas d'acquisition
HTTP ni qualification live. ADR-050/SPECS adoptés avant transfert principal.
Factory utilise les propriétaires tout en conservant les douze checks et le
graphe Gold. Source SQL préexistante obligatoire, garde de collecte avant run ;
rollback puis reçu failed indépendant, classe seule sans chaîne d'erreur collectée.
Wrapper caller historique/crash recovery/ledger/partitions restent ouverts.
QA portée à 368 tests minimum/34 intégrations, aucune régression historique retirée.

QA initiale principale 81371 code 1 : 367 passed/1 failed/431,61 s ;
B-R036 TypeError dans préparation de la fixture historique, garde appelée avec
connection au lieu de host/database. Correction limitée à la lecture de l'URL
de session réellement liée ; aucune garde ni assertion retirée. XML rouge
archivé gzip -n, SHA original/décompressé identique, scan original vert.
Après interruption, aucun reçu du run 17691 ; non réutilisé comme succès.
QA renouvelée Windows 37651 code final 0 : 368/34/273,25 s,
zéro échec-erreur-skip ; reçu 566e579b3d19430396ff2d6ea0916c27/291,931 s.
Types/unités principales 76548 code 0 : dix fichiers, 103 tests/347,66 s.
Check Windows intégral 63938 en cours sur code figé ; aucun commit fonctionnel
du lot 7, B-R036 à clore après réception globale/preservation/scan/commit.

Réception Windows intégrale 63938 code final 0 obtenue 2026-10-11T23:41:56Z.
Backend 1046/70 intégrations/1477,80 s/cinq warnings, zéro échec-erreur-skip ;
XML original 1477,786 s. Couvertures core 94,2094 %, extraction 86,3768 %,
normalize 88,2090 %. Front 35/quatre suites/4,45 s, reçu
af0f0afe-738a-49f8-bf5d-983ae5c603c4 : quatre étapes code 0, build 109683 ms.
Dix fichiers correspondent au snapshot testé ; gouvernance Windows 15546 code 0.
Après contrôle complet, SQL et toutes versions Bronze actifs inchangés,
preuve increment-7-active-preservation-final. Scan final/commit encore requis ;
R0.6 reste IN_PROGRESS, wrapper caller/crash recovery/ledger/partitions ouverts.

Commit reçu 1bb067025a66cef99c8e189ba4165efe48355ee8 (72010 code final 0).
Diff b2100f code 0 ; scan final configuré 31299 code 0/496673 octets/3,71 s,
aucune fuite. B-R036 RESOLVED_FIXED. Réception limitée aux phases natives et
cas d'échec testés, pas au wrapper historique, arrêt brutal ou ledger/reprise.
