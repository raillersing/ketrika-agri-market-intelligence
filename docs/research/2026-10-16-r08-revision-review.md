# R0.8 — révisions : correction logicielle et limite du corpus

## Correction nécessaire

Un document d'étude inchangé conserve son SourceRecord unique (source/SHA).
Son association à plusieurs lots est normale lors des éditions successives.
L'ancien parseur exigeait un seul lot pour tout document et refusait donc ce cas.
ADR-074 distingue le document d'étude, sans prix, et le document de données :
ce dernier exige le même contexte vérifié dans tous ses lots, sans choisir le
dernier contexte silencieusement. Les archives et valeurs anciennes restent intactes.

La validation SQL utilise deux éditions **synthétiques** : une valeur modifiée,
quatorze inchangées, même référence de contexte. Elle vérifie supersession et
nouvelle tentative sans doublon ; elle ne constitue pas une archive institutionnelle.
Voir PROGRESS pour le résultat réel, pas cette description de test.

## Pistes publiques examinées le 16 octobre 2026

| Source primaire | Constat | Ce que cela ne prouve pas |
|---|---|---|
| https://microdata.worldbank.org/catalog/4483 | Catalogue global, édition affichée2026-10-05 ; décrit des estimations historiques révisables | Ne fournit pas à lui seul les octets d'une précédente édition MDG |
| https://microdata.worldbank.org/catalog/8240/related-materials | Publications et présentations ; la version affichée par l'index web peut être plus ancienne | Un ancien intitulé en cache n'est pas une ancienne table de prix acquise |
| https://zenodo.org/records/18846560 | Paquet de réplication publié, CSV annoncés CMR/HTI/PHL/SDN/SOM | Aucun CSV Madagascar dans la liste examinée ; ne pas substituer un autre pays au pilote |

Aucun de ces constats ne démontre l'absence universelle d'archives. Aucun
téléchargement massif, contact de tiers, ni accès à une origine disabled réalisé.
Ne pas confondre rice et c_rice, changement de couverture et révision d'une même cellule.

## Preuve encore nécessaire pour le critère authentique

Deux éditions acquises légalement, octets originaux et SHA distincts, mêmes
clés métier (produit, lieu, période, unité, devise, type de valeur), valeur
réellement révisée et dates de publication/disponibilité prouvées. Conserver
URL/catalogue/droits/contexte et attendus indépendants, human_reviewed=false
tant qu'aucune revue humaine n'a eu lieu. Ingérer sur clone uniquement, rejouer
sans réseau et vérifier anciennes/nouvelles valeurs, superseded_by et empreintes.

Une correction de code ne remplace pas cette preuve ; R0.8 reste non terminé.
