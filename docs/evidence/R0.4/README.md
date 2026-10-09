# R0.4 — authenticité du corpus

État : IN_PROGRESS. Aucun DONE, commit ni tag de qualification de cette tâche.

## Preuves intermédiaires

- Inventaire initial mécanique : 63 fichiers ; `initial-corpus-inventory.json` conserve tailles
  et hashes avant conformité LF des quatre CSV historiques non authentifiés.
- Windows `qa R0.4`, reçu f2b969abbf4f408f81924af28e3eb0b0 : code 0, 45 tests / 6,89 s,
  zéro échec/erreur/skip ; version initiale avant annotation authentique et contrôles étendus.
- Acquisition Docker WDI : code 0, 4 requêtes déclarées, 510 octets SHA
  d7a21e6b8fe97bd21b2be7819df1dd8f5aab311e41612a9a8090e4642453f21a ;
  réponse brute officielle sous tests/fixtures/authentic, reçu C1 sous tests/corpus-evidence.
  Deux années de PIB, pas de prix PPN ni nouvelle qualification de connecteur R2.2.
- HDX 403 : B-R009. NASA POWER `/api/` interdit par robots : B-R010 ; aucune donnée API NASA
  acquise. Aucun contournement, source de prix/météo indisponible pour cette acquisition.

## Incidents et réceptions précédentes conservés

Check Windows session 97060 code 1 : 18 passed / 1 failed / 219,39 s, arrêt avant frontend.
`red-check-tests.xml.gz` / `red-check-coverage.json` conservent cet échec et sa couverture partielle,
jamais utilisée pour satisfaire 80 %. Diagnostic B-R011 : trois versions CRLF et LF conservées,
scénario douanier rejouait tout l'historique au lieu de ses trois artefacts. Correction ADR-015
temporaire dans le test uniquement, aucun objet/métadonnée supprimé et runtime rebuild inchangé.
`intermediate-qa-*` sont les reçus verts 71 avant cette correction, pas la réception finale.

QA Windows corrigée : `qa-task-*`, 72 passed / 35,34 s, code 0, 1 intégration,
reçu 8319efc26dcc41cdba2ac26cab9cab28. Check suivant 15670 code 1 sur annotation mypy,
avant pytest ; annotation corrigée puis mypy ciblé code 0.

Check 93678 : backend 411 passed / 1480,73 s, zéro échec/erreur/skip,
35 intégrations union ; couvertures core 92,646297 %, extraction 86,376812 %,
normalize 84,855234 %. `backend-check-*` conserve ces résultats. Frontend
`frontend-check-*`, reçu ab7830f5-04a9-4129-b1fb-f0bcbcd21892 : 35 tests / quatre suites,
lint/types/tests/build codes 0, build 194897 ms, passed=true, aucun timeout ni signal.
Le serveur a interrompu la conversation avant récupération du code final Windows :
celui-ci est inconnu, pas assimilé à un code 0. Aucun conteneur de check restant ;
réception complète renouvelée session 39003, version fonctionnelle inchangée,
conformément à la reprise AGENTS §3.1 ; résultats de cette relance ci-dessous.

## Réception courante complète

- Check Windows session 39003 : **code final 0 reçu**, version fonctionnelle inchangée.
  Backend : 411 passed / 1403,60 s, zéro échec/erreur/skip, cinq avertissements de dépendances.
  Intégrations : 31 par dossier / 31 par marqueur / union dédoublonnée 35.
  Couvertures : core 92,646297 %, extraction 86,376812 %, normalize 84,855234 %.
  Rapports `backend-renewed-check-*`, lint/format/types verts (166/165 fichiers).
- Front : `frontend-renewed-check-*`, reçu fe8baa92-6924-4f33-9135-72d4245e7a10,
  35 tests / quatre suites / 5,96 s ; lint 9135 ms, types 16865 ms, tests 11161 ms,
  build complet 154768 ms, tous codes 0 sans erreur/signal/timeout.
