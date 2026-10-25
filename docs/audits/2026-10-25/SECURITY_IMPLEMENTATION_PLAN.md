# Lot de sécurité — plan avant correction

Base7c42f24 ; worktree r08-security-20261025, séparé du check des faits affichés. Parent R0.8 ; aucun changement de source ou destination de ce check.

1. AU-04 : matrice exhaustive des routes/rôles ; authentifier côté serveur, vérifier la session côté web, prévoir révocation SQL partagée/expirable et refus des secrets de démonstration en production, avant migration additive et code.
2. AU-05, indépendant : inventorier tous transports ; autoriser uniquement la capture Mailpit du réseau local en dev/test ; refuser SMTP externe et Telegram avant toute construction du transport, même avec EXTERNAL_SEND_ENABLED=1.
3. Verrouiller aussi l'aperçu de bulletin ; garder les brouillons et ne journaliser ni adresse ni token ; ne déclarer envoyé qu'après acceptation du vrai transport local.
4. AU-06 : avis mainteneurs/relevé des locks, mise à jour reçue ; ADR/SPECS avant majeure. Next14 nécessite migration vers une ligne maintenue, pas seulement un ancien patch14.2.25.
5. AU-07 : manifeste et checksum obligatoires, outil absent refusé, clone neuf consenti/identifié, aucun overwrite/termination de base existante et tout pg_restore non-zéro fatal.
6. Développement isolé : tests négatifs sans réseau, vrai Mailpit interne distinct ; aucun accès mutant à main-final pendant son check, ni aux services actifs.
7. Regrouper les changements stabilisés pour leur propre check complet/SQL/E2E et scan ; états AU/R et documents mis à jour seulement avec leurs preuves, sans qualification de déploiement ni envoi externe.

Statut : préparation AU-04/06/07 ; AU-05 IN_PROGRESS, correction indépendante en premier pendant la réception du lot précédent. Contrat de notification ADR122/SPECS enregistré avant son code. L'authentification durable et le contrat de restauration seront précisés avant leurs propres modifications, pas déduits de ce mini-plan.

Source primaire relue le25 octobre2026 : https://nextjs.org/blog/nextjs-security-update-october-14-2026 (HTTP200), annonce Next15.5.28/16.4.1 ; vérifier encore registry/avis au moment du verrouillage. Ce document ne change aucune version.
