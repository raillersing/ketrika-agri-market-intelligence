# Plan détaillé après audit indépendant — 25 octobre 2026

**Complément utilisateur du27 octobre2026 :** le [plan données et parcours DP-0–7](../../plan/DATA_PRODUCT_IMPROVEMENT_PLAN.md) détaille les corrections de filtres/produits, collecte, économie, carte, alertes/bulletins et prévisions après recherche primaire. Il ne crée pas de nouveau lot AU ni de tâche R et ne change aucun statut/gate. DP-1 est un correctif de présentation borné à R0.8 ; les nouvelles collectes et capacités aval conservent leurs dépendances ci-dessous. DP-0 exige de réconcilier la portée des reçus natifs avant réutilisation.

**Exécutable par agents ; corrections autorisées après restitution le25 octobre2026.** Base auditée b7e63ee. [Audit](INDEPENDENT_AUDIT.md), [matrice des74 tâches](TASK_CAPABILITY_MATRIX.md), [plan R normatif](../../plan/MARKET_INTELLIGENCE_EXECUTION_PLAN.md). Les lots AU sont des sous-livrables de correction/réception, pas74 nouveaux MUST ni une substitution des dépendances R.

## Ordre, responsabilités et règles communes

1. Livrer d'abord une version locale qui ne fabrique aucun fait : AU-01 àAU-07. Ce sont des corrections du MVP existant pendant R0.8, pas la qualification anticipée de R6.7/R6.8.
2. Réparer la lignée et recevoir R0.8/R0.9 : AU-08/09. Les défauts techniques restent traitables ; l'absence de vraie édition ou d'un accord donne un blocage de données précis, jamais une fabrication.
3. Puis R1→R2→R3/R4→R5→R6 selon les dépendances détaillées du plan R. La présence actuelle d'un module ne permet pas de sauter son gate.
4. À chaque reprise : lire AGENTS/PROGRESS/BLOCKERS, le dernier reçu et le diff ; choisir le premier lot éligible. Marquer AU IN_PROGRESS ici et journaliser UTC ; conserver le miroir74 statuts identique à PROGRESS. Ne changer un statut parent R qu'après tous ses critères.
5. Un agent propriétaire par lot ; rôle Data/Backend, Frontend, ML/Geo ou QA indiqué. Si du travail parallèle est explicitement autorisé, worktrees distincts et fichiers réservés au canal Codex/Antigravity ; aucune suite mutante sur la même destination. Une suggestion de rôle n'est pas un ordre envoyé à un agent.
6. ADR/SPECS **avant code** pour schéma, endpoints, dépendance d'exécution ou version majeure. Les propositions ci-dessous ne constituent pas à elles seules les nouveaux contrats. Aucun gate H1–H7 levé.
7. Développement : lint/types et seuls tests nouveaux/impactés dans Docker. Geler un résultat fonctionnel complet puis **un check complet du lot groupé**, SQL/S3/E2E applicables, original JUnit et empreinte ; ne pas refaire une QA cumulée déjà incluse dans ce JUnit. Aucun seuil scientifique abaissé.
8. Avant réception : prouver API→DB→reload→provenance, états vides/non qualifiés/échec ; secrets scannés sur le seul delta ; Conventional Commit avec parent R, preuve et limites dans PROGRESS. Pas de DONE à partir d'un nombre de tests.
9. Réparer d'abord sur clone nommé, snapshot conservé et comparaison métier ; aucune suppression/écrasement Bronze, ni reset/rebuild/restore sur actif. Une réparation de lien requiert journal d'audit conservant l'état précédent. La sauvegarde active readonly est permise ; sa restauration cible uniquement un clone neuf autorisé.
10. Le recul exige de servir la dernière **version qualifiée** ou un état indisponible ; jamais de rétablir automatiquement les anciennes valeurs/faux tableaux ni d'effacer une migration d'audit. Ne pas modifier le worktree utilisé actuellement comme source runtime.

Commandes de réception : `bash scripts/dev.sh check` sous Linux, `./scripts/dev.ps1 check` sous Windows ; `e2e`, `qa-isolated` et `qualify` selon les runbooks et la configuration du dépôt. Les sous-commandes exactes et destinations doivent être relues avant exécution, pas devinées. Tous Python/Node/navigateurs dans Docker. Les états TODO ci-dessous sont des états de lots, sans modification automatique des74 tâches.

## Lots immédiatement correctifs

### AU-01 — Accueil et filtres réellement alimentés

