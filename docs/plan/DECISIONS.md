# DECISIONS (Architecture Decision Records - ADR)

> Format : `ADR-NNN | date | statut | contexte | décision | alternatives | conséquences`

## ADR-070 : tableau économique interprétable, fiches métriques et gestion stricte des dimensions non combinables (R2.8)

- **Date/statut :** 2026-10-16 UTC, adopté avant code R2.8 ; Phase R2.
- **Contexte :** La phase R2 exige la constitution d'un tableau économique interprétable articulant l'inflation (NIPC), le change (BFM), l'énergie/carburants (OMH) et le commerce extérieur/activité (TBE) avec le marché vivrier de référence (pilote rizicole R2.4).
  Afin de préserver l'intégrité analytique et d'éviter les dérives d'interprétation, les directives du plan R2.8 imposent des règles strictes :
  1. Interdiction formelle d'inventer un « score global de santé macroéconomique » synthétique : les dimensions économiques sont structurellement hétérogènes et doivent rester affichées séparément.
  2. Distinction absolue entre inflation (taux de variation d'un indice de prix à la consommation NIPC) et variation de prix de marché vivrier au kg : ne jamais les confondre ou les moyenner.
  3. Distinction des flux commerciaux en volume (tonnes métriques) et en valeur (monnaie/devises) ; interdiction des ratios d'importation sur des unités incompatibles.
  4. Interdiction de raccorder implicitement des indices de bases différentes (ex: base 2016 vs base 2024).
  5. Règle de nullité stricte : tout dénominateur nul, période non alignée ou série manquante doit produire `NULL` accompagné d'un code de raison standardisé (`zero_denominator`, `missing_denominator`, `base_shift`, `incompatible_units`, `unaligned_period`, `missing_series`). L'absence de séries BFM/OMH ne produit ni zéro ni estimation LLM.
- **Décision :**
  1. **Fiches métriques normatives (`EconomicMetricCard`) :** Définition formelle de 12 fiches métriques canoniques réparties en 5 dimensions autonomes (`inflation`, `exchange_rate`, `fuel_energy`, `external_trade`, `real_activity`), chacune documentant : définition, formule, unité, fréquence, périmètre géographique, publication/source primaire et limites d'interprétation.
  2. **Vue SQL matérialisée `gold.economic_dashboard` (`014_economic_dashboard.sql`) :** Agrégation ensembliste déterministe recomputable depuis `obs.macro_observation`, `obs.cpi_observation`, `obs.trade_flow` et `gold.price_monthly_best`, intégrant le statut de complétude (`complete`, `partial`, `no_data`).
  3. **Module métier `backend/src/ketrika/gold/economic.py` :** Moteur d'évaluation robuste des métriques, de détection des changements de base, de calcul des variations calendaires sécurisées et d'articulation de transmission économique pour le pilote rizicole (ex: comparaison du coût unitaire CAF d'importation avec le prix de détail local).
  4. **Contrats API REST (`/v1/economic/indicators`, `/v1/economic/dashboard`, `/v1/economic/pilot-context`) :** Endpoints typés exposant les fiches métriques et les observations avec traçabilité et codes de nullité explicites.
- **Alternatives rejetées :** Calculer un indice composite unique pondéré (rejeté par directive R2.8), interpolation des séries manquantes par la dernière valeur connue (rejeté, fausse stabilité), raccordement aveugle des bases d'indices (rejeté, fausse continuité).
- **Conséquences :** Tableau économique rigoureusement traçable, respect absolu de la nature multidimensionnelle de l'économie, transparence totale sur les lacunes et les limites méthodologiques.

## ADR-069 : formalisation des contrats temps, origine et métriques macroéconomiques (C1–C4)

- **Date/statut :** 2026-10-15 UTC, adopté avant migration et code R2.1 ; Phase R2.
- **Contexte :** l'extension de Ketrika vers l'observatoire macroéconomique et l'aide à la décision (Phase R2) requiert l'ingestion d'indicateurs macroéconomiques généraux (PIB, taux de change, taux directeur BCM, agrégats). Détourner `price_observation` ou `cpi_observation` violerait les contrats de données et corromprait les séries de prix vivriers. De plus, la gestion temporelle pour le ML interdit tout antidatage de la disponibilité sur la simple date affichée dans un document (anti-leakage).
- **Décision :**
  1. **Table additive `obs.macro_observation` :** création de la table dédiée avec indicateur (`indicator_code`, `indicator_name`, `frequency`, `unit`, `base_period`), périmètre (`geo_scope`), vintage (`preliminary | provisional | revised | final`), valeurs brutes et numériques exactes (`NUMERIC(20,4)`), et provenance complète (`source_record_id`, `evidence`, `extraction_method`).
  2. **Contrat de disponibilité temporelle (C2 / C4) :** distinction obligatoire entre période observée (`period_start`, `period_end`), date de publication officielle (`published_at`) et première disponibilité prouvée (`first_available_at`). En l'absence d'archive datée indépendante (Wayback, log immuable), `first_available_at` prend conservativement la date de première collecte UTC (`fetched_at`), sans jamais être antidatée.
  3. **Immuabilité & Révisions :** révisions par insertion de nouvelle ligne et liaison `superseded_by` (trigger immuable interdisant les UPDATE destructifs). Les révisions météo NRT vers consolidé suivent ce même mécanisme sans écrasement.
  4. **Famille de sources (C3) :** déclaration de `source_family` pour interdire la fausse confirmation d'indépendance entre sources dérivées (ex: RTFP et WFP).
  5. **Droits :** permissions accordées à `ketrika_app` (SELECT, INSERT, UPDATE sur superseded_by) et `copilot_ro` (SELECT seul).
- **Alternatives :** réutiliser `price_observation` avec des prix factices (rejeté), réécriture destructive des historiques (interdit par AGENTS §4.3).
- **Conséquences :** séparation nette des grains, garantie d'intégrité sans régression sur l'historique et les tables existantes, conformité aux rôles DB.

## ADR-063 : garde HTTP durable, quotas atomiques et arrêt persistant

- **Date/statut :** 2026-10-14, adopté avant code sur work/r06-http-takeover-20261014 ; aucune réception produit.
- **Contexte :** reprise C explicitement autorisée ; draft Antigravity conservé sans modification et non qualifié. Compteurs mémoire, transactions distinctes et DDL au runtime ne satisfont pas la durabilité.
- **Décision :** migration explicite 0010_http_policy_budget. Réserver ensemble source/jour UTC et hostname/jour UTC dans une transaction PostgreSQL indépendante avant chaque émission (robots, retry, redirect inclus). Plafond domaine conservateur 500, réduit par la limite source et les limites déjà rencontrées ; aucune réservation partielle. Une réservation peut être consommée sans émission en cas de crash : aucun remboursement optimiste.
- **Cadence :** créneau partagé par hostname, réservé dans cette même transaction ; débit minimum déjà rencontré, attente hors transaction. Pas de deuxième throttle local. Échec SQL : PolicyStop avant réseau, sans repli mémoire ; backend mémoire uniquement explicitement injecté dans tests.
- **Arrêt :** journal SQL source/origin indépendant, sans FK bloquant une transaction de collecte. Challenge ou 401/403 : aucun retry, désactivation mémoire et persistante ; source SQL disabled lorsque sa ligne peut être verrouillée sans attendre, sinon journal reste autorité de refus. Aucun rétablissement automatique.
- **HTTP :** robots cache origin exact 24 h, absent/expiré inconnu refusé sauf acquisition contrôlée des règles ; 404/410 permettent, autres erreurs refusent. Redirections manuelles et chaque tentative contrôlée ; rejet userinfo, options de bypass, schémas non HTTP(S). En cross-origin supprimer authentification, cookies et conditions du vrai request construit. Retry-After entier/date UTC, aucune attente anticipée ; attente >300 s refuse temporairement sans disabled.
- **Contrats :** bind source avant discovery/fetch depuis registre, limites caller ne peuvent augmenter celles du registre. Les fixtures autorisées par authorize_collection utilisent le même garde, sans exemption SQL/S3. Aucun connecteur privé, aucune dépendance nouvelle, aucune migration active.
- **Alternatives :** DDL runtime, SQLite/mémoire par défaut, réservations séparées et redirect automatique rejetés.
- **Réception :** négatifs transport inerte et SQL isolé concurrence/restart/rollback/cadence, collect réelle raccordée ; un check Windows intégral final du lot stabilisé. R0.6 IN_PROGRESS.

## ADR-062 : grain prix versionné et rapprochement historique prudent

- **Date/statut :** 2026-10-13, adopté avant code sur work/r06-price-identity-20261013 ; réception produit non acquise.
- **Contexte :** ancienne concaténation ambiguë, variété/statistique absentes de la clé ; historique sans statistique explicite non classifiable automatiquement.
- **Décision :** SHA-256 de JSON ASCII compact ordonné : price_identity_v2, source_id, product_raw, variety, location_raw, actor_level, period_start ISO, period_end ISO, value_kind statistique, unit_raw, currency_raw, observed_or_imputed. Valeurs brutes exactes, NULL distinct de chaîne ; aucune normalisation implicite. Unité/devise/origine observée ou imputée sont des grains distincts, pas des révisions de valeur. Aucun champ origin géographique nouveau (R2.1 non commencé).
- **Historique :** clé ancienne seulement filtre de candidats, jamais preuve de rapprochement. Source et toutes dimensions doivent correspondre, statistique explicitement attestée dans evidence.normalization.value_kind ou preuve price_identity interne. Candidat inconnu ou multiple : aucun changement d'observation ; review_item extraction_conflict avec IDs/provenance, action review_required comptée n_rejected/n_review. Aucun prix ambigu admis en Gold ni omission silencieuse. Revue H5 sans qualification humaine fictive.
- **Transactions :** verrou transactionnel source avant recherche/écriture sur les deux chemins prix ; ancienne clé/valeur inchangée. Révision connue atomique par superseded_by et nouvelle ligne ; refus/rollback conserve toute observation. Revue durable seulement après commit explicite du propriétaire, jamais après rollback.
- **Versions :** nouvelle normalisation price_normalizer_v2 et normalization.version=2 ; reçus v1 historiques lisibles comme histoire, jamais présentés comme traitement v2. Rejeu document explicite crée nouvelle tentative. Même UUID success reste reçu original, pas une exécution du nouveau code.
- **Alternatives :** backfill statistique point et réécriture des anciennes clés rejetés ; changer tous les RecordBase rejeté, portée prix uniquement. Aucune migration/dépendance nouvelle prévue.
- **Réception :** helper et raccordement des deux loaders, ambiguïtés/revues/counters/reçus ; SQL isolé coexistence, pont exact/refus, retry, rollback/concurrence ; check complet unique du lot stabilisé. R0.6 reste IN_PROGRESS, BL-016 ouvert jusqu'à réception.

## ADR-061 : publication Gold et contrats structurels de confiance

- **Date/statut :** 2026-10-13, adopté avant code du lot B, worktree uniquement.
- **Contexte :** refresh direct sans schema_drift ; construction Dagster seule insuffisante. Une baseline apprise du contenu contrôlé serait circulaire.
- **Décision :** registre immuable en code, déclarations explicites indexées par source_id/parser_version/MIME, contrats CSV/JSON fermés et versionnés. Défaut vide pour sources publiques non qualifiées ; aucune wildcard, aucun apprentissage Bronze/allowed_fields. Ajout par changement versionné après examen explicite du format/document de référence ; structure ne prouve ni authenticité ni droits.
- **Publication :** mêmes candidats/verrous SHARE que provenance, capture des source_record avant refresh ; audit fresh par source sur ces seules références. Absent/format inconnu/dérive/lecture/SHA invalides refusent tout le lot avant REFRESH. Historique hors candidats exclu de ce lot, mais conservé dans l'audit historique Dagster ; parser ancien candidat sans déclaration refusé.
- **Reçus :** ops.dq_result ajout seul, scope publication_candidate_artifacts, version/identité contrat et parseur, effectifs/état/codes fixes. Transaction caller ; exception expose reçus, rollback externe peut les annuler, aucune durabilité implicite revendiquée. Empty/metadata_only distincts, pas de 100 % sur vide.
- **Compatibilité :** override historique de contrat = diagnostic source, pas autorisation Gold. Check Dagster sans override et refresh direct résolvent le même registre. Tests déclarent leurs contrats synthétiques avant inspection via le même registre ; aucun bypass produit. Pas de migration/dépendance nouvelle.
- **Alternatives :** baseline automatique rejetée ; stockage SQL de contrats différé (complexité non nécessaire pour registre versionné). Identité métier BL-016/R2.1 et budget Antigravity distincts.
- **Réception :** unités registre/sélection/cache ; SQL/S3 direct et Dagster, refus sans refresh et caches/observations/Bronze conservés, historique exclu/candidat inconnu ; check complet unique. R0.6 reste IN_PROGRESS.

## ADR-060 : membres traités et identité de normalisation reçue

- **Date/statut :** 2026-10-13, accepté avant code du lot A, worktree uniquement.
- **Décision :** migration ajout seule 0009_silver_attempt_member : membre ordinal/FK résultat de tentative, SourceRecord, clé document, processing_key/normalizer_version/reference_manifest_sha256 nullable ensemble. Une ligne par artefact vérifié au succès, même transaction que données/résultat ; aucun membre de réussite après rollback. Pour prix, identité ArtifactProcessingIdentity calculée par framework après normalisation liée au vrai ReferenceSnapshot, version interne price_normalizer_v1 cohérente avec normalization.version=1. Pour non-prix/aucun prix, triplet NULL explicite : aucune référence/normalisation fictive.
- **Vérification :** membres relus lors d'un succès rejoué, ordre/comptes/references/clé document exacts ; identité prix recomputée depuis ses champs persistés. Intention et résultat ne constituent pas seuls un reçu complet. Aucune donnée collectée ne fournit la référence de configuration ou le processing_key. Archive SHA reste configuration interne non institutionnellement qualifiée.
- **Réception :** SQL/S3 identité reçue identique à preuve de normalisation et changement SHA configuration produisant identité différente, aucun succès incomplet accepté, immutabilité ; réception complète lot A. Pas de backfill ni modification d'observation/Bronze active.

## ADR-059 : partitions document-version et replay Dagster sans collecte

- **Date/statut :** 2026-10-13, accepté avant code dans le lot A ; aucune réception principale.
- **Décision :** identité document-version = SHA d'une frame JSON ASCII versionnée (source, SourceRecord UUID, SHA contenu, parser_version), sans inférer édition logique/URL/normalisation. Table ajout seule meta.document_partition (clé, premier run Bronze enregistré, SourceRecord, source, SHA, parser). Même identité conserve son origine, toute divergence refuse. Migration 0008_document_partition ajoute document_key nullable/FK à silver_attempt, sans backfill des anciennes tentatives. Historique UPDATE/DELETE/downgrade refusés.
- **Dagster :** un job document_replay par source éligible, DynamicPartitionsDefinition source-scopée, clés publiées après commit Bronze. Les assets/checks/schedules existants restent identiques. Une erreur de publication des clés reste explicite ; le registre SQL n'est pas effacé. Chaque job relit le membre exact du registre, crée un nouveau run partitionné et parse hors réseau ; pas d'AssetIn Bronze déclenchant une acquisition. Identité de run inclut UUID/run metadata et partition_key du document.
- **Sémantique :** replay document peut provenir d'un run success, à la différence de resume du lot running/failed. Intention relie document_key et run d'origine ; un seul artefact exact doit correspondre. La référence de normalisation effectivement utilisée reste dans les observations (ADR-053) ; cette partition ne revendique pas l'identité complète des transformations.
- **Réception :** clés déterministes/différentes versions/entrées invalides, définition réelle du job, isolation des sources, registre SQL immuable, replay materialisé et retry idempotent sans fetch, supersession de document révisé. Tests ciblés puis réception complète du lot, sans migration active ni nouveau source/connecteur.
- **Alternatives rejetées :** une partition par UUID de tentative, déduire document/édition de l'URL, réactiver une origine terminée, dépendance Bronze forçant refetch.

## ADR-058 : tentatives Silver natives et reprise explicite

- **Date/statut :** 2026-10-13, accepté avant code du lot A dans worktree ; réception principale non réalisée.
- **Contexte :** références Bronze persistées, mais aucune intention durable Silver ni reprise après perte du processus. Une FK écrite indépendamment après verrou du run peut s'auto-bloquer.
- **Décision :** tables ajout seules 0007_silver_attempt : intention unique par run et résultat unique par intention, immuables UPDATE/DELETE. Intention indépendante committée AVANT transaction de données/verrou run ; résultat success dans la transaction Silver, failed après rollback. Classes d'erreurs seulement, statistiques bornées non négatives sans texte collecté. Le digest enregistré doit correspondre au lot fourni avant parsing.
- **Exclusion :** verrous advisory PostgreSQL session-scoped par UUID run et source, connexion dédiée conservée jusqu'au résultat ; source sérialise aussi deux runs distincts traitant le même document (une ligne courante inexistante ne peut être verrouillée par supersession). Acquisition non bloquante, contention = refus sans marquer le run concurrent failed. Libération explicite inverse, connexion invalidée si acquisition partielle/libération impossible ; crash libère les verrous. Aucun délai supposé ne prouve un crash.
- **Reprise :** entrée Python explicite depuis UUID/source, sans discover/fetch. Sous verrou de l'ancien run, refuser success/worker actif, relire le registre ; créer nouveau run et copier ses membres immuables dans un nouveau header, puis exécuter Silver avec lien resumed_from. Ancien run et intention non modifiés. Intention sans résultat = unknown, jamais failed/success inventé. Reprise après rollback ou arrêt brutal idempotente via loaders existants ; aucune recovery automatique.
- **Succès répété :** relecture du même résultat success et du même lot enregistré permet de retourner les compteurs persistés sans parsing ; résultat incomplet/incohérent refuse. Ce reçu n'est pas une nouvelle qualification des octets/source/modèle.
- **Identité :** intention contient SHA du batch exact ; partitions document/version et identité complète de normalisation restent des étapes du lot A, pas déduites de ce registre de tentatives. Pas de schéma métier/donnée active/Bronze altéré, aucun ancien run réactivé.
- **Réception :** unités d'ordre/expurgation/gardes ; vrais SQL/S3 success, rollback, conflit, verrou concurrent et arrêt du processus/reprise sans refetch, invariance historique. Check global seulement à stabilisation du lot A complet ; R0.6 reste IN_PROGRESS.
- **Alternatives rejetées :** mutable retry de l'ancien run, succès déduit du timeout, commit de données pour préserver l'intention, journal indépendant après verrou FK, lock mémoire seulement.

## ADR-056 : consommation Silver du registre Bronze

- **Date/statut :** 2026-10-13, accepté avant raccordement du lot A.
- **Décision :** après liaison du run, relecture du batch SQL et comparaison canonique au batch fourni ; absent/corrompu/divergent refuse avant parse. GET fraîche/SHA des octets conservées. Échec rollback puis reçu indépendant expurgé.
- **Limites :** garde seule ne livre ni reprise ni tentative ni partition ; réception incluse dans lot A, pas check complet isolé du helper.

## ADR-057 : méthode d'exécution par lots et profiling readonly

- **Date/statut :** 2026-10-13, accepté avant code sur demande explicite utilisateur ; ADR-056 réservé à la préparation Silver.
- **Contexte :** incrément 13 backend 2161,30 s/build 190556 ms ; petites réceptions et checks de base successifs multiplient cette dépense.
- **Décision :** AGENTS §3.3 : développement ciblé/commits worktree puis réception complète par lot fonctionnel ; audit de reprise sans double check automatique. QA non répétée si inclusion effective de ses cas prouvée dans le JUnit global, jamais sur son seul effectif. Aucun échec/skip obligatoire promu en succès.
- **Diagnostic :** qa-profile lit un JUnit archivé dans Docker/network none/bind readonly, sans Compose, seed, SQL, S3 ni réexécution. Durées Decimal, paramètres de noms masqués, rapport borné, aucune qualification. Pas de dépendance nouvelle.
- **Réception de ce lot méthode :** exception bornée pour gouvernance/diagnostic readonly sans chemin applicatif modifié ; tests dédiés/lint/types/commandes Windows-Linux/cohérence du plan. Check applicatif b139c90/3975 conservé comme preuve historique, pas nouvelle réception produit. Changer sélection ou runner check exige contrôle complet.
- **Limites :** fits scientifiques non accélérés ; profiler puis traiter BL-012 séparément. H1–H7/Bronze/critères DONE conservés, aucun statut R produit clos.
- **Alternatives rejetées :** retirer/mocker les validations scientifiques, multiplier les petits checks, déclarer verts des skips.

## ADR-055 : R0.6 — registre SQL immuable des lots Bronze

- **Date/statut :** 2026-10-12, accepté avant transfert principal ; 39 unités et types reçus au worktree seulement, vrais SQL/réception principale requis.
- **Contexte :** BronzeBatch ne survit actuellement que dans la sortie Dagster. Reprendre ses références exactes ne doit ni discover ni fetch ni inventer un document logique.
- **Décision :** migration ajout seule 0006_ingestion_batch, header meta.ingestion_batch par run réel et membres ordonnés meta.ingestion_batch_member avec FK SourceRecord. Tous champs RawArtifact et parser_version conservés, SHA canonique du lot, bornes 100000 membres/32 MiB ; lot vide explicite. Verrou run avant écriture dans transaction Bronze existante, jamais transaction indépendante après verrou ; helper sans commit. Répétition identique sans mutation, divergence refusée. Lecture revalide les parents SQL et le SHA sans HTTP ; elle ne certifie pas les octets, que Silver doit toujours relire/vérifier. Refus des changements ORM pendants avant populate_existing, sans écraser les compteurs ou un parent modifié.
- **Immutabilité :** triggers refusent UPDATE/DELETE des deux tables ; downgrade refuse la suppression historique. Aucun backfill, Bronze/Silver existant inchangé. Nouveau head Alembic exact 0006_ingestion_batch dans le test de publication ; pas d'acceptation opportuniste de plusieurs heads.
- **Raccordement :** seul propriétaire Bronze natif persiste le lot avant son commit, dans sa transaction ; échec ledger implique rollback puis reçu d'échec indépendant expurgé. Appelants historiques non raccordés ne revendiquent pas le registre.
- **Réception :** vrais SQL lot vide/non vide/relecture nouvelle session/répétition/conflit/parents/rollback/immutabilité/concurrence ; durabilité des propriétaires/assets réelle conservée. QA et check Windows intégraux/source figée/originaux/préservation/scan/commit requis.
- **Limites :** registre de membres Bronze seulement, pas ledger des tentatives Silver, leases/recovery automatique, partitions ni source qualifiée. R0.6 reste IN_PROGRESS ; aucune reprise réussie déduite de la seule reconstruction d'un objet batch.
- **Alternatives :** JSON Dagster seul, refetch de reprise, digest déclaré sans parents relus, suppression du journal au downgrade (rejetés).

## ADR-053 : R0.6 — liaison transactionnelle des références prix

- **Date / statut :** 2026-10-12, accepté avant transfert principal incrément 12 ; préparation 106 unités et six SQL/S3 reçue séparément, pas réception principale.
- **Contexte :** archive et verrou seuls ne prouvent pas que le normaliseur utilise le snapshot. Le cache ORM peut représenter des références anciennes.
- **Décision :** contexte privé session/transaction racine active ; refus de changements ORM pendants sur les cinq tables ref ; SHARE locks en ordre fixe/5s, manifeste SQL et archive avec GET vérifiée dans la même transaction. Avant chaque normalisation liée, vérifier contexte actif/même session/transaction/manifeste inchangé. Entités ref chargées avec populate_existing ; chaque resolver refuse les modifications ORM ref pendantes avant lecture, y compris un caller historique sans contexte, sans écrasement silencieux.
- **Preuve :** normalization.reference_snapshot contient SHA/clé/comptes/version/scope interne/source_verified=false, calculés depuis le contexte et non le contenu collecté. Le SHA est comparé en supersession : changement de configuration implique une nouvelle ligne, jamais modification d'une valeur existante ni prétention de révision institutionnelle.
- **Raccordement :** batch Silver prépare un contexte une fois au premier PriceRecord et le transmet au loader. Autorisation limitée à archiver la configuration interne avec le store original ; le parseur conserve son store source readonly vérifié, sans refetch/discover ni SourceRecord fictif. Pas de commit/rollback implicite, nouvelle dépendance, migration ou clé naturelle.
- **Réception :** unités contexte/session/transaction/erreurs/lectures fraîches/batch ; vrais SQL/S3 usage du snapshot, relecture persistée, retry sans doublon, contexte expiré et changements propres refusés, ancien cache rafraîchi. QA 549/50 puis check Windows complet figé, originaux/snapshot/préservation/gouvernance/scan/commit obligatoires.
- **Fixture de panne B-R038 :** le wrapper after_insert transmet les kwargs au vrai loader pour conserver le nouveau contexte ; assertions insertion SQL=1, RuntimeError, rollback/prix=0, reçu durable/expurgation inchangées. Une erreur de signature TypeError avant insertion ne remplace pas ce scénario.
- **Limites :** références configurées non institutionnellement qualifiées ; callers historiques non liés ne revendiquent pas le snapshot. Ledger/rejeu historique/partitions/reprise/robots/garde SQL structure restent requis ; durabilité native incrément 7 conservée, aucun transfert global stages.py ancien.
- **Alternatives :** SHA fourni par parseur, archive hors transaction, ORM stale, inférence de provenance officielle, remplacement de la durabilité reçue (rejetées).

## ADR-052 : R0.6 — archive référentiel interne

- **Date / statut :** 2026-10-12, accepté avant transfert principal de l'incrément 11 ; préparation 17 unités et deux vrais S3 reçus séparément.
- **Contexte :** le manifeste SQL/SHA reçu ne conserve pas à lui seul ses octets pour un futur ledger/rejeu. Un snapshot configuré n'est pas une publication institutionnelle.
- **Décision :** valider contenu/frame canonique/SHA/comptes du ReferenceManifest puis archiver via BronzeStore sous racine interne reference_manifest/yyyy/mm/SHA.json. Application/json, URL vide, manual_upload/http_status 0/internal-snapshot;source_verified=false ; aucun Source/SourceRecord fictif. Descripteur contrôlé puis GET borné frais/SHA/octets exacts avant référence immutable. Pas de suppression/écrasement ni URL institutionnelle attribuée.
- **Réception :** 17 unités invalidité/descripteur/relecture/erreur/date et deux S3 réels répétition/versions inchangées/lecture endommagée simulée, jamais objet modifié. QA 504/44 puis check Windows complet, source figée, snapshot/préservation/scan/commit principaux obligatoires.
- **Limites :** snapshot interne non qualifié des données SQL configurées ; pas provenance officielle des mappings, liaison au normaliseur, ledger, partitions ou reconstruction reçus. Répétition S3 séquentielle testée, pas qualification de PUT concurrents ou réparation de sidecar absent. Aucun test de qualification n'écrit dans le bucket actif. Verrou référentiel et brouillon ledger du worktree non adoptés implicitement.
- **Alternatives :** SHA sans octets, lien institutionnel inventé, SourceRecord artificiel, accepter descripteur sans GET (rejetées).

## ADR-051 : R0.6 — preuve explicite d'absence prix

- **Date / statut :** 2026-10-12, accepté avant transfert principal de l'incrément 10 ; préparation 56 unités et trois SQL/S3/Gold reçue séparément.
- **Contexte :** BL-017 : un prix NULL avec marqueur ND/NA source exact est une observation d'absence, pas un nombre. Le binder ne reconnaît pas encore ce cas.
- **Décision :** pour price_value NULL + missing_code ND/NA explicite, exiger price_mga_per_base NULL et concordance du brut avec les tokens déjà normalisés : NFKC/strip/casse, ND/NA, vide/tiret = ND, longueur <=128. Cellule price_raw/value/text explicite à coordonnées exactes ; attentes remplacées par le brut SQL, toutes les identités conservées. Nombre non NULL + code absence refuse. Sans code, refus historique conservé ; ancien price_value/number jamais converti implicitement en texte.
- **Réception :** 23 unités nouvelles + 33 binders historiques et trois SQL réels ND/NA/cellule discordante ; relecture SQL des NULL, preuve Bronze, DQ persisté et refresh Gold numérique réellement vide/0-0-NULL. Manifeste QA 485/42, check Windows complet, snapshot/préservation/scan/commit exigés après transfert.
- **Limites :** ne fabrique ni zéro ni chiffre, ne publie pas de prix dérivé/prévision et ne qualifie pas une source. Aucun ORM, migration, parser de source, backfill ou donnée active changé. Les preuves historiques non conformes restent refusées ; BL-017 ne sera clos qu'après réception principale complète.
- **Alternatives :** ND→0, accepter NULL sans preuve, transformer silencieusement une preuve numérique, réécrire l'historique (rejetées).

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

