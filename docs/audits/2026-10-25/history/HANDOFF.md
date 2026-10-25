# Passation du programme — PARTIAL, non clôturé

Mise à jour2026-10-25 UTC. PROGRESS.md reste canonique :7 DONE,
52 IN_PROGRESS,15 TODO ;69 MUST et5 SHOULD. Aucun nouveau tag final.
Les anciens tags et rapports ne prouvent pas la réception actuelle.

## Travail en cours

Main2250c7b, PR1 fusionnée après CI verte40109568864. R0.8 reste
IN_PROGRESS : mécanisme de rejeu reçu historiquement côté logiciel, mais
révisions authentiques, inventaire S3 original et recalcul scientifique
encore non qualifiés. Correctifs1a6641c reçus :check6735 vert (2393 backend,
50 frontend/build16), E2E8021 vert (12 scénarios). La fenêtre WB récente
ac11e47 est reçue :check27111 vert (2398 backend/50 frontend/build16),
E2E76823 vert (12 scénarios). Sa réception ne qualifie pas les données.

Audit A012 :728 auto-liens superseded_by ne constituent pas des révisions
source ; B-R084 reste ouvert. Aucune réparation active par ce lot. Les
quinze lignes WB courantes observées lors de l'audit étaient imputées et
historiques. Après le clic actif du2026-10-24,135 lignes WB sont courantes,
toutes imputées, avec des périodes jusqu'à2026-10. Le clone WB a rejoué deux
documents/quinze lignes sans différence mais sans candidat Gold ni
prévision éligible : preuve bornée, pas qualification complète.

## Données nécessaires pour lever les limites de R0.8

Inventaire original acquis le2026-10-25 :684 versions S3, toutes relues,
tailles et adresses SHA cohérentes, inventaire stable. La concordance SQL
échoue :164 clés absentes sur485 entrées. Les234 prix liés sont déjà
auto-supersédés, aucun courant ; cela ne répare pas leur provenance.
Originaux et impact : R0.8_BRONZE_ORIGINAL_AUDIT_20261025.json et
R0.8_BRONZE_ORIGINAL_IMPACT_20261025.json. B-R085 requiert une réparation
sur clone sous contrat ; ne jamais fabriquer les objets manquants.

| Besoin | Format et droits | Réception attendue |
|---|---|---|
| Correction réelle d'une valeur source | Deux versions originales d'un même bulletin/fichier officiel, dates, URL ou origine autorisée, droit de réutilisation documenté ; même produit/lieu/période | Deux objets Bronze intacts, parseur avec preuves de cellules, nouvelle ligne et véritable lien vers la révision ; rejeu hors réseau identique |
| Corpus annoté et normalisable | Bruts officiels, métadonnées de période/unité/devise/produit/lieu, annotations indépendantes et statut de revue honnête | Normalisation sans alias inventé ; Gold publié uniquement après tous les gates |
| Inventaire Bronze original | Export versionné d'un bucket autorisé, tailles/SHA/version_id et copie en lecture seule sur destination dédiée | Identité originale vérifiée séparément de la simple copie locale |
| Recalcul scientifique | Historique éligible, versions dataset/modèle et protocole temporel | Résultats reproductibles, évaluations indépendantes ; abstention si données insuffisantes |

Une nouvelle acquisition WB du2026-10-23 a récupéré cinq réponses HTTP
(robots/documents), sans chargement actif. Les quinze valeurs sont
identiques à l'archive : elle ne fournit pas la correction réelle demandée.
Ses droits et annotations ne sont pas qualifiés par le seul téléchargement.
Une acquisition distincte61316 a obtenu120 estimations récentes2020-01 à
2026-10, parsées hors réseau avec preuves contre le contexte officiel
(39303). Cette sonde n'a rien chargé. Le clic actif63276 a ensuite intégré
120 estimations via le propriétaire durable normal et publié les vues :
HTTP200/statussucceeded, zéro rejet, reçu relu après reload, sans qualification
scientifique des estimations. Branche4226a29 :
sélection mensuelle récente raccordée à la collecte manuelle, réception
logicielle27111/76823 verte, activation locale3fec099 et clic actif confirmés.

Les corrections du libellé de portée futur120 et du500 des filtres prix
from/to sont reçues :check52578 vert (2398 backend/50 frontend/build16),
E2E87920 vert (12 parcours), CI40109568864 verte sur empreinte identique.
Le reçu historique bounded_15 est conservé, son compte120 était exact.
La construction MinIO depuis source officielle figée est reçue en QA ;
aucun stockage actif ni volume existant remplacé. Originaux52578/87920 et
reçus CI conservés dans docs/evidence. Cette réception reste logicielle.
La demande documentaire à l'utilisateur est non bloquante pour les travaux
logiciels et diagnostics sûrs restants.

## Suite autorisée

Compléter les qualifications manquantes de R0.8, puis gate R0.9 avant les tâches
R1 dépendantes. Les connecteurs, modèles, pages, alertes et copilote existants
ne sont pas à reconstruire : terminer corrections et qualification selon le
plan. Ne déclarer aucune phase terminée par le nombre de tests seul.

## Gates humains et sécurité

- H1 : replay/déterministe sans clé LLM ; aucune obligation de dépenser.
- H2 : aucune provision ni achat par l'agent ; déploiement non revendiqué.
- H3 : brouillons/Mailpit uniquement ; aucun envoi réel sans autorisation.
- H4 : marketplaces/sites privés hors périmètre MVP, sans connecteur.
- H5 : human_reviewed=false tant que non relu ; ne pas inventer une revue.
- H6 : budgets de configuration et par source, pas de hausse implicite.
- H7 : aucun contact humain externe par l'agent.

## Runtime et preuves

Frontend actif remis en service depuis une copie readonly du code main585c47f,
volume ketrika_runtime_web_585c47f et override opérateur au canal partagé.
Connexion HTTP200 et conteneur healthy vérifiés ; pas d'essai humain déduit.
Les volumes SQL/S3 et travaux concurrents sont conservés. Le dépôt GitHub
privé existe ; contrôler le SHA distant avant toute affirmation de push.

Voir [audit A012](evidence/R0.8_A012_AUDIT_20261024.md),
[runbook](runbooks/OFFLINE_REBUILD_QUALIFICATION.md), PROGRESS et BLOCKERS.
L'ancienne passation annonçant100% est conservée dans
[l'archive historique non reçue](evidence/HANDOFF_20261017_HISTORICAL_UNRECEIVED.md).