- **Statut :** DONE (logiciel5400f39, réception18572/44716 ; sources et modèles non qualifiés) · P0 · rôle Frontend/Backend · parent R0.8, réception ultérieure R2.10 · dépendance : aucune correction préalable.
- **Fichiers :** `web/src/app/page.tsx`, `web/src/components/ui/KpiCard.tsx`, `GlobalFilters.tsx`, `web/src/app/{prices,map,trade}/page.tsx`, `web/src/lib/api/*`, tests web et parcours navigateur. Constats IA-01/13.
- **Étapes :** inventorier chaque chiffre/statut/source actuellement constant ; remplacer les tableaux inline par lectures réelles des endpoints existants ; partager les codes canoniques des produits et lieux ; supprimer stock21j, score74, trois alertes et mention100% quand aucune mesure ne les justifie ; montrer NULL, données imputées et date de source ; rendre export et provenance cohérents avec les mêmes filtres.
- **Réception :** accueil et prix concordent avec API/SQL après reload ; choisir un produit vide ne fabrique ni carte ni courbe ; une erreur API est visible ; un compteur d'alertes suit la requête réelle. Aucun chiffre d'exemple dans le bundle de la page réelle ; si une démonstration est conservée, route/contexte explicitement séparé et non servi par défaut.
- **Preuves :** capture et reçu navigateur desktop/390px, réponses API et agrégat SQL indépendants. Une fixture sert aux régressions, jamais à la vérité du marché.

### AU-02 — Agroclimat sans fausses observations ni prévisions

- **Statut :** DONE (logiciel5400f39, réception18572/44716 ; sources et modèles non qualifiés) · P0 · rôle Backend/Geo · parents R0.8/R4.11 · dépendance : aucune ; même livraison de sécurité qu'AU-01 possible.
- **Fichiers :** `api/routers/climate.py`, `weather.py`, `api/schemas.py`, `web/src/app/climate/page.tsx`, tests SQL/API. IA-02/10/15.
- **Étapes :** supprimer toutes les constantes de repli115/95/21,5/14,2/6/28,5 et fausse émission ECMWF ; définir dans ADR/SPECS NULL+availability/reason si DTO étendu ; utiliser réellement le mois demandé et la variable/unité demandée ; ne pas remplacer une zone inconnue par ZONE_CENTRE ; distinguer observations/prévisions et absence/référence insuffisante ; corriger formule de baseline et source effective des anomalies.
- **Réception :** base sans WeatherForecast→aucune prévision numérique ; zone/période inconnue→état prévu par contrat, pas substitution ; le calcul pluie/température est vérifié à la main ; absence ne devient pas risque low ; JSON, UI et DB identiques après reload. Tests réels PostgreSQL, y compris from/to et erreur de schéma.

### AU-03 — Scénarios et offre : arrêter les fausses entrées

- **Statut :** DONE (logiciel5400f39, réception18572/44716 ; sources et modèles non qualifiés) · P0 · rôle Backend/Data · parents R0.8/R5.7/R5.8 · dépendance : contrat précis avant changement de DTO.
- **Fichiers :** `api/routers/supply.py`, `supply/{decision_pilot,peak_forecast,harvest_window}.py`, modèles stock réels. IA-05/16.
- **Étapes :** retirer24500tonnes et année2024 implicites ; valider produit/bassin/marché/campagne/lag ; interdire le premier calendrier de repli ; traduire les colonnes stock réellement persistées dans l'adaptateur ; supprimer le catch-all transformant SQL en liste vide ; séparer absence de mesure et hypothèse explicitement fournie ; ne publier ni confiance scientifique ni pic mesuré sans données.
- **Réception :** UNKNOWN/bad donne404/422 ou abstention documentée ; un défaut SQL donne erreur explicite ; aucune arrivée→aucun chiffre étiqueté observed ; scénario recomputable depuis paramètres versionnés et preuves. Tests sur PostgreSQL et campagne distincte de2024, marché sans correspondance, corps incomplet.

### AU-04 — Authentification et configuration sûres

- **Statut :** DONE (logiciel2a6ec4e, 2439 backend/57 web/15 E2E ; branche reçue, activation distincte) · P0/P1 · rôle Backend/Sécurité · parents R0.8/R6.7 · dépendance : matrice d'accès contractuelle avant patch.
- **Fichiers :** `api/auth.py`, `api/routers/*.py`, `api/main.py`, `core/settings.py`, middleware/proxy Next, Compose prod, tests d'accès. IA-06/08.
- **Étapes :** recenser toutes méthodes/routes et rôles ; appliquer l'auth serveur aux lectures métier conformément SPECS, toute exception publique exige décision explicite ; vérifier signature/session côté web plutôt que présence du cookie ; rendre révocation/logout durable partagée et expirable ; cookie Secure en HTTPS prod, HttpOnly/SameSite/CSRF selon mutations ; refuser defaults secrets/admin démo en prod et préserver le bootstrap local explicite.
- **Réception :** anonyme401 sur chaque route protégée, client403 sur mutations admin, cookie invalide/expiré refusé, logout rejeté par un second worker et après restart ; défaut de configuration prod refuse le démarrage sans imprimer de secret. Tests multi-processus/DB, pas uniquement set en mémoire ; aucune suppression d'utilisateur existant.

