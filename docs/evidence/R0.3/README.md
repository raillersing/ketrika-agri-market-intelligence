# R0.3 — réception logicielle locale (clôture en préparation)

Le check global courant et le navigateur final sont verts. R0.3 reste
IN_PROGRESS jusqu'au commit fonctionnel. Scan staged des secrets vert. Aucun tag
de phase avant le gate R0.9 ; les échecs antérieurs restent consignés.

## Réception finale Windows après ADR-013

- `dev.ps1 check`, session 36386, code final 0 : lint/format/types backend
  verts (163 fichiers formatés, 162 vérifiés par mypy), 340 passed / 3556,99 s,
  5 avertissements de dépendances, zéro échec/erreur/skip ; JUnit mesure 31
  intégrations par dossier, 31 par marqueur, union dédoublonnée 35.
  `backend-check-tests.xml` et `backend-check-coverage.json` sont les rapports
  exacts de cette réception, pas les anciens rapports réécrits.
- Couvertures validées : core 91,974957 %, extraction 86,376812 %,
  normalize 84,855234 % (seuil 80 % chacun).
- Front du même check : lint/types/tests/build codes 0, 35 tests / 4 fichiers
  en 5,08 s ; build complet 169177 ms, 15 pages statiques et routes dynamiques.
  Reçu `frontend-check-receipt.json`, rapport `frontend-check-tests.json`, run
  `c77c9881-dabf-45d5-a366-010b8711080e` ; aucun error_code/signal/timeout.
- `dev.ps1 qa R0.3`, session 46885, code 0 : 58 passed / 55,30 s, zéro
  échec/erreur/skip, 4 intégrations union, runner 62,689 s ; reçu
  `2305b7e8c762461e8c2f45b8459d664f`, fichiers `qa-check-task-receipt.json`
  et `qa-check-task-tests.xml`.
- `dev.ps1 qa-isolated negative-build`, session 10855, code 0 : stdout
  mesuré `actual_exit=1`, `detected_compile_error=true`, `passed=true`.
  Seule la copie jetable contient le défaut. Les trois défauts réels de lint,
  types et intégration sont également refusés dans la sous-suite ci-dessus.
- Préservation finale après check et contrôle négatif : DB/S3 read-only
  codes 0 ; mêmes 482/764 lignes et MD5, mêmes 674 versions / 1377481 octets,
  zéro delete marker et SHA-256 Bronze que les empreintes documentées plus bas.
- `dev.ps1 e2e`, session 50872, code 0 : 9 contrôles / 100,37 s, zéro
  erreur page, prix 200, profil après logout 401. Formulaire réel, session
  HttpOnly sans jeton injecté/JWT JS secondaire, reload, API et UI protégées,
  logout avec suppression de session et refus ultérieur réellement vérifiés.
  Run `1ce4ed19a3af4a9c81087df570efb17d`, `browser-check-receipt.json`
  et `browser-check-prices.png`. Trace ZIP conservée dans le volume QA, jamais
  exportée au dépôt (sessions possibles). Commit encore requis.
  CI syntaxe actionlint Docker code 0, CI distante non exécutée.
  Inspection visuelle : 16 lignes synthétiques, dont la sonde future 999999
  explicitement introduite par test_ml_forecast.py ; aucun prix authentifié.
  Graphique vide et badges statiques non qualifiés relèvent de BL-009/R2.10.
- Gitleaks Docker `git --staged --redact /repo` : code 0, environ 1,13 Mo
  de diff réellement scanné, aucune fuite. Portée staged uniquement, pas
  un audit complet de l'historique ni une qualification de sécurité R6.7.

Portée : logiciel et environnement synthétique QA dédiés, non-root, LLM replay.
Aucune collecte live, authenticité de prix, performance prédictive de marché,
revue humaine ni livraison distante n'est qualifiée par ces tests.

## Réceptions intermédiaires datées (ne remplacent pas la réception finale)

- Après ADR-012 : `dev.ps1 qa R0.3` code 0, 58 passed / 52,57 s,
  reçu `c2c0e10de62a449fa4678b601740aa1a`, durée runner 61,56 s,
  zéro échec/erreur/skip, 4 intégrations (union). Trois régressions ajoutées
  pour marqueur hors dossier/dédoublonnage, dont vrai subprocess pytest.
  E2E courant vert ci-dessous ; check global encore en cours.
