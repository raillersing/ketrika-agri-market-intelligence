# R0.6 C — réception HTTP durable

Logiciel reçu sur branche ; intégration main et clôture R0.6 requises.
Autorisation explicite de reprise, snapshot Antigravity non qualifié conservé
sans mutation du worktree original (cinq archives gzip lossless).

## Contenu et réception

- ADR-063/SPECS avant code ; migration explicite 0010 QA uniquement.
- Quotas source/domaine atomiques, cadence partagée, SQL par défaut fail-closed,
  arrêts indépendants du rollback métier, aucun DDL runtime.
- Robots cache origin exact et acquisition gardée, retries/redirects contrôlés,
  identité bot après fusion des headers, credentials cross-origin retirés.
- Binding source avant discovery, y compris client paresseux ; 304 sans artefact
  connu refusé avant Bronze. Source disabled/forbidden toujours refusée.
- Windows réel dev.ps1 check 80378 FINAL 0 sur
  a1ee5045f75c18844a95327668b10e29bdac8b14 : lint/format 280/types 279 ;
  1462 backend/1540,70 s/zéro failure-error-skip/154 intégrations union.
- Frontend 35/quatre suites/21,29 s, quatre étapes code 0, build 15 pages ;
  reçu 533c6633-279f-419c-9be3-9506ec609b6b original archivé.
- Vérification readonly de l'inclusion dans ce JUnit : 63 fichiers R0.6,
  805 cas/118 intégrations, aucune absence. Pas de QA cumulative répétée.
- Vingt fichiers backend comparés au snapshot effectivement testé :
  aucune différence. Code applicatif/tests figés durant le check.
- Couverture core 93,8982070561018 %, extraction 86,3768115942029 %,
  normalize 90,37758830694276 % ; HTTP 95,4545 %, budget 99,1453 %.

Originaux backend XML/coverage et frontend receipt/vitest conservés sans
transformation ; SHA et inclusion par fichier dans lot-c-reception.json.
Premier check 10681 rouge (attendu migration 0009 obsolète, 65/1) conservé
gzip lossless ; attendu exact 0010 corrigé sans assouplir les gardes Gold.
Incident fixture Dagster positive disabled conservé et corrigé en synthetic
active ; aucune source publique activée.

## Préservation et limites

Avant/après : 482 SR/47b4402859acc41e3ae91fdb128e56c6 ;
764 prix/4b2586cb8e422f11c4873ad513d66bc1 ; schema actif 0002 ;
674 versions Bronze/1377481 octets/
83ae4ee1b5a8b3c8c957a50dde479f3def170b8ec42257995a340f65294c265c ;
zéro delete markers. Aucun reset, backfill, migration ou arrêt actif.

Cette réception ne qualifie ni collecte live, fraîcheur, modèle de marché,
déploiement, ni usage humain. Le suivi durable des éditions/ETag et le contrôle
des cibles privées/DNS sont R1.2, non revendiqués ici. En cas de source SQL
verrouillée lors d'un challenge, le journal durable refuse même après rollback ;
la ligne source peut conserver son ancien statut, limite explicitement testée.
