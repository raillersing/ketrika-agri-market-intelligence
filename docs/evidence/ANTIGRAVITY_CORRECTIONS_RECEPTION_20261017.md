# Corrections Antigravity — validation logicielle sur branche

État au 2026-10-17T13:58:01Z : **VALIDATION LOGICIELLE VERTE** sur branche isolée. Ce résultat ne vaut ni fusion main, ni qualification des données de marché, ni fin du programme R.

## Résultat consolidé

- Source applicative testée : `9b638478638b290d0cd509b496818006267e758e`.
- Check Windows78513 FINAL0 : **1762 tests backend**, zéro échec/erreur/skip,156 intégrations ; **43 tests frontend**, sept suites, lint/types et build de production verts.
- Navigateur45858 FINAL0 : **12 contrôles**,117,354 s, zéro erreur JavaScript ; login réel/cookie HttpOnly, reload, API prix200, refus macro503 explicite, navigation mobile et contenu réellement pleine largeur à390px, logout/API401.
- Inspection83591 FINAL0 : donnée synthétique relue Bronze/SHA→SQL→API authentifiée→page/reload/390px, type `imputed`, état `not_qualified` et valeur brute conservés. Les deux captures finales ont été relues visuellement.
- Filtres SQL69451 FINAL0 en transaction `READ ONLY` : paramètres2024-01-01/2024-03-01 réellement exécutés dans PostgreSQL,39 lignes QA retournées ; aucune statistique de marché ou qualification de couverture déduite.
- Aucun seuil scientifique abaissé, aucun test retiré, aucune donnée active/Bronze modifiée par ce lot. Les incidents logiciels B-R074–B-R083 sont résolus **sur cette branche** ; R0.8 reste IN_PROGRESS, sept DONE/66 TODO conservés.

## Source et isolation

- Branche : `fix/agy-publication-audit-20261016`.
- Worktree : `/home/raillersing/projects/ketrika-qa-worktrees/agy-publication-audit-20261016`.
- Source figée : `9b63847`, basée sur Antigravity `3c8958f` ; correction mobile et assertions de lisibilité réelle.
- Commandes : `scripts/dev.ps1 check` (78513/FINAL0), puis `scripts/dev.ps1 e2e` (45858/FINAL0), puis diagnostic QA83591. PowerShell Windows depuis WSL, Python/Node/Chromium dans Docker.44536 antérieur est vert mais ne qualifie pas la nouvelle UI ;76892/19008 sont rouges,78027 interrompue rouge. Tous originaux conservés sans promotion d'un reçu partiel.
- Destination exclusive : projet `ketrika-qualification`, DB et MinIO dédiés ; aucune suite mutante concurrente autorisée.
- Main applicatif non modifié. Aucun merge du worktree Antigravity actif, aucun statut/tag R1–R3 importé.
- Probe readonly Docker sur le conteneur de76892 :444 fichiers backend identiques (src/tests/alembic et quatre configurations), aucun extra/manquant/changé. SHA256 des inventaires ordonnés : `3646bed52f59a1688297e804dc433c65e777fb48d7a531926974ddb2675e9b94` des deux côtés. Cette preuve ne couvre pas à elle seule les scripts et le frontend.
- Probe historique19008/198261c :444/444 fichiers identiques, SHA256 `d1e634ced12af912b4bc1531ba23a94f053bfac7494afc3797894380e6c0d0c8` ; son résultat global reste rouge.
- Source finale78513 :446/446 fichiers backend identiques, SHA256 `6779c5c6382285f88a2c740c96addceb96fc958c16f430ed950023d7f19f4ebd`, runner identique ;56/56 fichiers frontend identiques, SHA256 `4fd365e04bbda027c8fafa1aabde0d680d4e85cbb320b61c533950909019f600`. Inventaire frontend hors node_modules/.next/env/tsbuildinfo/résultats générés ; une ancienne métadonnée Playwright ne constitue pas du code testé. Diff Git applicatif contre9b63847 nul avant navigateur.

## Écarts et traitement

| Écart de l'audit | Correction logicielle validée | Limite conservée |
|---|---|---|
| Chiffres macro considérés comme métadonnées | Refus avant SQL/publication ; API économique HTTP503 explicite ; autres vues toujours traitées | Publication macro non qualifiée, pas de contournement par cache historique |
| Fixtures générées présentées authentiques | Notices, générateurs et inventaire rectifiés ; droits non prouvés retirés des générateurs | Aucun classeur/PDF/Bronze existant régénéré ou modifié |
| Authenticité déduite du nom de source | Source connue et clé hachée restent UNVERIFIED_ACQUISITION sans chaîne d'acquisition vérifiée | Aucun pilote authentique déclaré |
| Jointures macro mélangeant séries/grains | Source/unité/fréquence/base/périodes natives séparées ; ambiguïté donne variation NULL | SQL testé sur données synthétiques, pas validation de marché |
| Lignage et type perdus | IDs de tous les contributeurs, périodes natives, type ; API d'inspection Silver et adaptateur OpenAPI/UI | Inspection explicitement non qualifiée, aucun lien de téléchargement prétendument vérifié |
| Dates non liées et panne masquée | CAST paramétré vérifié en PostgreSQL ; erreurs stables expurgées, état UI distinct du vide vérifié au navigateur/reload | Aucune disponibilité de source réelle déduite |
| Statuts et preuves exagérés | 74 statuts alignés sur main :7 DONE/1 IN_PROGRESS/66 TODO ; notices de rectification | Historiques préservés, aucune nouvelle qualification |

## Régressions découvertes pendant la réception

