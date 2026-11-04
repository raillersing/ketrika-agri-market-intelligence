# Réception R0.8 des ZIP WB originaux

Le lot3.0.0 rejoue uniquement les estimations nationales c_rice depuis2020,
explicitement gid_mdg_national_average/Market Average, jamais une agrégation ou
une copie régionale. Les autres marchés et variables du CSV sont hors de cette
portée : aucun rappel global R1 de99% ni une couverture de marché ne s'en déduit.
Tous les prix restent imputés, acteur inconnu, bruts conservés ; unité KG et
Rice(local) viennent du contexte du batch. Publié à une date inconnue reste
published_at=null, distinct du nom d'édition et du fetched_at vérifié.

## Destinations conservées

Le profil `docker/wb-archive-replay.compose.yml` utilise PostgreSQL uniquement par
socket, network=none, zéro port, et des volumes neufs WB du2026-11-04. Les volumes
Source/DB/S3 actifs sont exclus. Le paquet original est readonly, tout comme le
code et la copie Bronze pendant le rejeu. La préparation refuse une base déjà
initialisée et tout inventaire existant ; ne jamais la relancer sur ces volumes.
Pour une nouvelle réception, utiliser une copie du profil avec tous les noms de
volumes et conteneurs neufs, sans effacer les destinations de preuve présentes.

`ketrika_wb_replay_code_20261104` contient le code figé ; empreinte applicative
7d81deb9b8846d9a3bd1e64f843e493134cff2100ec859f6e0188158b66f68eb.
Les184 distributions installées correspondent au lock. La copie Bronze contient
les2 ZIP, le contexte JSON et un snapshot interne de références, quatre objets
adressés SHA et scellés, avec un inventaire vérifié à chaque lecture. Ce store
filesystem n'est pas une preuve du versionnement ou de la rétention d'un S3.

## Preuves exécutées

```sh
docker compose -f docker/wb-archive-replay.compose.yml up -d db
docker compose -f docker/wb-archive-replay.compose.yml run --rm prepare
docker compose -f docker/wb-archive-replay.compose.yml run --rm worker
```

Ces commandes documentent la réception déjà effectuée, pas une invitation à
écraser son état. Avant le rejeu et les recalculs, le dump privé a été conservé
sous `/tmp/ketrika-wb-before-replay-20261104.dump`. Les résultats natifs restent
sur `ketrika_wb_replay_output_20261104` ; copies complètes comprimées et vérificateur
sous docs/evidence et docs/diagnostics/verify_wb_reception.py. Tous les contrôles
Python doivent s'exécuter en Docker.

Résultat :81+82 lignes d'édition,163 conservées,81 anciennes reliées et82
courantes,0 rejet/revue. Les60 nombres annotés correspondent exactement aux
cellules SQL et originales. Deux consommations durables du même batch sont
idempotentes. Les compteurs n_fetched de ces runs décrivent des membres déjà
acquis, aucune nouvelle requête HTTP n'est exécutée par la préparation/reprise.

Rejeu non-root1000, lo seul et zéro route externe :3/3 SourceRecord,0 skip/rejet,
comptes et empreintes Silver/Gold/ref identiques, quatre Bronze inchangés. Les
UUID/temps techniques seuls suivent le mapping explicite de rebuild_manifest ;
valeurs, unités, périodes, provenances et liens ne sont jamais ignorés. Treize
caches Gold sont rafraîchis ; economic_dashboard demeure réservé et non reçu.

Le recalcul modèle/dataset est séparé : seuil36 intact, une série et3 prévisions
par exécution, deux résultats identiques. Convergence ARIMA avertie dans le log,
aucune performance de marché ou calibration scientifique qualifiée par ce test.

## Contre-épreuve indépendante

Un second cluster ketrika-wb-counter-db-20261104, socket/volume propres, reçoit le
dump d'avant rejeu. La première restauration transactionnelle a refusé le schéma
tiger préinitialisé par l'image et a rollback. La base système a été renommée
ketrika_wb_counter_system_template_20261104 et conservée ; destination neuve
créée depuis template0, puis restauration complète avec ACL et rôles connus,
sans lecture/copie de mot de passe. Aucun DROP/reset ni volume supprimé.

Le worker dédié, code/Bronze readonly, non-root et network=none, exécute
`docs/diagnostics/wb_archive_false_parser.py` : une seule ancienne valeur est
modifiée après parsing, puis supersédée. Gold courant seul ne peut la détecter.
Le comparateur complet refuse l'identité des contenus :163 lignes avant/après,
seul obs.price_observation diffère. Références et Bronze identiques. Le résultat
counterproof_passed=true signifie que la corruption a été détectée ; son
replay_passed=false ne doit jamais être présenté comme un rejeu positif.

Aucune activation des migrations sur l'actif, source fraîche, revue humaine,
original S3 ou modèle de marché ne découle de ces reçus. Le check complet sur le
commit stabilisé reste obligatoire avant intégration du code et clôture R0.8.
