# DECISIONS (Architecture Decision Records - ADR)

> Format : `ADR-NNN | date | statut | contexte | décision | alternatives | conséquences`

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