### AU-05 — H3 effectif à la frontière des transports

- **Statut :** DONE (logiciel5400f39, capture locale reçue ; H3 externe fermé) · P0 · rôle Backend/Sécurité · parents R0.8/R6.6/R6.7 · dépendance : inventaire de tous transports.
- **Fichiers :** `alerts/notifier.py`, appels depuis `pipelines/definitions.py`, bulletin et configuration SMTP/Telegram. IA-07.
- **Étapes :** centraliser la politique de sortie ; garder Mailpit local explicitement autorisé ; refuser SMTP externe et Telegram sans autorisation humaine documentée, même si une variable est positionnée ; journaliser refus/brouillon/reçu local sans adresse/token dans logs ; ne marquer envoyé qu'après preuve transport conforme.
- **Réception :** SMTP externe+gate off→zéro construction/connexion transport ; gate on sans autorisation→zéro envoi ; Mailpit local fonctionne et reçu relisible ; aucune notification vers un tiers pendant tests. Doubles interceptés uniquement pour cas négatifs ; vrai Mailpit pour cas positif.

### AU-06 — Mise à jour des dépendances et preuve de sécurité

- **Statut :** DONE (logiciel cd77a26, 2464 backend / 68 web / 19 E2E ; [reçu](../../evidence/irooa-reception-20261026/RECEPTION.md)) · P0 · rôle Backend/Frontend/Sécurité · parents R0.8/R6.7 · dépendance : IA-09 et inventaires des locks.
- **Fichiers :** `web/package.json`, `pnpm-lock.yaml`, `backend/pyproject.toml`, `uv.lock`, Dockerfiles si nécessaires, SECURITY_REVIEW.
- **Étapes :** dédupliquer les avis par alias, classer runtime/dev et conditions réellement présentes ; corriger les versions affectées, dont Next14.2.10 et dépendances Python signalées ; vérifier les avis mainteneurs à la date de correction ; ADR/SPECS avant toute majeure nécessaire ; reconstruire et tester la stack réellement retenue ; éviter une simple suppression d'outil pour faire disparaître le scan.
- **Réception :** scans ne signalent aucune critique applicable non traitée ; réserve résiduelle précise avec preuve, pas phrase générique « non exploitable » ; locks régénérés dans Docker ; build et parcours auth/proxy/graphiques reçus. Ne pas considérer14.2.25 comme cible finale universelle : c'est le patch d'un seul avis historique.

### AU-07 — Restauration qui échoue réellement en cas d'erreur

- **Statut :** DONE (logiciel cd77a26, fidélité ACL et clone privé vérifiés, 2464 backend / 19 E2E ; [reçu](../../evidence/irooa-reception-20261026/RECEPTION.md)) · P0 · rôle Backend/Ops · parents R0.8/R6.8 · dépendance : contrat de destination explicite.
- **Fichiers :** `deploy/{backup,restore}.sh`, `ops/backup_restore.py`, scripts dev, runbooks restore/déploiement. IA-17.
- **Étapes :** exiger identité/consentement de clone neuf autorisé et refuser actif indépendamment du nom ; supprimer le contournement de sécurité non reçu ; manifeste/hash obligatoires, outil absent→erreur ; tout code pg_restore non-zéro propagé ; ne pas cacher erreur SQL par zéro ; comparer manifestes métier, droits et objets, pas seulement comptes.
- **Réception :** commande simulée pg_restore=1→sortie non-zéro sans succès ; fichiers absent/corrompu, outil manquant et cible active refusés avant opération ; une sauvegarde réelle se restaure dans un clone neuf identifié et donne mêmes empreintes/privilèges. Aucune reprise de ce script ancien contre l'actif.

**Réception groupée sécurité minimale :** AU-01–AU-07 peuvent partager un gel complet/check/E2E lorsque développés ensemble et tous critères présents. Les commits préparatoires restent sur worktree ; ne pas recevoir chaque helper séparément. Si les lots sont reçus séparément après changements, chaque nouveau contenu applicatif a son propre check complet.

## Réparer le socle et recevoir R0

### AU-08 — Quarantaine et réparation historique auditable

