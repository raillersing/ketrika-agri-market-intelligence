# Correction des faits affichés — plan avant implémentation

Base : 4b57562 ; branche fix/r08-safe-facts-20261025. Autorisation utilisateur du 25 octobre 2026. Parent R0.8, aucun gate aval anticipé.

1. AU-01 : remplacer les chiffres d'accueil par les réponses filtrées de prix et d'alertes ; afficher explicitement chargement, erreur, absence, nature et périmètre.
2. Réutiliser les référentiels API pour produits/lieux ; partager le produit par défaut ; aucune moyenne nationale de séries incompatibles.
3. Retirer la certification automatique des KPI dépourvus de preuve ; conserver les liens de provenance réels.
4. AU-02 : spécifier puis supprimer les valeurs météo de secours ; respecter zone/mois, variable, validité temporelle et source effective.
5. Corriger les dates SQL des anomalies et refuser les périodes invalides ; baseline et risque inconnus restent inconnus.
6. AU-03 : supprimer les entrées fictives des scénarios ; sélectionner exactement les calendriers et les arrivages persistés, sans catch-all SQL.
7. Ajouter les contre-exemples significatifs (base vide, mauvaise zone/date/variable/unité, erreur SQL, changement de filtre), dans Docker.
8. Geler le lot fonctionnel ; lint/types/tests ciblés puis un check complet et E2E SQL/S3 sur destination isolée ; conserver les originaux.
9. Mettre à jour AU/PROGRESS/miroir après réception seulement ; publier les limites restantes, sans qualifier source live ni modèle.

Statut : IN_PROGRESS. Les trois lots restent non reçus tant que leurs critères et la réception complète ne sont pas verts. Les autres lots AU-04–26 restent ordonnés par le plan correctif principal.

Précision après inspection : les moteurs d'offre exposent encore une confiance heuristique et les références calendaires ne sont pas documentées par un corpus reçu. Le premier correctif refuse donc leur publication opérationnelle (409) plutôt que produire un pic/calcul déclaré vérifié. Les moteurs hors ligne et leurs tests restent disponibles ; qualification et remise en service relèvent AU-18/20/21. Ce repli est explicitement spécifié dans ADR121/SPECS.

Développement : AU-01/02/03 IN_PROGRESS. Accueil et filtres raccordés aux lectures existantes ; null météo et sources effectives ; dates SQL liées et variable température distincte ; fin des24500tonnes/année2024/calendrier de secours. Les tests historiques qui attendaient ces faux résultats sont remplacés par assertions d'abstention du contrat ADR121 ; tests scientifiques des moteurs conservés.

Réception4405 du contenu7c42f24 :2411 succès/1 échec en1058,88s, aucun skip ; test_supply_api_endpoints attendait encore un pic de démonstration200 pour l'alias non canonique RICE. Les tests des moteurs ne changent pas ; le test de route vérifie désormais404 sans pic et422 sans campagne. Originaux JUnit/inventaire/couverture conservés gzip. Aucun frontend/global vert déduit.

Lot stabilisé élargi à AU-05 : les trois transports SMTP et Telegram ont leurs garde-fous ADR122 ;32 tests ciblés/20,56s et trois captures réelles Mailpit sur un réseau interne distinct, aucun tiers. Cette correction indépendante est regroupée avant la nouvelle réception complète, pour éviter une seconde livraison et un second check de sécurité séparés. AU-04/06/07 restent ouverts et n'entrent pas implicitement dans ce code.

Clôture logicielle :5400f39 reçu par18572 (2426/52/build16) et44716 (12 E2E), sonde27008 avec canvas942×340 et même empreinte applicative. AU-01/02/03/05 DONE logiciel, parent R0.8 IN_PROGRESS ; détails et limites dans RECEPTION.md. L'ajustement final de la sonde readonly et les documents ne modifient pas l'application.
