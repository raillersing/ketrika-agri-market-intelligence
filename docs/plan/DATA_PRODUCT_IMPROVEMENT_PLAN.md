# Irooa — plan de correction des données et des parcours

Date : 27 octobre 2026. Statut : PLANNED, aucune implémentation par ce document.
Demande utilisateur : planifier les corrections à partir de la recherche du27 octobre.
Base documentaire : f947f33, recherche et requêtes en annexe. Les lots ci-dessous
détaillent les AU existants ; ils ne créent pas de nouvelles tâches R, ne modifient
pas les74 statuts et ne lèvent aucun gate humain.

Liens : [plan correctif AU](../audits/2026-10-25/CORRECTIVE_EXECUTION_PLAN.md),
[programme R](MARKET_INTELLIGENCE_EXECUTION_PLAN.md), [progression](PROGRESS.md),
[recherche](../evidence/data-product-research-20261027/RESEARCH.md),
[requêtes SQL](../evidence/data-product-research-20261027/profile-readonly.sql),
[résultats SQL](../evidence/data-product-research-20261027/profile-readonly.txt),
[profil géographique](../evidence/data-product-research-20261027/geometry-profile.json).

## Résultat attendu

Un utilisateur sait quels produits et territoires ont des données, comprend le
stade de vente et la nature des valeurs, consulte une vraie carte et des indicateurs
économiques traçables, puis lit des alertes et bulletins qui expliquent leur utilité.
Les prévisions restent une capacité distincte, évaluée et publiable seulement si
ses critères sont remplis. Aucune promesse de couverture de tous les PPN.

## Ordre et rattachement au programme

| Lot | Priorité | Résultat | Rattachement | Dépendances de démarrage applicatif |
|---|---|---|---|---|
| DP-0 | P0 | État des preuves et périmètre de livraison fiables | R0.8, AU-04/06/07/25 | Aucune ; diagnostic documentaire |
| DP-1 | P0 | Filtres et écrans existants compréhensibles et honnêtes | Correctif R0.8, prolongement borné AU-01, présentations AU-13/23 | DP-0 ; aucune nouvelle collecte ou capacité aval |
| DP-2 | P1 | Données de test isolées, référentiels et lignée réparés | AU-08/09, R0.8/R0.9 | AU-07 reçu avant clone ; contrats ADR/SPECS |
| DP-3 | P1 | Collectes autorisées, réelles et suivies | AU-10/11 et parties collecte AU-12 | R0.9 reçu, puis dépendances R1 exactes |
| DP-4 | P1 | Couverture exploitable et économie alimentée par dimension | AU-12/13 | DP-2/3, prérequis R2 exacts |
| DP-5 | P1 | Carte géographique réelle et comparable | AU-10/13, R1.10/R2.10/R2.11 | Référentiel géographique reçu, DP-4 et R2.9 selon AU-13 |
| DP-6 | P1 | Alertes et bulletins lisibles et explicatifs | AU-23 ; questions métier AU-22 | AU-05 et capacités/données reçues selon R6.5/R6.6 |
| DP-7 | P1 | Analyse, prévisions et scénarios évalués | AU-14/15/16, AU-22 ; AU-17/18/20/21 si requis | Données/contrats R2 reçus, puis dépendances R3/R4/R5 exactes |

L'ordre de lecture est une priorité produit, pas une permission de sauter les gates.
DP-5 et DP-6 n'attendent pas les prévisions pour offrir une lecture descriptive si
leurs dépendances propres sont reçues. DP-1 ne lance ni AU-10 ni de nouvelle
fonctionnalité de collecte avant R0.9. Les compétences nommées sont fonctionnelles,
sans délégation automatique ; exécution successive par propriétaire identifié.

## DP-0 — Vérifier la base avant de poursuivre

- Relever branches, ressources en cours et version réellement servie ; conserver
  les modifications concurrentes et les sources runtime en lecture seule.
