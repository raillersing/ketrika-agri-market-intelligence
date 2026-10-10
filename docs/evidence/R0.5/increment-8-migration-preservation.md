# Migration isolée 0005

Windows `scripts/dev.ps1 qa-isolated prepare`, session 99199 : code final 0,
upgrade `0004_production_raw -> 0005_gold_unpopulated`.

Relecture PostgreSQL `BEGIN READ ONLY`, code 0 : les sept effectifs et
empreintes complètes de `increment-8-migration-baseline.json` sont identiques.
Les 12 vues matérialisées Gold existent et aucune n'est peuplée.

Une première requête de diagnostic a échoué (code 1) sur un nom inexistant
`obs.trade_observation`. La requête corrigée utilise `obs.trade_flow` ; aucun
DDL ou changement de données n'a été exécuté par ce diagnostic.

Cette preuve concerne la préservation des observations et références de
l'environnement isolé, pas l'authenticité des sources ni une publication
qualifiée. Relecture Bronze après migration, session 49891 code 0 : 567
versions, 567 objets courants, zéro delete marker, 1217311 octets et SHA-256
`ddc0bf7c858d11b3006a9e524302594cd0217a3b5a5e6032fa5005a22e4f91fe`
identiques à la référence. Lecture LIST/GET uniquement, aucun objet modifié.