- **Statut :** DONE (logiciel 0a8ed1a, ADR-133, migration 0020, triggers anti-auto-liens) · P1 · rôle Data/SQL · parent R0.8 · dépendances : AU-07 avant toute restauration ; arbitrage ADR/SPECS de B-R084/B-R085.
- **Fichiers :** migrations additives, modèles, `normalize/*`, `gold/sql/*`, `core/rebuild_manifest.py`, provenance/guards et runbook de réparation.
- **Étapes :** faire un inventaire exact des728 auto-liens,164 références absentes et autres données de test héritées ; capturer états avant et identités ; choisir une table de quarantaine append-only plutôt que fausse révision ; spécifier la réparation exceptionnelle des liens et ses permissions ; clone SQL/S3 séparé ; anti-auto-liens/cycles ; conserver toutes valeurs brutes et tous objets ; exclure quarantaine des publications et recompter les révisions réelles seulement.
- **Attention A013 :** le trigger actuel refuse UPDATE si OLD.superseded_by non NULL ; la remise à NULL proposée ne marche pas telle quelle. Ne pas désactiver les protections globalement ni lancer la migration sur actif pour « essayer ». La PK active observation_id doit être recontrôlée sur le clone avant FK.
- **Réception :** mêmes objets SHA avant/après, mêmes valeurs observées, audit complet des liens ; zéro auto-lien opérationnel après réparation, aucune ligne ancienne soudain publiée ; INSERT/UPDATE/DELETE illégaux refusés ; reprise idempotente sans perte ; manifestes et sauvegarde de clone relus. Anciennes références sans Bronze restent non qualifiées, jamais comblées par objets inventés.

### AU-09 — Rebuild authentique et gate R0.9

- **Statut :** TODO · P1 · rôle Data/QA · parents R0.8/R0.9 · dépendances : AU-08, R0.1–R0.7 reçus historiquement et non invalidés par le lot.
- **Fichiers :** `pipelines/rebuild*.py`, `core/rebuild_*`, runbook OFFLINE_REBUILD_QUALIFICATION, corpus/reçus.
- **Étapes :** réunir deux éditions authentiques du même produit/lieu/période avec une correction réelle ; vérifier droits/octets et annotations ; cloner destination explicitement dédiée ; exporter inventaire original avec versions et octets ; couper réellement le réseau du worker ; comparer valeurs, périodes, unités, provenance, révisions et Gold ; étape séparée de recalcul des modèles versionnés, avec abstention s'il manque les données.
- **Réception :** aucune requête réseau, ancienne/nouvelle révision correctement rejouées, diff métier nul et inventaire original inchangé ; faux parseur modifiant une valeur détecté même à effectif égal. Puis réception R0 et tag nouveau uniquement si tous critères passent. Si les deux éditions restent absentes, documenter B-R073 et le format attendu ; ne pas modifier les sources disabled pour les acquérir.

## Poursuite R1–R2 : observatoire utilisable

### AU-10 — Registre, découverte et contrat commun de sources

- **Statut :** TODO · P1 · rôle Data/Collecte · parents R1.1/R1.2/R1.10 · dépendance : R0.9 DONE.
- **Fichiers :** `registry/sources.yaml`, `connectors/{registry,discovery}.py`, `pipelines/source_definitions.py`, référentiels geo,18 fiches sources.
- **Étapes :** rapprocher identifiant, classe effective, famille, droits, URL vérifiée, cadence acquisition/publication et SLA ; distinguer active du niveau LIVE_VERIFIED ; vérifier les23 régions et les codes réellement servis ; tester pagination bornée et dérive ; recenser réellement jobs/schedules actifs/arrêtés ; isoler données de test et entrées institutionnelles sans effacer l'historique.
- **Réception :** aucune sourceplanned/disabled/fixture présentée qualifiée ; découverte d'édition suivante et idempotence sur serveur local ; URL inconnue en revue ; état registry/SQL/orchestrateur/API expliqué et cohérent. Aucune création autonome de source proposée par le copilote.

### AU-11 — Qualifier les sources du socle et l'actualisation

- **Statut :** TODO · P1 · rôle Data/Collecte/QA · parents R1.3–R1.9/R1.11/R1.12/R1.13 · dépendances : AU-10 et dépendances R exactes.
- **Fichiers :** connecteurs INSTAT NIPC, MiASA, MinCC, Douanes, WFP, WB, FAOSTAT, NASA, `manual_collection.py`, `manual_wb.py`, `/sources`.
- **Étapes par source :** lire CC-R et la fiche ; acquérir uniquement si autorisée ; archiver deux éditions authentiques lorsque requises et annotations indépendantes ; vérifier grain/produit/unité/lieu/fréquence ; charger par propriétaire durable et relire SQL/API ; réacquérir à date distincte pour le suivi d'édition ; interruption/reprise/idempotence sans refetch non autorisé ; calendrier Dagster effectivement démarré et visible.
- **Replis :** WFP/INSTAT/NASA disabled restent arrêtées, travail offline sur archives permises ; documents/accords manquants précisément listés. Le clic WB120 est une preuve partielle déjà acquise, à réutiliser sans recollecter pour chaque helper ; il ne couvre pas tous PPN ni tous marchés.
- **Réception :** CC-R et seuils normatifs mesurés sur vrais dénominateurs ; clic global/ciblé affiche portée/comptes/refus exacts, reçu durable et reload ; aucune réussite vide/certification générale. Gate R1.13 seulement sur état reçu, aucun ancien tag comme raccourci.

