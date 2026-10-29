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
