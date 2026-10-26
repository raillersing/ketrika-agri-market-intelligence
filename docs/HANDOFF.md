# Passation courante — audit indépendant terminé, programme PARTIAL

## Priorité utilisateur du27 octobre2026 — plan de correction des données et des parcours

Lire le [plan DP-0–7](plan/DATA_PRODUCT_IMPROVEMENT_PLAN.md), préparé depuis f947f33 et la recherche primaire du27 octobre. Il précise les lots AU existants et conserve leurs dépendances, les74 statuts et les gates humains. Ce document ne livre ni nouvelle collecte, ni carte, ni prévision.

La prochaine livraison de présentation est DP-1, correctif borné R0.8, après DP-0 : filtres sans références DQ, stade de vente explicite, retrait des filtres sans effet et des affirmations non calculées, états vides/non qualifiés/erreurs lisibles. Le prochain travail de réparation du socle reste AU-08 puis AU-09 ; ne pas lancer AU-10 avant R0.9. Collectes/macro/carte/alertes-bulletins/prévisions suivent les dépendances exactes des lots correspondants.

Avant réutilisation des reçus, réconcilier le regroupement documentaire f947f33 : originaux backend/frontend rattachés à4e455ed, navigateur rattaché àcd77a26. Aucune requalification de données ou activation ne découle de ce regroupement. Recevoir le prochain contenu applicatif stabilisé plutôt que refaire un check de base juste avant son développement. Les sections plus anciennes ci-dessous restent historiques lorsque leur état de réception diffère.

Date2026-10-25, base auditée b7e63ee. [Rapport indépendant](audits/2026-10-25/INDEPENDENT_AUDIT.md), [plan détaillé26 lots](audits/2026-10-25/CORRECTIVE_EXECUTION_PLAN.md), [matrice74 tâches/18 sources](audits/2026-10-25/TASK_CAPABILITY_MATRIX.md).

## Prochain travail autorisé

1. Lire AGENTS/PROGRESS/BLOCKERS et le plan correctif ; réserver un nouveau worktree. Le worktree r08-bronze-audit-20261025 est utilisé readonly par l'API active : ne pas y développer du code.
2. AU-01 accueil/filtres, AU-02 climat et AU-03 scénarios : supprimer les faux faits et brancher les entrées réelles ou l'abstention.
3. AU-04 accès/JWT/configuration, AU-05 H3, AU-06 dépendances et AU-07 restauration sûre. ADR/SPECS avant extension ; une réception groupée si le contenu est stabilisé ensemble, sinon lots fonctionnels reçus séparément.
4. AU-08 réparation historique sur clone, AU-09 rebuild authentique puis R0.9. Ne pas assimiler quarantaine et vraie révision.
5. Poursuivre AU-10–26 selon dépendances R. Les18 fiches sources distinguent désormais description historique et qualification actuelle. Aucune réimplémentation intégrale des modules déjà présents.

Les conclusions et défauts IA-01–20 sont documentés ; ils ne sont pas corrigés par la documentation. Statuts conservés :7 DONE historiques/52 IN_PROGRESS/15 TODO. Aucun nouveau gate/tag ni déploiement.

## Données et interventions réellement nécessaires

| Tâche/capacité | Action et format attendus | Droits / réception |
|---|---|---|
| R0.8, B-R073 | Deux éditions originales d'un même produit/lieu/période avec correction réelle ; fichiers, dates, URL/origine et tableau de cellules | Réutilisation autorisée, SHA distincts, nouvelle observation reliée à l'ancienne ; replay offline identique |
| R0.8, B-R084/085 | Conserver inventaire684 versions et ledger485 entrées dont164 clés absentes ; définir et recevoir réparation des728 auto-liens sur clone | Aucun faux objet, aucune valeur effacée ; audit append-only et objets inchangés |
| R1/R2 | Archives publiques/accords de sources manquantes, périodes/unités/produits/lieux et annotations indépendantes | Aucun contournement de disabled ; autorisation documentée, pas contact de tiers par agent |
| R3 | Historique observé éligible et vintages/disponibilité prouvés | Protocole figé avant résultat, sélection/calibration/test indépendants ; imputations séparées |
| R4/R5 | Bulletins/raster/émissions, calendriers/corridors, relevés quantitatifs par marché et campagnes | Origine/pages/droits ; ne pas déduire tonnes de prix ou NDVI seul |
| Usage humain | Scénarios pilote préparés, essai par personnes autorisées et compte rendu daté | NOT_EVALUATED jusque-là ; aucune décision ou commande autonome |