- Le document de réception f947f33 annonce un gel cd77a26. Les originaux consultés
  rattachent pourtant backend et frontend à4e455ed/cf7cf73d..., et navigateur19/19
  àcd77a26/79205eca.... Conserver les deux preuves, décrire le delta de tests et
  ne pas appeler cet ensemble un check complet unique de cd77a26.
- Les statuts déjà déclarés DONE ne sont pas réécrits par ce plan. Réconcilier leur
  portée documentaire avant réutilisation. Si du code ou le chemin des tests change,
  recevoir le prochain lot stabilisé avec un check complet exact ; pas de check
  de base supplémentaire juste avant celui du nouveau lot.
- Documenter les délais du parcours navigateur portés à240s et les échauffements ;
  cette attente de compilation n'est pas une preuve de rapidité de l'application.
  Préserver séparément le benchmark API P95<1000ms et les délais normatifs applicables.
- Distinguer source reçue, intégration main, activation et usage humain. Préparer
  la livraison de DP-1 avec sauvegarde/essai clone pour toute migration additive,
  et vérification des jobs avant remplacement ciblé API/web/Dagster.
- Critère : chaque résultat porte son vrai SHA/empreinte/images ; version active
  connue ; aucun succès ancien réétiqueté, aucun service partagé arrêté inutilement.

## DP-1 — Corriger la lecture des écrans existants

Périmètre borné : affichage et consommation des contrats existants, sans suppression
de données, fusion de produits ou nouvel endpoint. Toute extension passe en DP-2/4.

- Renommer « Niveau d'acteur » en « Stade de vente » avec aide courte : producteur,
  gros, détail, non renseigné. Préserver les codes reçus ; unknown ne devient jamais
  retail ; farmgate/producer sont expliqués sans migration implicite. Un prix
  réglementé n'est pas assimilé à une vente observée.
- Exclure des choix métier les références DQ identifiées par une classification
  explicite et testée, pas par une suppression SQL ni par verified=true. Le nettoyage
  durable et la classification versionnée appartiennent à DP-2.
- Retirer les filtres redondants ou sans effet ; liste de filtres par page réellement
  consommés. Économie nationale sans filtre produit/acteur inopérant ; prix utilise
  produit/zone/stade et période du contrat existant. Une sélection inconnue n'est
  jamais silencieusement remplacée par du riz ou Antananarivo.
- Afficher absence, données non qualifiées, panne et valeur zéro distinctement.
  Conserver un message honnête pour les produits sans série. Les disponibilités
  globales nécessitant un nouveau calcul/API sont réservées à DP-4.
- Nommer « points de prix » ou « estimations » les séries imputées ; ne pas appeler
  ces valeurs observations terrain. Garder les périodes manquantes visibles.
- Présenter la vue régionale actuelle comme tableau en attendant DP-5 ; retirer
  les affirmations constantes sur les corridors et le surcoût25% non calculé.
- Traduire les sévérités et statuts existants des alertes, montrer leur portée/date,
  garder le JSON dans un détail technique secondaire. Bulletin : retirer les
  certifications et mentions « officiel » non justifiées ; afficher période/statut.
- Préserver l'identité Irooa/Ketrikay, les thèmes irooa.com et les accès existants.
- Critères : aucune référence DQ dans un choix métier, aucun filtre visible sans
  effet annoncé, unknown lisible ; prix/tableau/export concordants quand disponibles ;
  états vides/erreur et reload vérifiés ; clavier,320/390px, texte200%, clair/sombre.

## DP-2 — Assainir sans effacer l'histoire

- Sur clone SQL/S3 distinct : inventorier données de test, auto-liens, références
  Bronze absentes, doublons et usages avant toute réparation ; conserver originaux,
  sommes de contrôle et valeurs brutes. Les comptes du diagnostic ne sont pas figés
  comme compteurs attendus après une évolution légitime de la base.