### AU-12 — Contrats, normalisation, macro et couverture fiables

- **Statut :** TODO · P1 · rôle Data/Backend · parents R2.1–R2.9 · dépendance : R1 applicable DONE, R2 dépendances conservées.
- **Fichiers :** `connectors/{instat_tbe,bfm_public,omh_public}.py`, `normalize/*`, `gold/{coverage,economic,dq}.py`, migrations macro, API/schemas/OpenAPI, métriques économiques.
- **Étapes :** vérifier contrats de temps/statistique/type/version/source, qualifier conversions et alias ; publier états par capacité durables ; brancher les vraies acquisitions macro sur leurs loaders ; unités/fréquences et prix réglementés distincts ; calculer couverture réelle par produit/zone/acteur/famille, sélectionner le pilote depuis cette couverture ; macro0→indisponible et aucune santé globale déduite d'un seul prix.
- **Réception :** JSON/CSV/SQL cohérents, nullité préservée, dimensions séparées, au moins un trajet autorisé par type réellement implémenté ; aucune corrélation/confirmation par copies WFP/RTFP ; alias faible confiance en revue. Toute absence métier requise garde le parent non DONE.

### AU-13 — Marché/économie, vraie carte et réception R2

- **Statut :** TODO · P1 · rôle Frontend/Geo/QA · parents R2.10/R2.11 · dépendances : AU-12 et R2.9.
- **Fichiers :** `ChoroplethMap.tsx`, pages prix/carte/économie, GlobalFilters, provenance et exports.
- **Étapes :** consommer les géométries administratives validées et codes communs ; dessiner des régions réellement interactives, avec zones manquantes explicites ; retirer les conclusions25% et tensions territoriales constantes ; afficher époque, acteur, unité, imputation, source et couverture ; provenance clic→observation→document ; régler rendu des graphiques avec preuve, pas simple présence de canvas.
- **Réception :** cinq questions du pilote calculées indépendamment, filtres→graphiques→provenance→reload, données API/DB exactes, erreurs visibles ; clavier/contraste AA et390px, état vide sans légende fictive. Gate R2.11 seulement si périmètre utile et sources requises reçus.

## Poursuite R3 : prévisions de prix

### AU-14 — Dataset SQL as-of et éligibilité réelle

- **Statut :** TODO · P1 · rôle ML/Data · parents R3.1/R3.2 · dépendances : R2.1/R2.3/R2.4/R0.8 DONE.
- **Fichiers :** `ml/{series,dataset,forecast}.py`, modèles et snapshots C4.
- **Étapes :** corriger les noms de colonnes contre PostgreSQL réel ; disponibilité depuis SourceRecord/ingestion prouvée, jamais po.published_at inventé ; conserver révisions point-in-time ; clé unité/qualité/acteur/zone complète ;36mois dont récence obligatoire et trous visibles ; cohortes observée/imputée séparées ; dataset/artefacts/version/hash persistés et effectivement passés au pipeline.
- **Réception :** appel session SQL réel vert, prix publié après origine exclu, révision future exclue, snapshot identique au rejeu ;35points/refus régional/données sans vintage en abstention ou rétrospectif explicite. Pas de série créée pour satisfaire un compteur.

### AU-15 — Sélection, calibration et holdout branchés

- **Statut :** TODO · P1 · rôle ML · parents R3.3–R3.6 (R3.6 SHOULD) · dépendance : AU-14.
- **Fichiers :** `ml/{models,backtest,conformal,exogenous,forecast}.py`, protocole d'évaluation.
- **Étapes :** geler folds/seuils avant résultats ; six origines de sélection et test final indépendant ; résidus du modèle hors entraînement, calibration séparée, pas différences successives de y ; modèles demandés/effectifs et replis exacts ; étanchéité des transformations et exogènes disponibles ; deadline/état d'échec de fit observables sans supprimer les vrais fits.
- **Réception :** calcul indépendant des métriques et quantiles, intervalles triés/finis, exclusion du futur, aucun holdout utilisé pour choisir ; calibration insuf→non calibré ; benchmark baseline acceptable. Exogènes retenues seulement après ablation et holdout reçus, sinon non retenues, sans bloquer les MUST.

### AU-16 — Publication ML, évaluations et gate R3

