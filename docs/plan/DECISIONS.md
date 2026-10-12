# DECISIONS (Architecture Decision Records - ADR)

> Format : `ADR-NNN | date | statut | contexte | décision | alternatives | conséquences`

## ADR-040 : R0.6 — identité explicite et manifeste de références

- **Date / statut :** 2026-10-12, accepté avant transfert principal de l'incrément 9. Identifiant réservé au prototype reconstruit ; les anciens worktrees temporaires perdus ne constituent pas une preuve actuelle.
- **Contexte :** URL ou UUID du run seuls ne distinguent pas les octets, les versions de traitement et le référentiel utilisé. Ces primitives préparent le ledger mais ne le remplacent pas.
- **Décision :** identité privée immutable source_id snake_case, source_record UUID non nul, SHA contenu, version parser, version normaliseur et SHA manifeste référentiel. Clé SHA256 d'une liste JSON canonique ASCII versionnée ; clé de membre séparée avec UUID run. Versions explicites <=128 caractères sans blancs périphériques/contrôles ; SHA lowercase strict. Aucune édition/document logique inférée.
- **Manifeste :** cinq tables ref : product/product_alias/location/location_alias/unit_conversion ; une requête UNION ALL et un snapshot SQL de statement. Payloads JSONB SQL conservés textuellement, NUMERIC sans réencodage float ; clés composées JSON, tri déterministe, doublons refusés. Maximum 100000 lignes/32 MiB, pas de résultat tronqué ; flux fermé sans commit du caller. Snapshot vide = zéro références, pas référentiel qualifié.
- **Réception requise :** 27+16 unités et cinq SQL READ ONLY/REPEATABLE READ, QA 426/39 puis check Windows complet, sources figées, snapshot/preservation/scan et commit. Tests de forme/répétition/comptes/lexèmes ne certifient ni provenance des mappings ni octets d'un artefact.
- **Limites :** aucun ORM/migration/API/permission changé, archive référentiel Bronze, liaison à la transaction de normalisation, ledger, partition/reprise et document logique restent non livrés. Clé prix/robots préparatoires non transférés. R0.6 demeure IN_PROGRESS.
- **Alternatives :** URL seule, UUID run seul, concaténation avec séparateurs ou baseline inférée du contenu (rejetées).

## ADR-050 : R0.6 — propriétaires transactionnels Bronze/Silver durables

