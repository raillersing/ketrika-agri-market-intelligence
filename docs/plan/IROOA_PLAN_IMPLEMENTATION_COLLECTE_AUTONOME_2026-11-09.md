# IROOA — Plan d'implémentation : collecte autonome, historique et vérifiable

**Version proposée :** 1.0 — 9 novembre 2026  
**Destination dans le dépôt :** `docs/plan/IROOA_AUTONOMOUS_DATA_IMPLEMENTATION_PLAN.md` (proposition, **non encore intégrée**).  
**Dépôt inspecté :** [`raillersing/ketrika-agri-market-intelligence`](https://github.com/raillersing/ketrika-agri-market-intelligence), branche par défaut consultée le 9 novembre 2026.  
**Statut :** planification uniquement ; aucun changement déployé ni tâche marquée DONE.

## 1. Décision et règles applicables

**Décision :** faire évoluer les connecteurs existants en système autonome d'acquisition de données ouvertes et autorisées, avec backfill, qualification, publications indépendantes et supervision. **Conserver** FastAPI, PostgreSQL/PostGIS, MinIO, Next.js, Docker et Dagster. Ne pas réécrire le produit.

Le document est subordonné à `AGENTS.md`, `docs/plan/SPECS.md`, `docs/plan/MARKET_INTELLIGENCE_EXECUTION_PLAN.md`, `docs/plan/DECISIONS.md`, `docs/plan/PROGRESS.md` et `docs/plan/DATA_PRODUCT_IMPROVEMENT_PLAN.md`. Le présent plan ne crée pas de statuts R concurrents. Les identifiants IA-DATA ci-dessous sont des **sous-lots de livraison**, à rattacher aux tâches R, lots DP et ADR applicables, après vérification de leurs dépendances.

Invariants :
1. Aucune ligne de marché inventée pour « peupler » la production ; données synthétiques/fixtures confinées à des environnements QA et clairement étiquetées.
2. Provenance vérifiable de chaque observation vers son `meta.source_record` et l'objet Bronze original ; SHA-256 ; archive non modifiable.
3. Révisions append-only : pas d'écrasement silencieux des valeurs historiques ; édition et date de disponibilité conservées.
4. Observé, imputé par l'éditeur, interpolé, prédit par Irooa et inconnu : statuts distincts à chaque couche et dans l'UI.
5. Droits, robots/ToS, quotas, restrictions de redistribution et attribution qualifiés avant activation par source ; pas de contournement des 401/403/CAPTCHA.
6. Toute migration SQL/contrat ou nouvelle dépendance doit passer par ADR/SPECS quand `AGENTS.md` l'exige.
7. Aucune collecte globale ni ordonnanceur activé en production avant recette sur clone, approbation des gates normatifs et backfill borné ; pas de modification de Casino-mdg.

## 2. Photographie de référence à préserver

Résultats VPS fournis lors des échanges (état observé le 8 novembre 2026, **pas** une mesure garantie pour le 9) :

| Indicateur | Observation fournie | Qualification |
|---|---:|---|
| Sources répertoriées | 20 | Métadonnées, pas 20 flux actifs |
| Connecteurs éligibles | 14 | Filtre de politique, pas preuve de collecte réelle |
| Connecteurs avec exécution `success` lors d'un lancement | 5/14 | Quatre autres sources ont obtenu 0 observation |
| Exécutions `failed` lors de ce lancement | 9/14 | Causes individuelles non encore diagnostiquées |
| Documents Bronze | 5 | Trois sources ; à rapprocher des objets réels |
| Observations de prix Banque mondiale | 120 | 119 `pending`, 1 `accepted` à la date du diagnostic |
| Vue Gold prix | 1 ligne dans chacune des trois vues | Publication réussie, couverture très étroite |
| Domaine / backend | `irooa.store`, `127.0.0.1:3005`, `127.0.0.1:8090` | Tunnel Cloudflare ; API privée |
| Orchestration de production | `docker compose config --services` a listé `db`, `minio`, `api`, `web` | Dagster n'a pas été observé parmi ces services ; recontrôler le compose actif |

Le poste Windows conserve `aiagent-db-1`, `aiagent-minio-1`, et plusieurs volumes de QA/rejeu ainsi que des sauvegardes PostgreSQL. **L'existence des volumes n'atteste pas la qualité des données qu'ils contiennent.** L'audit indépendant du 5 novembre 2026 a identifié des scripts de génération de valeurs synthétiques et de fausses preuves de provenance possibles ; vérifier le contenu actif avant import. [Audit](https://github.com/raillersing/ketrika-agri-market-intelligence/blob/main/docs/audits/2026-11-05-INDEPENDENT_AUDIT.md).

## 3. Architecture : réutiliser plutôt que remplacer

Flux cible : `SourceRegistry → Discover/Version → Fetch/Backfill → Bronze/S3 immutable → Parse/Normalize Silver → Quality/Provenance gates → Gold par domaine → API/UI`, orchestré par Dagster.

**Réutiliser les modules existants :**
- `backend/src/ketrika/connectors/base.py`, `registry.py`, `discovery.py`, `manual_collection.py` ;
- `durable_phases.py`, `batch_ledger.py`, `document_partitions.py`, `silver_attempts.py` pour reprises et rejouabilité ;
- `core/bronze.py`, `core/policy.py`, `core/provenance*.py`, `core/schema_*.py` ;
- `normalize/price_loader.py`, `normalize/price_references.py`, `core/geo.py`, `taxonomy/` ;
- `gold/refresh.py`, `gold/*_gate.py` ;
- `pipelines/factory.py`, `pipelines/source_definitions.py`, `pipelines/definitions.py`.

**Extensions proposées** (répertoires/couches à créer seulement si le code actuel ne fournit pas déjà l'équivalent) :

```text
backend/src/ketrika/
  connectors/adapters/       # rest_paged, archive_bulk, tabular, pdf, spatial
  connectors/catalogs/       # découverte d'éditions et métadonnées par fournisseur
  ingestion/                 # plans de backfill, checkpoints, rapport de santé
  geo/                       # référentiel de marchés versionné, géorésolution qualifiée
  gold/                      # publication ciblée par domaine et preuves de qualification
  observability/             # causes d'échecs redigées, données de couverture/fraîcheur
backend/tests/               # corpus réels archivés, adversariaux, replay et intégrations
web/src/                     # disponibilité par source, qualité, fraîcheur, états vides
```

**Changements éventuels de schéma (ADR + migration additive obligatoire)** : examiner d'abord les tables existantes. Si elles sont insuffisantes, prévoir métadonnées de version d'édition, curseur de collecte par source/partition, statut de tentative, contrat d'extraction versionné, marché propre au fournisseur, identifiants administratifs datés, et décisions de revue. Ne jamais créer des tables redondantes sans cartographie des modèles existants.

## 4. Plan de livraison : 11 sous-lots, ordre de dépendance

| Sous-lot / priorité | Implémentation concrète | Critères de réception minimum | Rattachement indicatif |
|---|---|---|---|
| **IA-DATA-00 — P0 : inventaire et clone [DONE]** | Auditer `aiagent` local : comptages par table/source/méthode, SHA et présence S3, versions Git ; créer `pg_dump -Fc` et sauvegarde des objets ; restaurer en clone isolé. Relever images et migrations Contabo. | Inventaire chiffré, sources non vérifiées identifiées, restauration testée, zéro écriture sur prod. | DP-2 ; R0.9 ; audit C1/C2 |
| **IA-DATA-01 — P0 : garde-fous [DONE]** | Bloquer chemins synthétiques vers Gold, rendre leur isolement testable ; interdire toute auto-acceptation ou source-record fictif ; vérification de preuves source-cellule. | Tests négatifs prouvent qu'une valeur synthétique ou un objet absent est refusé ; aucun Bronze supprimé. | DP-2 ; R0.9 ; ADR si contrat |
| **IA-DATA-02 — P0 : diagnostics et santé [DONE]** | Exposer `downloaded / parsed / normalized / published / no_data / policy_blocked / schema_drift / failed` ; cause stable en base, détail technique protégé côté serveur ; panneau par source. | Une source `success` avec 0 observation est visible comme telle ; 9 échecs récupèrent un code diagnostique exploitable sans secrets. | DP-3 ; R1.1/R1.12 |
| **IA-DATA-03 — P1 : adaptateurs communs** | Ajouter pagination bornée, streaming contrôlé, `ETag`/`Last-Modified`, checkpoints, retries/backoff et gestion des quotas ; politiques SSRF et tailles maximales. | Simulations de 429/503/coupure/doublon/révision ; reprise à la bonne page, aucun saut ni duplicat, logs sans secret. | DP-3 ; R1.2/R1.12 |
| **IA-DATA-04 — P1 : RTFP historique** | Exploiter les archives complètes Banque mondiale + métadonnées, plutôt que `manual_wb.py` limité à 120 ; conserver la qualification nationale actuelle et développer séparément tout élargissement marchés/produits. | Rejeu déterministe des deux éditions d'épreuve, différences de versions et codes produits vérifiés ; import identique deux fois sans doublon ; provenance cellule→ZIP. | DP-3 ; R0.8/R0.9/R1.8 |
| **IA-DATA-05 — P1 : marchés et géographie** | Charger des limites datées et référentiels de marchés authentiques ; apparier par identifiant source, pcode daté ou point validé ; proposer des alias avec preuve et revue. | Aucun rattachement arbitraire ; toutes les correspondances validées traçables ; les 119 `pending` ne sont pas approuvées en masse. | DP-2/5 ; R1.10/R2.10 |
| **IA-DATA-06 — P1 : Gold indépendant** | Conserver les contrôles stricts mais séparer refresh Prix / Commerce / Climat / Macro, avec dépendances explicites et publication atomique par domaine. | Une erreur Macro n'empêche pas une publication Prix valide ; aucune vue non qualifiée rendue publique. | DP-4 ; R2.3/R2.4 + ADR |
| **IA-DATA-07 — P1 : prix multisources** | Réparer WFP HDX HAPI avec identifiant d'app, pagination, marché/prod/date/unités ; introduire FAO FPMA si contrat/licence et couverture vérifiés. | Éditions réelles, champs/valeurs recoupés avec source, biais de double comptage WB↔WFP↔FAO documenté. | DP-3/4 ; R1.7/R2 |
| **IA-DATA-08 — P2 : statistiques & économie** | FAOSTAT API actuelle/export, OpenStat/INSTAT, BFM, OMH ; Douanes / Comtrade selon preuve d'accès, fréquence et droits. | Une série réelle qualifiée par famille avant activation des widgets ; unité/base/année/vintage corrects ; aucune valeur de remplacement. | DP-3/4 ; R1.3–R1.9/R2 |
| **IA-DATA-09 — P2 : agroclimat** | NASA POWER/CHIRPS et sources autorisées ; tuilage/partitions de Madagascar, produits raster traités hors charge web. | Échantillons géospatiaux vérifiés, attributs temporels et résolution explicites, ressources contenues. | R4 ; DP-4/5 |
| **IA-DATA-10 — P2 : automatisation et recette** | Activer Dagster (après vérification compose), cadences par source, pools, quotas, alertes, monitoring, backups et déploiement progressif. | 1 source certifiée pilotée automatiquement puis élargissement source par source ; rollback éprouvé ; Casino inchangé. | R1.12/R6 ; DP-3 |

**Parcours critique :** `00 → 01 → 02 → 03 → 04 → 05 → 06 → 07 → 10`. `08` et `09` sont indépendants une fois les fondations prêtes ; ne pas attendre les modèles IA pour réussir une première ingestion.

**Règle de reprise normative :** chaque lot doit vérifier son éligibilité R réelle, ses dépendances et les éventuels gates humains. Les statuts indiqués « IN_PROGRESS » dans les plans historiques ne doivent pas être déclarés DONE au seul vu d'un test ciblé antérieur.

## 5. Détail du premier pilote : World Bank RTFP

1. **Découverte d'édition** : lire le catalogue de Madagascar, version, date de publication, licence et liens de téléchargement, sans URL inventée. Vérifier que le fichier et la métadonnée correspondent à la même édition.
2. **Backfill** : priorité au ZIP officiel archivé dans Bronze ; alternative API limitée à 1 000 lignes par page, pagination `offset` et contrôles des compteurs. Garder un curseur par édition/partition ; limite globale configurable et journalisée.
3. **Extraction** : séparer corpus déjà qualifié « national `c_rice` imputé depuis 2020 » du **nouveau périmètre à qualifier** « marchés / riz-sucre-farine ». Ne pas élargir le parser d'archive nationale au niveau marché par réinterprétation implicite.
4. **Géographie** : sauvegarder nom de marché, coordonnées d'éditeur, identifiant fournisseur et subdivision ; ne publier une zone normalisée qu'après rapprochement fondé. Préserver `location_raw` et la file de revue.
5. **Révisions** : édition N et N+1 peuvent corriger des mois anciens. Comparer les éditions, versionner les modifications et mettre à jour uniquement la référence « dernière édition qualifiée » ; conserver le passé pour analyses as-of.
6. **Validation** : le taux de lignes valides, ignorées, en attente et rejetées doit être explicite ; un échec de schéma bloque la partition visée, pas les publications Gold non dépendantes.
7. **Publication** : disposer d'un prix avec provenance, période, stade de vente et statut `imputed` si cette valeur a été estimée par l'éditeur. L'UI ne doit pas la présenter comme un relevé terrain.

Les tests doivent utiliser d'abord les **deux éditions archivées** déjà mentionnées dans les documents du projet (163 lignes de rejeu au périmètre historique R0.8, chiffre documentaire à revalider) ; ne pas les confondre avec la taille de l'archive complète moderne.

## 6. Séquence de PR / branches proposée

Branches descriptives, **sans forcer le workflow normatif du dépôt** :

| PR | Objet | Déploiement production autorisé ? |
|---|---|---|
| PR-A | Inventaire, evidence snapshot et documentation de l'état | Non, diagnostic seulement |
| PR-B | Interdiction des données synthétiques publiables + tests | Après recette complète et approbation des gates |
| PR-C | Causes d'erreur fiables et source health | Après tests, sans planifications automatiques |
| PR-D | Pagination et backfill RTFP versionné | Non tant que le clone n'a pas réussi |
| PR-E | Marchés / géocodage daté / migrations additives | Après backup+restore testés et validation métier |
| PR-F | Gold Prix indépendant | Après tests provenance et atomicité |
| PR-G | WFP + FPMA source-par-source | Activation séparée, par flag, après droits/test |
| PR-H | FAOSTAT/économie et agroclimat | Activation séparée |
| PR-I | Dagster / supervision / limites de charge | Une source pilote d'abord, pas `all sources` |

Pour chaque PR : `AGENTS.md` et spécifications appliqués ; ADR si besoin ; tests unitaires et d'intégration ; corpus réel + corpus adversarial ; `bash scripts/dev.sh check` sur lot stabilisé, QA et E2E applicables ; rapport de preuve avec SHA exact ; statut `PROGRESS.md` mis à jour uniquement après réception, sans retoucher les tags historiques. CI du dépôt : [`.github/workflows/ci.yml`](https://github.com/raillersing/ketrika-agri-market-intelligence/blob/main/.github/workflows/ci.yml).

## 7. Déploiement Contabo sans interruption du Casino

### Préproduction et sécurité
- Ne **pas** réutiliser la base `irooa-prod` pour les tests de backfill, ni le bucket Bronze de production. Utiliser un compose `irooa-staging`, bases et buckets distincts, ports uniquement localhost, aucune publication Cloudflare publique avant les tests.
- Réviser l'état exact du déploiement via `docker compose ls`, `docker compose config --services`, santé Docker, migrations et versions d'image ; les services Dagster ne figuraient pas dans la liste constatée lors du déploiement initial.
- Faire une sauvegarde PostgreSQL cohérente (`pg_dump -Fc`) **et** sauvegarder les objets Bronze correspondants ; vérifier restauration, compatibilité du schéma et SHA de chaque objet.
- Déployer avec images versionnées par SHA/digest, paramètres de ressources et secrets protégés ; ne jamais tester un import en tant que superutilisateur SQL si un rôle applicatif dédié convient.
- Garder Casino-mdg et ses ports inchangés. Irooa reste derrière Cloudflare Tunnel sur `127.0.0.1:3005`; API privée sur `127.0.0.1:8090`.

### Activation progressive
1. En staging : importer une édition et mesurer volume, latence, CPU/RAM/IO, lignes acceptées vs pending, qualité, logs et taille Bronze.
2. Sur production : déployer **le code sans activer** la nouvelle planification ; appliquer uniquement les migrations additives reçues ; vérifier santé et régression des écrans.
3. Activer le pilote RTFP avec `feature flag` de source, backfill borné et quota défini ; observer l'ensemble du chemin jusqu'à Gold.
4. Comparer résultats SQL ↔ API authentifiée ↔ UI, versions et historique ; publier seulement si les contrôles sont verts.
5. Autoriser une cadence automatique propre à la source, avec une fenêtre et des budgets. Ajouter les sources une par une.
6. Rollback : revenir au digest applicatif précédent, désactiver le flag/planification ; **ne pas détruire Bronze ni réécrire les événements**. Pour migration irréversible, élaborer une procédure de compensation avant activation.

## 8. Critères de succès et métriques (objectifs proposés, non constatés)

| Métrique | Définition opérationnelle | Réception proposée |
|---|---|---|
| Provenance Gold | `valeurs Gold possédant une preuve Bronze intacte / valeurs Gold` | 100 % |
| Réutilisation du même artefact | Nouveaux doublons après second rejeu identique | 0 |
| Attribution artificielle | Lignes synthétiques ou non justifiées présentées comme « observées » | 0 |
| Couverture publiée | Produit × marché × période × nature de la valeur réellement disponible | Compteur exposé ; pas de chiffre arbitraire |
| Fraîcheur | Délai entre la dernière édition **attendue** et la dernière édition publiée | SLO par source selon cadence de l'éditeur |
| Réussite de collecte | Runs terminés normalement / runs réellement tentés ; `no_data` compté séparément | Cible proposée ≥95 % sur 30 jours pour chaque source qualifiée, après rodage |
| Échecs silencieux | Échecs sans code stable ni référence d'incident | 0 |
| Récupération | Relance d'un lot interrompu sans dupliquer l'existant | Réussi sur tests de coupure/réessai |
| Isolation de domaine | Gold Prix publié malgré erreur Macro non liée | Test E2E positif |
| Performance/hébergement | RAM, CPU, IO, disque et durée de backfill réellement mesurés | Limites ajustées sur mesure ; pas de supposition de capacité illimitée |

Ne jamais réduire le nombre de lignes `pending` en changeant leur statut sans preuve ; le nombre de lignes Gold n'est pas un KPI de qualité à lui seul.

## 9. Risques, décisions, interdits

- **SSRF** : discovery et téléchargement ne doivent suivre que des domaines autorisés, vérifier les résolutions DNS, refuser les IP internes et revalider chaque redirection, selon la fiche OWASP ; interdire les URL arbitraires administrables depuis l'UI sans contrôle.
- **Licences commerciales** : chaque jeu a ses propres obligations d'attribution/redistribution ; World Bank demande citation et interdit l'impression d'endossement. Les données satellites ne sont pas automatiquement libres de toute condition d'utilisation. Google Earth Engine nécessite une configuration payante pour l'usage commercial opérationnel si ce service est choisi ; aucune dépendance à celui-ci n'est requise par le pilote.
- **Accès authentifié** : HAPI exige un identifiant d'application ; stocker les jetons uniquement en variables d'environnement/gestionnaire de secrets, jamais dans les logs ni le dépôt.
- **Dépendance statistique** : WB RTFP réutilise WFP/FAO ; ne pas compter deux fois la même observation comme validation indépendante.
- **Géographie historique** : conserver le découpage administratif à la date de référence ; ne pas forcer les 119 observations pending vers une région « par défaut ».
- **Dérive des fournisseurs** : JSON/CSV/PDF peuvent changer ; bloquer les éditions non conformes tout en préservant les versions Gold anciennes qualifiées.
- **Disponibilité** : la collecte automatique n'est pas équivalente à la publication garantie. En cas d'absence ou de panne de source, afficher la dernière édition connue, sa date et son statut.
- **H3/H7/H4** : aucun envoi de messages à des tiers ni connecteurs de marketplaces privées dans le MVP sans autorisation correspondante ; les propositions de partenariat peuvent rester des brouillons.

## 10. Actions initiales, prêtes pour développement

**Premier lot implémentable après audit documentaire :** IA-DATA-00 + IA-DATA-01, puis IA-DATA-02. Cela inclut :
- lire la constitution AGENTS, les dépendances R0.9 et les derniers statuts PROGRESS ;
- créer un inventaire readonly du PostgreSQL et MinIO `aiagent` ; identifier dates, types, méthodes d'extraction et liens Bronze ;
- produire et tester des sauvegardes sur clone, sans import direct dans `irooa-prod` ;
- écrire les tests qui prouvent qu'une donnée synthétique ne peut franchir Gold et que les données `observed`, `imputed` et `forecast` ne sont pas confondues ;
- préserver dans le plan la dette liée à `manual_collection.py` (refresh Gold global, exceptions génériques) et à `manual_wb.py` (`limit=120`) ;
- rédiger les ADR requis pour les nouveaux contrats, puis avancer sur le backfill archivistique qualifié.

**Décisions restant conditionnelles à une preuve :** schéma réellement nécessaire après inspection des tables ; contenu authentique des volumes locaux ; existence/permissions des éditions WFP/FPMA; granularité complète des marchés et géographies ; budget CPU/RAM/stockage après essai réel. Ne pas les « valider » par intuition.

## 11. Sources vérifiables

**Code et doctrine du projet :**
- [AGENTS.md](https://github.com/raillersing/ketrika-agri-market-intelligence/blob/main/AGENTS.md)
- [DATA_PRODUCT_IMPROVEMENT_PLAN.md](https://github.com/raillersing/ketrika-agri-market-intelligence/blob/main/docs/plan/DATA_PRODUCT_IMPROVEMENT_PLAN.md)
- [MARKET_INTELLIGENCE_EXECUTION_PLAN.md](https://github.com/raillersing/ketrika-agri-market-intelligence/blob/main/docs/plan/MARKET_INTELLIGENCE_EXECUTION_PLAN.md)
- [manual_collection.py](https://github.com/raillersing/ketrika-agri-market-intelligence/blob/main/backend/src/ketrika/connectors/manual_collection.py)
- [manual_wb.py](https://github.com/raillersing/ketrika-agri-market-intelligence/blob/main/backend/src/ketrika/connectors/manual_wb.py)
- [rtfp_archive.py](https://github.com/raillersing/ketrika-agri-market-intelligence/blob/main/backend/src/ketrika/connectors/rtfp_archive.py)
- [durable_phases.py](https://github.com/raillersing/ketrika-agri-market-intelligence/blob/main/backend/src/ketrika/connectors/durable_phases.py)
- [gold/refresh.py](https://github.com/raillersing/ketrika-agri-market-intelligence/blob/main/backend/src/ketrika/gold/refresh.py)
- [Audit indépendant 2026-11-05](https://github.com/raillersing/ketrika-agri-market-intelligence/blob/main/docs/audits/2026-11-05-INDEPENDENT_AUDIT.md)

**Fournisseurs et sécurité :**
- [Banque mondiale : Madagascar RTFP, catalogue et éditions](https://microdata.worldbank.org/catalog/8240) ; [API](https://microdata.worldbank.org/catalog/8240/data-api) ; [licences](https://microdata.worldbank.org/catalog/8240/get-microdata)
- [WFP/HDX HAPI : Getting started](https://hdx-hapi.readthedocs.io/en/latest/getting-started/)
- [FAOSTAT : API Developer Portal](https://www.fao.org/faostat/) ; [annonce FAO du 13 avril 2026](https://www.fao.org/statistics/highlights-archive/highlights-detail/faostat-launches-a-new-api-developer-portal-to-make-data-access-easier/en)
- [Dagster : concurrency](https://dagster.io/docs/guides/operate/managing-concurrency) ; [sensors](https://single-run-backfill-docs.dagster.dagster-docs.io/concepts/partitions-schedules-sensors/sensors) ; [backfills](https://master.dagster.dagster-docs.io/concepts/partitions-schedules-sensors/backfills)
- [OWASP SSRF Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html)
- [PostgreSQL 17 pg_dump](https://www.postgresql.org/docs/17/app-pgdump.html)
- [PostGIS ST_Covers](https://postgis.net/docs/ST_Covers.html)

---

**Conclusion d'implémentation :** commencer par sécuriser et auditer les données déjà possédées, puis livrer un pipeline RTFP historique complet et reproductible. Étendre à WFP/FPMA et à d'autres familles seulement lorsque chaque trajet a été qualifié. Déployer le code avant les activations de collecte, avec le **même processus de réception R** que le dépôt, sans perturber Casino-mdg.