- **Statut :** TODO · P1 · rôle ML/Backend/QA · parents R3.7–R3.9 · dépendances : AU-15/R2.9/R2.10.
- **Fichiers :** Gold forecast_latest, API forecasts, persistance dataset/model_run/forecast/evaluation, graphiques.
- **Étapes :** garder les41 résultats historiques consultables comme archives non qualifiées ; publier seulement runs éligibles et versions prouvées ; réparer `/performance` sur vrai PostgreSQL ; relier chaque erreur à son forecast/observation cible ; prévoir job d'évaluation des échéances et abstentions durables ; ne pas appeler latest une cible2024 sans avertissement.
- **Réception :** DB/API/reload même dataset et résultats, rapports par produit/zone/horizon/saison, métriques0/0 indisponibles, preuve as-of vs rétrospective distincte ; gate R3.9 seulement sur données indépendantes, pas39 lignes héritées.

## Poursuite R4 : agroclimat et environnement

### AU-17 — Acquérir et archiver les produits agroclimatiques

- **Statut :** TODO · P1 · rôle Geo/Data · parents R4.1–R4.5 · dépendances : contrats R2.1/R1.10 et découverte R1.2.
- **Fichiers :** `connectors/{chirps,meteo_mg,fewsnet_ipc,ecmwf_open}.py`, `geo/{contracts,raster}.py`, modèles WeatherForecast/Event et fiches.
- **Étapes :** qualifier licences/URLs/formats actuels ; deux partitions CHIRPS préliminaire/finale et deux émissions météo prévues ; sous-ensemble pilote borné ; archiver bruts avant expiration ; émission/validité/grille/unité/nodata/projeté distincts ; raccordement découverte→fetch→parse→load→API, sans simple script test réservé.
- **Réception :** lecture des vrais rasters/bulletins/émissions depuis Bronze hors réseau,0pluie distinct de nodata, aucune projection IPC présentée actuelle ; absence de bulletin ou droit→unavailable, pas calendrier fabriqué. Coût CPU/stockage plafonné avant acquisition.

### AU-18 — Anomalies, calendriers, carte climat et gate R4

- **Statut :** TODO · P1 · rôle Geo/Frontend · parents R4.6/R4.7/R4.11/R4.12 · dépendances : AU-17 et sources du calendrier reçues.
- **Fichiers :** `geo/{anomalies,calendar,contracts}.py`, taxonomy/crop_calendar.yaml, routes/page climat.
- **Étapes :** baseline réelle documentée, agrégation zonale/CRS/surface/pixels valides ; rattacher chaque calendrier et corridor à document/page/version ; drapeaux verified contrôlés, pas preuve par booléen ; saison/variété/cycle/campagne préservés ; couches météo observée/prévue/calendrier séparées avec disponibilité et confiance adaptées.
- **Réception :** agrégat calculé à la main et contre-référence réelle, zone inconnue refusée, double campagne et hors-validité contrôlées ; absence de climatologie→abstention ; gate R4 MUST sans attendre les trois SHOULD mais sans fausse météo de repli.

### AU-19 — Trois extensions environnementales facultatives

- **Statut :** TODO · P2 · rôle Geo · parents R4.8/R4.9/R4.10 SHOULD · dépendance : uniquement si aucun MUST éligible et dépendances R satisfaites.
- **Sous-lot satellite :** acquisition STAC autorisée à créer, assets/bandes/SCL/masque cultivé/baseline versionnés, dérivé stocké avec hash et exposé. Conserver les fonctions NDVI/VCI déjà présentes. Pixels insuffisants→unavailable ; aucune tonne déduite du NDVI seul.
- **Sous-lot FIRMS :** connecteur réellement absent à créer après contrat/ADR, clé humaine si nécessaire, capteur/temps/confiance et dédoublonnage ; anomalie thermique distincte de surface brûlée/dégâts.
- **Sous-lot GloFAS/EWDS :** connecteur absent à créer après vérification couverture/droits/contrat, émissions/horizons/ensembles/unités archivés ; risque hydrologique prévu distinct de dommage observé.
- **Réception :** un petit périmètre réel/source par sous-lot, limites UI et API, replay borné et attribution. À défaut, documenter la non-livraison facultative ; aucun retard imposé aux MUST pour ces raffinements.

## Poursuite R5 : offre et décision

### AU-20 — Quantités, qualité et bilan d'offre