- QA Windows session 41954 : code 0, 72 passed / 35,66 s, une intégration réelle,
  zéro échec/erreur/skip. `qa-renewed-task-*`, reçu 4d4b0d2fd4914baf8a51bd3d4bcb3fdf,
  durée runner 45,023 s. Rejeu douanier borné 3 objets / zéro ignoré / 40 inserts /
  une supersession / trois skips d'observations ; métadonnées conservées, pas preuve R0.8.
- Inventaire hors réseau courant code 0 : 65 fichiers / 507483 octets, 44 synthetic /
  19 unverified / deux authentic (un document + une annotation), dix cellules relues.
- Préservation read-only codes 0 : sources 482, MD5 47b4402859acc41e3ae91fdb128e56c6 ;
  prix 764, MD5 4b2586cb8e422f11c4873ad513d66bc1. Bronze 674 versions/objets,
  zéro delete marker, 1377481 octets, SHA
  83ae4ee1b5a8b3c8c957a50dde479f3def170b8ec42257995a340f65294c265c, inchangé.
- Aucun déploiement, CI distante, prix/météo live, modèle de marché ni revue humaine
  qualifiés. B-R009/010 portent les refus à R1 ; B-R011/012/013 reçus sur la relance complète.
  Scan de secrets Docker staged code 0 : 775572 octets scannés, aucune fuite.
  Le XML rouge est compressé sans perte, pas nettoyé : 11215 octets originaux,
  SHA 4c85cd7c76e2706c3205247e268d1d2d4872be1f75d27fa51b3e39b4c36eb22c ;
  archive 2921 octets, SHA cac5a736b1d8e9c9c89b497ed7ed9054f392e2dd767154dce1eb1794528d1eb3.
  Décompression identique vérifiée dans Docker. Commit vert encore à consigner avant DONE.

## Commandes et périmètre

Commandes Windows réellement utilisées depuis WSL (interop système) :

```sh
env WSL_INTEROP=/run/WSL/2_interop powershell.exe -NoProfile -ExecutionPolicy Bypass -File 'C:\Users\raillersing\Documents\#Entreprise\Ketrika AI\AI Agent\scripts\dev.ps1' qa R0.4
env WSL_INTEROP=/run/WSL/2_interop powershell.exe -NoProfile -ExecutionPolicy Bypass -File 'C:\Users\raillersing\Documents\#Entreprise\Ketrika AI\AI Agent\scripts\dev.ps1' check
```

Acquisition WDI réellement exécutée (lecture seule du dépôt, sans DB/S3/secrets actifs) :

```sh
docker run --name ketrika-r04-wdi-acquisition --mount 'type=bind,source=/mnt/c/Users/raillersing/Documents/#Entreprise/Ketrika AI/AI Agent,target=/workspace,readonly' -e PYTHONPATH=/workspace/backend/src -e PYTHONDONTWRITEBYTECODE=1 ketrika-backend:qa-r03 python /workspace/backend/scripts/acquire_wdi_corpus.py
```

Cette acquisition bornée sur réseau Docker sortant est distincte des tests entièrement isolés,
projet ketrika-qualification, DB ketrika_qualification et bucket ketrika-qa-bronze.
Ne pas relancer les acquisitions arrêtées HDX/NASA. Les sorties machine sont copiées depuis
le conteneur ; aucune réponse officielle brute n'est éditée. Le runtime existant qui ignore
source.status reste une dette explicite BL-010/R0.6/R1.2, pas un verrou réseau qualifié.

Inventaire final + annotation indépendante, suite authentique distincte, QA R0.4 courant,
check Windows complet avec couvertures ≥80 %, préservation active et secrets, commit vert.
Revue humaine absente H5 ; publication historique inconnue ; pas de modèle, déploiement ou essai
institutionnel qualifiés. Le corps intégral de la page de droits n'est pas conservé : reçu HTTP,
hash de réponse et clauses vérifiées/paraphrasées, URL source permettant une relecture distincte.