- Définir avant code la quarantaine append-only, les permissions, les exclusions de
  publication et la réparation exceptionnelle des liens. Respecter le trigger actuel
  interdisant la modification des supersessions ; aucun contournement global.
- Définir un produit canonique et des alias versionnés. Ne pas fusionner aveuglément
  riz local/importé/paddy, farine et grain, qualités ou unités. Les correspondances
  incertaines restent en revue ; le drapeau verified actuel ne suffit pas.
- Vérifier que les suites de test ne créent plus de références dans une base métier.
  Préserver et expliquer les références historiques DQ plutôt que les supprimer.
- Recevoir AU-09 avec vraies éditions corrigées, rejouées hors réseau sur destination
  dédiée. Si les éditions manquent, consigner l'absence et travailler les tâches
  indépendantes ; ne pas inventer une correction ou un artefact Bronze.
- Critères : archive inchangée, diff métier/audit explicable, aucun auto-lien publié,
  pas de republication d'une ancienne ligne, réparation idempotente et droits vérifiés.

## DP-3 — Alimenter le catalogue et les sources réelles

- Réutiliser les connecteurs existants. Priorité aux API/export CSV/XLSX, puis HTML,
  puis PDF/navigateur si nécessaire ; choisir le format par source, pas une nouvelle
  pile générale de scraping. Extraction LLM en repli avec preuve et revue.
- Pour chaque source : vérifier droits/robots/URL réelle/édition/version, cadence,
  limites de débit et budget ; cache et revalidation, reprise bornée, hash et archive
  immuable. Une source disabled reste arrêtée ; import humain d'une édition autorisée
  possible avec origine et preuve, sans contournement de challenge.
- Priorité métier : prix vivriers autorisés et couverture vérifiée ; OMH carburants ;
  BFM change officiel ; INSTAT IPC ; Douanes commerce. Ajuster cette priorité au premier
  trajet réellement autorisé ; aucune source supposée acquise par son nom « active ».
- RTFP : contrôler la disponibilité pays/marché des produits supplémentaires riz,
  sucre et farine ; conserver le statut estimé. WFP/FAO/RTFP ne sont pas comptés comme
  trois confirmations indépendantes quand ils partagent les mêmes observations.
- Journal par acquisition : résultat reçu/vide/refusé/échoué, compte, dernière édition,
  période couverte, prochaine échéance attendue et raison de blocage, relisible après
  restart. Pas de notification réelle vers un tiers.
- Critères par source : vrai document→Bronze→parse→SQL→API, preuve de cellule,
  découverte/révision et idempotence, reprise après incident ; fixtures distinctes des
  sources live. Étendre les produits seulement après un trajet prouvé, pas en créant
  des lignes pour remplir les filtres.

## DP-4 — Couverture, filtres disponibles et économie

- Avant code, spécifier les contrats de disponibilité : produit×zone×stade×période,
  unité/qualité/fréquence et nature des valeurs. Réutiliser la couverture existante
  lorsqu'elle répond réellement au besoin ; sinon ADR et API/schéma explicites.
- Une option produit indique série disponible/période ou absence ; la sélection
  active valide reste visible. Afficher les autres produits métier comme indisponibles
  avec explication/action de collecte adaptée ; ne pas confondre catalogue et couverture.
- Une courbe représente une série homogène :produit/qualité/zone/stade/unité.
  Toute agrégation multi-zone doit être définie, pondérée si nécessaire et expliquée ;
  ne pas relier des prix de marchés différents comme une même évolution temporelle.
- Macro par dimension : IPC/base et variations INSTAT ; change officiel BFM avec sens
  de cotation ; prix administrés OMH/date d'effet ; importations Douanes valeur/masse
  et période ; activité réelle lorsque corpus reçu. IPC n'est pas un prix en MGA/kg.
