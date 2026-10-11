# R0.6 — matrice de réception incrémentale

Statut de tâche : **IN_PROGRESS**. PROGRESS est canonique ; cette matrice ne
certifie ni collecte officielle live, ni conversion économique, ni modèle,
ni essai humain. Les fixtures QA sont synthétiques et séparées de l'actif.

| Critère | Réception actuelle | Preuve et limite |
|---|---|---|
| Bronze retourne les références exactes | Reçu, c63fe22 | `increment-1-qa-observability.json/xml`, transport SQL/S3 réel et batch immuable ; ledger persistant de membres encore absent |
| Silver ne refetch pas | Reçu, c63fe22 | Compteur HTTP local inchangé à un appel pendant Silver, relecture dans nouvelle session ; pas collecte officielle |
| Même artefact deux fois sans doublon | Reçu, c63fe22 | Trois inserts initiaux puis zéro insert/trois skips, une requête HTTP ; retry/version/restart complet encore requis |
| Révision append-only/supersession | Reçu, c63fe22 | Deux requêtes après révision, une supersession/deux skips, quatre lignes dont trois courantes ; normalisation réelle encore absente |
| Construction invalide explicite | Reçu, b873f44 | `increment-2-qa-final.json/xml`, erreurs expurgées, pas de continue silencieux |
| Inventaire/schedules selon statuts | Reçu, b873f44 | 15 assets/six checks/six schedules mesurés ; NASA/WFP disabled et fixtures exclues, timezone business ; inventaire des connecteurs enregistrés seulement |
| Checks de provenance mesurés | Reçu, 27d4e0e | QA finale 107/douze et global 83312 verts, 787 backend/35 web/build ; check réel Dagster et reçu négatif relu, empty failed/0/0/NULL |
| Provenance bloque le refresh concerné | Partiel | Garde SQL Gold reçue R0.5 ; raccordement aval réel Dagster/Gold et durabilité restent requis, sentinel ne qualifie pas un refresh Gold |
| Schema drift bloque le refresh concerné | Non reçu | Détection/mesure/run/propagation/Gold encore à implémenter et vérifier |
| Silver normalize puis load | Reçu, 47dc4a8 | Decimal/référentiels/load raccordés ; QA 197/16 et Windows 99868 code 0/875 backend/35 web/build. SQL/S3 FMG/USD, retry/révision et seuil MiASA 5 % conservés ; références MiASA exclusivement synthétiques sans P-code, aucun backfill actif ; value_kind colonne/UI restent R2.1 |
| Partitions document/version/run | Non reçu | Batch/run source liés ; ledger/document/version/partition durable et rejeu après restart restent requis |
| Erreurs et DQ durables après rollback | Partiel | Wrapper caller et Mailpit reçus ; rollback caller peut perdre le run, assets directs à traiter |
| Runs visibles sans cache Gold | Reçu, 2d5b8ae | QA 207/18, deux scénarios SQL/API réels : cache absent/ancien, dernier run meta visible, freshness NULL et santé indisponible 503 sans refresh ; aucun autre indicateur DQ qualifié |
| Politique robots sans contournement | Partiel | Disabled/forbidden avant collecte et schedules reçus ; robots automatique BL-010 reste ouvert |
| Definition of Done complète | Non reçue | Incrément 5 committé 2d5b8ae, check Windows 44242 code 0 : 885 backend/35 web/build ; critères R0.6 restants non reçus, prototypes schema/Gold/ledger/robots indépendants non inclus |

R0.6 ne devient DONE que lorsque tous ses critères et le check global du
snapshot final sont reçus, documentés et committés. Aucun tag R0 avant R0.9.
Les checks source-cell ne remplacent pas une qualification de source ou de marché.
