# Aperçu minimal des prix historiques

Tranche locale expérimentale R0.8 / ADR-071. Ce n'est ni le dashboard de
production, ni une réception R0.8, ni une source de prix actuels.

## Résultat disponible

- Page : http://localhost:18877
- JSON et provenance : http://localhost:18877/api/prices
- 15 estimations mensuelles du riz local à Alakamisy, mai 2010 à juillet 2011.
- Source : paquet officiel Banque mondiale acquis le 15 octobre 2026 ; date de
  collecte récente ne signifie pas prix récent. Valeurs `c_rice` imputées,
  acteur inconnu, données non validées pour une décision actuelle.
- Les lieux non résolus restent `pending` ; aucun alias inventé pour publier Gold.

## Isolation et persistance

Projet `ketrika-price-preview`, trois volumes nommés dédiés datés 20261015,
PostgreSQL `network_mode: none`, accès par socket Unix. HTTP publié uniquement
sur `127.0.0.1:18877`. Aucun service existant n'est arrêté ni migré.

La préparation crée seulement une nouvelle destination vide, conserve les deux
objets par SHA256, inscrit les SourceRecords et le batch immuable, vérifie les
cellules puis charge et audite les observations dans la même transaction.
Les consultations SQL utilisent `SET TRANSACTION READ ONLY`. Le redémarrage du
serveur ne lance jamais la préparation et ne réimporte aucune donnée.

Depuis le worktree Linux de développement (commandes Docker uniquement) :

```sh
docker compose -f docker-compose.price-preview.yml up -d --wait db
# Une seule fois, sur destination neuve et paquet attendu disponible :
docker compose -f docker-compose.price-preview.yml run prepare
docker compose -f docker-compose.price-preview.yml up -d web
# Relecture sans import :
docker compose -f docker-compose.price-preview.yml exec web /app/.venv/bin/python /workspace/backend/scripts/price_preview.py report
```

Le paquet est monté readonly depuis `/tmp/ketrika-r08-modeled-packet` et ses deux
SHA sont épinglés dans le préparateur ; aucune URL fournie par un contenu n'est
suivie. L'original reste dans le conteneur d'acquisition
`ketrika-r08-wb-modeled-c1-20261015:/out/wb-c1-20261015T160306Z` et le volume
d'acquisition conservé. Restaurer les octets avec `docker cp` si nécessaire,
jamais les fabriquer ou remplacer un objet existant. La licence et les termes
additionnels WB sont documentés dans le corpus acquis précédemment.

## Vérifications effectuées en développement

Préparation réelle PostgreSQL code 0 ; SQL : 15 lignes, toutes imputées et pending,
deux membres du batch. Navigateur Chromium : HTTP200, 15 lignes, 15 après reload,
JSON15, viewport390x844, zéro erreur JavaScript. Copie Bronze readonly au serveur.
Les tests et la réception complète restent des preuves distinctes de l'aperçu.

## Suite du plan inchangé

### Rejeu du clone vérifié le 2026-10-15

Le serveur de consultation n'est jamais la destination de rejeu. Une autre instance
PostgreSQL sans réseau, `ketrika-price-replay-db-20261015`, utilise ses propres
volumes `ketrika_price_replay_pgdata_20261015` et `..._socket_20261015`.
Copier uniquement les six schémas applicatifs avec `pg_dump --no-owner
--no-privileges --schema=meta --schema=ref --schema=obs --schema=ml --schema=ops
--schema=gold`, vers une base neuve de cette instance uniquement.

Préconditions du clone : mêmes extensions PostgreSQL que la source (notamment
pg_trgm, pgcrypto, unaccent, uuid-ossp, PostGIS), rôles locaux NOLOGIN
ketrika_app et copilot_ro pour les GRANT Gold. Les rôles sont des objets cluster
non inclus dans pg_dump. L'essai initial de restauration a été conservé par
renommage, aucune donnée existante effacée. Ne pas restaurer les schémas tiger
déjà fournis par l'image PostGIS.

Le worker `backend/scripts/replay_price_preview.py` exige network=none,
la destination socket dédiée et exactement deux SourceRecords WB. Monter la
copie `/copy` readonly, le socket du clone, et un volume de rapports `/out` neuf.
Le script initialise les vues du clone, reconstruit réellement Silver/Gold et
écrit un nouveau rapport UUID sans écraser les précédents.

Résultat1064 FINAL0 : deux SourceRecords rejoués, quinze prix insérés, zéro
document ignoré/rejeté et dix-neuf manifestes identiques. Gold prix reste vide car
les quinze lieux sont pending ; aucune qualification Gold implicite. Les révisions
historiques réelles et la performance modèle ne sont pas prouvées par cet essai.
Rapports originaux sous `docs/evidence/R0.8-authentic-price-replay*.json`.

Réception complète du lot stabilisé avant intégration applicative main ; contexte
structurel et chemin Silver natif à finaliser, qualification du rejeu et révisions
réelles, puis suite R0–R6. Aucune prévision, fraîcheur de marché, revue humaine ou
performance du modèle fournisseur déduite de cet aperçu.