- Check Windows courant après ADR-012 : backend 340 passed / 4230,55 s,
  zéro échec/erreur/skip, 5 avertissements de dépendances. JUnit : 31 cas par
  dossier, 31 par marqueur, union dédoublonnée 35 (minimum 32 satisfait).
  Couvertures validées : core 91,974957 %, extraction 86,376812 %,
  normalize 84,855234 %. Rapports `backend-tests.xml` et
  `backend-coverage.json`, reçu de tâche `qa-task-receipt.json`.
  Front lint/types verts et 32 tests / 4 fichiers verts en 33,59 s ; rapport
  `frontend-tests.json`, run `5da66418-7360-44a5-a354-50f843c11ca0`.
  Build interrompu après 900341 ms (limite runner 15 minutes), check Windows
  final code 1. Aucun build complet ni succès global ; incident B-R008.
  Reçu négatif `frontend-timeout-receipt.json`, trace Webpack exacte
  `frontend-timeout-trace.json` (616117 octets). Le status natif 0 du processus
  accompagné d'une erreur timeout n'est pas une compilation réussie :
  `passed=false`, vérificateur code 1. La trace mesure la phase serveur à
  359,235 s, dont fermeture Webpack 105,520 s ; cause racine non établie.
  Diagnostic frontend seul relancé avec la même limite, sans omission de
  lint/types/tests/build ; ce diagnostic ne vaut pas check global.
  Second diagnostic code 1 à 901509 ms : compilation et 15/15 pages vertes,
  finalisation des traces interrompue ; reçu `frontend-second-timeout-receipt.json`.
  Repli ADR-013/SPECS avant code : build borné à 1800 s, autres commandes
  à 900 s, CI à 150 minutes ; reçus error_code/signal/timed_out explicites,
  trois nouvelles régressions de délai/erreur/timeout réel. Réception de cette
  version code 0 : 35 tests / 4 fichiers, 34,56 s ; lint/types/build codes 0.
  Build complet 922633 ms, reçu 8158e316-307c-4eab-81b5-31185e49f81e,
  aucune erreur ni timeout. Durées lint 65288 ms, types 76294 ms, tests
  56773 ms ; actionlint Docker courant code 0. Check complet Windows
  relancé session 36386 ; aucun succès global ni timeout effacé.
- HEAD concurrent `799f869af5da4a7ccc36773ba1277bde8cf2f846` (14:53:51 UTC)
  conserve le design et le contrat de connexion ADR-011, avec mot de passe
  de démonstration prérempli. Ce commit précède l'E2E ADR-012 et le check
  courant ; il est préservé, sans attribution de ses changements à R0.3.
- Préservation read-only finale pendant build : commandes DB/S3 codes 0,
  482 source_record (MD5 `47b4402859acc41e3ae91fdb128e56c6`),
  764 prix (MD5 `4b2586cb8e422f11c4873ad513d66bc1`), Bronze 674 versions,
  1377481 octets, zéro marqueur de suppression ; SHA-256 global
  `83ae4ee1b5a8b3c8c957a50dde479f3def170b8ec42257995a340f65294c265c`.
  Empreintes identiques aux contrôles antérieurs, aucune mutation active.
- `dev.ps1 e2e` après ADR-012 : code 0, 9 contrôles / 124,458 s,
  zéro erreur page, prix 200 / profil après logout 401. Check complet de
  cette version relancé ; aucune clôture sur sous-suite seule.
  Reçu `browser-receipt-adr012.json`, capture `browser-prices-adr012.png`,
  run `6428d0672d934a6e898c33d5b0580db3`. Inspection visuelle : tableau
  de 16 lignes provenant du dataset synthétique QA, pas de prix authentifiés.
  Les badges statiques et la présentation de provenance restent BL-009/R2.10.
- Check avant ADR-012 : 337 passed / 1922,33 s, 5 avertissements,
  couverture brute 2293/2549 lignes ; code final 1 car compteur limité à 31
  dossiers, sans marqueur du 32e test ML. Front non exécuté, pas de succès
  global. Minimum 32 conservé et minimum de suite renforcé à 340 cas.

- `dev.ps1 qa-isolated negative-build` : code 0 du vérificateur, vrai code
  Next 1 / erreur de compilation détectée, uniquement dans copie jetable.