- **Statut :** TODO · P1 · rôle Data/Agri · parents R5.1/R5.2/R5.3/R5.6 · dépendances : sources commerce/production et contrats R2/R4 applicables.
- **Fichiers :** `connectors/market_supply.py`, `supply/{contracts,quality,balance}.py`, modèles stocks/arrivages et API.
- **Étapes :** remplacer les chemins file:// institutionnels supposés par dépôt réellement fourni ou acquisition autorisée, avec droits et provenance ; production/arrivages/stocks cibles distinctes ; unité/niveau/marché/couverture/jour sans donnée vs zéro explicites ; distinguer import et arrivage pour éviter double compte ; aucune vente/perte inconnue inventée dans le bilan observé.
- **Réception :** au moins un vrai petit corpus quantitatif légal relu API/DB/Bronze ; équation de conservation indépendante et cas double compte ; année nationale FAOSTAT non présentée comme stock de marché. Corpus absent→protocole et HANDOFF précis, module non qualifié.

### AU-21 — Récolte, pics d'arrivage et production facultative

- **Statut :** TODO · P1 · rôle Agri/ML · parents R5.4/R5.5/R5.7 · dépendances : AU-18/AU-20 et R5 exact ; R5.5 facultatif.
- **Fichiers :** `supply/{harvest_window,peak_forecast,production_model}.py`, évaluations/rapports.
- **Étapes :** fenêtres par bassin/cycle et campagne prouvés, décalage logistique documenté ; suffisance de deux campagnes selon couverture et grain, pas deux dates espacées ; observation de pics à partir de quantités, jamais minima de prix ; tests chronologiques indépendants et erreurs de timing/volume ; modèle superficie×rendement seulement avec référentiels et conversion vérifiés.
- **Réception :** pas d'historique→baseline qualitative ou abstention clairement nommée, pas0,81 sans mesure ; erreur de pic décalée volontairement détectée ; production optionnelle sans références ne publie aucune tonne qualifiée. Le lien bassin→marché ne provient pas d'une simple proximité.

### AU-22 — Parcours métiers et copilote utiles

- **Statut :** TODO · P1 · rôle Produit/Backend/Frontend · parents R5.8/R5.9/R6.1–R6.4 · dépendances : gates métier applicables avant usage de leur capacité.
- **Fichiers :** `supply/decision_pilot.py`, `core/pilot.py`, `copilot/{workflow,agent,executor,writer,tools}.py`, pages/copilot/scénarios et protocoles pilote.
- **Étapes :** expliciter question/action pour institution, acheteur et planificateur ; rendre les paramètres et hypothèses persistants/versionnés avec auteur/temps, séparer du fait observé ; outils typés lecture seule et budget, SQL AST/rôle Gold ; citations relues jusqu'aux observations et documents ; boucle bornée, aucune source activée ni commande d'achat générée ; eval en français sur erreurs sémantiques et injections.
- **Raccordements constatés manquants :** résolution produit du copilote encore sur codes hérités ; valeur_kind observed attribuée même à un résultat vide et provenance certifiée par texte constant ; moteur de workflow séparé de CopilotAgent.ask. Partager le référentiel canonique, dériver le type/provenance des résultats réels et brancher le moteur seulement pour les parcours qui en ont besoin ; conserver le repli déterministe honnêtement nommé, sans prétendre un provider testé.
- **Réception :** trois parcours recomputables et cinq questions réelles, résultats API/DB/reload ; pas de24500tonnes imposées ; aucune réponse LLM numérique sans fait ; provider replay explicitement OFFLINE_TESTED si H1 ; essai humain reste NOT_EVALUATED tant que non réalisé. Les gates R5/R6 ne se déduisent pas du nombre de templates.

### AU-23 — Bulletin et alertes à partir de faits recevables

- **Statut :** TODO · P1 · rôle Backend/Data · parents R6.5/R6.6 · dépendances : AU-05 et données/capacités reçues selon R.
- **Fichiers :** `bulletin/{facts,writer,semantic_guard,render,service}.py`, `alerts/{rules,engine,notifier}.py`, API/pages et jobs.
- **Étapes :** qualifier les brouillons existants séparément, sans rééditer leur histoire ; faits versionnés reliés à observations/runs, placeholders et direction/sens/type vérifiés ; calendriers et familles indépendantes pour alertes, silence≠rupture ; déduplication/résolution/reprise et approbation durable ; calendrier hebdo réellement relié au job, Mailpit uniquement.
- **Réception :** PDF/HTML/SQL mêmes faits et citations après restart ; hausse↔baisse volontairement inversée rejetée ; WFP/RTFP ne comptent pas deux preuves indépendantes ; aucun faux risque sans quantités ; aucun envoi externe et aucune approbation interprétée comme levée de H3.

## Exploitation et réception finale

### AU-24 — Supervision et sauvegardes durables

