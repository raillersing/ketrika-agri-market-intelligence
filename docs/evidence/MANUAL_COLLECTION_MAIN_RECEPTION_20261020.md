# Réception collecte manuelle sur le socle Antigravity

Source applicative figée : `790201bb9a4d82cdb1ff28048550005ec707416f`, issue de main `75d8674`. Empreinte : `82b5961c7b7e91d45e6fec7c4c37fdd25635ca7176ba9bdee5bff6d02dc720a0`.

## Logiciel reçu

- `bash scripts/dev.sh check`, processus 78730 : sortie 0. Backend : 2313 succès, zéro échec/erreur/skip, 1379,25 s ; 167 cas d'intégration (union inventaire). L'inventaire inclut les neuf tests SQL de collecte et les neuf tests API dédiés.
- Ruff, format (408 fichiers), Mypy (407 fichiers), cohérence des 74 tâches : verts. Couvertures : core 92,3219 %, extraction 87,7660 %, normalize 88,2624 %.
- Frontend : lint, TypeScript, 50 tests / sept suites et build des 16 pages verts. Reçu `a90bc050-79d8-4343-bf1d-52e0f5580782`, même commit/empreinte.
- `bash scripts/dev.sh e2e`, processus 32688 : sortie 0 ; douze scénarios / 130,551 s, zéro erreur navigateur. Reçu `f9ec5c7f77c549f1b5e17f82bcae1897`. Le refus économique 503 reste explicite, il n'est pas transformé en preuve de données qualifiées.
- Originaux conservés : `MAIN_COLLECTION_CHECK_78730_GREEN_JUNIT.xml.gz`, inventaire et couverture JSON, reçu frontend/Vitest, `MAIN_COLLECTION_E2E_32688_RECEIPT.json`. Traces contenant potentiellement des cookies non versionnées.

## Isolation et limites

Diagnostic Sources 76286 : sortie 1 avant tout clic, attente Playwright par défaut 5 s alors que le catalogue chargeait encore. Reçu rouge conservé. Seul le diagnostic readonly a été ajusté (`expect.set_options(timeout=60000)`), lint ciblé 87532 vert ; aucune source applicative ni dépendance changée. Diagnostic 58896 : sortie 0, vrai formulaire puis clic sous verrou SQL transitoire, refus 409, aucun reçu nouveau, quota 444 avant/après, reçu antérieur identique après reload, contexte sécurisé localhost, largeur mobile 390 sans overflow et zéro erreur JS. Reçu et captures joints. Le reçu antérieur est une fixture SQL partielle, pas une preuve de collecte live ; la capture pleine page ne vaut pas un essai humain de lisibilité.

Projet `ketrika-qualification-main-final`, base `ketrika_qualification`, bucket `ketrika-qa-bronze`, réseau interne et huit volumes dédiés. Identités exactes des trois images dans les reçus. Aucun reset, restore ou effacement Bronze ; anciennes destinations conservées.

La fonctionnalité admin distingue collecte externe et recalcul local. UUID idempotent, verrou de propriétaire, reçu SQL durable, quotas/politiques HTTP, Bronze puis Silver puis publication contrôlée ; aucune file asynchrone fictive. Migration additive 0017 après les quatre migrations AGY, correction des permissions/vues en 0018. Les modules AGY sont conservés, pas remplacés par l'ancienne branche Codex.

Ces preuves sont logicielles. Elles ne qualifient ni fraîcheur universelle, ni performance des nouveaux modèles, ni essai humain. La collecte WB live antérieure reste une preuve historique bornée (quinze estimations imputées), pas une collecte réexécutée sur ce commit. Les réserves scientifiques communiquées à AGY en C022 restent ouvertes ; R1.12 et les dépendances R ne passent pas DONE par déduction. Aucun tag final.

## Réception locale

Sauvegarde préalable active : `backups/ketrika_backup_20261020_083019.dump` (ignorée par git, non publiée). Base avant migration : 0016. Empreintes de conservation avant migration : source_record 482 / `970aa1dde9b2ece31fd785ede51f435c`, prix 764 / `fa29f041c264ca68db87f00f50aa2f23`, stocks 35 / `76b3fbe69e5377f78fe3cf2d63ab39f2`, météo 116 / `0214411a665b52f4121647c034856c43` (MD5 agrégat ordonné des lignes, contrôle de conservation, pas identité Bronze).

Fusion fast-forward53649 FINAL0 : main75d8674 →5e4a004, tous les commits AGY conservés. Aucun remote git configuré : aucun push revendiqué.

Activation :29315 FINAL1, upgrade0018 refusé car la base active ancienne gardait price_monthly sans source_family ; rollback confirmé0016/empreintes identiques. Maintenance opérateur48664 FINAL0 avec la fonction existante init_gold_views :14 définitions actuelles non peuplées, zéro observation modifiée.93060 FINAL0 : migration0018. Les quatre effectifs/empreintes ci-dessus sont strictement identiques après migration. Les caches invalidés sont des données dérivées, récupérables par recalcul contrôlé, pas par publication forcée. Runbook ajouté ; automatisation et test de toutes les formes historiques restent BL-019, non revendiqués comme livrés.

Sonde54863 : les trois routes Sources200, mais sortie1 sur un mauvais chemin santé /health404 ;35386 FINAL0 sur le vrai /v1/health200. Navigateur actif70230 FINAL1 : ancien bundle Next encore servi malgré nouveaux fichiers. Redémarrage du seul frontend33511 FINAL0 ; même parcours22475 FINAL0 : connexion formulaire, Sources200, bouton global activé, options200 (douanes_stats, faostat, miasa_odr, mincc_ppn, wb_rtfp_mdg), historique200, mobile390 sans débordement. Capture viewport MAIN_COLLECTION_ACTIVE_22475_MOBILE.png inspectée visuellement. Aucune collecte externe émise ni seuil modifié.

Les clôtures suivantes ne changent que documentation/preuves ; le contenu applicatif reste celui du check78730. Les caches ne sont pas déclarés repeuplés et la fraîcheur des marchés n'est pas certifiée par cette réception.