- **Date / statut :** 2026-10-11, accepté avant transfert principal ; préparation isolée validée par 104 tests unitaires et dix tests SQL.
- **Contexte :** un rollback de la transaction de données peut effacer le démarrage et le statut failed ; le succès d'un helper seul ne prouve pas la durabilité du pipeline.
- **Décision :** la factory confie Bronze et Silver à des propriétaires privés. Garde de collecte avant démarrage ; Source SQL déjà persistée obligatoire, jamais créée/activée implicitement. Démarrage meta dans une session indépendante, données dans une autre ; référence explicite UUID/source/date/dagster vérifiée sous verrou. Après échec : rollback des données puis failed/classe/date dans une session indépendante. Silver reprend exclusivement le batch et la référence SQL running.
- **Erreurs :** conserver seulement type(error), sortir du bloc except avant persistance et exception finale ; aucun message collecté ni objet d'erreur dans __context__. Reçu impossible = failure_receipt_unavailable, jamais succès ni affirmation de failed durable. Compteurs de phases échouées restent transactionnels ; Bronze immuable conservé.
- **Alternatives :** commit de la transaction du caller (rejeté, risque d'écritures partielles), statut uniquement Dagster (insuffisant pour API SQL).
- **Conséquences / limites :** aucun changement ORM ni dépendance ; wrapper caller historique inchangé et non qualifié durable. Ledger/reprise/partitions, arrêt brutal, sources live et notifications restent distincts. Douze checks et graphe Gold reçus en ADR-049 conservés ; aucun gate levé.

## ADR-049 : R0.6 — adoption du contrôle structurel et du Gold connecté

- **Date :** 2026-10-11 ; accepté avant transfert principal de l'incrément 6. Les numéros intermédiaires restent réservés aux préparations isolées, non adoptées implicitement.
- **Contexte :** provenance source mesurée reçue, mais Gold Dagster sans dépendances Silver et aucun contrôle structurel réel. Préparation indépendante : huit scénarios SQL/S3 code final 0, dont six Gold/provenance/CSV/JSON et deux helpers durables ; seuls les six premiers concernent cette adoption.
- **Décision :** contrats CSV/JSON fermés, code-owned et versionnés, jamais appris du contenu ; absent ou MIME discordant = unknown/refus. CSV UTF-8/BOM, colonnes requises/optionnelles explicites, doublons/largeur/colonnes inattendues refusés. JSON typé sans coercition, clés dupliquées/constantes non finies refusées et tokens numériques exacts. Diagnostics fixes et SHA/compteurs seulement ; aucun contenu exécuté.
- **Bornes :** document 32 MiB ; CSV 256 colonnes/noms 256 caractères ; JSON profondeur 128, contrat 32 niveaux/4096 nodes, traversal 100000 nodes. Audit au maximum 100000 artefacts réellement référencés par six tables d'observations, historique/rejeté inclus, références et SHA relus dans Bronze, lecture dédupliquée. Vide failed/metric NULL, aucune certification de 100 % sur vide.
- **Raccordement :** chaque bundle source porte exactement provenance_complete et schema_drift natifs blocking ERROR sur son Silver. Reçu structure append-only ops.dq_result, threshold 0/metric nombre non vérifié, commit indépendant du check avant résultat. Repository Gold construit avec dépendances Silver exactes ; helper SQL de refresh et export historique conservés. Inventaire 15 assets/12 checks/six schedules ; statuts et droits de collecte inchangés.
- **Limites :** structure valide n'est ni qualification de parsing/conversion/source ni preuve de prix. Aucun contrat de source publique inféré ou automatiquement enregistré ; exécutions sans baseline restent refusées. Garde structure SQL directe/CLI, ledger/partitions/reprise et durabilité des pipelines restent distincts à recevoir. Helpers de runs et autres préparations non transférés dans ce lot. Réception principale ciblée et check Windows intégral requis après transfert.
- **Alternatives rejetées :** check constant, contrôle uniquement Pydantic, apprendre le premier en-tête, ignorer champs inconnus, Gold sans prérequis ou annonce de qualification live à partir de fixtures.

## ADR-039 : R0.6 — observabilité API sans cache Gold

- **Date :** 2026-10-11 ; accepté avant transfert principal. Identifiant conservé du prototype isolé ; ADR-038 de structure CSV reste préparatoire et non transféré.
- **Contexte :** B-R031/BL-015 : GET /v1/sources échoue avant première publication de source_health et préfère un ancien statut en cache.
- **Décision :** lire pg_matviews avant de joindre la vue. Cache absent/non peuplé : liste depuis meta, freshness_days/is_stale NULL. Dernier statut/date toujours depuis meta.ingestion_run, ordre started_at/run_id décroissant ; aucun refresh implicite ni exception SQL absorbée.
- **Santé dédiée :** GET /v1/sources/{id}/health renvoie 503 RFC 7807/about:blank si cache indisponible, jamais de métriques fabriquées. Cache disponible : métriques de la vue, statut/date relus meta ; entrée absente conserve 404. Aucun schéma de réponse 200 modifié.
- **Réception :** unité et vraie API/SQL sur WITH NO DATA et cache ancien, signatures des prix et population des vues numériques inchangées. Préparation worktree reçue séparément ne vaut pas réception principale ; QA et check Windows complets après transfert obligatoires.
- **Alternatives :** refresh à chaque GET, fabriquer une santé vide, présenter un statut obsolète (rejetés).
- **Limites :** pas correction des autres métriques DQ historiques, pas qualification de fraîcheur du cache, source, prix ou modèle. Gates H1–H7 inchangés.

## ADR-037 : R0.6 — normalisation décimale avant chargement append-only

- **Isolation météo et niveaux symboliques :** seconde manifestation B-R033 : fixture météo prenait le premier admin2 sans exiger son P-code. Exiger explicitement pcode non NULL et ordre déterministe dans sa sélection. Les lieux MiASA sont tous symboliques au niveau 9, sans assertion d'un niveau administratif à partir de l'acteur producer ; lors du rejeu, corriger uniquement les anciennes lignes de cette fixture, identifiées par alias source exact/origin exact/pcode NULL/boundary synthetic-fixture;verified=false. Aucun lieu officiel, alias de production, P-code, preuve source ou observation historique n'est réécrit. Les garde-fous de destination QA restent obligatoires avant toute correction de fixture.

- **Isolation du scénario NASA :** B-R033 : ses références étaient sélectionnées par admin_level seul, puis tout P-code absent remplacé par MDG1101 avec coordonnées par défaut. Borner le test aux trois P-codes déjà déclarés dans son propre mapping de fixture, exiger leur présence exacte et supprimer ces valeurs de remplacement. Aucun P-code officiel/coordonnée nouvelle, aucune restriction d'un connecteur réel ; assertions de volumes/idempotence/rebuild inchangées. Les lieux MiASA symboliques ne deviennent jamais des districts NASA qualifiés.

- **Date :** 2026-10-11 ; accepté avant transfert et raccordement ; prototype isolé préparé avant cet incrément.
- **Contexte :** BL-013 : chargement brut sans conversion ; normalizer historique float, invalid/ND confondus et sac générique supposé. Le contrôle source-cell ne valide pas une conversion.
- **Décision :** Decimal avec styles explicites decimal_dot/decimal_comma concordants à la preuve, ND/NA conservés sans zéro, invalides/non finis/hors NUMERIC(18,4) refusés sans missing inventé. Aucun arrondi observé ; dérivé seul quantifié HALF_UP à quatre décimales. MGA explicite, FMG/francs divisés par cinq selon SPECS ; aucune autre conversion FX. Facteur positif documenté/confiance >=0,8 et base compatible produit obligatoires ; aucun sac générique/densité deviné.
- **Référentiels :** SQL, alias exact source puis global ; pg_trgm >=0,85 uniquement si identité unique. Lieu P-code/alias exact, fuzzy seulement avec niveau administratif explicite. Aucun alias créé, ambiguïté/insuffisance refusée, token numérique borné à 128 caractères. Milliers à points sans number_style explicite restent en revue.
- **Chargement :** FK/source contrôlées, bruts/preuve conservés, normalization.version=1 distinct. Comparer bruts et dérivés/devise/missing/variété/classification ; revue seulement à insertion/supersession, pas retry. Inconnus/non convertibles pending et dérivé NULL. Champs evidence comparés par chemins tuple statiques, jamais exécutés. Confidence = minimum des composants configurés tronqué à 0,01, pas probabilité calibrée ; human_reviewed=false.
- **Raccordement :** consume_connector_silver appelle ce loader pour PriceRecord et compte les revues réellement créées ; autres types inchangés. Aucun commit implicite, backfill, migration ou mutation Bronze. value_kind demeure métadonnée explicite, colonne/UI dédiée R2.1 non livrées.
- **Classification existante :** SPECS §8 définit producer/wholesale/retail/official_ppn/listing/unknown, tandis que PriceRecord documente farmgate ; conserver l'union explicite des sept valeurs sans traduction ni changement du brut. Cela n'autorise aucune collecte privée/listing nouvelle (H4 inchangé) ; valeurs étrangères refusées. Première préparation à quatre valeurs trop étroite corrigée avant réception globale.
- **Précision exacte :** B-R030 interdit normalize() pour décider de la précision SQL observée : contrôler coefficient/exposant exacts via as_tuple(), sans contexte d'arrondi ni conversion float. Exposants extrêmes et décimales non nulles au-delà de quatre positions refusés mécaniquement, pas arrondis ; nouvelle réception globale requise.
- **Fixture d'observabilité :** B-R031, préciser le prérequis existant du scénario Mailpit/API en rafraîchissant seulement source_health (métadonnées, effectifs 0/0/NULL), jamais prix Gold ; toutes assertions originales conservées. API sans cache reste un défaut BL-015 à traiter séparément avant DONE R0.6, pas une disponibilité opérationnelle qualifiée par ce scénario.
- **Fixture MiASA :** B-R032 révèle 390 revues/180, géographie échantillon et aliases source non préparés. Ne pas supprimer arbitrairement variété/sous-lieu ni prétendre qu'un district/marché est résolu par sa seule région. Fournir uniquement dans QA gardée des références synthétiques source-scopées pour les libellés du golden existant : produits vers codes déjà présents explicitement déclarés, lieux symboliques pcode=NULL/boundary_version=synthetic;verified=false. Origin documente fichier golden et human_reviewed=false. Aucune modification du golden, de la seed/taxonomie/production ni alias créé par normalizer. Seuil 5 % inchangé ; preuve logicielle de normalisation avec référentiels fournis, pas qualification de MiASA ou de géographie R1.1/R1.3. Réception réelle des références reste obligatoire dans ces tâches.
- **Alternatives :** raccorder float historique, supposer sac=50kg ou réécrire les observations (rejetés).
- **Limites :** réception SQL/S3/raccordement/retry/révisions puis check global obligatoires ; prototype non qualifié par le check de l'incrément 3. Authenticité/facteurs externes/modèle non certifiés par ces tests ; schema_drift/Gold réel/ledger/partitions/durabilité restent requis avant DONE R0.6.

## ADR-036 : R0.6 — check de provenance mesuré par source

- **Date :** 2026-10-11 ; accepté avant implémentation.
- **Contexte :** factory renvoie passed=True sans lecture SQL/Bronze malgré le vérificateur reçu en R0.5.
- **Décision :** sélectionner toutes les observations des six tables liées à la source via source_record, sans filtre accepted/current/conversion ; réutiliser la vérification octets/SHA/cellules et persister un reçu DQ source-scopé. Ensemble vide = failed, état empty, 0/0, métrique NULL, jamais 100 %. Le check Dagster est blocking avec sévérité ERROR et métadonnées mesurées (UUID DQ, effectifs, objets, état).
- **Transactions :** le vérificateur ne commit pas ; l'asset check commit son reçu dans son propre get_session avant de retourner le résultat négatif. Erreur technique propagée, aucun faux vert. Aucun accès réseau source, aucune mutation d'observation/Bronze.
- **Alternatives :** contrôler seulement les FK, reprendre un ancien reçu ou certifier un ensemble vide (rejetés).
- **Limites :** source-cell uniquement, pas authenticité/conversion/modèle. Orphelins sans source attribuable restent couverts par l'audit global R0.5, jamais attribués artificiellement. Lignée Gold explicite, schema_drift, ledger et durabilité des échecs de parsing restent à recevoir avant DONE R0.6.

## ADR-035 : R0.6 — définitions explicites et inventaire sans acquisition automatique désactivée

- **Date :** 2026-10-10 ; accepté avant implémentation.
- **Contexte :** inspection 64611 : 19 assets / 8 checks / 8 schedules, NASA/WFP disabled encore planifiées ; definitions.py masque toute erreur de construction, factory masque celle du registre et invente une cadence de repli.
- **Décision :** construire un inventaire déterministe des connecteurs enregistrés. Exclure explicitement namespaces dummy/fixture, status planned/disabled et crawl_permission forbidden de l'assemblage automatique ; active/degraded restent admissibles à construction, sans qualification de source. Concordance identité/classe/registre obligatoire. Toute erreur de résolution/construction devient une erreur explicite expurgée, jamais continue. Restituer les exclusions et les effectifs réellement construits.
- **Factory :** résolution du registre avant construction ; KeyError admis uniquement pour définition pure de fixture dummy/fixture, jamais pour source réelle inconnue. Aucun schedule de fixture, source planned/disabled/forbidden ou cadence event/static ; autres cadences mappées explicitement, cadence inconnue refusée. Horaire business Indian/Antananarivo explicite. La définition pure d'une fixture ne donne aucun droit d'exécution : garde d'acquisition QA/disabled de ADR-032/033 inchangée.
- **Alternatives :** schedules désactivés mais erreurs ignorées, ou inventaire constant (rejetés).
- **Limites :** aucun nouveau connecteur, appel réseau, requalification live, seed/migration active ou mutation Bronze. Checks mesurés/blocage Gold, ledger, normalisation, partitions, reprise et durabilité restent obligatoires avant DONE R0.6 ; l'inventaire décrit uniquement les connecteurs effectivement enregistrés, pas toutes les capacités du registre.

## ADR-034 : R0.6 — identité du run avant retour du lot et erreurs expurgées

- **Date :** 2026-10-10 ; accepté avant correction.
- **Contexte :** check Windows 41998 rouge, 35 passed / 1 failed : le scénario d'échec utilise une source fictive non enregistrée, désormais correctement refusée. Le wrapper perd aussi l'UUID lorsqu'une collecte échoue avant de retourner BronzeBatch.
- **Décision :** réinitialiser ctx.run_id au début de collecte puis le lier uniquement au run SQL effectivement créé. Le wrapper utilise cet UUID pour statut failed et notification Mailpit, même sans lot ; stocker/envoyer uniquement la classe d'erreur, jamais le texte source. Le scénario utilise une identité dummy et une classe temporairement enregistrée dans QA validée, sans exemption de politique.
- **Alternatives :** autoriser les sources inconnues ou notifier sous une identité fixe (rejeté).
- **Limites :** transaction du caller, aucun commit implicite ; un rollback du caller peut encore supprimer ce reçu. Durabilité indépendante et gestion des assets directs restent obligatoires dans les prochains incréments R0.6.

## ADR-033 : R0.6 — séparer les sources désactivées des acquisitions de fixtures locales

- **Date :** 2026-10-10 ; accepté avant adaptation.
- **Contexte :** les tests historiques NASA/WFP collectent un serveur HTTP local sous l'identité de la source publique disabled. La nouvelle garde doit refuser cette identité avant discover, sans exemption de test ni réactivation.
- **Décision :** les acquisitions synthétiques de ces scénarios utilisent une identité fixture_<source>_<UUID>, avec classe locale temporairement enregistrée et même parseur ; aucune modification du statut public. Résolution de ces identités pour le rejeu uniquement dans l'environnement QA validé, jamais comme source live/asset/schedule de production. Les anciennes observations et objets conservent leur identité ; aucun backfill ni purge. Mêmes valeurs/comptes/révisions et refus Gold conservés.
- **Conséquences :** le rejeu QA peut résoudre son historique de fixtures sans contacter la source désactivée. Ce mécanisme ne qualifie ni la source, ni des droits, ni le rebuild complet R0.8. Tests de refus hors QA et identité de fixture obligatoire.

## ADR-032 : R0.6 — lot Bronze exact et consommation Silver hors collecte

- **Date :** 2026-10-10 ; accepté avant implémentation.
- **Contexte :** factory Silver relance execute_connector_pipeline, donc discover/fetch, et perd la lignée du résultat Bronze. Le wrapper existant reste nécessaire aux tests et CLI ; les erreurs/durabilité et normalisation ne sont pas encore qualifiées.
- **Décision :** contrat interne de lot immuable : source_id, ingestion_run_id, parser_version et tuple des RawArtifact liés aux UUID source_record réellement persistés. Collecte et consommation exposées séparément ; le wrapper les compose. Silver vérifie la concordance lot/source/parser/run/référence/clé/SHA/MIME puis les octets avant parse, sans discover/fetch ; contexte copié offline avec client HTTP refusant les requêtes, sans changer HTTP_OFFLINE global ni le contexte de collecte. Aucune référence fournie par le document ne peut remplacer celle de la DB.
- **Alternatives :** refetch avec déduplication (rejeté : ne démontre pas la lignée) ; faire confiance au lot sans relire les octets (rejeté).
- **Métadonnées :** URL et published_at du lot proviennent de la référence SQL fraîchement relue et doivent concorder à consommation. La représentation TIMESTAMPTZ SQL est conservée, aucun fuseau/date inventé ni backfill.
- **Conséquences :** pas de nouvelle dépendance ni changement ORM ; transaction/commit au caller. Les compteurs représentent les étapes réelles et le rejeu reste idempotent. Garde disabled/robots, normalisation, checks mesurés/durables, construction et partitions restent réception obligatoire R0.6 ; un incrément transport seul ne termine pas la tâche.

## ADR-031 : R0.5 — distinguer Gold vide du refus et de la certification

- **Date :** 2026-10-10 ; accepté avant implémentation.
- **Contexte :** QA élargie 318 passed / 4 failed : quatre scénarios prix n'ont aucune observation éligible Gold. Relecture WFP : 36 accepted/exact, mais 36 price_mga_per_base NULL et zéro ligne Gold. Le loader brut de connectors/runner.py ne normalise pas ces prix ; le raccordement Silver/normalisation reste à corriger en R0.6. Exiger une exception de preuve sur un ensemble vide était une mauvaise attente de test.
- **Décision :** rebuild expose le véritable état/effectifs/taux/scope du refresh ; empty=0/0 et taux NULL ne deviennent jamais 100 % ou source qualifiée. Quatre tests prix peuvent autoriser explicitement cet état, uniquement après vérification réelle que toutes les vues numériques sont vides ; succès cells_verified inattendu, compteur manquant/non nul ou taux fabriqué restent refusés par le helper. Les contrôles Silver originaux restent inchangés.
- **CSV borné :** vérifier trois preuves natives sur observations rejouées/objet Bronze, séparément du Gold vide dû au loader non normalisant. Aucune revendication de publication numérique positive dans ce scénario.
- **Conséquences :** pas de bypass ni réparation rétroactive ; diagnostics sans qualification du rebuild complet R0.8. Lacune de normalisation et fausse étiquette exact consignées pour R0.6/R2.1.

## ADR-030 : R0.5 — statistiques de rejeu sur refus explicite de publication

- **Date :** 2026-10-10 ; accepté avant implémentation.
- **Contexte :** les anciens tests de connecteurs vérifient les effectifs Silver après rebuild, mais leurs parseurs ne fournissent pas encore les preuves de cellules. Le refus Gold ne doit ni perdre ces diagnostics ni devenir un succès de rebuild.
- **Décision :** enrichir uniquement l'exception GoldProvenanceRejected propagée par rebuild avec les statistiques réellement mesurées avant publication, gold_views_refreshed=0 et gold_publication_state=refused. Aucun catch silencieux, retour réussi, exemption, ajout de preuves persistées ou collecte externe. Les tests historiques gardent leurs assertions Silver/revisions et exigent explicitement ce refus lorsqu'ils utilisent un parseur non qualifié ; leur helper échoue sur réussite inattendue, reçu invalide ou statistiques absentes.
- **Rejeu positif :** le CSV de test possède désormais des cellules natives ; son test de rebuild se limite explicitement à son source_id existant et conserve valeurs/effectifs, en ajoutant la publication vérifiée. Ce corpus borné n'est pas le rebuild complet R0.8.
- **Conséquences :** un rejeu Silver peut réussir avant un refus Gold sans qualifier la capacité source. La CLI continue de sortir en erreur et n'affiche aucun succès global. Qualification native et rebuild complet restent obligatoires selon R1 et R0.8 ; aucun ancien tag T recertifié.

## ADR-028 : R0.5 — clôture des dépendances de publication Gold

- **Date :** 2026-10-10 ; accepté avant implémentation.
- **Contexte :** price_monthly, price_monthly_best, price_changes et market_health lisent des caches Gold ; une sélection partielle peut réutiliser des caches anciens malgré un audit Silver frais.
- **Décision :** étendre toute sélection à ses ancêtres Gold via allowlist statique, puis auditer et rafraîchir cette clôture en ordre topologique dans le même savepoint. price_changes inclut ses quatre niveaux prix ; market_health inclut aussi stock_latest/weather_monthly. Les vues indépendantes le restent.
- **Alternatives :** refuser toute sélection partielle ; accepter les caches anciens (rejeté).
- **Conséquences :** count/views_refreshed décrivent le lot effectif, possiblement plus large que demandé ; tests de fraîcheur et rollback requis. Aucune certification rétroactive, aucun scope économique/modèle élargi.

## ADR-029 : R0.5 — NASA historique sans preuve ne publie plus

- **Date :** 2026-10-10 ; accepté avant adaptation du test historique.
- **Contexte :** QA courante 304 passed / 1 failed : le parseur NASA historique n'émet pas de coordonnées de preuve complètes ; son ancien test supposait une publication Gold sur la seule présence d'une FK. La nouvelle garde refuse correctement ce résultat. Source publique toujours disabled, aucune acquisition externe tentée.
- **Décision :** conserver les contrôles réels de collecte locale, couverture, idempotence et rejeu Silver ; mesurer les appels au vrai parseur pendant le rejeu, puis exiger le refus Gold et son reçu DQ négatif. Aucun ajout de preuve artificielle aux observations persistées ni exemption du verrou. Adapter les parseurs natifs/requalifier les données NASA reste R1.11 ; R0.8 reste une réception de rejeu distincte, non satisfaite par cette fixture.
- **Alternatives :** rétablir publication non vérifiée (interdit) ; inventer des cellules source pour les identités dérivées (rejeté).
- **Conséquences :** l'ancien succès T3.4 n'est pas recertifié ; la capacité NASA reste non qualifiée. Le test doit prouver effectivement les mêmes nombres Silver et un échec de publication, pas masquer une erreur de rejeu ni déclarer un rebuild complet réussi.

## ADR-023 : R0.5 — garde de publication des cellules source

- **Date :** 2026-10-10 ; accepté avant transfert du prototype au principal.
- **Décision :** contrôler fraîchement les observations consommées avant REFRESH, sous verrous SHARE transactionnels des tables et références, lock_timeout local 5 s. Vues/tables allowlist statique ; prix courants accepted et convertis non NULL ; stocks courants avec produit/lieu, historique LAG inclus ; production courante production_t ; autres tables courantes sans filtre source/statut. Audit complet historique distinct, pas de cache de réussite ni bypass APP_ENV/test. Empty et metadata_only ne deviennent pas 100 %.
- **Limites :** scope source_cells seulement, pas authenticité/droits, conversions économiques ou validation de modèle ; les champs calculés et les sources natives restent à qualifier selon tâches R pertinentes. Critères R0.5 et réception SQL restent obligatoires, statut non terminé pendant transfert.

## ADR-024 : R0.5 — nouvelles fixtures Gold réellement sourcées

- **Date :** 2026-10-10 ; accepté avant transfert.
- **Décision :** uniquement pour nouvelles observations transient dans la DB/bucket QA gardés : créer octets JSON synthetic/verified=false et références content-addressed réelles ; vérifier cellules avant insertion. Représenter les literals du générateur en Decimal ; aucune reconstitution de brut réel, réparation d'ancienne observation ou assouplissement du binder. Anciennes références/objets conservés. Générateur auxiliaire sous tests/e2e_data et inventaire corpus recalculé ; mêmes valeurs analytiques, quantités/unités de stock explicitement générées.
- **Limites :** source synthétique, pas acquisition officielle ni modèle validé. Autorisation H5 et droits de sources réelles inchangés ; pas de collecte depuis ces faux URL déclarés verified=false.

## ADR-025 : R0.5 — lecture Bronze bornée des preuves

- **Date :** 2026-10-10 ; accepté avant transfert.
- **Décision :** reader dédié GET existant, au plus 32 MiB + sentinelle, flux fermé dans tous les cas ; ContentLength ne peut que refuser, jamais prouver l'intégrité. Refus de taille incohérente/non entière, contenu non bytes ou surdimensionné. SHA réel reste obligatoire, jamais ETag. Store historique et objets inchangés ; négatifs sur flux simulés.
- **Limites :** durée transport et mémoire du parsing distinctes, pas garanties par cette borne ; aucune nouvelle dépendance.

## ADR-026 : R0.5 — groupement sans rétention des octets du corpus entier

- **Date :** 2026-10-10 ; accepté avant transfert.
- **Décision :** prévalider références/doublons dans ordre d'entrée, grouper par clé validée, GET une fois par groupe, vérifier puis libérer octets avant suivant. Résultats rendus dans ordre original, comptes/erreurs conservés ; chaque nouveau lot relit les objets. Aucune omission pour économiser mémoire ou obtenir un taux vert.
- **Limites :** claims/résultats proportionnels au lot, parsing à la taille d'un objet ; réception SQL obligatoire en plus des mocks.

## ADR-027 : R0.5 — initialisation non publiée et refresh atomique

- **Date :** 2026-10-10 ; accepté avant transfert.
- **Décision :** scripts statiques WITH NO DATA, donc pas de chiffres implicitement publiés à init/migration. Migration 0005 après 0004 invalide seulement les 12 caches Gold et recrée leurs permissions, sans toucher Bronze/Silver/ML. Downgrade n'effectue aucune repopulation non auditée. Refresh : allowlist/ordre topologique, vue absente refusée, garde fresh puis savepoint global ; concurrent retry après rollback du savepoint local, seconde erreur propagée en code stable. Aucun succès partiel, empty jamais 100 %. Résultat expose provenance_state/source_cell_dq_id/effectifs/scope non modèle/non conversions.
- **Limites :** aucune migration active ; preservation SQL QA et scénarios négatifs/rollback réels requis avant réception. Échecs de pipeline et leur durabilité après rollback externe restent R0.6 ; une preuve source-cell ne qualifie pas toute la sémantique Gold.

## ADR-022 : R0.5 — lexèmes numériques JSON et coordonnées CSV natives

- **Date :** 2026-10-10 ; accepté avant transfert au principal (prototype nommé ADR-023 dans son worktree, non normatif).
- **Contexte :** un nombre JSON exact ne prouve pas un brut reconstruit depuis float/Decimal ; les parsers doivent fournir des coordonnées natives plutôt qu'une recherche libre.
- **Décision :** option de cellule raw_encoding=json_number_lexeme, JSON/number seulement ; conserver le token original via parse_int/parse_float et comparer valeur décimale et brut exact. Sans option, refus historique d'un brut textuel sur token numérique maintenu. Clés JSON dupliquées, option inconnue, chaîne sous option numérique et identité numérique implicitement convertie sont refusées. Limite générale 32 MiB avant parsing et profondeur JSON 128 niveaux indépendante de Python, chaînes/échappements exclus ; exposant non interprétable refusé avec erreur stable.
- **CSV de test :** DummyCsvConnector 1.0.1 fournit ligne zéro-indexée et colonnes originales pour prix/produit/lieu/date/unité/devise. Une devise par défaut n'invente jamais une cellule source. Pas de nouveau connecteur public ni réactivation NASA/HDX.
- **Alternatives :** sérialiser un float/Decimal pour inventer le brut, accepter une autre ligne de même prix, résoudre opportunistement une clé dupliquée (rejetées).
- **Conséquences :** réception unitaires et SQL/MinIO isolée obligatoire ; aucune preuve de conversion Gold, collecte live ou modèle. Garde Gold distincte encore non livrée ; aucun changement de précision SQL ni migration active.

## ADR-021 : R0.5 — brut de production conservé sans backfill

- **Date :** 2026-10-10 ; accepté avant implémentation.
- **Contexte :** ProductionRecord.value_raw existe mais les deux insertions du loader le perdent ; l'idempotence ne distingue pas une nouvelle preuve ou une révision source de même valeur.
- **Décision :** migration additive 0004 ajoutant value_raw TEXT nullable sans backfill. Le loader conserve ce brut, copie evidence et compare valeur décimale, brut, preuve, méthode, statut observé/imputé et source_record_id avant skip. Une différence crée une révision append-only, jamais un remplacement destructif. NUMERIC(20,4) inchangé ; nouvelles valeurs non finies, hors capacité ou exigeant un arrondi refusées.
- **Alternatives :** reconstruire le brut depuis float, renseigner artificiellement les anciennes lignes ou ignorer une preuve révisée (rejetées).
- **Conséquences :** audit lie value_raw au lexème vérifié ; anciennes lignes sans brut ne deviennent pas qualifiées. Downgrade refuse de supprimer un brut non NULL. Migration et réception SQL uniquement QA, aucune migration active ; Gold/adaptateurs natifs restent à réaliser.

## ADR-020 : R0.5 — provenance météo et révisions ajout seules

- **Date :** 2026-10-10 ; accepté avant transfert du prototype au dépôt principal.
- **Contexte :** WeatherRecord porte evidence/extraction_method/location_raw mais le loader les perd ; la table interdit deux versions et le loader modifie les anciennes valeurs en place. Aucun audit mécanique ni historique fiable n'est possible ainsi.
- **Décision :** migration additive 0003 : location_raw, value_raw, evidence, extraction_method et superseded_by nullable, aucune réécriture/backfill des anciennes valeurs. WeatherRecord ajoute value_raw optionnel, jamais inventé à partir d'un float. FK de supersession différée, unique partiel des observations courantes ; même trigger append-only que les autres observations. Le loader conserve preuves/bruts, insère une nouvelle observation pour une révision et ne modifie que superseded_by de l'ancienne. Identique contenu/provenance stockée => skip ; changement de preuve/brut/méthode crée une révision, pas une mise à jour destructive.
- **Gold météo :** exclure les lignes supersédées via to_jsonb(wo)->>'superseded_by' IS NULL, compatible avec le schéma 0001 afin de ne pas casser la migration historique 0002 qui lit les fichiers SQL courants. Migration 0003 recrée uniquement les vues dérivées weather_monthly et market_health dans sa transaction ; pas de suppression Bronze/Silver. Cela ne remplace pas la future garde de provenance Gold.
- **Alternatives :** attribuer des preuves aux anciennes lignes, recalculer un brut depuis un float, écraser value/source_record_id ou compter les deux versions dans Gold (rejetées).
- **Précision :** conserver NUMERIC(10,3) ; une nouvelle valeur non finie, hors capacité ou non exactement représentable est refusée avant insertion, jamais arrondie silencieusement. value_raw reste celui du source/record, pas str(value) fabriqué par le loader. Toute extension de précision future exige contrat explicite.
- **Conséquences :** anciennes lignes sans preuves restent invalides, aucun statut live NASA/H5 changé. Tests SQL de preservation/relecture, unicité courante, refus UPDATE/DELETE, supersession et Gold sans double comptage ; migrations exclusivement QA isolée, aucune application à la DB active. Downgrade refusé dès qu'il perdrait une preuve ou une révision ; pas de purge pour rendre les tests verts.

## ADR-019 : R0.5 — preuve LLM mécanique, jamais preuve par étiquette

- **Date :** 2026-10-10 ; accepté avant transfert du prototype au dépôt principal.
- **Contexte :** un nombre présent dans une page entière ou un label llm_verified ne prouve ni la ligne ni l'identité ; les conversions float perdent la précision.
- **Décision :** preuve v1 avec llm_evidence={page:int,text:str}, contrôlée après cellules/identités exactes et SHA réel. PDF : page identique à la page de la table, texte relu depuis les octets ; HTML : page logique 1 et texte nettoyé relu. Extrait non vide ancré au texte normalisé selon §11.2 (sous-chaîne ou partial_ratio>=95), puis toutes les cellules vérifiées de valeur et d'identité doivent apparaître comme tokens complets dans l'extrait. Nombres issus des cellules relues, sans génération/arrondi float ; ne pas confondre un préfixe, une décimale prolongée ou un nombre signé. XLSX/JSON/CSV LLM non pris en charge dans ce lot ; refus explicite.
- **Liaison SQL :** llm_verified/dual_agree admis uniquement avec cette preuve structurée obligatoire et validation mécanique complète ; attentes toujours issues des champs SQL autorisés. human et méthode inconnue restent refusés sans contrat de revue. Pas de fournisseur/OCR/nouvelle dépendance, ni instruction ou outil provenant du contenu collecté.
- **Alternatives :** faire confiance au label, à une page voisine, à rice dans price ou à un nombre arrondi (rejetées).
- **Conséquences :** résultat DQ négatif persisté et relu, pas de succès sur extrait omettant une identité obligatoire. Réception ciblée/globale requise ; garde Gold et adaptateurs métier restent obligatoires avant DONE. Une fixture ne qualifie aucune source live, performance LLM ou marché ; Bronze actif jamais modifié.

## ADR-018 : R0.5 — coordonnées des tableaux PDF, HTML et XLSX

- **Date :** 2026-10-10 ; contrat préparé dans un worktree isolé avant code, intégré avant le raccordement principal.
- **Contexte :** les cellules CSV/JSON ne couvrent pas les publications PDF/tableurs ; trouver un nombre dans une page entière est insuffisant. Le prototype séparé passe 113 tests ciblés et lint/types, sans qualification globale.
- **Décision :** formats pdf_table/html_table/xlsx_table. PDF : page 1-indexée, tableau/ligne/colonne zéro-indexés, en-têtes inclus. HTML : tableau/ligne/colonne zéro-indexés, aucun sélecteur/expression issu du document, scripts/styles/noscript écartés et tableaux imbriqués refusés. XLSX : feuille exacte et ligne/colonne 1-indexées ; toutes les cellules dans la même ligne. MIME explicite concordant, coordonnées entières sans bool, cellule absente et formule refusées même avec valeur cachée. La valeur numérique XLSX vient du lexème XML original, pas d'un float arrondi ; date/format d'affichage non interprétés implicitement. Structure OOXML/membres/relations contrôlés ; aucun lien, macro, formule ou entité XML exécuté.
- **Bornes :** 32 MiB de contenu, 512 pages PDF ; XLSX au plus 4096 entrées ZIP et 128 MiB déclarés décompressés, jamais extraction sur disque. Les formats de scan/OCR restent non pris en charge et ne prouvent aucun chiffre.
- **Alternatives :** recherche libre/fuzzy d'un nombre, page voisine, cellule calculée/cachée sans preuve et approximation flottante (rejetées).
- **Conséquences :** deuxième incrément SQL/DQ reçu avant transfert des formats ; nouvelle QA/check Windows complète obligatoire. Le scénario positif SQL lit un vrai objet MinIO du bucket QA, créé par manual_upload synthétique (URL verified=false, aucun HTTP acquis, statut sidecar 0) ; effectifs DQ archivés dans JUnit avant nettoyages de fixtures. Les liaisons des périodes/en-têtes métier et preuves LLM restent distinctes ; les tableaux synthétiques ne qualifient aucune source authentique. Aucun ajout de dépendance ni changement de schéma, tâche toujours IN_PROGRESS.

## ADR-017 : R0.5 — liaison SQL et journal DQ, sans certification implicite

- **Date :** 2026-10-10 ; accepté avant implémentation.
- **Contexte :** le vérificateur pur accepte les attentes fournies par son appelant ; cela ne prouve pas leur concordance avec les observations SQL. Des tables historiques n'ont pas de preuve exploitable, notamment la météo.
- **Décision :** ajouter un auditeur explicite des six tables d'observations existantes. Le contrôle complet sélectionne toutes les lignes sans filtrer les orphelins, supersessions ou sources disabled ; l'incrémental exige une liste explicite de couples table/UUID et produit une anomalie pour tout UUID absent. Preuve version 1 dans evidence.provenance, attentes remplacées depuis les champs SQL autorisés ; cellules obligatoires de valeurs et d'identité selon le type. Aucun chemin de champ arbitraire ni expression de conversion dans le document. Date ISO littérale et Decimal, sans arrondi implicite. Une cellule numérique peut porter raw_expected, également lié au champ brut SQL correspondant ; ce contrôle supplémentaire ne dispense pas l'identité de ligne.
- **Persistance :** une ligne ops.dq_result par audit, mode, périmètre, numérateur/dénominateur, tentatives/lectures d'objets et résultats individuels non sensibles. Flush uniquement, transaction maîtrisée par l'appelant ; aucune mise à jour d'observation, migration, suppression Bronze ou exception APP_ENV=test. Les erreurs de binding deviennent des raisons stables et des échecs.
- **Alternatives :** utiliser les expected du document, masquer les orphelins par JOIN interne, certifier uniquement les prix, dispenser les fixtures ou convertir les valeurs dans une instruction collectée (rejetées).
- **Conséquences :** cet incrément ajoute un audit utilisable mais ne branche pas encore la garde Gold. Les formats/adaptateurs non pris en charge et observations sans preuve restent invalides. Les conversions économiques, provenance du modèle, authenticité et qualification de marché ne sont pas démontrées par un simple binding ; R0.5 demeure IN_PROGRESS jusqu'à réception complète.

## ADR-016 : R0.5 — vérification des octets et cellules, qualification non implicite

- **Date :** 2026-10-09 ; accepté avant implémentation.
- **Contexte :** le contrôle DQ historique vérifie uniquement une FK de prix et affiche 100 % sur zéro ligne. Des SourceRecord de tests portent des pseudo-hashes ; toutes les preuves historiques ne fournissent pas de cellule exacte. Le corpus WDI authentique R0.4 n'est pas un prix et n'est pas ingéré en Silver.
- **Décision :** introduire un vérificateur hors réseau réutilisable, sans nouvelle dépendance ni migration. Contrat de preuve v1 : format explicite, cellule numérique/brute et cellules d'identité ancrées au même enregistrement. JSON : chemin de clés/indices et scope_path ; CSV : ligne de données zéro-indexée après en-tête et noms de colonnes, séparateur déclaré. Valeurs et identités attendues viennent de l'observation/appelant, jamais d'un texte collecté exécuté ni d'un LLM inventant les attentes. Comparaison décimale sans float. Un format absent/non pris en charge, une identité insuffisante ou une cellule discordante échouent ; le support PDF/HTML/XLSX exige ses coordonnées et contrôles avant qualification.
- **Chaîne :** référence SourceRecord existante, UUID concordant, SHA hexadécimal 64 caractères, clé relative content-addressed source/année/mois/hash.extension, octets relus et SHA recalculé. Cache uniquement pour la durée d'une vérification, par clé objet ; une erreur de lecture n'est jamais un succès et les erreurs ne divulguent pas URL/texte/exception/secrets. Les comptes portent sur les observations vérifiées, pas le nombre d'objets partagés ; contrôle complet et incrémental restent distingués, zéro ligne n'est jamais certifié 100 %.
- **Incréments :** commencer par vérificateur pur et preuves CSV/JSON, régressions simulées et cellules WDI originales sans créer de fausse observation GDP/prix. Persistance DQ et garde Gold viennent ensuite ; la tâche reste IN_PROGRESS tant que publication et tous critères ne sont pas reçus. Le marqueur extraction_method seul n'atteste aucune vérification LLM ; preuve mécanique obligatoire pour toute valeur publiée.
- **Alternatives :** accepter un hash seulement non nul, un snippet contenant le même nombre sur une autre ligne, l'absence d'objet, un jeu vide ou une étiquette llm_verified comme preuve (rejetés). Modifier/purger des objets Bronze ou utiliser le WDI PIB comme prix PPN (interdits).
- **Conséquences :** cette intégrité technique ne prouve ni authenticité, droits, disponibilité historique, conversion économique ni modèle de marché. R0.6 consommera les résultats mesurés ; R0.7 certifiera son périmètre complet. L'actif n'est pas modifié et les contrôles négatifs d'objets utilisent exclusivement un store simulé.

## ADR-015 : R0.4 — périmètre explicite du test de rejeu douanier

- **Date :** 2026-10-09 ; accepté avant correction.
- **Contexte :** B-R011, check Windows rouge : 18 passed / 1 failed, supersessions 3 au lieu de 1. Lecture QA seule confirme trois anciennes versions CSV CRLF, leurs trois versions LF et un pseudo-artefact hérité d'un autre test. Bronze est conservé ; le test rejoue à tort tout l'historique QA pour une assertion portant sur ses trois fixtures.
- **Décision :** dans ce seul test d'intégration, projeter explicitement la sélection SQL SourceRecord du module rebuild sur les trois UUID réellement ingérés par le scénario courant. Substitution temporaire pytest monkeypatch, déclarée dans le test ; aucune sélection implicite dans le runtime. Exiger 3 objets sélectionnés/rejoués, zéro ignoré, 40 inserts, 1 supersession, 3 skips d'observations et mêmes valeurs finales ; conserver toutes les lignes source_record avant/après et aucun objet Bronze supprimé.
- **Alternatives :** purger Bronze/metadata, augmenter arbitrairement le résultat attendu à 3, revenir aux fins de ligne Windows incompatibles avec Git, ajouter un filtre silencieux au rebuild de production (rejetés).
- **Conséquences :** ce test prouve le scénario borné et non un rebuild intégral ; R0.8 doit rejouer son corpus complet indépendant et ne peut reprendre cette projection pour masquer une anomalie. La commande rebuild et ses contrats restent inchangés. Réception ciblée puis check Windows complet renouvelés obligatoires ; incident rouge conservé.

## ADR-014 : R0.4 — authenticité explicite et corpus indépendant

- **Date :** 2026-10-09 ; accepté avant implémentation.
- **Contexte :** des générateurs produisent les PDF ODR, HTML MinCC et CSV douaniers ainsi que leurs attendus. Les autres anciennes fixtures ne possèdent pas toutes de preuve d'acquisition ; une fiche déclarative ne prouve ni leurs octets ni leurs droits. Le catalogue HDX a répondu HTTP 403 via le lecteur web le 2026-10-09 : arrêt de cette acquisition, cause côté serveur ou transport non établie.
- **Décision :** étendre C1 et SPECS §11.4 avec `authentic|synthetic|unverified`. Inventaire versionné JSON de tous les fichiers fixtures/golden/e2e et générateurs, SHA-256 recalculé, taille, type, origine, droits, annotateur et revue humaine. `unverified` n'affirme pas une fabrication ; seuls les documents authentiques avec acquisition et droits prouvés peuvent entrer dans le corpus réel. Les tests historiques restent des régressions logicielles. Les attendus authentiques sont transcrits indépendamment avec cellules ou pages, périmètre explicite, sans prétendre mesurer le rappel sur un extrait.
- **Conservation :** les nouvelles réponses officielles brutes sous `tests/fixtures/authentic/` sont exclues de la normalisation Git des fins de ligne (`-text`) afin que leur SHA corresponde aux octets reçus ; aucune ancienne fixture, aucun Bronze ni schéma DB ne sont réécrits. Les manifestes et scripts restent LF.
- **Repli :** aucun nouvel accès HDX après 403, aucun proxy ni Wayback de contournement. État d'acquisition local `disabled`, incident porté à R1.7 (renvoi documentaire corrigé le 2026-10-10) ; d'autres archives publiques officielles indépendantes peuvent avancer. Cela ne prétend pas que HDX est universellement indisponible, et ne supprime aucune donnée active.
- **Alternatives :** qualifier les documents générés comme officiels, attribuer une licence inconnue, marquer toute origine inconnue synthetic ou réessayer le 403 (rejetés).
- **Conséquences :** aucune fixture n'établit une collecte continue, une performance de marché ou une revue humaine. Les archives API peuvent constituer un corpus authentique sans PDF ; toute future annotation PDF exige lecture texte et contrôle visuel. Aucun droit de diffusion supposé à partir de la seule accessibilité HTTP.
- **Précision avant acquisition indépendante :** NASA POWER robots refuse `/api/` (B-R010), donc aucun appel de données. Une réponse publique WDI Madagascar peut servir de corpus JSON macroéconomique pour R0.4, sans créer un connecteur ni registre DB avant R2.1/R2.2. Robots HTTP 404 explicitement consigné = absence de règles (RFC 9309 §2.3.1.3) ; 401/403/challenge restent interdits et 5xx/erreur réseau refusent l'acquisition. Les droits WDI doivent être prouvés séparément, pas déduits du statut 200.
- **Fins de ligne des tests historiques :** quatre CSV non authentifiés sont physiquement CRLF/mixed malgré les blobs Git LF et `.gitattributes` LF. Archiver leur inventaire initial puis appliquer seulement la mise en conformité LF, sans changer de cellule ; recalculer les hashes après formatage. Cela ne touche aucun document authentique, PDF/XLSX, Bronze ou donnée active. Ne pas présenter ces CSV normalisés comme des originaux officiels.
- **Registre :** HDX et NASA POWER sont marqués `disabled` dans le registre versionné ; leur acquisition de corpus est arrêtée et une requalification R1 est requise pour réactivation. Aucun seed ni UPDATE n'est lancé sur la DB active ; les parsers offline restent testables. Cela ne prouve pas un arrêt du runtime historique : la factory Dagster ignore actuellement status, correction/garde obligatoire R0.6/R1.2 (BL-010). Aucun accès interdit n'a été lancé par l'agent après les refus.

## ADR-013 : R0.3 — délai de build borné et timeout machine explicite

- **Date :** 2026-10-09 ; accepté avant implémentation.
- **Contexte :** B-R008 : deux builds refusés à 900 s ; le second compile et génère 15/15 pages, mais termine sa collecte de traces après cette limite. CPU partagé some avg60 76,98 %, pas d'OOM, espace disponible. La durée totale nécessaire et la cause racine restent non établies.
- **Décision :** délai maximal frontend build 1800 s, autres commandes frontend 900 s ; aucun contrôle, test ni seuil de couverture supprimé. Le reçu expose error_code, signal et timed_out ; une erreur spawn refuse le succès même si status vaut 0. CI reste bornée à 150 minutes pour images/check/QA/négatif/E2E, sans revendiquer une exécution distante.
- **Alternatives :** arrêter les services tiers, ignorer build/traces, considérer Compiled successfully comme succès complet (rejetés) ; attente illimitée (rejetée) ; abandon immédiat sans repli autorisé (non retenu).
- **Conséquences :** repli technique réversible, pas validation métier ; régressions de délai et timeout réel en copie requises, réception frontend puis check complet à refaire. Si le nouveau délai est atteint, code non nul et protocole de blocage conservé.

## ADR-012 : R0.3 — intégrations mesurées par dossier et marqueur JUnit

- **Date :** 2026-10-09 ; accepté.
- **Contexte :** check courant : 337 tests verts, puis refus du minimum 32 car JUnit compte seulement 31 cas sous tests/integration ; le test ML marqué integration réside sous tests/unit. Aucun test n'est absent, mais le rapport ne conservait pas ce marqueur.
- **Décision :** enregistrer le marqueur integration de chaque item dans user_properties JUnit (ketrika.integration=true), après garde d'environnement. Le lecteur mesure séparément integration_by_layout, integration_by_marker et leur union integration_tests, sans double compte. Le minimum global reste 32 ; zéro échec/erreur/skip et rapport cohérent restent obligatoires. Aucun nom de fonction n'est utilisé comme preuve de marqueur et aucun ancien XML n'est réécrit.
- **Alternatives :** abaisser le minimum à 31 ou ajouter une constante pour ML (rejetés), déplacer le test sans corriger la perte générale de métadonnées (non retenu).
- **Conséquences :** rapports JSON étendus additivement ; lecteur JUnit propre accepte properties (pas de validation par schéma externe), conformément à la documentation pytest. Tests de compteur/dédoublonnage et vrai subprocess pytest à marqueur hors dossier requis ; toute réception complète doit être refaite sur cette version.
- **Référence :** [pytest, marqueurs vers JUnit](https://docs.pytest.org/en/stable/how-to/output.html#record-property), consulté le 2026-10-09.

## ADR-011 : R0.3 — authentification navigateur same-origin vérifiée

- **Date :** 2026-10-09.
- **Contexte :** le login web lisait `access_token` alors que l'API renvoie `token`, écrivait un cookie JS distinct du cookie HttpOnly API, et ciblait localhost Windows ; aucun E2E Docker authentifié réel ne peut qualifier ce chemin.
- **Décision :** proxy Next same-origin `/api/v1/*` vers l'API interne configurée, forwarding borné des méthodes/headers et cookies HttpOnly. Login utilise le contrat `token` sans écrire de JWT en JavaScript ; middleware utilise le cookie `session_token` existant de l'API ; logout passe par l'API et attend son succès. Les endpoints et schémas backend restent inchangés.
- **Alternatives :** injecter un token/cookie manuel dans le navigateur pour contourner le login (rejeté), cookie JS/non-HttpOnly (non conforme), dépendre du port Windows ou CORS large (rejeté).
- **Conséquences :** corriger les défauts nécessaires au vrai parcours E2E dans R0.3 ; ne pas déclarer un essai humain ni un déploiement. Les droits restent contrôlés par l'API, pas par la seule présence d'un cookie dans le middleware.

## ADR-010 : R0.3 — qualification machine, lockfiles et navigateur isolé

- **Date :** 2026-10-09.
- **Contexte :** dépendances Docker installées sans lock garanti, E2E hôte, aucun manifeste QA mesuré et réception locale sur images anciennes/root.
- **Décision :** installer depuis les lockfiles vérifiés, uv version figée compatible avec leur format ; garder les versions applicatives verrouillées pour cette requalification (pas approbation de sécurité production, revue R6.7). Ajouter le stage optionnel `backend-browser`, Playwright et Chromium de même version, utilisateur app non-root, réseau QA interne uniquement, sans port ni accès Docker socket. Les init de permissions concernent seulement les volumes QA identifiés ; Bronze ne participe jamais à un nettoyage. Les tests négatifs opèrent dans des copies temporaires.
- **Contrat QA :** manifeste version 1 de suites livrées, sélection par ID exact, chemins tests relatifs bornés, minimums de tests et rapports JUnit ; ID absent/non livré, suite vide, erreur/échec/skip obligatoire ou rapport incomplet = code non nul. Reçus JSON mesurent codes, durées et effectifs ; chaque exécution est séparée pour ne pas réutiliser un succès ancien. `qa` qualifie un sous-ensemble logiciel, pas automatiquement le DONE ni source/modèle/usage ; `qualify` reste R0.7.
- **Alternatives :** installation flottante avec repli (rejeté), E2E Chrome Windows/CDP sur actif (rejeté), tout marquer vert via constantes/fixtures (rejeté), mettre à niveau des majeures applicatives implicitement (rejeté).
- **Références :** https://playwright.dev/docs/docker ; https://docs.astral.sh/uv/guides/integration/docker/ ; https://docs.astral.sh/uv/concepts/projects/sync/ (consultées le 2026-10-09). L'image navigateur teste uniquement le site de confiance dédié, jamais des sites tiers. Pas de `privileged`, SYS_ADMIN ou IPC hôte.
- **Conséquences :** nouvelles preuves locales obligatoires, CI même runner ; les tâches sans suite livrée échouent explicitement. L'E2E démontre le workflow logiciel sur données de test, pas authenticité des marchés.

## ADR-009 : R0.2 — retrait du runner de certification synthétique

- **Date :** 2026-10-09.
- **Contexte :** `ketrika.demo` importait les tests, injectait des séries synthétiques et publiait des KPI constants comme certification ; la base active contient des références explicites de tests.
- **Décision :** retirer ce chemin de mutation/certification et conserver la commande comme refus explicite sans accès DB/S3 jusqu'au moteur R0.7. Les datasets synthétiques restent exclusivement dans les tests sur la DB dédiée, contrôlée par environnement et session liée. Inventaire actif uniquement en transaction read-only et GET/list S3, sans afficher secrets ni données personnelles.
- **Alternatives :** déplacer le seed dans le code applicatif (rejeté : contamination), conserver les faux succès avec un avertissement (rejeté), supprimer les données actives (interdit).
- **Conséquences :** `demo` n'est plus une réception actuelle ; historique T et tags conservés. Réhydratation d'archives authentiques documentée, pas de restore actif. R0.7 doit implémenter les mesures réelles et les profils de qualification.

## ADR-008 : Programme R autorisé, qualification isolée et statuts vérifiables

- **Date :** 2026-10-09
- **Statut :** Accepté, sur demande explicite d'implémentation du plan R0–R6.
- **Contexte :** la gouvernance historique s'arrête à T11.6 ; l'audit révèle des critères déclaratifs, un seed synthétique de démonstration et un runner susceptible de sauter l'intégration/front. Le reset historique supprimerait le volume Bronze. Il faut poursuivre sans altérer la stack active, les preuves ou les interdits.
- **Décision :** intégrer les 74 tâches R dans AGENTS/plan/PROGRESS, synchroniser le miroir demandé après chaque incrément, distinguer statut de tâche et qualification de capacité. Contrôles complets dans projet Compose dédié, DB et S3 propres, réseau interne sans ports partagés ; aucun reset/suppression Bronze ni restore/rebuild sur actif. Les scripts dev restent l'entrée unique et échouent si une vérification obligatoire manque. Bootstrap minimal R0.2/R0.3 dans R0.1 avant son DONE, puis validation séparée de ces tâches.
- **Alternatives :** considérer T11.6 comme qualification actuelle (rejeté), relancer le runner contre la base active (rejeté), multiplier les runners ou supprimer les données pour repartir (rejeté).
- **Conséquences :** gouvernance et gates R remplacent l'arrêt au MVP pour ce programme ; tests pouvant écrire restent exclusivement isolés. Les seuils métier existants ne sont pas abaissés ; les futures extensions C1–C5 exigent leurs contrats/migrations/ADR avant code. H1–H7, absence d'envoi/contact et Bronze immuable inchangés. Aucun push/merge/provisionnement autorisé.

---

## ADR-001 : Choix de l'orchestrateur (Dagster)
- **Date :** 2026-10-05
- **Statut :** Accepté
- **Contexte :** Le pipeline doit gérer des données partitionnées (mensuelles, annuelles, par document/bulletin), des backfills historiques, une lignée (lineage) claire entre Bronze, Silver et Gold, ainsi que des contrôles de qualité (asset checks).
- **Décision :** Utiliser **Dagster** comme orchestrateur principal auto-hébergé.
- **Alternatives :** Prefect 3, Apache Airflow, scripts cron indépendants.
- **Conséquences :** Développement structuré autour d'assets logiciels déclaratifs. Nécessite l'exécution du daemon et webserver Dagster en conteneur.

---

## ADR-002 : Politique sur les sites privés et marketplaces
- **Date :** 2026-10-05
- **Statut :** Accepté
- **Contexte :** Les plateformes comme Tantsah ou CoinAfrique présentent des données d'offre haute fréquence mais posent des questions de CGU, de présence de PII (numéros de téléphone, noms) et d'absence d'API documentée.
- **Décision :** Appliquer une politique **« permission d'abord »**. Les marketplaces et réseaux sociaux sont strictement **exclus du périmètre du MVP** (Gate H4). Toute intégration ultérieure nécessitera un accord de flux/partenariat ou une validation juridique explicite.
- **Alternatives :** Scraping agressif avec contournement de CAPTCHA / proxies (interdit par AGENTS.md §8).
- **Conséquences :** Risque juridique nul sur le MVP, focus total sur les données officielles et publiques vérifiables à 100 %.

---

## ADR-003 : Premier livrable commercial (Bulletin hebdomadaire PPN)
- **Date :** 2026-10-05
- **Statut :** Accepté
- **Contexte :** Pour un fondateur solo ciblant les traders, industriels et institutions, un dashboard web complexe nécessite beaucoup de temps avant d'apporter de la valeur commerciale concrète.
- **Décision :** Le **bulletin hebdomadaire PPN automatisé** (format PDF/HTML certifié, avec zéro chiffre halluciné) constitue le premier livrable tangible et vendable, parallèlement à l'API et au dashboard.
- **Alternatives :** Dashboard web seul, API seule.
- **Conséquences :** Priorité donnée au moteur de calcul de faits et au générateur de template auditable dès la Phase 8.

---

## ADR-004 : Granularité géographique des prévisions
- **Date :** 2026-10-05
- **Statut :** Accepté
- **Contexte :** Les séries historiques sont riches au niveau national et régional, mais très lacunaires et irrégulières au niveau des communes individuelles.
- **Décision :** Restreindre la cible des modèles de prévision de prix aux niveaux **régional et national** pour le MVP.
- **Alternatives :** Modèles au niveau commune (trop de valeurs manquantes, bruit excessif).
- **Conséquences :** Séries plus stables, backtests fiables et réduction du coût de calcul.

---

## ADR-005 : Historique cible et couverture temporelle
- **Date :** 2026-10-05
- **Statut :** Accepté
- **Contexte :** Le besoin analytique requiert de la profondeur pour capturer la saisonnalité et les chocs économiques.
- **Décision :** Viser un historique débutant en **2007** pour les prix (via World Bank RTFP et FAOSTAT), couvrir **toutes les éditions disponibles de l'ODR**, et remonter à **1991** pour la climatologie NASA POWER.
- **Alternatives :** Se limiter aux 12 ou 24 derniers mois.
- **Conséquences :** Permet des backtests rolling-origin solides (≥ 36 mois) pour les modèles de prévision.

---

## ADR-006 : Environnement de développement et déploiement local-first
- **Date :** 2026-10-05
- **Statut :** Accepté
- **Contexte :** L'agent autonome doit travailler sans bloquer sur l'achat ou le provisionnement d'infrastructures distantes (VPS, Cloudflare R2, nom de domaine).
- **Décision :** Architecture **local-first** en environnement de développement via Docker Compose (MinIO pour le Bronze S3, Mailpit pour la capture d'emails, PostGIS local). La configuration de production (Caddy, VPS Ubuntu 24.04, Cloudflare R2) est préparée sous forme de scripts et docker-compose.prod.yml pour déploiement par l'humain (Gate H2).
- **Alternatives :** Provisionner directement un cloud externe pendant le développement.
- **Conséquences :** Autonomie complète de l'agent sans risque de coût cloud imprévu ni dépendance à des identifiants externes.

---

## ADR-007 : Ports d'hôte configurables pour coexistence multi-projets
- **Date :** 2026-10-06
- **Statut :** Accepté
- **Contexte :** La machine de développement héberge d'autres projets conteneurisés actifs (ex. casino-mdg, titan-erp) occupant les ports standard par défaut (5432, 8000, 9000, 3000, 3001).
- **Décision :** Rendre tous les ports d'hôte Docker Compose configurables via des variables d'environnement dans `.env` avec des valeurs par défaut alternatives en développement local : `API_PORT=8090`, `WEB_PORT=3005`, `DAGSTER_PORT=3010`, `MINIO_API_PORT=9100`, `MINIO_CONSOLE_PORT=9101`, `POSTGRES_PORT=5434`. Les réseaux et résolutions internes entre conteneurs Docker restent strictement sur leurs ports normatifs (db:5432, minio:9000, api:8000, etc.).
- **Alternatives :** Tuer/arrêter les projets existants de l'utilisateur (rejeté par l'utilisateur).
- **Conséquences :** Isolation parfaite sans conflit de ports avec d'autres conteneurs sur l'hôte, et conformité totale avec le plan d'acceptation via les variables d'environnement.

