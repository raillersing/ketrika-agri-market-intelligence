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

Réception complète du lot stabilisé avant intégration applicative main ; contexte
structurel et chemin Silver natif à finaliser, qualification du rejeu et révisions
réelles, puis suite R0–R6. Aucune prévision, fraîcheur de marché, revue humaine ou
performance du modèle fournisseur déduite de cet aperçu.