- `dev.ps1 e2e` final : code 0, 9 contrôles / 90,293 s, zéro erreur page,
  prix 200 / profil après logout 401. Connexion via formulaire, cookie HttpOnly,
  aucun cookie JWT JS secondaire, reload, API same-origin, prix, logout/refus.
  Les deux runs précédents sont rouges : bouton ancien absent puis attente
  30 s dépassée lors de la compilation proxy mesurée 47,6 s. UI concurrente
  65541c8 préservée ; contrat ADR-011 et runner corrigés avant la relance.
  Reçu exporté dans `browser-receipt.json`, capture `browser-prices.png`
  (run `32f9fd8d34904351ab635a4880f968f0`). Inspection visuelle : écran vide
  pour la sélection, design présent ; badges statiques 100 % provenance /
  3 alertes / stack 6/6 non qualifiés, dette BL-009 affectée à R2.10.
  La trace reste dans le volume QA et n'est pas publiée (sessions possibles).

- `dev.ps1 qa R0.3` : code 0, 55 passed / 65,43 s ; JUnit 55 cas,
  4 intégration par dossier, zéro échec/erreur/skip. Reçu courant
  `b93cb350b778459b8cffdf19ba6b7111`, durée runner 74,721 s.
- Diagnostic `qa-isolated test tests/integration/test_wb_rtfp_mdg.py -vv
  --tb=long` : code 0, 1 passed / 40,89 s. Répétition `tests/integration -vv
  --tb=long --maxfail=1` : code 0, 31 passed / 337,14 s, 5 avertissements.
  B-R005 n'est pas reproduit ; sa cause initiale n'est pas établie.
- Premier check courant : lint/format verts, 163 fichiers ; mypy code 0,
  162 fichiers ; 337 tests collectés, test WB échoué. Arrêt volontaire du
  seul conteneur de check pendant le test ML suivant : Docker 137, Windows 1.
  Aucun résultat global/couverture/front de ce run ne vaut réception.
- Image navigateur construite code 0, utilisateur app :
  `sha256:2646169d3348b9d52388664d307e05e38b18e0a72869dcdae906cdece75f66cf`.
  Export 1708,5 s et décompression 320,8 s ; ce build ne prouve pas l'E2E.

## Résultats intermédiaires antérieurs

- `bash scripts/dev.sh qa-isolated test tests/unit/test_qa_manifest.py -q` :
  code 0, 29 tests en 1,93 s sur l'état intermédiaire du manifeste.
- `bash scripts/dev.sh qa R0.3` : code 0, 42 tests en 50,49 s, dont 4 intégration
  par dossier JUnit, zéro erreur/échec/skip. Reçu unique
  `528d16b6f9f34630866bf47d1c8db959`. La suite a été renforcée depuis : refaire
  la réception courante, ne pas appliquer ces effectifs aux nouveaux tests.
- Front Docker QA intermédiaire : lint/types codes 0, 32 tests / 4 fichiers en
  12,03 s ; build Next 14.2.10 code 0 (15 pages statiques et route proxy dynamique).
  Reçu `bb7f1bdc-e69e-4f2f-b700-4edc4c57f567`, étapes mesurées
  lint 10139 ms, types 14397 ms, tests 17795 ms, build 256488 ms.
- Probe mypy de qa_manifest.py : code 0, 1 fichier ; notes de sections inutilisées
  car contrôle ciblé seulement. Probe ruff ciblée corrigée : contrôles verts.
- Syntaxe PowerShell via socket WSL système et bash -n : codes 0 sur état
  intermédiaire. Renouveler sur le runner final.

Incidents conservés : première commande front code 1 (option Vitest interprétée
par pnpm), corrigée par pnpm run ; probe ruff read-only code 2 (cache), corrigée
par /tmp. Deux builds QA interrompus volontairement code 130, puis suppression
du chown récursif au profit d'installation non-root. Une tentative navigateur
échoue code 1 sur timeout registre uv avant installation ; relance en cours.
Aucun de ces résultats n'est présenté comme une réception verte globale.

Environnement : projet interne ketrika-qualification, DB/bucket synthétiques
dédiés, LLM replay, aucun envoi réel, aucune suppression de Bronze. Les nouveaux
volumes r03 conservent les anciens volumes de preuve. Logiciel testé ne signifie
pas collecte live, authenticité du marché, validation du modèle ou essai humain.
