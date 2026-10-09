# R0.2 — réception logicielle verte

Réception complète le 2026-10-09T10:13:51Z : check Windows code 0, empreintes
actives inchangées. Statut DONE ; commit fonctionnel vert
`6b4ad7feef184acff08cdbbf65b372d52019f2f8`, clôture 2026-10-09T10:15:59Z.

## Réception finale

- Commande : `env WSL_INTEROP=/run/WSL/2_interop powershell.exe -NoProfile
  -ExecutionPolicy Bypass -File scripts/dev.ps1 check` ; code 0. Socket d'interop
  sélectionné après incident B-R003, aucun service actif redémarré.
- Backend : lint/format 160 fichiers, mypy 159 fichiers ; 290 passed, zéro
  erreur/échec/skip, 2360,00 s. XML relu indépendamment : 32 tests dans le dossier
  intégration/ou marqués, 258 autres du dossier unit (certains utilisent aussi DB).
- Couvertures par paquet : core 91,57 %, extraction 86,38 %, normalize 84,86 %.
  Rapport JSON : 2189/2443 statements, SHA256
  `17aa0ded412c9cdaa36f12563b544ea92449aa17a286477d6f47156525c85247`.
- Front : lint et types codes 0 ; 15 tests / 2 fichiers passés ; build 15 routes
  compilées, code 0. Aucun E2E navigateur, source live, performance de marché,
  usage humain, déploiement, image reconstruite ou CI distante qualifié.
- DB active après : 482 références / 764 prix, mêmes digests. S3 après : mêmes
  674 versions, 1377481 octets et SHA256 de manifeste. Aucun objet supprimé,
  modifié ou artificiellement corrompu ; négatifs uniquement mocks/DB dédiée.
- Le runbook fournit la procédure de réhydratation authentique ; aucune archive
  réhydratée ni purge réalisée par cette tâche. Profil réel distinct des tests.

Les lignes de suivi ci-dessous décrivent les étapes intermédiaires, pas un
check final encore en attente. Résultats machine : [check-summary.json](check-summary.json).

Pré-commit : `git diff --cached --check` code 0 ; gitleaks Docker
`git --staged /repo --config /repo/.gitleaks.toml --redact` code 0,
24810 octets analysés, zéro fuite ; scan final des changements de réception :
31084 octets, code 0, zéro fuite. Un premier appel avec `--source` a été
refusé (code 126) ; la syntaxe documentée par l'aide locale a été utilisée
ensuite. Ce contrôle ne remplace pas le check applicatif complet.

## Inventaire actif en lecture seule

Source : DB locale historique `aiagent-db-1/ketrika`, pas données actuelles du
marché. Grain : un source_record par document et une observation de prix par
natural_key/révision ; des liens FK présents ne prouvent pas l'authenticité.
SQL inspectable : [inventory.sql](inventory.sql), exécution par `docker exec -i
aiagent-db-1 psql -U ketrika -d ketrika -P pager=off`, code 0. Transaction read-only.

| Contrôle | Effectif / population | Risque et qualification |
|---|---:|---|
| IDs source explicitement test/dummy | 227 / 482 (47,10 %) | Critique, preuve directe de contamination ; exclure du corpus décisionnel |
| URL locale/fictive connue | 466 / 482 (96,68 %) | Critique ; ne prouve pas une collecte publique authentique |
| SHA256 mal formé | 129 / 482 (26,76 %) | Critique ; impossible de revendiquer 100 % de provenance bytes |
| Prix liés à une source test/dummy | 246 / 764 (32,20 %) | Critique, contamination analytique |
| Prix liés à URL locale/fictive | 552 / 764 (72,25 %) | Critique ; synthétique et collecté ne sont pas séparés historiquement |
| Prix sans source_record | 0 / 764 | FK complète, mais insuffisante pour provenance Bronze |
| Prix négatifs / kind hors observed,imputed | 0 / 764 chacun | Contrôles de domaine réussis, sans certification de valeurs |
| Valeurs déclarées observées / imputées | 750 / 14 | Toutes accepted ; ce libellé ne rend pas le corpus authentique |

Ces populations se recouvrent ; ne pas additionner les taux. Les 16 références
sans URL de test ne sont pas déclarées authentiques. Vérification bytes/objets
et golden sets indépendante restent R0.4/R0.5. Les dates de prix vont de
2018-05-01 à 2025-01-31 ; ingestion maximale 2026-10-07T19:09:57.473059Z.
L'ingestion récente n'est pas la fraîcheur du marché. Cause probable confirmée
par le code historique : tests intégration et seed démo partageaient la base.

Action proposée, non exécutée : conserver l'historique en archive non
décisionnelle, réhydrater un corpus authentique dans une destination neuve,
avec manifeste d'exclusion latéral, sans modifier/supprimer Bronze ou observations.
Voir [runbook qualification](../../runbooks/qualification.md).

## Préservation et limites

Avant changements R0.2 : source_record 482, digest
`47b4402859acc41e3ae91fdb128e56c6` ; prix 764, digest
`4b2586cb8e422f11c4873ad513d66bc1`. Résultats identiques après le check final.
Empreinte S3 avant et après : bucket bronze, 674 versions et
674 objets courants, zéro delete marker, 1377481 octets cumulés ; SHA256 du
manifeste trié incluant clés/versions/hash des octets :
`83ae4ee1b5a8b3c8c957a50dde479f3def170b8ec42257995a340f65294c265c`.
Commande Docker GET/list uniquement, code 0 ; script reproductible
`scripts/bronze-fingerprint-readonly.py`. Aucun test négatif sur store actif.
Seconde lecture S3 après modifications : résultat et digest strictement identiques,
code 0. Refus CLI `qa-isolated production` Linux et Windows : code 1 attendu
avant initialisation. Windows utilise le socket d'interop système pour B-R003.
Réception globale terminée : lint/format 160 fichiers, mypy 159 fichiers,
gouvernance des 74 tâches, 290 tests backend, 15 tests front et build verts.
Refus Windows `scripts/dev.ps1 demo` : code 1 attendu, message ADR-009/R0.7,
aucun client DB/S3 chargé. Vérification préalable du bind mount backend actif
confirmant l'exécution du module retiré du checkout, pas d'une ancienne image.
Ces MD5 ne sont que des témoins de conservation,
pas des preuves SHA256 du Bronze. Aucun contenu ni secret imprimé.