Les données absentes ne bloquent pas AU-01–08 ni les diagnostics sûrs indépendants. H1→replay, H2→paquet local sans achat, H5→human_reviewed=false. H3 et H7 restent fermés ; Mailpit local seulement. Aucun message tiers à envoyer.

## Environnement et preuves

API active montée readonly depuis r08-bronze-audit-20261025/backend ; override opérateur externe coordination/runtime-api-native-20261025.yml. Web source volume ketrika_runtime_web_ac11e47. Les sources applicatives partagent l'empreinte reçue7c79ce2e... ; montages et identité à vérifier à chaque reprise, ne pas changer les volumes pour faire passer des tests.

Docker Desktop a été redémarré après arrêt, base existante conservée. Les réparations runtime ne qualifient pas un déploiement durable. Pas de suite mutante réservée par cet audit ; préserver les originaux main-final. Les mesures de latence sous imports/compilation ne sont pas un benchmark.

Dernière réception applicative52578/87920 et CI40109568864 ; nouveaux contrôles d'audit en lecture seule, scans actuels et navigateur dans audits/2026-10-25/evidence. Les premiers essais de sonde invalidés sont exclus ; les scripts finaux et limites sont explicités.

## Correction des faits affichés — en cours le25 octobre2026

Branche `fix/r08-safe-facts-20261025`, base4b57562, [plan avant code](audits/2026-10-25/SAFE_FACTS_IMPLEMENTATION_PLAN.md), ADR121/SPECS. AU-01–03 IN_PROGRESS : accueil via API/référentiels, climatNULL et dates PostgreSQL, scénarios/pics409 sans preuve opérationnelle.42 tests ciblés verts ; la réception complète sur source figée et le navigateur restent requis avant main/runtime. Dernier canal lu A013 ; réservation C037. Les AU-04–26 et les blocages de données restent ouverts. Ne pas prendre l'abstention pour une qualification ni relancer un moteur dont les entrées ne sont pas prouvées.

Complément18:11Z : check4405 rouge (2411/1, ancien test de pic attendu200 corrigé vers404) ; aucune réception main. Regroupement AU-05 ADR122 :32 tests sans réseau et trois captures Mailpit interne distinct vérifiées. Aucun SMTP externe/Telegram autorisé. Les contrats AU-04 ADR123 restent uniquement en préparation dans r08-security-20261025, sans code ni migration reçus ; ils ne font pas partie du présent lot. Reprendre le prochain check connu sans modifier sa source pendant son exécution.

Réception19:00Z : AU-01/02/03/05 reçus logiciellement sur5400f39 (2426 backend/167 intégrations,52 web/build16,12 E2E58,389s ; API/reload/mobile/graphique942×340). Voir docs/evidence/safe-facts-20261025/RECEPTION.md et originaux. .gitleaksignore ne vise que le marqueur de déduplication synthétique du commit5400f39, pas un secret. Activation et publication à confirmer séparément. AU-04 reste isolé/non migré/non reçu ; aucun autre lot ni gate final terminé.

Activation locale confirmée : main03ea267/application5400f39,96 points RICE_WHITE_LOCAL tous imputés, rechargement/graphique/mobile et météo sans faux chiffres constatés par c1b03355... ; API/web/Dagster sains. Source backend/Dagster native r08-safe-facts-20261025, frontend volume ketrika_runtime_web_safe_facts_5400f39, override externe coordination/runtime-safe-facts-20261025.yml. Aucun reset, migration, collecte ni objet Bronze modifié. Publication distante/CI à vérifier après push ; auth AU-04 non incluse. Trace E2E brute locale ignorée par Git (sessions synthétiques), SHA versionné. Les exceptions Gitleaks ne visent que les deux introductions du même marqueur synthétique, pas une règle globale.

## AU-04 — réception logicielle complétée le26 octobre2026

Source2a6ec4e reçue :2439 backend/168 intégrations,57 web/build et15 E2E ; inventaire, images et empreinte vérifiés, originaux dans docs/evidence/auth-20261026/RECEPTION.md. Révocation SQL multi-processus, matrice serveur et session web ont leurs preuves. L'ancien état de préparation AU-04 ci-dessus est historique. Main/runtime et migration active ne sont pas activés par cette clôture de branche. AU-06/AU-07 restent à recevoir séparément ; programme PARTIAL et74 statuts R conservés.
