# AU-07 — plan avant correction

Parent R0.8, branche fix/r08-restore-20261026, base2a6ec4e. Travaux indépendants pendant le check AU-04 ; aucune mutation de sa source, de sa QA ou de l'actif. AU-06 reste ouvert : sa reconstruction des images est différée jusqu'à libération du check.

1. ADR124/SPECS : clone neuf explicitement consenti, aucun override actif, manifeste/checksum/catalogue obligatoires et tout statut non zéro fatal.
2. Corriger les helpers : absence d'outil/manifeste refusée, hash/taille/nom/source vérifiés, erreurs SQL jamais remplacées par un zéro, identifiants de table bornés.
3. Remplacer restore.sh : nom ketrika_restore_*, confirmation exacte, outils présents, validation intégrale avant CREATE, refus de toute DB existante, restauration transactionnelle sans clean ni terminaison de connexion.
4. Aligner backup.sh : manifeste JSON échappé, alias latest cohérent ; ne pas changer la rétention ni appeler Restic pendant les tests.
5. Tests négatifs de vrais processus shell avec faux outils locaux : défauts de preuve, cible existante/active/invalide, pg_restore1, SQL1, aucune fausse réussite ni requête destructive.
6. Après libération QA : vraie sauvegarde/restauration uniquement sur PostgreSQL distinct neuf, comparaison de tables, échec réel préservé ; aucun volume Bronze impliqué.
7. Regrouper le lot stable pour check complet/E2E applicable avant main ; AU-07 reste IN_PROGRESS jusqu'à réception, R6.8 non qualifié par ces réparations seules.
