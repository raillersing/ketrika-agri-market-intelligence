# Irooa — démonstration investisseurs en 4 minutes

Préparation du26 octobre2026. Prototype local, données et modèles en requalification. Aucun rendez-vous, investisseur ou engagement commercial n'a été vérifié.

**Meeting source:** User-supplied meeting identity; not Calendar-verified — demande de démonstration investisseurs, date et participants non précisés.

## Objectif

Montrer un prototype fonctionnel et obtenir un retour sur un premier pilote métier. Le parcours ne constitue ni une preuve de traction commerciale, ni une validation de prévisions, ni une recommandation d'achat agricole.

## Ouvrir la démonstration

- Interface : [http://localhost:3006](http://localhost:3006).
- Écran d'accueil : [http://localhost:3006/](http://localhost:3006/).
- Support visuel local : ouvrir `demo.html` dans ce dossier. Les captures constituent un secours daté si la connexion ou le premier chargement échoue ; elles ne sont pas des données temps réel.

Utiliser le compte de démonstration local déjà configuré. Ne pas diffuser son accès ni ouvrir les services internes sur Internet. Pour une présentation distante, partager l'écran de ce poste.

## Fil conducteur

> Comprendre une série de prix vivriers, voir exactement ce qu'elle représente, puis transformer le prototype en un pilote métier mesurable.

Le parcours est fondé sur l'interface réellement accessible : accueil, graphique, tableau des derniers points, dates, unité, zone et mention « Imputé ». La provenance complète et les modèles restent en requalification ; la mention « Provenance non liée » ne doit pas être masquée.

## Déroulé proposé — 4 minutes

1. **0:00–0:35 — Le besoin.** « Irooa vise à rendre les informations sur les marchés vivriers de Madagascar plus faciles à comprendre et à utiliser. Nous construisons un espace commun pour examiner les prix et leurs limites. » Ouvrir l'accueil.
2. **0:35–1:40 — Le prototype en action.** Montrer le riz blanc local, la zone et la série affichée. « Le graphique et les dernières valeurs viennent de l'API du prototype. L'unité, la date et le périmètre restent visibles. » Ne pas présenter le dernier point affiché comme un cours observé national.
3. **1:40–2:50 — La bonne lecture des données.** Faire défiler le tableau des derniers points sur l’accueil. Montrer le badge « Imputé » et les informations de source disponibles. « Les valeurs de cette démonstration sont estimées. Notre objectif est de rendre explicite la différence entre observation, estimation et prévision. La chaîne de provenance complète est encore en cours de qualification. » Un filtre sans données est un résultat à expliquer, pas à remplir artificiellement.
4. **2:50–4:00 — Le prochain jalon.** « La prochaine étape est un pilote délimité avec un partenaire métier, des sources autorisées, une qualité mesurée et un usage testé. » Proposition de question : « Quel premier cas d'usage souhaiteriez-vous valider avec nous : veille acheteur ou suivi institutionnel ? » Ce sont des pistes, pas des clients acquis.

## À présenter comme vision, pas comme résultat acquis

Prévisions de marché validées, précision prédictive, alertes opérationnelles, couverture nationale, traçabilité100%, volumes/stocks, clients payants, revenus et gains de temps ne sont pas démontrés dans ce parcours. Ne pas inventer de métrique, de témoignage, de taille de marché ou de montant de levée.

## Avant le rendez-vous

Utiliser le support capturé pour la présentation immédiate. L’application directe reste complémentaire : les essais répétés ont montré des chargements irréguliers. Ouvrir l’accueil en avance, se connecter et vérifier que le graphique est chargé. Prévoir le support capturé : la première navigation peut compiler les pages de développement et être lente. Garder les écrans administratifs, la collecte, les recalculs et les envois hors du parcours de présentation.

## Points encore à préciser

Profil des investisseurs, date, durée disponible, cas d'usage pilote et éventuel objectif de financement. Ces informations permettraient d'adapter le récit ; elles ne sont pas nécessaires pour cette première démonstration produit.

## Preuves et limites

La capture montre le nouvel aperçu Irooa : menus réorganisés et palette inspirée d’irooa.com, sur un frontend séparé au port3006. Le backend reste celui du lot de données sûres5400f39. Les nouveaux lots d'authentification/dépendances/restauration sont reçus séparément : ne pas les annoncer comme actifs dans cette démo. Le parcours montre l’accueil, son graphique réel et son tableau. L’explorateur, les prévisions et les pages administratives restent hors du parcours. Aucun nouvel objet métier, collecte ou envoi externe n'est créé pour rendre le parcours plus convaincant.

La page publique [À propos](http://localhost:3006/about) présente Irooa et son entreprise mère Ketrikay, anciennement Ketrikai. Le bouton soleil/lune permet de présenter les thèmes clair et sombre.
