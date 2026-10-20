# Collecter les sources publiques en un clic

Connectez-vous comme administrateur, ouvrez Sources puis « Collecter les nouvelles
données ». « Collecter » sur une carte ne lance que ce connecteur. Les boutons
sont désactivés pour les sources sans connecteur autorisé ou lorsqu'une opération
est déjà en cours. « Recalculer les indicateurs » ne télécharge rien.

Le suivi décrit l'étape réellement exécutée : téléchargement, intégration,
publication. Il est enregistré dans PostgreSQL et relu après rechargement.
Les documents nouveaux, les enregistrements intégrés/révisés et les sources
abouties sont comptés séparément. Zéro document nouveau est possible.
Une collecte peut durer plusieurs minutes ; aucune promesse de fraîcheur globale.
La Banque mondiale est bornée à15 estimations c_rice avec contexte d'étude,
pas l'intégralité des prix ni des cours observés en temps réel.

Une source en échec ne bloque pas les autres. Le statut de publication est
distinct : les données peuvent être archivées/intégrées sans publication Gold
si les gardes de qualité/provenance la refusent. Les bulletins, prévisions et
alertes externes ne sont pas régénérés/envoyés par cette action.

## Réponse perdue ou interruption

Ne cliquez pas répétitivement : rechargez Sources et consultez le reçu SQL.
Une interruption est constatée quand le propriétaire SQL a disparu. Aucun
rejeu réseau automatique, aucune affirmation qu'aucune requête n'a été émise.
Les ingestion_run et objets Bronze déjà produits restent conservés. Une nouvelle
collecte explicite après diagnostic est une nouvelle demande, soumise aux quotas.

## Contrat technique

- POST /v1/sources/collect : administrateur, `{request_id: UUID, source_id?: string}`.
- GET /v1/sources/collections : dix derniers reçus, authentification obligatoire.
- GET /v1/sources/collections/{id} : reçu exact, authentification obligatoire.
- GET /v1/sources/collection-options : IDs actuellement éligibles.
- UUID identique/sélection identique : reçu existant, aucune nouvelle émission.
- UUID réutilisé pour autre sélection, source interdite ou propriétaire actif :409.
- Migration additive0017 requise après0016 avant activation ; aucune table runtime créée.

Exécution HTTP synchrone, pas une file de tâches redémarrable. Le verrou
transactionnel global protège aussi le recalcul. Le suivi utilise des connexions
distinctes ; ne pas imposer un pool d'une seule connexion. En cas d'indisponibilité
du stockage, aucun succès n'est annoncé. Déployer via la procédure de migration
habituelle, sans reset ni effacement de volumes.
