# HTTP : admission durable et arrêt (ADR-063)

Statut : implémentation en qualification, pas une qualification de source live.

## Déploiement

Appliquer les migrations via le runner normal dans la destination explicitement
autorisée. La migration 0010 ajoute uniquement les trois tables de garde HTTP.
Le client ne crée jamais de table. Si migration, connexion ou droits manquent,
PolicyStop refuse avant réseau ; aucun repli mémoire implicite.
Dans ce lot, migration et tests se limitent au profil de qualification dédié.

## Admission

authorize_collection lie source_id, daily_request_budget et max_rps du registre
au vrai client avant discovery. Les fixtures autorisées suivent le même chemin.
Chaque émission (robots, retry, redirect) consomme une réservation source et
hostname dans une transaction indépendante et réserve un créneau partagé.
Le domaine est limité à 500/jour et au minimum des limites rencontrées.
Jour UTC, pacing conservé au changement de jour. Une baisse de plafond
n'efface pas le compteur ; une réservation après crash n'est pas remboursée.
L'attente se fait hors transaction, puis arrêt/offline sont recontrôlés.

## Robots, redirects et retries

Cache 24 h par origin exact ; pas de partage HTTP/HTTPS ni de ports.
Règles absentes/expirées : acquisition contrôlée ; 404/410 permettent,
autres erreurs refusent sans désactivation permanente.
Chaque redirect est manuel, plafond dix ; pas de flow auth HTTPX.
Credentials, cookies et conditions cross-origin sont retirés après fusion
des defaults et cookie jar, identité bot réinjectée.
Retries réseau/429/502/503/504 : quatre tentatives maximum par exécution.
Retry-After entier ou date HTTP, aucun délai anticipé ; au-delà de 300 s
refus temporaire, pas de disabled. Aucun retry d'un challenge/401/403.
304 sans référence d'artefact connue refuse avant écriture Bronze ; le suivi
durable ETag et la résolution de la référence connue appartiennent à R1.2.

## Incidents

meta.http_policy_stop conserve des codes fixes, sans corps collecté ni secret.
Un arrêt source/origin est indépendant de la transaction métier. Si la ligne
meta.source est verrouillée, le journal reste autorité de refus même après
rollback, sans attente sur cette ligne. Aucun rétablissement automatique :
ne supprimer ni modifier l'historique des arrêts.
Le backend mémoire est une injection explicite pour transports inertes, pas
une preuve de durabilité ni un mécanisme de déploiement.