- Qualifier le chemin source/cellule et le calcul avant d'ouvrir la publication Gold.
  Le refus macro_publication_not_qualified reste jusqu'à réception du remplacement.
  Une publication partielle par dimension exige contrat/ADR et preuve ; elle ne
  clôt pas le gate économique si une dimension requise manque.
- Examiner aussi les noms/champs DTO consommés par le frontend, pas seulement les
  tableaux SQL ; chaque indicateur expose unité/base/date/source et raison d'absence.
- Critères : calculs indépendants des variations, pas de moyenne de prix incompatible,
  aucune substitution de taux parallèle en taux officiel ; filtres/API/SQL/CSV/reload
  concordants ; disponibilité partielle explicite et aucun faux zéro.
- Questions de réception du pilote descriptif DP-4/5 :quels produits ont des données
  pour cette zone ? À quelle période, quel stade et de quelle nature ? Quelle variation
  est calculable ? Quels écarts territoriaux sont comparables ? Quels indicateurs
  économiques qualifiés éclairent le cas ? « Non calculable » reste une réponse
  légitime assortie d'une raison, pas un échec caché par une valeur de repli.

## DP-5 — Carte géographique qualifiée

- Acquérir des contours authentiques réutilisables et versionnés ; vérifier le
  découpage applicable, codes, dates, licence et attribution. Les23 rectangles locaux
  ne sont ni une preuve ni une base acceptable à présenter comme contour officiel.
- Raccorder les géométries à un moteur existant adapté ; MapLibre est déjà dépendance,
  aucune nouvelle bibliothèque sans justification/ADR. Versionner les fichiers reçus.
- Jointure par code validé, aucune coordonnée ou affectation régionale de repli.
  Une localisation non résolue reste visible comme telle, avec compte exclu expliqué.
- Dessiner les contours même sans prix, zones sans données grises, légende explicite,
  période commune et unité/stade/nature comparables. Ne pas mélanger les derniers mois
  différents des régions comme s'ils étaient simultanés. Table accessible de secours.
- Critères : vraies formes visibles, clic/clavier→série/source, sélection et reload,
  correspondance des codes et agrégats, attribution, desktop/mobile/thèmes ; aucun
  diagnostic de stock, marge ou coût logistique déduit du seul écart de prix.

## DP-6 — Alertes et bulletins orientés décision

- Une carte d'alerte répond à quoi/où/période/importance/raison et comparaison/action
  de vérification possible. Mini-série et accès progressif aux sources ; afficher
  méthode/couverture et si un facteur est mesuré, supposé ou inconnu.
- Séparer alerte marché, qualité et panne de collecte. « Aucune détectée » est distinct
  de surveillance inactive, données insuffisantes et calcul en échec. Calibrer les
  règles saisonnières/historiques, suivre fausses alertes, dédoublonnage, résolution,
  statut relisible et reprise durable. Changer la couleur ne qualifie pas une règle.
  Les seuils normatifs restent inchangés sauf ADR justifié avant code et évaluation
  indépendante ; pas de baisse d'exigence pour obtenir davantage d'alertes.
- Bulletin : jusqu'à trois faits essentiels réellement disponibles, carte si reçue,
  mini-courbes, implications conditionnelles, inconnues et sources. Période du bulletin
  distincte des dates des données ; brouillon/revu/publié distincts. Une rubrique sans
  fait reçu reste indisponible ; pas trois chiffres imposés pour remplir une mise en page.
- Conserver le contrat bulletin : LLM sur IDs/libellés sans valeurs, placeholders
  validés puis substitution numérique côté serveur ; repli déterministe explicite.
- Réserver les détails JSON/méthode à une vue secondaire. Parcours pédagogique par
  explications au clic et comparaison temporelle, sans score de confiance inventé.
- Critères : nombres/directions/unités identiques HTML/PDF/SQL et citations relues ;
  inversion hausse/baisse refusée ; une copie de source ne double pas les preuves ;
  lecture mobile/clair/sombre ; approbation durable et capture Mailpit seules, H3 fermé.
