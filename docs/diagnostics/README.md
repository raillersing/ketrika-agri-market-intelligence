# Diagnostic readonly des rôles SQL

`sql_role_audit.py` vérifie les métadonnées effectives de `ketrika_app` et
`copilot_ro` sur la base explicitement sélectionnée par `DATABASE_URL`. Il ne
contient ni migration, GRANT, réparation, lecture de ligne métier ou accès S3.
Exécution Python exclusivement dans un conteneur outils existant avec SQLAlchemy
et psycopg reçus ; ne pas installer de dépendance sur l'hôte.

Après copie du fichier dans ce conteneur et configuration explicite de sa
connexion, exécuter `python /tmp/sql_role_audit.py` avec son Python reçu.
Ne jamais mettre de mot de passe dans une commande versionnée ou un rapport.
Codes : 0 profil conforme aux contrôles décrits, 1 écarts exportés, 2 contrôle
impossible (seule la classe d'erreur est exportée). Les erreurs de connexion et
paramètres SQL ne sont pas imprimés. Aucun mécanisme de correction automatique.

La transaction est REPEATABLE READ READ ONLY, avec statement_timeout local5s.
Inventaire de huit schémas, maximum1024 tables/vues et1024 séquences par rôle ;
un dépassement refuse le contrôle. Les permissions `has_*_privilege` incluent
PUBLIC et l'héritage ; les appartenances directes imposent une revue explicite.
Le diagnostic relève les rôles élevés, droits CREATE de schéma, absence d'USAGE,
accès applicatifs requis et permissions du registre de révocation ; Gold reste
SELECT seulement pour les deux rôles, le copilote ne reçoit aucun droit sur
les autres schémas ou séquences. Le réglage explicite statement_timeout5s du
copilote tient compte de la priorité du réglage par base sur celui du rôle.
Seul ce paramètre est lu, jamais rolpassword ou des configurations arbitraires.

Ce rapport de métadonnées n'est pas un essai de connexion sous chaque rôle,
un contrôle exhaustif de RLS/fonctions/extensions, une preuve d'authentification,
un workflow applicatif ou une autorisation de déployer. Des droits de table
sans USAGE restent des droits latents à examiner, pas un accès effectif affirmé.
La liste de permissions applicatives requises est une vérification minimale,
pas une certification de chaque opération métier. Les refus restent visibles.

`test_sql_role_audit.py` utilise unittest et une nouvelle instance PostgreSQL
sans ports publiée, sur réseau interne et volume dédiés. Il exige
AUDIT_TEST_DATABASE_URL pointant vers `ketrika_role_audit_20261029` et crée ses
rôles, schémas et tables de fixture : ne jamais le lancer sur l'actif, un clone
historique ou une autre destination partagée. Absence de SQL = erreur, aucun
skip. Les GRANT/REVOKE des seuls tests restent dans cette fixture isolée.
Les essais positifs synthétiques ne qualifient aucune donnée de marché.

## Témoin de transport ODR

`transport_witness.py` enveloppe le transport déjà borné du diagnostic ODR :
aucune relance, requête, politique, identité ou admission supplémentaire.
Il conserve au maximum dix tentatives et seulement leur heure UTC, phase,
code HTTP éventuel et classe d'erreur. Aucun message d'exception, URL, en-tête,
cookie, identifiant ou corps n'entre dans ce témoin. Une erreur de lecture après
réception des en-têtes reste distincte d'un téléchargement complet ; elle se
propage au caller. Les réponses préchargées sont également prises en compte.

`odr_candidates.py` est une nouvelle copie instrumentée du diagnostic ADR144 ;
le script et les rapports historiques dans evidence restent inchangés.
Le probe exige la base dédiée historique `ketrika_corpus_discovery_20261028`,
son compteur source original du 29 octobre (10/10), puis le contrôle natif des
arrêts source/origine avant tout appel réseau. Il ne recrée pas le laboratoire,
ne réactive aucune source et ne remet aucun quota à zéro. Le report inclut les
tentatives de transport ; ses documents restent non qualifiés et hors Silver.
L'emplacement de sortie est exclusif : conserver une tentative existante.

Au 2026-11-03 le conteneur et le volume de ce laboratoire ne sont plus présents
dans Docker Desktop ; aucune nouvelle tentative ODR n'est exécutée. Rétablir
le laboratoire avec son registre durable original et vérifier ses arrêts avant
usage ; à défaut fournir les deux éditions publiques autorisées décrites dans
HANDOFF. Un changement de date ne suffit pas à reconstruire un registre perdu.

Vérification locale dans Docker : `python -m unittest -v test_transport_witness`
depuis le répertoire des diagnostics ; cinq tests offline, dont trois classes
d'erreur de connexion/timeout, flux interrompu, succès et borne de tentatives.
Ce sont des tests du diagnostic, aucune preuve de collecte réelle.