- **Statut :** TODO · P1 · rôle Backend/Ops · parents R6.8/R6.9 · dépendances : AU-07, R0.8 et autres capacités requises.
- **Fichiers :** `ops/{supervision,backup_restore}.py`, jobs/sensors, meta/ops, `/sources`, runbooks.
- **Étapes :** remplacer listes/set en mémoire par incidents/états/version/outbox durable selon ADR ; relier effectivement arrêt source/publication/qualité/budget ; preuve réelle de capture Mailpit, pas booléen positionné ; backup SQL+inventaires Bronze/dérivés/modèles/bulletins ; restore dans un clone neuf, comparer contenu et droits ; conserver sources de runtime hors worktree de développement mutable et documenter relance WSL.
- **Réception :** restart pendant incident conserve l'état, aucune collecte interdite après arrêt ; absence de sauvegarde et checksum corrompu échouent ; ancien bulletin/document lisibles après restore ; volumes actifs strictement inchangés. Aucune réexécution live juste pour tester le tableau DataOps.

### AU-25 — Performance, accessibilité et paquet local prêt

- **Statut :** TODO · P1/P2 · rôle QA/Ops/Frontend · parents R6.7/R6.10 · dépendances : lots applicatifs et gates préalables reçus.
- **Fichiers :** tests API perf, Playwright, Compose prod/Caddy, Dockerfiles et runbooks.
- **Étapes :** profil figé et représentatif,100 requêtes mesurées après10 échauffements et cinq clients par endpoint agrégé ; distinguer API/proxy/browser, volume et ressources ; clavier/contraste et parcours mobile complets ; scanner images/dépendances/secrets courants ; config prod refuse secrets démo, services sensibles non exposés ; imports ML paresseux seulement si mesures confirment le coût, sans supprimer les calculs réels.
- **Agent Visual Bridge :** retrouver l'installation et son contrat avant d'agir, vérifier configuration versionnée expurgée, démarrage local et échange de revue réel ; la seule image Docker présente n'est pas une intégration. Réutiliser le composant existant, ne pas importer de secrets ni supposer une continuation automatique de session externe. Ce contrôle d'outillage ne remplace aucun gate métier.
- **Réception :** p50/p95/max/erreurs et périmètre consignés, objectifP95<1s, aucun résultat issu des mesures de compilation de cet audit ; installation neuve et mise à niveau clone ; paquet local prêt sans achat/provisionnement. Déploiement et test humain demeurent qualifications distinctes.

### AU-26 — Gates finaux et passation honnête

- **Statut :** TODO · P1 · rôle Coordinateur/QA · parent R6.11 · dépendances : R0.9/R1.13/R2.11/R3.9/R4.12/R5.9 et R6.1–R6.10 DONE.
- **Étapes :** auditer chaque preuve et état parent ; environnement isolé neuf/corpus authentique ; rebuild sans réseau, qualify all, check complet, API/DB/reload, navigateur, citations, bulletin/Mailpit, permissions/restauration ; comparer matrices capacités/statuts et docs ; demander seulement les interventions humaines réellement indispensables selon HANDOFF, sans arrêter les travaux indépendants.
- **Réception nominale :** tous critères MUST avec preuves originales ; aucun fait fabriqué ni provenance invalide publié ; rapport et HANDOFF actuels ; nouveau tag final autorisé seulement ici. Les SHOULD manquants sont explicitement nommés et ne deviennent pas des MUST implicites.
- **Réception partielle :** corpus/droit/usage humain absent→limite et action précise par tâche, aucun tag final ni « succès100% ». Un problème technique corrigeable suit le protocole de blocage, pas une demande de confirmation générale.

## Conditions de reprise et preuves minimales

Pour chaque lot : ID, parent R, état, SHA avant/après, chemins modifiés, environnement/destination, commandes et codes, effectifs et dénominateurs, JUnit/reçus natifs, empreinte, limites et action suivante. Toute affirmation non mesurée reste NOT_EVALUATED. Les tests d'un helper ne suffisent pas à recevoir sa route SQL ni son parcours utilisateur.

**Prochain travail éligible après restitution : AU-01**, préparé avec AU-02/AU-03 pour supprimer les fausses données sur les surfaces principales. Les corrections de sécurité AU-04–07 font partie de la même première livraison sûre si le périmètre peut être stabilisé ; sinon livraisons fonctionnelles distinctes avec leur propre réception. Ne pas commencer AU-10 ni une nouvelle fonctionnalité dépendante avant R0.9.

Mise à jour de réception : AU-01/02/03/05 corrigés et reçus logiciellement sur5400f39 ; [preuves complètes](../../evidence/safe-facts-20261025/RECEPTION.md). La suppression des faux faits et l'abstention ne qualifient pas les sources/modèles ni les fonctionnalités R aval. Prochain correctif AU-04, en développement séparé ; AU-06/07 restent ouverts avant réparation/requalification du socle. Les instructions « après restitution » ci-dessus décrivent l'ordre initial, pas une demande de recommencer AU-01.