- Validation d'usage préparée : l'utilisateur peut retrouver le produit/territoire,
  expliquer ce qui a changé et citer la limite principale sans ouvrir le JSON.
  Mesurer compréhension et temps de repérage pendant un essai humain réellement tenu ;
  ne pas inventer de score ou fixer un seuil de succès après avoir vu ses résultats.

## DP-7 — Analyse, prévisions et scénarios utiles

- Fixer une question, un utilisateur et une action possible avant de choisir le modèle :
  veille des prix pour acheteur, pression alimentaire pour institution, suivi des
  approvisionnements seulement avec données quantitatives reçues.
- Descriptif→saisonnalité→comparaisons→hypothèses explicatives ; prix ne prouve pas
  rupture, stock ou causalité. Exogènes change/carburant/climat utilisables seulement
  avec dates de disponibilité et contrats reçus ; cohorte imputée identifiée.
- Conserver les critères R3 :36mois/récence/éligibilité, six origines de sélection,
  calibration séparée et holdout indépendant, seuils existants. Apprentissage avec
  seules données disponibles à l'époque, y compris révisions ; pas de validation
  de marché contre les seules estimations du modèle fournisseur.
- Comparer aux références naïves/saisonnières, mesurer erreurs et couverture des
  intervalles par horizon/zone/produit ; publier modèle effectif, repli et abstention.
  Aucun horizon quotidien à partir d'une seule série mensuelle.
- Scénarios conditionnels avec hypothèses versionnées et facteurs qui changeraient
  l'issue, distincts de prévisions probabilistes calibrées et d'actions automatiques.
  LLM pour expliquer/citer, pas fabriquer les chiffres ou décider d'un achat.
- Critères : preuves as-of, jeu indépendant et métriques recalculables ; résultats
  correctement qualifiés dans les alertes/bulletins. Essai humain avec utilisateurs
  représentatifs mesurant compréhension/utilité ; non réalisé reste NOT_EVALUATED.

## Méthode de livraison et limites

- Un résultat fonctionnel par lot ; regrouper les raccordements et cas négatifs.
  Tests ciblés pendant développement, puis un check complet du contenu figé et les
  SQL/S3/E2E applicables. Rien de tel n'est lancé pour la seule rédaction de ce plan.
- Avant tout schéma/endpoint/politique/nouvelle dépendance : ADR et SPECS. Ce plan
  décrit les choix à instruire, pas des contrats techniques déjà adoptés.
- Livrer un reçu par lot : source exacte, images, environnement, commandes/codes,
  effectifs, couverture, état des sources et limites. Aucun mélange des SHA comme gel
  unique ; tests logiciels, live, modèle et usage humain qualifiés séparément.
- Intégration/activation après réception, sources runtime figées, sauvegarde et essai
  clone pour migration, contrôle des jobs, remplacement ciblé et preuve API/proxy/UI.
  Préserver bases, volumes et Bronze, ainsi que les services et travaux concurrents.
- Aucun achat, contact ou envoi externe ; aucune réactivation implicite de source,
  aucun gate R ou statut DONE obtenu par la rédaction du plan. Pas de nouvelle
  délégation ni de date de livraison garantie dépendant de documents encore absents.

## Preuves et références de la recherche

Les pièces en annexe conservent la requête READ ONLY et son résultat daté, le profil
des géométries et les références primaires. Les40 références,16 produits DQ et135
lignes de prix sont un constat local, pas un objectif de couverture ni une mesure
du nombre de points mensuels affichés. Références détaillées dans l'annexe de recherche.

Sources de méthode : RFC9309 et Scrapy (débit/cache), Nations unies (qualité des prix),
FAO FPMA (anomalies historiques/saisonnières), OTexts (validation chronologique et
intervalles), FEWS NET (scénarios), INSTAT/BFM/OMH/Douanes/Banque mondiale (sources
publiques candidates), geoBoundaries (géométries candidates, non encore qualifiées).
