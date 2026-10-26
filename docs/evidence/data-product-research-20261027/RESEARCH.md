# Recherche préalable — collecte et utilité économique d’Irooa

27 octobre2026. Code applicatif, schémas, référentiels et services conservés. Requêtes uniquement READ ONLY sur la base active aiagent, résultats dans profile-readonly.txt et requêtes exactes dans profile-readonly.sql. Analyse des fichiers du worktree r08-navigation-20261026 ; ne pas confondre cette source avec une activation sur3005.

## Constats vérifiés

-40 références produits ;16 libellés Riz Test DQ, tous sans prix courant. Deux vocabulaires de produits coexistent. Une seule référence possède des observations prix courantes :RICE_WHITE_LOCAL,135 lignes normalisées, toutes imputed et actor_level=unknown. Ce sont des lignes obs, pas135 points Gold mensuels ni une couverture nationale. Le filtre charge tout /v1/products sans filtrage métier/disponibilité ; le drapeau verified est aussi vrai pour les produits DQ et ne suffit pas à les identifier correctement.
-0 CPI et0 macro courants ; gold.economic_dashboard non peuplée. Le code provenance_gate refuse explicitement economic_dashboard (macro_publication_not_qualified). Ajouter une collecte ne suffit donc pas à lever la retenue : contrat/provenance/calculs/SQL/API/UI à recevoir.
-Carte :ChoroplethMap dessine une grille de boutons, pas un moteur géographique.23/23 géométries admin1 locales sont des rectangles alignés sur les axes ; manifeste et README ne prouvent pas leur authenticité. Les déclarations figées sur les corridors/+25% ne sont pas des résultats de calcul.
-Alertes :codes/règles/sévérités anglais et preuve JSON directement exposés. Bulletins :métadonnées et prétentions Certifié/Officiel/Audit-proof non étayées par l'état de qualification courant. Repenser en faits lisibles, portée, incertitude, sources et actions possibles.

## Sources primaires consultées

-https://www.rfc-editor.org/info/rfc9309/ — règles robots ; distinctes des droits d'usage.
-https://docs.scrapy.org/en/latest/topics/autothrottle.html — adaptation du débit et plafonds par domaine.
-https://docs.scrapy.org/en/latest/topics/downloader-middleware.html — cache et revalidation.
-https://unstats.un.org/bigdata/task-teams/scanner/index.cshtml — sources alternatives des statistiques de prix.
-https://millenniumindicators.un.org/wiki/spaces/GWGSD/pages/240910480/Data%2Bfiltering%2Band%2Bmissing%2Bprices — filtrage et valeurs manquantes ; prix web sans quantités vendues.
-https://www.instat.mg/index.php/p/nipc-nouvel-indice-des-prix-a-la-consommation-decembre-2025 — page officielle et Excel indices2016–2025 ; consultation documentaire seulement, source collecteur disabled conservée.
-https://www.banky-foibe.mg/publication/outdoor_tmp_2.html — rubrique officielle change ; aucune série journalière ni extraction opérationnelle qualifiée ici.
-https://www.omh.mg/index.php — publications et prix administrés avec date d'effet.
-https://www.douanes.gov.mg/statistiques-et-bilan/ — statistiques commerce extérieur ; poids/valeur/grain à vérifier avant coût unitaire.
-https://microdata.worldbank.org/catalog/8240/study-description — estimations mensuelles riz/sucre/farine de blé, métadonnées pays ; liste globale n'implique pas disponibilité de tous les produits dans chaque marché. Estimations et observations distinctes ; origines WFP/FAO ne constituent pas des confirmations indépendantes.
-https://www.fao.org/giews/food-prices/research/detail/en/c/235685/ — indicateur d'anomalie tenant compte de la croissance saisonnière/historique.
-https://otexts.com/fpp3/toolbox.html — références naïves, intervalles, évaluation temporelle à origine glissante.
-https://fews.net/about/projections — scénarios fondés sur hypothèses et suivi des facteurs qui changeraient l'issue.
-https://www.geoboundaries.org/ — limites ouvertes CC BY4, alternative à examiner ; aucune géométrie MDG téléchargée ou qualifiée ici.

## Direction proposée, non implémentée

1. Réception du lot en attente puis isolement des données de test et réparation/quarantaine/lignée AU08–09, sans effacement historique ni contournement des dépendances.
2. Référentiel produits canonique et alias validés ; exclure DQ des choix métier, montrer disponibilité par produit/zone/stade/période ; distinguer absence et zéro. Garder inconnus et ne pas requalifier unknown en retail.
3. Acquisition autorisée par priorité API/export structuré puis HTML puis PDF/navigateur si nécessaire ; archive des originaux, SHA, source/cellule, dates publication/ingestion/disponibilité, licence, révisions. Respect plafonds, robots, cache, refus et statut disabled. Import humain d'une édition authentique si acquisition bloquée, sans bypass. Réutiliser les connecteurs existants avant nouvelle pile.
4. Un trajet macro complet par source :INSTAT indices et base, BFM cours officiels, OMH prix réglementés et date d'effet, Douanes valeur/masse/période/code produit. Contrats/préuves avant ouverture de Gold. Ne pas remplacer IPC officiel par prix d'un seul riz ni change officiel par estimation parallèle.
5. Vraies géométries avec version/codes validés ; cartes à dates et unités comparables, zones sans données grises, provenance et séries accessibles. Prix ne prouve ni stock ni coût livré ni marge nette.
6. Descriptif puis saisonnalité, comparaison spatiale, facteurs explicatifs, scénarios. Prévisions à fréquence compatible avec données, validation chronologique avec informations disponibles à l'époque, comparaisons naïves, erreurs et couverture d'intervalles par horizon ; abstention si insuffisant. LLM pour explication/extraction assistée avec preuves, chiffres déterministes et contrôle humain.
7. Alertes :quoi/où/période/importance/raison/comparaison/historique/couverture/preuves/action possible. Séparer marché, qualité et panne de collecte ; dédoublonnage et fausses alertes suivis. Bulletins :trois faits, carte, mini-séries, implications conditionnelles, inconnues et sources ; pas de certification auto-proclamée. Mesurer compréhension, utilité et fraîcheur, pas nombre de cartes/UI.

## Limites

Recherche et diagnostic, aucune nouvelle source collectée, aucune donnée corrigée, aucun modèle entraîné. Les sites et exports repérés ne sont pas des connecteurs reçus. Le rendu de reçu interactif du plugin Data exige load_workspace_dependencies, outil non disponible dans cette session ; sources et SQL conservés sous fichiers inspectables en remplacement, sans prétendre à un rendu interactif.