- Suivi Alembic VARCHAR32 incompatible avec les nouveaux IDs : taille128, identifiants conservés ; migrations0011/0012 réellement appliquées sur QA uniquement.
- Ancienne copie QA superposant les branches : remplacement des seules copies de code/tests/migrations dans le volume QA, avant chaque réception.
- Contrôle du parsing sur tout l'historique sans rapport avec la publication : contrôle de chaque lot complet contribuant, y compris échecs et éléments en attente ; seuil99% inchangé, nombre attendu vérifié, incohérences refusées. Diagnostic global conservé séparément.
- Fixtures HTTP locales sans opt-in explicite : corrections test-only pour NIPC, CountingHttp et fabrique Dagster ; refus SSRF par défaut maintenu et testé avant émission.
- Diagnostics groupés jusqu'à dix échecs par réception rouge ; aucune sélection scientifique ni couverture réduite, tout échec reste éliminatoire.
- ADR086 : versions de première acquisition et de traitement distinctes, sans mutation du parent ; lot/connecteur/ParseResult doivent toujours correspondre. Unitaires74 verts, mypy onze fichiers vert, vingt intégrations vertes et seul scénario Douanes corrigé puis reçu individuellement (18,79 s). Les références, octets, versions réellement exécutées et seuils métier restent vérifiés.
- ADR087 : migrations historiques bornées/snapshot forecast et0013 pour vues nouvelles non peuplées/droit Silver révoqué. Installation réelle depuis PostGIS neuf :0001→0013,14 vues/0 peuplée,Silver=false/Gold=true,0 observation.23 unités vertes ; anti-fuite SQL105,53 s vert avec39 prévisions du run et deux lignes seed d'autres périodes conservées ; lint/tsc web verts, mypy156 verts. Aucun seuil scientifique modifié.

## Preuves finales et historique

Originaux de la réception finale dans ce dossier : [JUnit](ANTIGRAVITY_FULL_CHECK_78513_JUNIT.xml), [couverture](ANTIGRAVITY_FULL_CHECK_78513_COVERAGE.json), [reçu frontend](ANTIGRAVITY_FULL_CHECK_78513_FRONTEND_RECEIPT.json), [Vitest](ANTIGRAVITY_FULL_CHECK_78513_VITEST.json), [navigateur](ANTIGRAVITY_BROWSER_45858_RECEIPT.json), [économie390px](ANTIGRAVITY_BROWSER_45858_ECONOMY_390.png), [inspection Silver](ANTIGRAVITY_MACRO_83591_RECEIPT.json), [provenance390px](ANTIGRAVITY_MACRO_83591_390.png).

Temps mural backend1895,65 s (JUnit1895,523 s) ; build225018 ms/16 pages statiques générées. Couvertures : core94,4863459%,extraction87,0422535%,normalize87,9858657% ; seuil80% conservé pour chaque groupe. Vérification explicite dans le JUnit : neuf gardes audit, six contrats de lignage macro, six contrats temporels/API, quatre migrations Gold, onze intégrations registre de lots, deux HTTP/Dagster, un garde publication SQL/S3 et un parsing SQL ; aucune sélection obligatoire déduite du seul total.

Les traces Playwright originales restent dans le volume QA ; elles ne sont pas versionnées, car elles peuvent contenir des éléments de session. Reçus et captures uniquement sont archivés dans Git.

44536 FINAL0 :1762 backend/1338,04 s/zéro échec-erreur-skip/156 intégrations ;42 frontend/six suites/build152667 ms. Couvertures core94,4863%,extraction87,0423%,normalize87,9859%.21636 passed=true/11 contrôles et98269 inspection synthétique passent leurs assertions, mais leur qualification visuelle mobile est retirée : capture390px relue montrant contenu comprimé par sidebar. Ce défaut n'est pas masqué ni présenté comme reçu.

ADR088 : navigation mobile repliée, contenu pleine largeur et contrôles des dimensions réelles/menu ; affirmations statiques100% provenance/3 alertes/Stack6-6/Live supprimées.50900/85958/85673 sont les contrôles de développement ;78513/45858/83591 qualifient ensuite le même contenu final. Aucune source ni modèle réel qualifié.

Les JUnit rouges originaux et contrôles ciblés sont conservés sous `docs/evidence/` du worktree de correction. Les codes finaux rouges96846,78054,30551,42382 ne sont pas des réceptions et ne sont pas réutilisés comme succès.

La réception logicielle est terminée sur cette branche. Une clôture documentaire ne justifie pas de relancer les suites vertes. Toute modification applicative/test/environnement invalidant la preuve exige en revanche une nouvelle réception complète.

Les ADR079–088 de cette branche sont locaux : leurs numéros ne remplacent pas ceux de main. Leur réconciliation et la préservation du code R0.8 plus récent restent obligatoires avant une intégration. Le résultat de cette réception ne terminera ni R0.8 ni le programme R6.11, et ne prouvera ni collecte live, ni performance de prévision, ni essai humain.

## Chronométrage sans nouvelle exécution de tests

Diagnostic93688 FINAL0 avec `qa_profile` sur le JUnit44536 déjà archivé, SHA256 `c70f9940b5a4e4ab0149a5b1d3f74fc4b42f6493525fc71c752b7b7e2649218d` :1762 cas, zéro échec/erreur/skip, somme des temps de cas1214,266 s (distincte du temps mural pytest1338,04 s). Cas les plus longs : cycle PDF MiASA230,544 s ; anti-fuite ML63,377 s ; benchmark API55,290 s ; cycle WB50,745 s. Ce sont les mesures de cette exécution antérieure, pas une estimation garantie de la suivante. Aucun test relancé, seuil abaissé ou gain avant/après revendiqué par ce diagnostic.
