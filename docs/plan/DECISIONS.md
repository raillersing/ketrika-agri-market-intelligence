# DECISIONS (Architecture Decision Records - ADR)

> Format : `ADR-NNN | date | statut | contexte | décision | alternatives | conséquences`

## ADR-097 : réponses du copilote analyste basées exclusivement sur des résultats exécutés, zéro chiffre inventé, métadonnées de provenance complètes et abstention explicite (R6.3)

- **Date/statut :** 2026-10-17 UTC, adopté avant code R6.3 ; Phase R6.
- **Contexte :** La tâche R6.3 impose de répondre avec des résultats exécutés et référencés. Les directives normatives de R6.3 et d'AGENTS.md imposent :
  1. Respect absolu des Règles 6 et 7 d'AGENTS.md :
     - Aucun chiffre inventé dans le texte en prose (substitution mécanique via `build_cell_placeholders` et `assemble_final_response` ou présentation tabulaire déterministe).
     - Tout nombre affiché dans la réponse doit provenir d'une cellule SQL auditée sur le schéma Gold ou d'un calcul déterministe certifié.
  2. Métadonnées de provenance complètes :
     - Citation de la source officielle (`citations`: source_id, type de source), provenance Bronze et Gold, horodatage, statut métrologique (`value_kinds`: `observed`, `imputed`, `forecast`, `composite`).
  3. Gestion loyale de l'ambiguïté et du hors-périmètre :
     - Si une question de l'utilisateur ne concerne pas les filières vivrières malgaches couvertes (riz, maïs, manioc, huile, sucre, légumineuses, farine) ou pose une question hors domaine (actualité non agricole, sports, météo internationale), l'agent refuse poliment avec une explication claire et loyale (`sql = ""`), sans tenter de deviner ou de renvoyer par défaut les prix du riz.
  4. Benchmark de qualification :
     - Validation des 22+ questions d'évaluation réelles du corpus `backend/tests/copilot_eval.yaml` avec une exactitude >= 80% et 0 requête interdite.
- **Décision :**
  1. Étendre `CopilotAgent` pour détecter les requêtes hors domaine agricole et renvoyer un message d'abstention loyale sans générer de fausse requête SQL.
  2. Structurer la réponse avec métadonnées enrichies de traçabilité et de nature des valeurs.
  3. Garantir que tout texte produit passe par le validateur anti-hallucination `validate_anti_hallucination_prose` (zéro chiffre libre hors placeholders).
- **Alternatives rejetées :**
  - Renvoyer par défaut les prix du riz d'Analamanga sur n'importe quelle question obscure (rejeté, fausse réponse trompeuse).
  - Laisser le LLM rédiger librement des chiffres dans la prose (rejeté, risque majeur d'hallucination).
- **Conséquences :**
  - Réponses 100% vérifiables et auditables, conformité absolue aux règles constitutionnelles, expérience utilisateur transparente et honnête.


## ADR-096 : architecture des workflows IA bornés, isolation des rôles, budgets atomiques sous concurrence, reprise d'état sans double publication et choix officiel du modèle (R6.2)

- **Date/statut :** 2026-10-17 UTC, adopté avant code R6.2 ; Phase R6.
- **Contexte :** La tâche R6.2 impose de borner rigoureusement tous les workflows d'intelligence artificielle et d'orchestration dans Ketrika. Les directives normatives de R6.2 et d'AGENTS.md imposent :
  1. Frugalité et séparation des responsabilités : Dagster demeure l'orchestrateur central de collecte et calcul ; les tâches IA sont découpées en petits rôles spécialisés et déterministes (reconnaissance, extraction, analyse, rédaction), sans framework multi-agent opaque ou complexe non supervisé.
  2. Bornes contractuelles d'exécution pour chaque workflow : chaque exécution est modélisée par un état persistant (`WorkflowExecutionState`, `WorkflowStep`), bornée par des plafonds stricts : nombre maximal d'étapes (`max_steps`), nombre d'appels d'outils (`max_tool_calls`), consommation maximale de tokens (`max_tokens`), durée maximale d'exécution (`max_duration_seconds`), et coût maximal (`max_budget_usd`). Dès qu'un plafond est atteint, l'exécution s'interrompt immédiatement et proprement (`WorkflowLimitExceededError`).
  3. Sécurité budgétaire atomique sous concurrence : le contrôle budgétaire de `BudgetGuard` doit être atomique et résistant aux accès concurrents (`AtomicBudgetGuard`). Deux appels simultanés ne peuvent en aucun cas dépasser le budget mensuel (`LLM_MONTHLY_BUDGET_USD`) ou le budget par exécution (`LLM_PER_RUN_BUDGET_USD`).
  4. Interdiction formelle d'ajout autonome de sources : un document ou un workflow IA peut suggérer un nouveau domaine ou une nouvelle source, mais cette proposition est strictement consignée en attente de revue humaine (`PENDING_HUMAN_REVIEW`) et ne peut en aucun cas être injectée automatiquement dans le registre de production (`registry/sources.yaml`).
  5. Reprise d'état idempotente sans duplication de publication : en cas d'interruption réseau ou de redémarrage système, le moteur restitue l'état exact du workflow et reprend à la première étape non complétée sans réexécuter les étapes antérieures ni dupliquer les publications ou alertes déjà émises.
  6. Mode replay explicite et fail-closed : en mode `LLM_PROVIDER=replay`, l'absence d'une réponse pré-enregistrée entraîne une erreur explicite immédiate (`KeyError` / `ReplayNotFoundError`), interdisant tout fallback fictif ou halluciné.
  7. Modèle de référence et tarification officielle : le modèle retenu pour l'intelligence de marché économique est Google Gemini 2.0 Flash / 1.5 Flash (taux officiel vérifié : $0.075 / 1M tokens d'entrée, $0.30 / 1M tokens de sortie ; cache hit = 0 USD). Les logs d'audit sont épurés de tout secret ou clé d'API.
- **Décision :**
  1. Créer le module `backend/src/ketrika/copilot/workflow.py` avec les modèles Pydantic d'état (`WorkflowExecutionState`, `WorkflowStep`, `WorkflowLimits`) et le moteur `BoundedWorkflowRunner`.
  2. Étendre `BudgetGuard` avec un mécanisme atomique de réservation (`AtomicBudgetGuard`) thread-safe.
  3. Intégrer la détection de documents hostiles (les textes collectés sont des données pures et ne peuvent ni modifier les quotas du workflow ni altérer les droits).
- **Alternatives rejetées :**
  - Laisser un workflow IA itérer sans plafond d'étapes jusqu'à convergence (rejeté, risque critique de boucle infinie et d'explosion budgétaire).
  - Permettre l'enregistrement automatique de nouvelles sources Web scrapées sans validation humaine (rejeté, violation d'AGENTS.md §5 H4/H7).
  - Tolérer des dépassements de budget lors d'appels concurrents (rejeté, non-respect du garde-fou budgétaire H6).
- **Conséquences :**
  - Maîtrise financière et temporelle absolue de tous les composants IA, reprise résiliente après panne sans effet de bord, intégrité totale du registre de sources.


## ADR-095 : sécurisation absolue des outils d'analyse et SQL Guard du Copilot (outils typés, SQL Gold strict, interdiction des CTE d'écriture et fonctions réseau, timeouts et validation de paramètres sans fuite) (R6.1)

- **Date/statut :** 2026-10-17 UTC, adopté avant code R6.1 ; Phase R6.
- **Contexte :** La tâche R6.1 impose de sécuriser les outils de lecture et d'analyse utilisés par le copilote et l'IA de marché. Les directives normatives de R6.1 et AGENTS.md imposent :
  1. Catalogue d'outils typés et autorisés :
     - Séries temporelles de prix, faits de marché, provenance et sources, couverture des relevés, prévisions qualifiées, calendrier agroclimatique.
     - Privilégier les outils métier déterministes pour les calculs et requêtes récurrents plutôt que de générer du SQL ad-hoc non contraint.
  2. SQL Guard AST strict :
     - Interrogation exclusive du schéma `gold` (seules les vues analytiques auditées sont autorisées : `price_obs_current`, `price_monthly`, `price_monthly_best`, `price_changes`, `stock_latest`, `trade_monthly`, `import_dependency`, `weather_monthly`, `cpi_food`, `market_health`, `source_health`, `forecast_latest`, `market_coverage`, `economic_dashboard`).
     - Instruction unique (`SELECT` strict).
     - **Interdiction formelle des CTE modifiants** : détection et blocage de tout CTE contenant `INSERT`, `UPDATE`, `DELETE`, `DROP` ou des expressions de modification.
     - **Interdiction formelle des fonctions réseau ou d'exfiltration** (`http_*`, `net_*`, `dblink*`, `query_to_xml`, etc.) et des fonctions système (`pg_*`, `lo_*`, `current_setting`, etc.).
     - Injection ou clampage automatique de `LIMIT <= 500`.
     - Exécution sous rôle PostgreSQL restreint `copilot_ro` avec `statement_timeout = 5000` ms (5 secondes).
  3. Validation stricte des paramètres et hygiène des messages d'erreur :
     - Contrôle des paramètres produit et localisation (taxonomie officielle). Rejet immédiat de toute valeur suspecte ou inconnue.
     - En cas d'erreur ou d'interdiction, **exposition d'un message d'explication standardisé et sans fuite d'informations sensibles** (aucun dump de variables d'environnement, secrets, adresses IP ou schémas internes protégés).
- **Décision :**
  1. Renforcer `backend/src/ketrika/copilot/sql_guard.py` avec inspection récursive de tous les CTEs (`exp.Insert`, `exp.Update`, `exp.Delete`, `exp.Command`), liste noire étendue des fonctions réseau/exfiltration, et intégration des vues `market_coverage` et `economic_dashboard`.
  2. Créer le module `backend/src/ketrika/copilot/tools.py` exposant le catalogue d'outils d'analyse typés Pydantic (`ToolCatalog`) avec validation stricte des taxonomies autorisées et gestion des erreurs sans fuite d'information.
  3. Mettre à jour `backend/src/ketrika/copilot/__init__.py`.
- **Alternatives rejetées :**
  - Permettre l'exécution de requêtes SQL arbitraires sans parser AST (rejeté, risque majeur d'injection et de contournement).
  - Tolérer des CTEs d'écriture (`WITH del AS (DELETE ...) SELECT ...`) au motif que l'instruction racine est un SELECT (rejeté, faille d'écriture en base).
  - Renvoyer la stack trace complète ou les détails techniques de connexion à l'utilisateur lors d'un échec (rejeté, fuite de vecteurs d'attaque).
- **Conséquences :**
  - Cloisonnement étanche et éprouvé des accès analytiques, impossibilité physique d'écriture ou d'accès aux tables système/privées, robustesse face aux injections de requêtes.

## ADR-094 : architecture des scénarios d'approvisionnement et des trois parcours pilotes décisionnels (régulateur public, acheteur commercial, vulgarisation agricole), étanchéité anti-injection et gouvernance humaine auditée (R5.8)

- **Date/statut :** 2026-10-17 UTC, adopté avant code R5.8 ; Phase R5.
- **Contexte :** La tâche R5.8 impose de concevoir et structurer les scénarios d'offre et les fiches pilotes d'aide à la décision pour trois profils réels d'acteurs de la filière vivrière malgache (institution publique/régulation, acheteur/collecteur commercial, planificateur/vulgarisateur agricole). Les directives de R5.8 et d'AGENTS.md imposent :
  1. Structurer 3 parcours décisionnels distincts :
     - *Institution publique / Régulateur (ex: SPM, MIC)* : surveiller les tensions d'approvisionnement urbain, estimer le déficit net et planifier les interventions de régulation ou les importations d'appoint.
     - *Acheteur commercial / Agro-industriel (ex: minoteries, grossistes d'Anosibe)* : planifier les achats de campagne en synchronisation avec les décades de pic d'arrivages, optimiser la rotation des entrepôts et minimiser la pression à la hausse sur les prix de collecte.
     - *Planificateur agricole / Vulgarisation (ex: MinAE, DRDA)* : comparer les fenêtres agronomiques nominales et les retards induits par le stress hydrique précoce, évaluer la durée de la soudure locale.
  2. Scénarios déterministes bornés :
     - Paramètres explicitement typés avec source ou justificatif d'hypothèse (`ScenarioParameter`).
     - Si un paramètre obligatoire est absent, le moteur refuse formellement le calcul (`missing_parameters`), sans jamais fabriquer une valeur invisible.
  3. Sécurité et intégrité constitutionnelle :
     - **Interdiction formelle de modification de scénario par le contenu collecté** (AGENTS.md Règle 10 : les données scrapées ne sont jamais des instructions).
     - **Interdiction formelle de générer des ordres d'achat financiers autonomes** : Ketrika est un système d'aide à la décision et d'intelligence de marché, pas un bot de trading autonome.
     - Traçabilité et versionnage : auteur interne (`author_id`), version (`v1.0`), date et empreinte.
  4. Gouvernance humaine et honnêteté métrologique :
     - Préparation d'un protocole d'essai et d'un questionnaire structuré pour les futurs utilisateurs humains (`docs/protocols/decision_pilot_protocol.md`).
     - Règle constitutionnelle H7 : aucun contact ni recrutement de tiers sans validation explicite.
     - Les rapports de scénarios portent obligatoirement `human_reviewed: false` et `evaluation_status: "NOT_EVALUATED"` tant qu'une séance humaine en conditions réelles n'est pas consignée. Aucune revendication de « pilote client réussi » sans séance documentée.
- **Décision :**
  1. **Création du module `backend/src/ketrika/supply/decision_pilot.py` :**
     - Enums : `DecisionPersona`, `DecisionJourneyType`.
     - Modèles Pydantic : `ScenarioParameter`, `DecisionScenarioDefinition`, `DecisionImpactMetric`, `DecisionPilotReport`.
     - Moteur `DecisionPilotEngine` implémentant les trois parcours d'évaluation.
  2. **Exposition API dans `backend/src/ketrika/api/routers/supply.py` :**
     - `POST /v1/supply/scenarios/run` et `GET /v1/supply/scenarios/templates`.
  3. **Documentation du protocole d'évaluation :**
     - `docs/protocols/decision_pilot_protocol.md`.
- **Alternatives rejetées :**
  - Laisser le LLM générer les chiffres d'impact d'un scénario (rejeté, violation d'AGENTS.md Règles 6 et 7).
  - Générer automatiquement des bons d'achat ou contrats fournisseurs (rejeté, responsabilité financière humaine exclusive).
  - Alléguer un succès pilote avant toute revue humaine réelle (rejeté, fraude de qualification proscrite par R5.8).
- **Conséquences :**
  - Outil d'aide à la décision robuste, transparent, mathématiquement traçable et directement prêt pour les tests utilisateurs humains.


## ADR-093 : prévision des fenêtres et pics d'approvisionnement des marchés, as-of cutoff temporel, décalage logistique récolte/marché et règle d'abstention sous historique insuffisant (R5.7)

- **Date/statut :** 2026-10-17 UTC, adopté avant code R5.7 ; Phase R5.
- **Contexte :** La tâche R5.7 impose de prévoir les fenêtres d'approvisionnement et les pics d'arrivages sur les marchés vivriers malgaches, tout en réutilisant les contrôles d'évaluation rigoureux (as-of splits, calibration déterministe). Les directives normatives de R5.7 imposent :
  1. Fixer la cible : arrivages physiques (`inflow_arrival`) ou volume d'approvisionnement en kg / tonnes, à résolution temporelle décadaire (D1: 1-10, D2: 11-20, D3: 21-fin) cohérente avec le calendrier cultural et les enquêtes de marché.
  2. Baseline calendrier / récolte : le pic d'arrivage sur le marché terminal de gros (ex: Anosibe, Toamasina) découle de la fenêtre de récolte dans les bassins fournisseurs (ex: Alaotra, Marovoay, Vakinankaratra) modulée par un décalage logistique $\tau_{\text{logistique}} \in [1, 2]$ décades (séchage, battage/usinage paddy $\to$ riz blanc, chargement et transport par camion).
  3. Cloisonnement temporel as-of strict : interdiction absolue de toute fuite d'information future. Une prévision à date $T_{\text{as-of}}$ n'a accès qu'aux relevés de quantités antérieurs ou égaux à cette date.
  4. Règle métrologique d'honnêteté sur les données insuffisantes : **au moins deux cycles complets d'arrivages réels observés sont requis** pour prétendre calibrer un modèle statistique saisonnier empirique. Si l'historique d'observations réelles couvre moins de deux cycles complets (ex: quelques semaines ou mois de relevés pilotes), le système refuse de simuler de fausses années d'entraînement. Il classe obligatoirement la prévision en `qualification: "experimental_baseline"` ou `"abstained_insufficient_history"` et fournit la projection agronomique baseline assortie d'une note d'incertitude qualitative.
  5. Les labels de pics d'offre sont dérivés **exclusivement des quantités physiques observées**, jamais d'un minimum sur la courbe de prix (décorrélation possible liée au stockage spéculatif ou aux coûts logistiques).
  6. Évaluation indépendante sur quantités réelles : métriques de calage temporel (erreur en décades / jours entre pic prévu et pic observé) et de couverture du volume de campagne (% des arrivages tombant dans la fenêtre prédite).
  7. Calculs déterministes : amplitudes, largeurs de fenêtres et incertitudes sont calculées mathématiquement, jamais générées par un LLM.
- **Décision :**
  1. **Création du module `backend/src/ketrika/supply/peak_forecast.py` :**
     - Modèles Pydantic : `SupplyWindowPrediction`, `PeakEvaluationResult`, `CycleSufficiencyReport`.
     - Moteur `SupplyPeakForecastEngine` :
       - `assess_data_sufficiency(records, min_cycles=2)` : vérification stricte du nombre de cycles complets couverts par les observations.
       - `predict_supply_window(harvest_window, logistics_lag_dekads=1, historical_arrivals=None, as_of_date=None)` : projection déterministe de la fenêtre et du pic d'approvisionnement, avec décalage logistique explicite et qualification selon l'historique disponible.
       - `detect_observed_peaks(records)` : identification du pic réel d'arrivages à partir des tonnages physiques.
       - `evaluate_peak_forecast(prediction, test_arrival_records)` : confrontation empirique indépendante (erreur de calendrier en décades/jours, taux de couverture volumique).
  2. **Route API dédiée :**
     - Exposition dans `backend/src/ketrika/api/routers/supply.py` (`/v1/supply/peak-forecast`) avec traçabilité complète de la provenance, de la zone d'approvisionnement et du niveau de qualification.
- **Alternatives rejetées :**
  - Entraîner un modèle ML complexe sur des données synthétiques pour faire croire à un modèle saisonnier validé (rejeté, violation directe de la consigne utilisateur et d'AGENTS.md §8).
  - Inférer le pic d'arrivage à partir du point le plus bas des prix de détail (rejeté, violation de R5.7).
- **Conséquences :**
  - Prévisions d'approvisionnement physiquement plausibles, auditables, scientifiquement honnêtes et directement exploitables par les acteurs de la chaîne de valeur vivrière.


## ADR-092 : architecture de bilan d'approvisionnement sans double comptage, conservation de masse et étanchéité imports vs arrivages (R5.6)

- **Date/statut :** 2026-10-17 UTC, adopté avant code R5.6 ; Phase R5.
- **Contexte :** La tâche R5.6 impose de construire les bilans d'approvisionnement des marchés vivriers et des bassins de production sans aucun double comptage. Les directives normatives de R5.6, SPECS §27 et les règles constitutionnelles d'AGENTS.md imposent :
  1. Équation stricte de conservation de masse :
     $$\text{Stock}_{\text{fin}} = \text{Stock}_{\text{début}} + \text{Entrées} - \text{Sorties} - \text{Ventes} - \text{Pertes}$$
  2. Prévention formelle des collisions macro/micro : une importation douanière nationale (`trade_flow` des douanes au port de Toamasina) ne doit **jamais** être additionnée aux arrivages physiques observés sur un marché de gros (`inflow_arrival` sur le marché d'Anosibe), car le riz importé au port constitue déjà la cargaison des camions arrivant à Anosibe. L'additionner constituerait un double comptage dévastateur.
  3. Les volumes d'importations nationales ne sont pas attribuables à un marché spécifique sans preuve formelle d'allocation logistique (`allocated_imports`).
  4. Les stocks statiques d'inventaire (`stock_inventory`) ne s'additionnent **jamais** comme un flux de production périodique.
  5. Règle d'honnêteté métrologique : **un composant inconnu reste inconnu**. Si les pertes post-récolte ou les ventes de détail n'ont pas fait l'objet d'enquêtes observées, le système refuse catégoriquement de présenter un solde net calculé comme un « total observé ».
  6. Séparation étanche entre **Bilan Observé Partiel** (`observed_partial`) fondé uniquement sur des faits vérifiés et **Scénario de Simulation** (`scenario_simulation`) paramétré avec des hypothèses explicites versionnées hors des tables d'observations.
- **Décision :**
  1. **Création du module `backend/src/ketrika/supply/balance.py` :**
     - Modèles de données Pydantic : `BalanceTerm`, `SupplyBalanceReport`, `ScenarioAssumption`.
     - Moteur `SupplyBalanceEngine` :
       - `compute_observed_partial_balance(market_code, product_raw, start_date, end_date, records)` : compilation des flux observés, identification explicite des termes inconnus (`is_observed=False`, `quantity_kg=None`), calcul des sommes partielles entrées/sorties sans falsification.
       - `simulate_scenario_balance(market_code, product_raw, start_date, end_date, records, assumptions)` : bilan complet sous hypothèses paramétrées (taux de perte post-récolte estimé, ratio de consommation journalière) clairement identifié comme scénario non observé.
       - `check_customs_vs_market_double_count(market_arrivals, customs_imports)` : alerte automatique et blocage d'addition si tentative de combiner flux douaniers et arrivages locaux sur le même périmètre.
       - Vérification de la conservation de masse sur les séries complètes ($\Delta \text{Stock} = \text{Entrées} - \text{Sorties}$).
  2. **Auditabilité totale :**
     - Chaque terme de bilan référence obligatoirement soit un `source_record_id` (fait Bronze), soit un `assumption_id` (scénario paramétré).
- **Alternatives rejetées :**
  - Deviner les ventes journalières pour forcer l'équilibre du bilan (rejeté, falsification prohibée par AGENTS.md §4.9).
  - Additionner les statistiques douanières nationales aux tonnages des marchés d'Antananarivo (rejeté, double comptage illégal).
- **Conséquences :**
  - Bilans de marché rigoureux, conformes à la physique des flux, explicables aux analystes et sans agrégation hybride trompeuse.


## ADR-091 : modèle de fenêtre de récolte vérifiable à résolution décadaire, ajustement agronomique sous contrainte hydrique et qualification expérimentale (R5.4)

- **Date/statut :** 2026-10-17 UTC, adopté avant code R5.4 ; Phase R5.
- **Contexte :** La tâche R5.4 impose de produire une fenêtre de récolte vérifiable pour les principaux bassins agricoles et cultures vivrières (riz Asara, riz Hosy, maïs, manioc) à Madagascar. Les directives normatives de R5.4 imposent :
  1. Partir du calendrier cultural baseline vérifié (R4.7, SPECS §26, `taxonomy/crop_calendar.yaml`).
  2. Ajustements de campagne fondés uniquement sur des règles agronomiques étayées (FAO, MinAE, FOFIFA) : un déficit pluviométrique précoce (démarrage tardif des pluies, CHIRPS anomalie < -30%) retarde le repiquage/semis et décale mécaniquement la maturité physiologique et le début de récolte d'une à deux décades. En régime irrigué pérenne avec maîtrise de l'eau, aucun décalage artificiel n'est appliqué.
  3. Sortie explicite : début/fin de fenêtre, pic de récolte, durée du cycle végétatif, facteurs agroclimatiques motivant le décalage, et niveau de validation (`baseline_reference`, `adjusted_campaign_rule`, `experimental_unverified`).
  4. Résolution temporelle rigoureuse : granularité décadaire agronomique (décade 1 : jours 1-10, décade 2 : jours 11-20, décade 3 : jours 21-fin), **interdiction absolue de simuler une date au jour près sans capteur de terrain à résolution journalière**.
  5. Confrontation avec des données indépendantes réelles : tester la concordance temporelle entre la fenêtre calculée et les premiers arrivages massifs constatés sur les marchés de collecte et de gros (ex: ODR Ambatondrazaka et Anosibe).
  6. En l'absence de réseau de capteurs phénologiques in situ continus, la projection est qualifiée de statut `experimental` avec incertitude qualitative documentée, sans jamais revendiquer une « précision garantie ».
- **Décision :**
  1. **Création du module `backend/src/ketrika/supply/harvest_window.py` :**
     - Modèle Pydantic `HarvestWindowProjection` portant la fenêtre temporelle décadaire, les dates d'encadrement, le décalage en décades (`shift_dekads`), les facteurs agroclimatiques, le niveau de validation et la note d'incertitude.
     - Modèle `HarvestConfrontationResult` confrontant la fenêtre aux flux d'arrivages réels (`inflow_arrival`).
     - Moteur `HarvestWindowModel` :
       - `project_baseline_window(crop_record, year)` : extraction de la fenêtre nominale issue du calendrier validé.
       - `project_adjusted_window(crop_record, year, rainfall_early_anomaly_pct, is_drought_scenario)` : calcul déterministe du décalage phénologique selon la sensibilité hydrique et l'accès à l'irrigation.
       - `evaluate_against_market_arrivals(harvest_window, arrival_records)` : calcul du taux de concordance entre la fenêtre de récolte du bassin et les arrivages observés.
  2. **Transparence et étanchéité :**
     - La fenêtre de récolte est distincte des relevés d'observation ; elle porte le statut d'estimation agronomique modélisée.
- **Alternatives rejetées :**
  - Fixer une date exacte au jour près (ex: « récolte le 14 mai ») (rejeté, fausse précision trompeuse en agronomie).
  - Utiliser le même calendrier cultural comme donnée d'évaluation (rejeté, tautologie circulaire proscrite par R5.4).
- **Conséquences :**
  - Calendriers agricoles dynamiques, explicables, auditables et conformes à la réalité agricole malgache.


## ADR-090 : contrôle qualité des quantités, matrice spatio-temporelle marché × période, taux de couverture d'échantillonnage et distinction stricte absence de relevé vs zéro arrivage (R5.3)

- **Date/statut :** 2026-10-17 UTC, adopté avant code R5.3 ; Phase R5.
- **Contexte :** La tâche R5.3 impose de contrôler les quantités physiques d'approvisionnement et leur représentativité spatio-temporelle. Les directives de R5.3 et SPECS §27 imposent de :
  1. Distinguer formellement relevé ponctuel (`spot_reading`) et période cumulée (`cumulative_period`), stock résiduel (`stock_inventory`) et flux logistique (`inflow_arrival`).
  2. Valider rigoureusement les conversions métriques des unités physiques locales (kg, tonne, sac 50kg, sac 100kg, gony, kapoaka) et interdire toute modification de conditionnement sans preuve documentée.
  3. Construire une matrice marché × période pour quantifier la complétude des enquêtes et expliciter les jours non enquêtés.
  4. Règle métrologique non négociable : **absence de relevé ≠ zéro arrivage**. Un jour sans relevé d'enquêteur n'est ni un stock vide ni une rupture d'approvisionnement, c'est une absence d'observation (`missing_survey`).
  5. Quantifier la représentativité via le taux de couverture d'échantillonnage ($N_{\text{observés}} / N_{\text{attendus}}$) et expliciter la part déclarée (`declared_trader`) vs mesurée (`measured_scale`), sans jamais transformer du déclaratif en mesure certifiée.
  6. Détecter et empêcher le double comptage temporel (ex: sommer simultanément les relevés journaliers et un total hebdomadaire ou mensuel).
- **Décision :**
  1. **Création du module `backend/src/ketrika/supply/quality.py` :**
     - Modèles de données Pydantic : `MarketCoverageStats`, `TemporalDoubleCountViolation`, `QuantityAuditIssue`, `SupplyDataQualityReport`.
     - Validateur `SupplyQualityChecker` implémentant :
       - `build_market_period_matrix(records, start_date, end_date)` : construction de la grille calendrier des relevés par marché et produit vivrier.
       - `evaluate_missing_vs_zero(matrix)` : séparation formelle des zéros réels vérifiés (`zero_inflow`, pesée 0 kg) et des absences d'observation (`missing_survey`, aucun enquêteur). Interdiction absolue d'imputer 0 kg en l'absence de relevé.
       - `detect_temporal_overlap_double_counting(records)` : algorithme de détection des chevauchements d'intervalles $[start, end]$ pour une même cible et un même marché prévenant toute double sommation.
       - `compute_sampling_coverage_rate(market_code, records, start_date, end_date, expected_days)` : calcul exact de la représentativité d'échantillonnage et ventilation métrologique (`measured_scale`, `declared_trader`, `estimated_survey`).
       - `audit_unit_conversions(records)` : vérification stricte que chaque conversion vers le kilogramme respecte la table de densité produit et n'utilise pas de ratio arbitraire.
  2. **Interdiction d'extrapolation non pondérée :**
     - Le système signale le taux de couverture d'échantillonnage comme métrique de confiance sans extrapoler à l'ensemble du marché sauf modèle de pondération formellement qualifié.
- **Alternatives rejetées :**
  - Remplacer les jours non enquêtés par des zéros pour faciliter les graphiques (rejeté, falsification grossière de l'activité économique de marché).
  - Fusionner les tonnages mesurés sur bascule et les tonnages déclarés verbalement sans distinction de confiance (rejeté, violation de SPECS §27).
- **Conséquences :**
  - Traçabilité et auditabilité totales des séries temporelles de flux et stocks.
  - Prévention mécanique du double comptage temporel et spatial.


## ADR-089 : extension de StockRecord et ingestion des flux d'arrivages et stocks légaux (R5.2)

- **Date/statut :** 2026-10-17 UTC, adopté avant code R5.2 ; Phase R5.
- **Contexte :** La tâche R5.2 impose d'importer les quantités physiques légalement disponibles (ODR, MinAE, dépôts institutionnels) et de relier ces observations à la couche Bronze immuable avec calcul automatique d'empreinte SHA-256. Le modèle `obs.stock_observation` existant ne distingue pas explicitement la cible métrologique (`stock_inventory` vs `inflow_arrival` vs `harvest_volume`) ni le mode de mesure (`measured_scale` vs `declared_trader` vs `estimated_survey`), ce qui limite la granularité d'analyse demandée par SPECS §27 et expose aux risques d'agrégation hybride.
- **Décision :**
  1. **Migration Alembic 0016 (`0016_supply_arrival_and_stock_targets.py`) :**
     - Ajouter les colonnes `target TEXT NOT NULL DEFAULT 'stock_inventory'`, `measurement_mode TEXT NOT NULL DEFAULT 'declared_trader'`, `market_type TEXT` à `obs.stock_observation`.
     - Index partiel unique `uq_stock_observation_active` sur `(natural_key, target)` où `superseded_by IS NULL` pour garantir l'unicité par cible tout en conservant les versions historiques.
  2. **Extension du modèle `StockRecord` (`ketrika.connectors.records`) :**
     - Intégrer les champs optionnels rétrocompatibles `target: str = "stock_inventory"`, `measurement_mode: str = "declared_trader"`, `market_type: str | None = None`.
  3. **Création du connecteur `MarketSupplyConnector` (`source_id="market_supply"`) :**
     - Connecteur public et d'import institutionnel ingérant les fichiers de relevés de marchés (arrivages et stocks d'Anosibe, Boeny, Alaotra).
     - Vérification anti-PII stricte via `validate_payload_no_pii` avant toute écriture.
     - Écriture Bronze immuable et liaison `meta.source_record`.
     - Normalisation en `StockRecord` avec conversions métriques en kilogrammes et calcul de l'empreinte `natural_key`.
     - Support complet de la supersession non destructrice (`superseded_by`).
- **Alternatives rejetées :**
  - Créer une table `obs.arrival_observation` séparée dupliquant 90% des colonnes de `obs.stock_observation` (rejeté, complexification inutile du schéma et des requêtes analytiques Gold).
  - Utiliser des données de quantités synthétiques pour qualification (rejeté, formellement prohibé par AGENTS.md §3.1 et R5.2).
- **Conséquences :**
  - `obs.stock_observation` devient le conteneur unifié des stocks et des flux d'arrivages de marché.
  - La provenance Bronze SHA-256 est garantie à 100%.

## ADR-088 : architecture de relevé des quantités, cibles d'approvisionnement, contrat anti-PII et prévention du double comptage (R5.1)

- **Date/statut :** 2026-10-17 UTC, adopté avant code R5.1 ; Phase R5.
- **Contexte :** La phase R5 aborde les volumes physiques et les flux d'approvisionnement des marchés vivriers à Madagascar. Les quantités sont des variables d'état extensives et cumulatives, fondamentalement distinctes des prix (variables intensives). Une modélisation naïve expose le système à trois risques critiques :
  1. Le double comptage destructeur (ex: sommer un stock instantané en magasin et les arrivages quotidiens du mois, ou additionner la production brute du bassin et les flux sur les marchés de collecte et de consommation).
  2. La contamination par des données personnelles (PII) : noms de commerçants, transporteurs, chauffeurs, plaques d'immatriculation, numéros de téléphone des collecteurs ou enquêteurs, formellement prohibés par AGENTS.md §8.3.
  3. L'ambiguïté des unités physiques locales (sacs de 50 kg vs sacs de 100 kg, gony de riz paddy vs riz usiné, kapoaka vs kg).
- **Décision :**
  1. **Définition de 3 cibles métrologiques strictement disjointes (`QuantityTarget`) :**
     - `HARVEST_VOLUME` : volume agricole primaire produit/récolté par bassin et cycle cultural (ex: tonnes récoltées dans la plaine d'Ambatondrazaka).
     - `INFLOW_ARRIVAL` : flux logistique entrant constaté sur un marché public donné au cours d'une période temporelle explicite (ex: arrivages journaliers en tonnes ou sacs).
     - `STOCK_INVENTORY` : inventaire physique statique disponible à un instant précis $T$ sur le marché ou en entrepôt (stock de sécurité, stock commerçant).
     - `OUTFLOW_SALES` : volume sortant ou écoulé sur le marché.
  2. **Règle absolue d'interdiction de cumul croisé :**
     - Le moteur de calcul refuse catégoriquement d'additionner des flux (`INFLOW_ARRIVAL`) avec des stocks (`STOCK_INVENTORY`) ou de la production primaire (`HARVEST_VOLUME`).
     - L'agrégation temporelle n'est autorisée qu'au sein de flux de même nature (ex: somme des arrivages quotidiens sur une semaine) et strictement interdite pour les stocks (qui ne peuvent être agrégés que sous forme d'instantanés d'inventaire ou de moyennes temporelles).
  3. **Mode de constatation (`QuantityMeasurementMode`) :**
     - `MEASURED_SCALE` : pesée mécanique ou électronique sur balance/bascule étalonnée.
     - `DECLARED_TRADER` : déclaration orale ou écrite du commerçant/transporteur sans pesée directe.
     - `ESTIMATED_SURVEY` : estimation visuelle de l'enquêteur basée sur le dénombrement de contenants standards.
  4. **Contrat anti-PII absolu à la validation Pydantic :**
     - Les modèles `QuantityObservationRecord` et `SurveyForm` imposent `model_config = ConfigDict(extra="forbid")`.
     - Rejet formel et automatique si un champ personnel (`trader_name`, `phone`, `email`, `driver_id`, `vehicle_plate`, `national_id`) est soumis.
     - Seules les métadonnées de lieux publics (`market_code`, `location_pcode`, `market_name`, `market_type`) et de protocole institutionnel sont acceptées.
  5. **Dictionnaire d'unités physiques et conversion standardisée (`QuantityUnit`) :**
     - Pivot métrique universel : kilogramme (`KG`, facteur 1.0) et tonne métrique (`TONNE`, facteur 1000.0).
     - Contenants standardisés : `BAG_50KG` (50 kg), `BAG_100KG` (100 kg).
     - Unités traditionnelles locales : `GONY` (poids nominal vérifié par produit, défaut 50 kg pour riz paddy/blanc), `KAPOAKA` (contenance standardisée de 300 ml, densité spécifique par produit vivrier selon tables MinAE/ODR).
  6. **Gouvernance des collectes terrain (H3, H7) :**
     - Les formulaires d'enquête et protocoles sont rédigés dans `docs/protocols/` et les projets de conventions de collecte dans `docs/outreach/`.
     - Aucun contact de tiers ni transmission externe (H3, H7).
- **Alternatives rejetées :**
  - Fusionner flux et stocks dans une colonne générique `quantity` sans indicateur de type (rejeté, source de double comptage).
  - Tolérer des champs optionnels libres pouvant contenir des coordonnées personnelles (rejeté, violation d'AGENTS.md §8.3).
  - Assumer une conversion fixe de 1 sac = 100 kg pour toutes les denrées (rejeté, un sac de maïs en épi ne pèse pas comme un sac de riz blanc).
- **Conséquences :**
  - Spécification formelle dans SPECS §27.
  - Implémentation du module `backend/src/ketrika/supply/contracts.py`.
  - Intégrité métrologique garantie pour les importations (R5.2), la DQ des quantités (R5.3) et l'analyse des corridors d'approvisionnement (R5.6).

## ADR-087 : architecture de la vue agroclimatique explicable, étanchéité multi-couches et transparence des sources facultatives (R4.11)

- **Date/statut :** 2026-10-16 UTC, adopté avant code R4.11 ; Phase R4.
- **Contexte :** La vue agroclimatique consolidée `/climate` et ses endpoints REST associés `/v1/climate/*` constituent le point de contact opérationnel entre données satellitaires, stations météo, modèles numériques NWP, calendriers culturaux et documents d'alerte précoce. Les directives normatives de R4.11, SPECS §19, §26 et les principes d'AGENTS.md imposent :
  1. **Disjonction stricte en 4 couches de données indépendantes :**
     - **Couche 1 (Météo observée et estimée) :** Précipitations et températures mesurées ou estimées par satellite (CHIRPS, DGM). Méthode d'agrégation explicite (`zonal_mean` avec avertissement sur l'absence de masque agricole si non vérifié).
     - **Couche 2 (Anomalies climatiques rigoureuses) :** Écart en mm/°C, % de la normale, z-score, risque catégoriel, référence climatologique documentée ($N \ge 10$ ans) ou statut explicite `insufficient_history`.
     - **Couche 3 (Météo prévue numérique archivable) :** Prévisions NWP (ECMWF IFS Open Data), étanches des observations, avec `issued_at`, `valid_from`, `valid_to`, horizon en heures, quantiles p10/médiane/p90, et flag `value_kind: projected`.
     - **Couche 4 (Calendrier cultural et corridors commerciaux) :** Stades phénologiques calculés dynamiquement pour le mois actif (`peak_harvest`, `harvest`, `planting`, `growing`), typologie baseline vs recommandation, corridors d'approvisionnement documentés.
     - **Couche 5 (Événements et perspectives FEWS NET/IPC) :** Phases IPC, alertes documentées, statut de projection explicite.
  2. **Transparence absolue sur les sources facultatives non intégrées :**
     - Les sources optionnelles (FIRMS pour les feux, GloFAS pour les inondations, Copernicus NDVI pour la biomasse) sont affichées avec leur statut exact (`unavailable` / non configuré) et leur justification, et JAMAIS avec des valeurs numériques nulles (0 feux ou 0 mm) qui donneraient une fausse impression de risque zéro.
     - Interdiction formelle de fabriquer un « indice global de santé environnementale » synthétique non étayé.
- **Décision :**
  1. Créer le routeur FastAPI `backend/src/ketrika/api/routers/climate.py` exposant :
     - `GET /v1/climate/summary` (vue consolidée explicable par zone/district),
     - `GET /v1/climate/anomalies` (séries temporelles d'anomalies observées avec baseline),
     - `GET /v1/climate/forecasts` (prévisions numériques archivées),
     - `GET /v1/climate/calendars` (calendriers culturaux et corridors d'approvisionnement),
     - `GET /v1/climate/events` (événements et perspectives FEWS NET/IPC),
     - `GET /v1/climate/facultative-status` (statut transparent des sources facultatives).
  2. Maintenir la compatibilité ascendante sur `/v1/weather/anomalies`.
  3. Mettre à jour `web/src/app/climate/page.tsx` pour consommer ces contrats certifiés, afficher les badges `observed` / `projected`, expliciter la méthode d'agrégation et rendre consultables les corridors commerciaux sans inventer de métriques.
- **Alternatives rejetées :**
  - Fusionner prévisions et observations dans une seule courbe temporelle (rejeté, violation de la règle 9 d'AGENTS.md).
  - Afficher 0 feux pour FIRMS lorsque l'API n'est pas connectée (rejeté, falsification de sécurité).
  - Maintenir un calendrier statique hardcodé dans le frontend (rejeté, découplage de la taxonomie vérifiée).
- **Conséquences :** Vue agroclimatique 100% explicable, traçable, auditée et conforme aux exigences agronomiques malgaches.

## ADR-086 : versioning des calendriers culturaux, typologie traditionnelle vs recommandations saisonnières et liaisons de corridors commerciaux prouvés (R4.7)

- **Date/statut :** 2026-10-16 UTC, adopté avant code R4.7 ; Phase R4.
- **Contexte :** Les calendriers culturaux fournissent les fenêtres phénologiques critiques (semis, croissance/tallage, floraison, récolte, pic de récolte) et la sensibilité hydrique par bassin de production et régime (irrigué, pluvial, bas-fond) à Madagascar. Les directives normatives de R4.7, SPECS §26 et les principes d'AGENTS.md imposent :
  1. **Disjonction stricte entre calendrier traditionnel (baseline) et recommandation saisonnière :**
     - Le calendrier traditionnel reflète les pratiques agronomiques pérennes (`calendar_type: traditional_baseline`, `campaign: baseline_permanent`).
     - Les avis ou recommandations spécifiques pour une campagne donnée (`calendar_type: seasonal_recommendation`, ex: campagne 2023/2024 émise par le MinAE face à un retard de pluies) sont versionnés avec leur campagne et ne modifient pas la baseline traditionnelle.
  2. **Immutabilité, révision et visibilité des versions passées (Principe 3 d'AGENTS.md) :**
     - Aucun remplacement destructif. Une révision crée une nouvelle entrée avec `superseded_by` pointant vers la nouvelle version, tandis que l'ancienne reste consultable avec `is_active = False`.
  3. **Attribution spatiale sans extrapolation géographique :**
     - Tout calendrier est formellement rattaché à un bassin/zone spécifique (`zone_code`, ex: `ZONE_ALAOTRA`, `ZONE_CENTRE`, `ZONE_BOENY`, `ZONE_EST`, `ZONE_SUD`).
     - Interdiction absolue d'appliquer un calendrier unique ou générique à l'ensemble du territoire national.
  4. **Liaison explicite bassin de production -> marchés de consommation avec statut de preuve :**
     - Les corridors d'approvisionnement entre bassins producteurs et marchés récepteurs (`market_links`) exigent une référence documentée (`proof_status: documented_trade_corridor`, `official_supply_basin`, `unverified_assumption`).
     - Rejet catégorique de l'attribution de corridors par simple proximité géographique sans preuve.
  5. **Éligibilité aux alertes automatiques et gestion du verified/review :**
     - Une entrée sans source officielle ou comportant une interprétation non mécanique a `verified: false` et est formellement exclue des alertes automatiques de marché (`eligible_for_alerts: false`).
  6. **Interdiction stricte de dérivation de tonnages ou de prix :**
     - Un calendrier cultural fournit exclusivement des fenêtres phénologiques temporelles. Il ne contient ni ne produit aucune estimation de tonnage de récolte, ni de prévision de prix, ni de pic de volume de marché inventé.
- **Décision :**
  1. Étendre `CropCalendarRecord` et le schéma SQL `ref.crop_calendar` (migration 0015) avec `calendar_version`, `calendar_type`, `campaign`, `variety`, `eligible_for_alerts`, `is_active`, `superseded_by`, et `market_links`.
  2. Implémenter le module `ketrika.geo.calendar` gérant la détection des stades phénologiques, les chevauchements inter-annuels, la consultation des versions passées et la traçabilité des corridors commerciaux.
  3. Enrichir `taxonomy/crop_calendar.yaml` avec les métadonnées de versioning et les corridors documentés des principaux bassins de Madagascar (Alaotra, Boeny/Marovoay, Hauts Plateaux, Est, Sud).
- **Alternatives rejetées :**
  - Écraser les calendriers lors d'une nouvelle campagne (rejeté, violation de l'immutabilité et de l'auditabilité historique).
  - Déduire les flux commerciaux par calcul de distance euclidienne (rejeté, méconnaissance des infrastructures réelles et des flux fluviaux/routiers malgaches).
- **Conséquences :** Calendriers culturaux auditables, versions antérieures préservées, alertes précoces fiables et modélisation réaliste des flux de denrées sans conjectures.

## ADR-085 : calcul rigoureux des anomalies agroclimatiques, seuils minimaux de référence historique et agrégations zonales fiables (R4.6)

- **Date/statut :** 2026-10-16 UTC, adopté avant code R4.6 ; Phase R4.
- **Contexte :** Le calcul des anomalies agroclimatiques (pluviométrie, températures) et l'agrégation spatiale sur les régions et districts agricoles de Madagascar exigent une métrologie sans faille (directives R4.6, règles 1, 8, 9 et 10 d'AGENTS.md) :
  1. **Seuil minimal de climatologie de référence ($N \ge 10$ années) :**
     - Une anomalie (écart absolu, pourcentage de la normale, z-score standardisé) n'a de validité scientifique que si elle s'appuie sur une climatologie de référence homogène (même source, même version).
     - Si l'historique disponible compte moins de 10 années de référence pour le mois ou la décade concernée, le calcul d'anomalie s'abstient formellement (`status: insufficient_history`, valeurs d'anomalies à `None`). Il est formellement interdit d'inventer une climatologie synthétique.
  2. **Somme pluviométrique vs Moyenne thermique :**
     - Précipitations : cumul ou somme décadaire/mensuelle. L'anomalie s'exprime en écart absolu ($P - \bar{P}$ en mm), en pourcentage de la normale ($P / \bar{P} \times 100\%$), et en indice standardisé $Z = (P - \mu) / \sigma$.
     - Températures : moyenne arithmétique. L'anomalie s'exprime en écart absolu ($T - \bar{T}$ en °C) et en z-score standardisé.
  3. **Agrégation zonale rigoureuse et ratio de couverture spatiale :**
     - Une moyenne zonale n'est déclarée représentative que si le ratio de couverture des pixels valides satisfait `coverage_ratio >= 0.5`. En deçà, l'agrégation est signalée comme couverture incomplète (`incomplete_coverage`).
     - Refus catégorique de déguiser une grille lâche en pluie de station locale.
  4. **Strict respect des sources et versions :**
     - Interdiction de mélanger les versions de fournisseurs pour calculer une anomalie (ex: comparer CHIRPS v2.0 à une baseline NASA POWER).
- **Décision :**
  1. Implémenter le module `ketrika.geo.anomalies` fournissant `ClimateBaseline`, `ClimateAnomalyResult`, `compute_climate_baseline`, `compute_climate_anomaly`, `classify_rainfall_anomaly`.
  2. Imposer le seuil strict $N_{\text{min}} = 10$ années pour toute climatologie de référence.
  3. Fournir une suite de tests unitaires validant :
     - le calcul exact des anomalies sur un jeu de données connu à la main,
     - l'abstention formelle lorsque $N < 10$,
     - la classification agronomique des déficits et excédents hydriques,
     - l'agrégation zonale à surface corrigée et le comportement en présence de nodata et frontières côtières.
- **Alternatives rejetées :**
  - Calculer des anomalies avec seulement 2 ou 3 ans d'historique (rejeté, bruit statistique non représentatif du climat).
  - Imputer les années manquantes par la moyenne globale (rejeté, falsification de données météo).
- **Conséquences :** Alertes de sécheresse et d'excès pluviométrique certifiées, transparentes et scientifiquement fondées.

## ADR-084 : qualification de la météo prévue archivable, intégration ECMWF Open Data et étanchéité prévisionnelle (R4.5)

- **Date/statut :** 2026-10-16 UTC, adopté avant code R4.5 ; Phase R4.
- **Contexte :** L'anticipation agroclimatique requiert des prévisions météorologiques à court et moyen terme (1 à 14 jours) issues de centres mondiaux de référence (ECMWF, NOAA/NCEP). Leur intégration impose des règles strictes (directives R4.5, règles 1, 3, 8, 9 et 10 d'AGENTS.md) :
  1. **Séparation étanche météo observée vs météo prévue (Règle 9) :**
     - Les prévisions sont exclusivement enregistrées dans la table dédiée `obs.weather_forecast` (créée en R4.1 via la migration 0014).
     - Il est strictement interdit d'insérer une prévision dans `obs.weather_observation` ou de la présenter comme un fait météorologique mesuré.
  2. **Archivage Bronze immuable avant expiration glissante (Règle 2 & 4) :**
     - Les API de prévision écrasent typiquement leurs runs toutes les 6 à 12 heures. Ketrika archive chaque payload brut sous Bronze (`bronze/weather_forecast/...`) avec son horodatage d'émission officiel (`issued_at`), son empreinte SHA-256 et sa validité (`valid_from`, `valid_to`), rendant le rejeu hors ligne 100 % reproductible sans réseau.
  3. **Quantiles d'incertitude et horizons temporels :**
     - Conservation de l'horizon de prévision en heures (`horizon_hours` : 24, 48, 72, 168, etc.), de la valeur médiane/attendue (`predicted_value`), et des quantiles probabilistes d'ensemble (`predicted_p10`, `predicted_p90`).
  4. **Interdiction de fabriquer des pseudo-hindcasts :**
     - Il est strictement interdit de reconstituer artificiellement un run de prévision du passé en utilisant les observations réalisées réelles (anti-triche A09, Règle 10).
  5. **Contrôles de cohérence physique :**
     - Rejet ou alerte sur valeurs physiquement impossibles (précipitations négatives, températures supérieures à 55 °C ou inférieures à -10 °C à Madagascar).
- **Décision :**
  1. Déclarer la source officielle `ecmwf_open` dans `registry/sources.yaml` avec priorité P2, licence CC-BY-4.0 / WMO Essential.
  2. Créer le type `WeatherForecastRecord` dans `backend/src/ketrika/connectors/records.py`.
  3. Implémenter le connecteur `ketrika.connectors.ecmwf_open.EcmwfOpenConnector` gérant l'ingestion Bronze et l'extraction des horizons multi-variables (précipitations, températures min/max, humidité).
  4. Implémenter `load_weather_forecast_record_with_supersession` dans `backend/src/ketrika/connectors/runner.py` pour alimenter `obs.weather_forecast`.
  5. Développer la suite de tests unitaires et de contrats validant la distinction météo observée vs prévue, l'archivage de runs successifs, et la détection d'anomalies d'unités ou de valeurs.
- **Alternatives rejetées :**
  - Utiliser un service météo payant imposant des clés secrètes non fournies (rejeté, respect de H1/H2).
  - Fusionner les prévisions dans `obs.weather_observation` avec un flag (rejeté, risque d'altération silencieuse des séries historiques).
- **Conséquences :** Anticipation des chocs climatiques avec conservation historique complète des prévisions émises et zéro ambiguïté prévision vs observation.

## ADR-083 : intégration des événements, perspectives et classifications de sécurité alimentaire FEWS NET et IPC Madagascar (R4.4)

- **Date/statut :** 2026-10-16 UTC, adopté avant code R4.4 ; Phase R4.
- **Contexte :** L'intégration des rapports d'alerte précoce et des classifications de la sécurité alimentaire issus de FEWS NET (Famine Early Warning Systems Network, USAID) et du Cadre Intégré de Classification de la Sécurité Alimentaire (IPC Madagascar / Gouvernement / Partenaires) exige des garanties strictes de fidélité et d'intégrité métrologique (directives R4.4, règles 1, 6, 7, 8, 9 et 10 d'AGENTS.md) :
  1. **Disjonction formelle entre situation courante et perspectives projetées :**
     - Une classification de phase IPC actuelle (ex: Phase 2 « Stress » ou Phase 3 « Crise » pour la période courante) ne doit jamais être fusionnée ni confondue avec une projection future (ex: projection à 3 ou 6 mois pour la période de soudure).
     - Tout enregistrement d'événement ou d'alerte projeté doit obligatoirement porter le drapeau booléen explicite `is_projected: true` dans son contrat et son evidence, avec dates de validité projetée distinctes de la période courante.
  2. **Interdiction de fabriquer des chiffres ou des phases synthétiques :**
     - Les phases IPC (1: Minimale, 2: Stress, 3: Crise, 4: Urgence, 5: Famine) et les estimations de populations en insécurité alimentaire doivent provenir textuellement ou tabulairement de publications officielles authentiques.
     - Aucune interpolation mathématique continue ni extrapolation n'est autorisée sur les phases discrètes d'insécurité alimentaire.
  3. **Traçabilité totale, citations textuelles et facteurs de bascule :**
     - Chaque événement renseigne le titre du rapport, la date de publication officielle, la zone géographique concernée (région ou district de Madagascar, ex: Androy, Atsimo-Andrefana, Grand Sud), le numéro de page, et une citation verbatim des hypothèses clés et facteurs de bascule (ex: retard des pluies, attaques acridiennes, flambée des prix sur les marchés locaux).
  4. **Sécurité et intégrité documentaire (Règle 10) :**
     - Le texte des rapports FEWS NET / IPC est une donnée passive d'observation socio-économique et agro-météorologique. Aucune instruction ou directive contenue dans ces documents ne peut altérer la politique de l'agent.
     - Aucune donnée nominative ou personnelle n'est collectée (H4).
- **Décision :**
  1. Déclarer les sources officielles `fewsnet_mdg` et `ipc_mdg` dans `registry/sources.yaml` avec priorité P2, licences ouvertes et URLs officielles documentées.
  2. Implémenter le connecteur `ketrika.connectors.fewsnet_ipc.FewsnetIpcConnector` (exposé sous `fewsnet_mdg` et `ipc_mdg`), produisant des `EventRecord` normalisés enrichis avec :
     - `event_type='food_security_ipc'`,
     - `period_start` et `period_end` alignés sur la fenêtre d'analyse ou de projection,
     - champs `evidence` traçant `is_projected`, `ipc_phase`, `assumptions`, `key_drivers`, `page`, `verbatim_citation`.
  3. Étendre `load_record_with_supersession` dans `runner.py` pour supporter `EventRecord` et persister fidèlement dans la table `obs.event`.
  4. Écrire la suite de tests validant la séparation stricte situation courante vs perspective projetée, la résolution spatiale, et le rejet d'inventions numériques.
- **Alternatives rejetées :**
  - Fusionner les phases courantes et projetées dans un seul champ sans distinction temporelle (rejeté, risque critique de confusion décisionnelle).
  - Générer des scores continus ou prédire une phase IPC future par ML (rejeté, compétence exclusive du comité national d'analyse IPC).
- **Conséquences :** Contextualisation institutionnelle des crises alimentaires et chocs de marché à Madagascar, provenance totale et auditabilité garantie.

## ADR-082 : qualification de la source officielle Météo Madagascar, extraction déterministe et intégrité métrologique des bulletins agroclimatiques (R4.3)

- **Date/statut :** 2026-10-16 UTC, adopté avant code R4.3 ; Phase R4.
- **Contexte :** L'intégration des bulletins agro-météorologiques et des perspectives climatiques publiés par la Direction Générale de la Météorologie de Madagascar (DGM / Météo Madagascar, `https://www.meteomadagascar.mg/`) impose des garanties strictes de fidélité documentaire et métrologique (directives R4.3, règles 1, 7, 8, 9 et 10 d'AGENTS.md) :
  1. **Disjonction formelle entre date d'émission et période de validité :** Un bulletin publié le 10 janvier 2024 portant sur la décade du 1er au 10 janvier (`valid_from: 2024-01-01`, `valid_to: 2024-01-10`) ne doit pas voir sa date d'observation confondue avec sa date de publication (`issued_at: 2024-01-10`).
  2. **Interdiction de fabriquer des probabilités à partir de catégories qualitatives :** Les cartes et textes décrivant des catégories (ex: « pluies normales à supérieures », « déficit hydrique modéré ») doivent être consignés textuellement avec citation exacte et extrait de page. Il est strictement interdit de convertir une catégorie qualitative ou une couleur de carte en fausse probabilité numérique (ex: « 75 % ») absente du document source officiel.
  3. **Principe de fidélité au réel et absence de document :** Si aucun bulletin officiel n'est publié ou accessible pour une période donnée, l'état pour cette période est obligatoirement étiqueté `unavailable` avec raison documentée. Il est strictement interdit d'inventer un bulletin de remplacement ou un calendrier fictif.
  4. **Provenance vérifiable à 100 % (Règle 1) :** Chaque observation ou avis extrait référence obligatoirement le `source_record_id` de l'artefact Bronze original (PDF ou bulletin HTML officiel), son empreinte SHA-256, le numéro de page, et l'extrait textuel verbatim.
- **Décision :**
  1. Déclarer la source `meteo_mg` dans `registry/sources.yaml` avec priorité P2, entrée `https://www.meteomadagascar.mg/`, cadence mensuelle/décadaire, licence publique officielle.
  2. Implémenter le connecteur `ketrika.connectors.meteo_mg.MeteoMgConnector` (`Connector = MeteoMgConnector`).
  3. Extraire de façon déterministe les cumuls pluviométriques observés chiffrés en `WeatherRecord` (`provider='meteo_mg'`), et consigner les perspectives et alertes zonales dans des enregistrements d'événements/perspectives structurés avec preuves citations exactes.
  4. Rédiger la suite de tests validant la séparation émission/validité, la conservation des citations, le rejet de probabilités inventées, et le comportement `unavailable` en l'absence de document.
- **Alternatives rejetées :**
  - Fabriquer une prévision probabiliste continue à partir des cartes qualitatives (rejeté, violation de la règle 10 d'AGENTS.md).
  - Utiliser un modèle météo non institutionnel en prétendant qu'il s'agit du service officiel malgache (rejeté, hérésie de provenance).
- **Conséquences :** Intégration certifiée de la parole officielle de Météo Madagascar, distinction absolue entre faits observés et perspectives qualitatives.

## ADR-081 : qualification du connecteur CHIRPS v2.0, double versioning préliminaire/finale et distinction stricte pluie nulle vs nodata (R4.2)

- **Date/statut :** 2026-10-16 UTC, adopté avant code R4.2 ; Phase R4.
- **Contexte :** L'intégration du produit satellitaire et stationnaire CHIRPS v2.0 (Climate Hazards Center, UC Santa Barbara) exige des garanties métrologiques strictes (directives R4.2, règles 1, 3, 8 et 9 d'AGENTS.md) :
  1. **Gestion du double cycle temporel préliminaire vs final (C2/C4) :** CHIRPS produit d'abord une version préliminaire rapide (`chirps-v2.0.prelim`) disponible 2 à 5 jours après la fin du mois, puis une version définitive (`chirps-v2.0.final`) vers le 15 du mois suivant après assimilation des stations pluviométriques au sol. En application de la règle 3 (Append-only) et de l'auditabilité C4, la publication définitive ne détruit pas la version préliminaire : elle l'archive avec `superseded_by` pointant vers la définitive, garantissant la traçabilité des séries as-of.
  2. **Distinction physique stricte entre pluie nulle ($0{,}0\text{ mm}$) et nodata ($-9999{,}0$) :** En climatologie tropicale et dans le Grand Sud malgache, $0{,}0\text{ mm}$ représente une observation avérée d'absence de pluie (sécheresse météorologique), tandis que $-9999{,}0$ est la valeur sentinelle nodata désignant un pixel hors masque maritime ou sans acquisition. Les confondre corromprait gravement le calcul des anomalies pluviométriques et le suivi des sécheresses.
  3. **Découpage spatial systématique (budget Bronze raster) :** Les rasters d'origine (continentaux ou globaux) sont bornés à la BBOX officielle Madagascar `[43.0, -25.8, 50.8, -11.8]` avant stockage et agrégation, garantissant un volume inférieur au plafond de 50 Mo.
  4. **Agrégation zonale traçable vers les entités administratives :** L'agrégation zonale calcule la moyenne spatiale des pixels valides sur chaque région (`admin1`) et district (`admin2`) avec rapport de couverture spatiale (`coverage_ratio`).
- **Décision :**
  1. Implémenter le connecteur `ketrika.connectors.chirps.ChirpsConnector` avec support complet des partitions préliminaires et finales.
  2. Produire des `WeatherRecord` typés avec `provider='chirps'`, `variable='precip_mm'`, `method='zonal_mean'`, `spatial_resolution='0.05_deg'`, `stage='preliminary'|'final'`, et preuve structurée incluant l'empreinte SHA-256 du raster.
  3. Valider la supersession dans `load_weather_record_with_supersession` afin qu'une mise à jour finale conserve l'historique préliminaire sans écrasement destructif.
- **Alternatives rejetées :**
  - Attendre uniquement la version définitive (rejeté, priverait le système de réactivité opérationnelle précoce à J+5).
  - Écraser la version préliminaire en base sans historisation (rejeté, viole l'Append-only et l'auditabilité C2/C4).
  - Imputer les valeurs nodata à 0 mm (rejeté, hérésie métrologique).
- **Conséquences :** Disponibilité précoce et définitive des précipitations, auditabilité totale des sources CHIRPS Bronze et Silver.

## ADR-080 : formalisation des contrats géospatiaux, agroclimatiques et séparation stricte météo observée vs prévue (R4.1)

- **Date/statut :** 2026-10-16 UTC, adopté avant code R4.1 ; Phase R4.
- **Contexte :** L'intégration des données agroclimatiques et géospatiales exige des garanties métrologiques strictes (directives R4.1, constats d'audit A14, règles 1, 3, 8 et 9 d'AGENTS.md) :
  1. **Séparation étanche météo observée vs météo prévue :** Une prévision météorologique (ex: pluie projetée à 7 ou 14 jours par ECMWF/GFS) ne doit jamais être stockée ni confondue avec une observation historique (`obs.weather_observation`). La confusion créerait un risque critique d'intoxication des modèles d'alerte et de prix.
  2. **Double version fournisseur sans écrasement (C2/C4) :** Des sources majeures comme CHIRPS publient deux versions temporelles successives d'un même mois : préliminaire (`stage: preliminary`, dispo sous 5 à 10 jours) puis définitive (`stage: final`, dispo au mois $M+1$ après étalonnage avec les stations de surface). En vertu de la règle 3 (Append-only) et de l'auditabilité C4, la version définitive ne détruit pas la version préliminaire. Elle crée un nouvel enregistrement avec supersession explicite (`superseded_by`).
  3. **Système de Coordonnées et Bounding Box Madagascar :**
     - CRS standard : `EPSG:4326` (WGS84).
     - Bounding box Madagascar : `[43.0, -25.8, 50.8, -11.8]` (min_lon, min_lat, max_lon, max_lat).
     - Résolutions natives explicitées : $0{,}05^\circ$ (CHIRPS), $0{,}1^\circ$ à $0{,}5^\circ$ (NASA POWER, ERA5).
  4. **Masque Agricole et Agrégation Zonale Explicable :**
     - L'agrégation zonale d'un raster vers une zone administrative (`ref.location`) doit déclarer sa méthode : `point_centroid`, `zonal_mean` ou `cropland_weighted_mean`.
     - Une moyenne pondérée par les terres cultivées exige la présence d'un masque agricole vérifié (`cropland_mask`). En son absence, l'agrégation est obligatoirement étiquetée `zonal_mean` sans usurpation de précision agronomique.
  5. **Modèle de Calendrier Cultural :**
     - Les calendriers culturaux sont formalisés dans `taxonomy/crop_calendar.yaml` et historisés dans la table `ref.crop_calendar`, reliant le produit, la zone géographique, le régime pluvial ou irrigué, les fenêtres de semis/croissance/récolte, et la référence officielle.
  6. **Plafonds de Stockage Bronze & Budget Raster :**
     - Interdiction de télécharger le globe entier si des sous-ensembles sont découpables.
     - Découpage/clipping immédiat sur la bounding box Madagascar avant archivage Bronze (limite 50 Mo par fichier mensuel).
- **Décision :**
  1. Créer la migration Alembic 0014 étendant `obs.weather_observation` (colonnes `stage`, `spatial_resolution`, `coverage_ratio`, `raster_source_record_id`) et créant les tables `obs.weather_forecast` et `ref.crop_calendar`.
  2. Créer le module `backend/src/ketrika/geo/contracts.py` et `backend/src/ketrika/geo/raster.py` formalisant les types géospatiaux, CRS, BBOX Madagascar, calculs de masques et validation d'agrégation.
  3. Définir `taxonomy/crop_calendar.yaml` pour les bassins rizicoles et PPN prioritaires à Madagascar.
  4. Mettre à jour `SPECS.md` (§8, §13, §17bis).
- **Alternatives rejetées :**
  - Stocker les prévisions météo dans la même table `obs.weather_observation` avec un flag (rejeté, risque critique de fuite et de confusion).
  - Écraser la version préliminaire de CHIRPS par un simple `UPDATE` (rejeté, violation de la règle 3 Append-only et de la rejouabilité C4).
- **Conséquences :** Transparence totale des séries climatiques, étanchéité de l'historique et des prévisions, auditabilité des sources rasters Bronze.

## ADR-079 : évaluation réelle et suivi des erreurs maturées, décomposition multidimensionnelle et benchmarking loyal face aux baselines (R3.8)

- **Date/statut :** 2026-10-16 UTC, adopté avant code R3.8 ; Phase R3.
- **Contexte :** L'évaluation de la performance d'un modèle prédictif ne peut se résumer à des métriques in-sample ou à un unique score agrégé flatteur (directives R3.8, constats d'audit A08 et A09). Pour garantir une évaluation scientifique intègre des prévisions de prix :
  1. **Suivi des erreurs maturées sans rétroaction temporelle (C2/C4) :** Lorsqu'une date cible $T_{\text{target}}$ est franchie dans le temps réel ($T_{\text{target}} \le T_{\text{evaluation}}$), la prévision passée est confrontée à l'observation authentique devenue disponible (`actual_price`). Ces observations futures ne doivent en aucun cas être réinjectées rétroactivement dans le passé connu de l'entraînement du run initial.
  2. **Classification chronologique tripartite :**
     - `as_of_holdout` : évaluation sur la partition de test as-of certifiée (Phase 3 out-of-sample).
     - `matured_actual` : prévision de production confrontée à l'observation réelle après échéance.
     - `prospective_pending` : prévision en cours d'attente d'échéance ($T_{\text{target}} > T_{\text{evaluation}}$).
  3. **Décomposition multidimensionnelle obligatoire :** Tout rapport ou tableau d'évaluation doit obligatoirement ventiler les métriques (WAPE, MAE, sMAPE, couverture 80%, largeur) :
     - par produit (`product_code`),
     - par région géographique (`location_pcode`),
     - par horizon temporel ($h=1, 2, 3$),
     - par régime saisonnier (soudure vs récolte).
     Aucun score moyen global ne peut être présenté de manière isolée sans sa table de décomposition.
  4. **Benchmarking loyal et primauté de la parcimonie :** Tout candidat statistique (`AutoETS`, `AutoARIMA`) doit être comparé frontalement aux baselines de référence (`NaiveLast`, `SeasonalNaive`). Si un modèle complexe ne dégage aucun gain statistiquement significatif ($\Delta\text{WAPE} \le 0.01$), le modèle naïf est déclaré vainqueur par parcimonie. Aucun gain imaginaire ou surestimé ne peut être attribué.
  5. **Traçabilité de provenance totale (Règle 1 AGENTS.md) :** Chaque ligne d'évaluation référence explicitement le `forecast_id`, le `model_run_id`, et l'`observation_id` de la valeur réelle constatée.
- **Décision :**
  1. Créer la table `ml.forecast_evaluation` (migration Alembic 0013) stockant chaque évaluation individuelle d'horizon ($e_{\text{abs}}$, $e_{\text{pct}}$, `is_covered_80`, `actual_observation_id`).
  2. Implémenter le module `backend/src/ketrika/ml/evaluation.py` avec `MaturedForecastEvaluator`, `PerformanceTable`, `compute_evaluation_metrics`.
  3. Étendre l'API avec la route `GET /v1/forecasts/performance` (filtrage par produit, zone, horizon, régime, format CSV/JSON).
  4. Publier le rapport de référence `docs/reports/market_forecast_evaluation.md`.
- **Alternatives rejetées :**
  - Réévaluer le modèle en ré-entraînant sur toute la série incluant la période de test (rejeté, fuite de données flagrante).
  - Présenter uniquement un WAPE moyen agrégé masquant des divergences régionales ou des horizons $h=3$ dégradés (rejeté, violation de transparence).
- **Conséquences :** Auditabilité totale des erreurs constatées, fidélité exemplaire envers les baselines, détection rapide de toute dérive de prévision.

## ADR-078 : publication des prévisions, traçabilité des limites, gestion des abstentions et intégrité visuelle sans extrapolation (R3.7)

- **Date/statut :** 2026-10-16 UTC, adopté avant code R3.7 ; Phase R3.
- **Contexte :** La mise à disposition des prévisions de prix de marché ne doit jamais donner l'illusion d'une certitude ou d'une continuité artificielle (directives R3.7, R2.9, R2.10, constats d'audit A08 et A09). Pour satisfaire les principes de transparence et de provenance totale :
  1. **Conservation immuable de l'historique des runs (C4) :** Chaque exécution de prévision crée un nouveau `model_run_id` horodaté rattaché à l'empreinte canonique du dataset as-of (`dataset_fingerprint`). Les prévisions antérieures ne sont jamais écrasées destructivement, permettant la reproductibilité et l'audit rétrospectif.
  2. **Exposition exhaustive des limites et modèles :** Chaque prévision publiée expose obligatoirement son horizon ($h \in \{1, 2, 3\}$), sa cible temporelle (`target_period`), son origine (`data_cutoff`), son modèle effectif (`model_effective`), son statut de baseline (`is_baseline`), son statut de calibration conforme (`is_calibrated`), l'effectif d'étalonnage (`calibration_sample_size`), l'intervalle `[p10, p90]`, la largeur d'intervalle, la cohorte d'entraînement (`pure_observed` vs `mixed_cohort`), la devise (`currency`), l'unité physique (`unit`), et toute cause de repli (`fallback_reason`).
  3. **Traçabilité des abstentions loyales :** Lorsqu'une série ne répond pas aux critères d'éligibilité normatifs (moins de 36 mois, absence de 12 mois récents, ou granularité non régionale/nationale) ou qu'elle présente trop de lacunes (> 30%), le système publie explicitement son abstention (`status: abstained` ou `experimental_insufficient_windows`) avec la raison méthodologique (`abstention_reason`), sans jamais tenter d'inventer une valeur.
  4. **Intégrité visuelle absolue (Zéro courbe de remplacement LLM/UI) :** L'interface utilisateur (`PriceChart`, `/prices`) affiche distinctement les points observés et les prévisions avec leurs bandes conformes. En l'absence de prévision certifiée, l'UI affiche un panneau d'abstention loyale et s'interdit formellement de générer une courbe d'extrapolation ou d'interpolation artificielle par le front ou un LLM.
- **Décision :**
  1. Étendre `ml.forecast` (migration 0012) et `gold.forecast_latest` avec les colonnes de métadonnées conformes : `model_requested`, `model_effective`, `is_baseline`, `is_calibrated`, `calibration_sample_size`, `status`, `fallback_reason`, `currency`, `unit`, `interval_width`, `coverage_rate_80`.
  2. Étendre l'API `/v1/forecasts` avec :
     - `GET /v1/forecasts` (support filtres `product`, `location`, `actor_level`, `model_run_id`, pagination `limit`, `offset`, formats `json` et `csv`).
     - `GET /v1/forecasts/runs` (historique des model runs, récupération de vieux runs avec empreinte `dataset_fingerprint`).
     - `GET /v1/forecasts/runs/{model_run_id}` (détail et métriques d'un run archivé).
     - `GET /v1/forecasts/abstentions` (catalogue des séries écartées ou abstentions avec motifs normatifs).
  3. Enrichir `web/src/components/charts/PriceChart.tsx` pour afficher fidèlement le modèle effectif, le statut calibré/heuristique et le disclaimer en cas de repli.
  4. Mettre à jour `web/src/app/prices/page.tsx` pour intégrer les prévisions réelles de l'API et l'affichage d'abstention loyale sans falsification de courbe.
- **Alternatives rejetées :**
  - Écraser les runs précédents par un simple `UPDATE` (rejeté, viole l'immutabilité et l'audit C4).
  - Tracer une courbe continue entre le dernier point observé et les prévisions manquantes avec une heuristique front (rejeté, création de fausse information).
- **Conséquences :** Clarté absolue pour l'analyste, auditabilité rétrospective de chaque run de modèle, conformité contractuelle totale avec SPECS §17 et §19.

## ADR-077 : calibration conforme des intervalles de prévision, élimination des replis arbitraires +-10% et surveillance de couverture (R3.5)

- **Date/statut :** 2026-10-16 UTC, adopté avant code R3.5 ; Phase R3.
- **Contexte :** L'estimation de l'incertitude des prévisions de prix ne peut reposer sur des heuristiques arbitraires non vérifiées (constat d'audit A09, directives R3.5). L'ancien code utilisait un repli artificiel $\pm 10\%$ (`p10 = mean * 0.9`, `p90 = mean * 1.1`) lorsque StatsForecast n'était pas disponible ou en cas d'échec. R3.5 prescrit :
  1. **Calibration conforme rigoureuse :** Les intervalles à 80% doivent être étalonnés sur les résidus d'erreurs empiriques réels observés sur les fenêtres de backtest antérieures ($e_t = y_t - \hat{y}_t$), selon les principes de la prédiction conforme (Conformal Prediction pour séries temporelles).
  2. **Interdiction formelle des replis arbitraires :** Aucun intervalle $\pm 10\%$ ne peut recevoir le label `calibrated`. Tout intervalle non étalonné sur des résidus authentiques porte obligatoirement `is_calibrated = False` et un statut explicite `uncalibrated_heuristic`.
  3. **Garanties structurelles des quantiles :** Respect strict de $0 \le p10 \le p50 \le p90$, valeurs finies non nulles.
  4. **Seuil d'échantillon minimal et étanchéité :** Au moins $N_{\text{calib}} \ge 8$ résidus antérieurs requis pour prétendre à un étalonnage conforme valide. Les résidus sont collectés strictement avant la cible évaluée.
  5. **Surveillance et incertitude binomiale :** Mesure systématique de la couverture empirique et de la largeur d'intervalle par horizon ($h=1, 2, 3$). Publication de l'intervalle de confiance binomial à 95% de Wilson sur la couverture réelle mesurée, afin de refléter l'incertitude statistique sur la couverture elle-même.
- **Décision :**
  1. Créer le module `backend/src/ketrika/ml/conformal.py` contenant `ConformalCalibrator`, `ConformalIntervalResult`, `compute_wilson_score_interval` et la fonction de calcul de quantiles conformes `calibrate_conformal_bounds`.
  2. Enrichir `ForecastPrediction` et `ModelForecastResult` avec `is_calibrated`, `calibration_sample_size`, `interval_width`, `binomial_ci_95`.
  3. Raccorder `ConformalCalibrator` dans l'orchestrateur de prévision `forecast.py` et les modèles statistiques.
  4. Couvrir l'ensemble des règles de calibration dans `backend/tests/unit/test_ml_conformal_intervals.py`.
- **Alternatives rejetées :**
  - Conserver le repli $\pm 10\%$ sans métadonnées d'alerte (rejeté formellement par A09).
  - Présenter des quantiles gaussiens théoriques comme conformes sans vérification des résidus réels (rejeté par directive R3.5).
- **Conséquences :** Honnêteté statistique exemplaire sur l'incertitude, traçabilité indiscutable de la calibration, refus de toute promesse abusive de couverture.

## ADR-076 : protocole d'évaluation temporelle en trois phases étanches, sélection rolling-origin à 6 fenêtres, calibration conforme et évaluation finale hors-échantillon (R3.4)

- **Date/statut :** 2026-10-16 UTC, adopté avant code R3.4 ; Phase R3.
- **Contexte :** La sélection d'un modèle de prévision de prix ne doit en aucun cas utiliser des observations futures ou des erreurs calculées sur le jeu de test final (directives R3.4, contrats C2 et C4). Le constat d'audit A08 a mis en évidence des protocoles à seuil réduit (4 à 6 points) sans séparation nette des phases d'apprentissage, d'étalonnage et de test. R3.4 prescrit :
  1. **Séparation étanche en trois étapes chronologiques :**
     - **Étape 1 (Sélection du modèle) :** Backtest rolling-origin mensuel sur l'historique d'apprentissage sur 6 fenêtres glissantes ($h=3$). Chaque fold d'entraînement doit respecter la longueur minimale ($\ge 24$ mois). Le modèle vainqueur $M^*$ est désigné exclusivement sur ces 6 origines.
     - **Étape 2 (Calibration conforme) :** Les résidus d'étalonnage sont collectés strictement avant la cible finale, sans réutiliser d'observations ultérieures.
     - **Étape 3 (Évaluation finale hors-échantillon) :** Le modèle $M^*$ retenu est évalué sur un jeu de test final temporellement disjoint. **Aucune information du test set ne peut influencer le choix de $M^*$ ou les hyperparamètres.**
  2. **Intégrité des origines de sélection :** Si l'historique disponible est insuffisant pour instancier les 6 fenêtres complètes avec un historique d'entraînement éligible, l'algorithme ne doit pas réduire silencieusement le nombre de fenêtres : le protocole est qualifié d'`experimental` avec notification d'historique court, ou s'abstient pour une certification normative.
  3. **Décomposition des métriques par horizon :** Calcul des métriques WAPE, MAE, sMAPE et couverture globale ainsi que par horizon spécifique ($h=1, h=2, h=3$).
  4. **Gestion rigoureuse des cas limites et division par zéro :** Si la somme des valeurs réelles est nulle ou si aucune observation valide n'est disponible pour un horizon, la métrique renvoie explicitement `None` ou `float('nan')` au lieu d'un faux score flatteur `0.0`.
- **Décision :**
  1. Refactoriser `backend/src/ketrika/ml/backtest.py` pour introduire `RollingBacktestProtocol`, `WindowEvaluation`, `HorizonMetrics` et la fonction de découpage temporel étanche `partition_backtest_windows`.
  2. Imposer que `select_best_model` n'opère que sur le split de sélection, et séparer la fonction d'évaluation finale `evaluate_final_holdout`.
  3. Mettre à jour `SeriesMetrics` pour inclure `by_horizon: dict[int, HorizonMetrics]`, `sample_size: int`, `status: str`.
  4. Implémenter les tests de non-fuite et de vérification d'étanchéité dans `backend/tests/unit/test_ml_backtest_protocol.py`.
- **Alternatives rejetées :**
  - Sélectionner le modèle sur l'ensemble de la série incluant la période de test (rejeté, fuite de données majeure et surapprentissage).
  - Réduire discrètement à 1 ou 2 fenêtres sans marquer le statut expérimental (rejeté par directive R3.4).
- **Conséquences :** Évaluation scientifique honnête, absence absolue de surapprentissage sur les cibles d'évaluation, compatibilité directe avec les intervalles conformes de R3.5.

## ADR-075 : modèles de prévision conformes, références normatives, transparence model_requested vs model_effective et traitement des lacunes calendaires (R3.3)

- **Date/statut :** 2026-10-16 UTC, adopté avant code R3.3 ; Phase R3.
- **Contexte :** La phase R3 impose des prévisions de prix évaluées et honnêtes. Le constat d'audit A09 a révélé que les versions initiales réduisaient silencieusement la saisonnalité (saisons de 2 à 4 mois) et masquaient les échecs des modèles en affichant un ARIMA alors qu'un repli naïf ou une moyenne traînante avait tourné. R3.3 exige :
  1. **Références normatives authentiques :** Le dernier prix observé (`NaiveLast`, $y_{t+h} = y_t$) constitue la référence de diagnostic minimale. Le modèle saisonnier naïf (`SeasonalNaive`, $y_{t+h} = y_{t+h-12}$) exige strictement une saisonnalité annuelle (`season_length = 12`).
  2. **Candidats statistiques normatifs :** `AutoETS` et `AutoARIMA` configurés avec `season_length = 12`. Interdiction formelle de substituer une saison artificielle de 2, 3 ou 4 mois pour contourner le manque d'historique. En cas d'historique insuffisant pour estimer la saisonnalité (< 24 mois), le modèle doit s'abstenir ou déclarer un repli explicite.
  3. **Transparence absolue des métadonnées (Anti-tricherie A09) :** Chaque prédiction trace obligatoirement `model_requested`, `model_effective`, `status` (`fitted`, `fallback`, `abstained`), et `fallback_reason`. Aucun résultat ne peut porter l'étiquette `AutoARIMA` si un modèle naïf ou une moyenne a été exécuté.
  4. **Traitement documenté et étanche des lacunes calendaires :** Les trous de la grille mensuelle (`np.nan`) sont traités par interpolation linéaire locale appliquée strictement sur le jeu d'entraînement (`train_y`), sans aucune fuite d'information future. Si le taux de valeurs manquantes dépasse 30% ou si une lacune consécutive excède 4 mois, le modèle s'abstient (`excessive_missing_values`).
  5. **Conservation dimensionnelle :** Chaque prédiction conserve explicitement son unité (`unit`) et sa devise (`currency`).
  6. **Légitimité des références naïves :** Si un modèle naïf surpasse ou égale (à 1 point de WAPE près) un modèle complexe, il est légitimement sélectionné et affiché comme vainqueur.
- **Décision :**
  1. Refondre `backend/src/ketrika/ml/models.py` avec la classe de base `ForecastModel` retournant un `ModelForecastResult` contenant `model_requested`, `model_effective`, `status`, `fallback_reason`, `predictions` (`mean`, `p10`, `p90`), `parameters`, `unit`, `currency`.
  2. Implémenter les classes conformes : `NaiveLastModel`, `SeasonalNaiveModel` (strictement `season_length=12`), `AutoETSModel` (strictement `season_length=12`), `AutoARIMAModel` (strictement `season_length=12`), et `DeterministicBaselineModel`.
  3. Implémenter la fonction d'imputation locale du train `impute_training_gaps(y: np.ndarray, max_gap: int = 4, max_missing_ratio: float = 0.3) -> tuple[np.ndarray, str | None]`.
  4. Mettre à jour `ketrika.ml.backtest` pour comparer loyalement les candidats et conserver les métadonnées de repli.
- **Alternatives rejetées :**
  - Réduire `season_length` à 3 mois lorsque la série a moins de 12 points (rejeté par A09 et R3.1).
  - Renvoyer silencieusement un modèle naïf en conservant le libellé "AutoARIMA" (rejeté formellement par A09).
- **Conséquences :** Honnêteté méthodologique totale, traçabilité irréprochable des modèles réellement exécutés, élimination définitive de toute dissimulation d'échec de fit.

## ADR-074 : constructeur de datasets d'entraînement as-of, traçabilité temporelle C2/C4 et partitionnement sans fuite (R3.2)

- **Date/statut :** 2026-10-16 UTC, adopté avant code R3.2 ; Phase R3.
- **Contexte :** L'apprentissage machine et l'évaluation des modèles de prévision de prix requièrent des jeux de données d'entraînement rigoureusement gelés au point dans le temps (`as_of`) sans fuite d'informations futures (directives R3.2, contrats C2 et C4). Trois impératifs techniques s'imposent :
  1. **Étanchéité temporelle C2 :** Seules les observations effectivement publiées ou disponibles à la date `as_of` (`first_available_at <= as_of` ou `published_at <= as_of` et `ingested_at <= as_of`) peuvent faire partie du dataset. Tout prix observé pour un mois antérieur mais publié ultérieurement (ex: prix de janvier publié en mars) doit être strictement exclu d'un dataset as-of de février.
  2. **Résolution historique des révisions :** Le stockage Bronze/Silver étant en ajout seul (append-only avec `superseded_by`), une révision ultérieure (ex: révision intervenue en avril sur une observation de mars) ne doit pas rétroactivement altérer le dataset as-of de mars. Au temps `as_of`, c'est la version qui était active à ce moment-là qui doit être sélectionnée (`ingested_at <= as_of` et (`superseded_by IS NULL` ou remplacement postérieur à `as_of`)).
  3. **Traçabilité et empreinte canonique C4 :** Chaque dataset d'entraînement porte un identifiant unique, une version, un mode d'origine (`as_of_point_in_time` ou `retrospective`), la liste exhaustive des `observation_ids` et des clés d'artefacts Bronze sources, les règles de sélection, et une empreinte canonique SHA-256 (`canonical_fingerprint`) calculée sur les enregistrements triés de façon déterministe. Deux constructions au même `as_of` doivent produire exactement la même empreinte.
  4. **Partitionnement temporel étanche :** Découpage formel en sous-ensembles `train`, `calibration` et `test` respectant strictement la chronologie sans chevauchement ni utilisation de données futures pour l'étalonnage.
- **Décision :**
  1. Création du module `backend/src/ketrika/ml/dataset.py` avec `DatasetRecord`, `DatasetSplit`, `AsOfDataset` et la fonction constructeur `build_as_of_dataset`.
  2. Requête SQL et filtrage en mémoire point-in-time joignant `obs.price_observation`, `meta.source_record` et `obs.macro_observation`.
  3. Reconstitution déterministe de la clé canonique et de l'empreinte SHA-256 (tri par natural_key/observation_id, sérialisation JSON canonique UTF-8 sans blancs inutiles).
  4. Partitionnement temporel strict par fenêtres calendaires disjointes.
- **Alternatives rejetées :**
  - Utiliser la vue `gold.price_obs_current` sans filtre temporel de révision (rejeté, fuite de données de révisions futures).
  - Déduire la disponibilité temporelle uniquement du champ `month` (rejeté par C2, interdiction d'antidatage).
- **Conséquences :** Reproductibilité absolue des datasets d'apprentissage, élimination radicale des fuites d'information, alignement parfait avec les exigences d'évaluation scientifique de R3.4 et R3.5.

## ADR-073 : éligibilité, calendrier régulier et audit d'exclusion des séries de prévision de prix (R3.1)

- **Date/statut :** 2026-10-16 UTC, adopté avant code R3.1 ; Phase R3.
- **Contexte :** La phase R3 porte sur les prévisions de prix évaluées et honnêtes (directives R3.1 à R3.9). Les séries de prix candidates à l'apprentissage et à l'évaluation doivent être sélectionnées selon des critères statistiques et méthodologiques rigoureux, interdisant tout contournement ou simplification artificielle :
  1. **Seuil d'éligibilité historique et récence :** minimum absolu de 36 mois observés non nuls (`total_points >= 36`), dont au moins 12 mois observés non nuls sur la fenêtre des 24 derniers mois précédant le cutoff (`recent_points_24m >= 12`). Tout seuil artificiel de 6 points ou saisonnalité factice de 2 à 4 mois est formellement interdit et rejeté.
  2. **Granularité géographique (ADR-004) :** niveaux régional (`admin_level = 1`) et national (`admin_level = 0`) uniquement. Rejet formel des districts (`admin_level = 2`) et communes (`admin_level = 3`) pour la modélisation et la publication de prévisions de prix.
  3. **Grille calendaire mensuelle régulière sans compression :** les mois sans observation doivent être explicitement représentés dans la grille régulière par une valeur nulle/absente (`price = None`, `np.nan`), interdisant la compression artificielle des lacunes calendaires en une suite de points consécutifs contigus.
  4. **Étanchéité des types de prix :** exclusion absolue des prix réglementés (`official_ppn`, prix administrés OMH) et des indices (CPI/NIPC) de la cohorte des prix de marché vivriers observés.
  5. **Distinction des cohortes et vérité terrain :** vérité terrain d'évaluation réservée aux observations observées (`observed_or_imputed == 'observed'`). Cohorte purement observée (`cohort = 'observed'`) vs cohorte composite/imputée (`cohort = 'mixed'`).
  6. **Clé de série explicite à 5 composantes :** format canonique `product_code|quality_grade|actor_level|location_pcode|unit`.
  7. **Audit complet et exhaustif :** reporting systématique de chaque série évaluée avec liste d'exclusions documentée et motivée (`SeriesEligibilityReport`). Aucune création de série artificielle pour satisfaire un quota ou un KPI.
- **Décision :**
  1. Refactorisation et enrichissement de `backend/src/ketrika/ml/series.py` pour implémenter `PricePoint` (avec gestion explicite des trous calendaires), `EligibleSeries`, `ExcludedSeries` et `SeriesEligibilityReport`.
  2. Implémentation du constructeur de calendrier régulier `generate_monthly_calendar` et de l'arithmétique mensuelle exacte `shift_months`.
  3. Application des gardes d'éligibilité : 35 points = rejeté, 36 points sans récence = rejeté, district = rejeté, prix réglementé = rejeté.
  4. Séparation des cohortes `observed` et `mixed`, avec flag `can_backtest_6_windows` et `can_calibrate_conformal`.
  5. Maintien de la compatibilité avec l'orchestrateur `forecast.py`.
- **Alternatives rejetées :**
  - Conserver le seuil historique de 6 points (rejeté par directive R3.1 et SPECS §17).
  - Comprimer les mois manquants pour créer une série continue sans trous (rejeté, fausse saisonnalité et distorsion des retards temporels).
  - Inclure les districts pour gonfler le nombre de séries éligibles (rejeté par ADR-004 et R3.1).
- **Conséquences :** Séries temporelles statistiquement intègres, transparentes, exemptes de fuite ou d'artefact de calendrier, conformes aux exigences de validation scientifique.

## ADR-072 : vues marché et observatoire économique, route dédiée `/economy`, fiches métriques et transparence de couverture (R2.10)

- **Date/statut :** 2026-10-16 UTC, adopté avant code R2.10 ; Phase R2.
- **Contexte :** La phase R2 requiert l'exposition frontend des observatoires de marché et d'économie (directive R2.10). Les visualisations doivent refléter fidèlement les principes d'honnêteté et de traçabilité : filtres cohérents, séparation stricte des dimensions macroéconomiques sans score synthétique inventé, intégration de la matrice de couverture et des lacunes calendaires, présence systématique de la provenance et des badges de typage (`ValueKindBadge`), et conformité mobile/accessibilité WCAG AA.
- **Décision :**
  1. **Nouvelle route `/economy` (`web/src/app/economy/page.tsx`) :** Observatoire économique interprétable articulé autour des 5 dimensions étanches d'ADR-070 (`inflation`, `exchange_rate`, `fuel_energy`, `external_trade`, `real_activity`). Chaque dimension expose son statut de complétude (`complete`, `partial`, `no_data`), ses indicateurs avec unités et sources réelles, ses fiches métriques normatives (formule, lag de publication, limitations) et le contexte d'articulation de transmission sur le pilote rizicole (ex: comparaison du coût CAF à l'importation avec le prix de marché local).
  2. **Navigation globale (`web/src/components/layout/Sidebar.tsx`) :** Raccordement de `/economy` sous le libellé « Économie & Conjoncture » avec icône adaptée.
  3. **Enrichissement de la vue Marché (`web/src/app/prices/page.tsx`) :** Intégration d'un composant de couverture de marché restituant la complétude des séries (sources indépendantes, familles, part imputée, ancienneté et lacunes calendaires).
  4. **Transparence et provenance totale :** Utilisation systématique de `ValueKindBadge` et de `ProvenanceLink` vers `/observations/[id]` sur chaque chiffre et graphique. Interdiction formelle de valeurs de remplissage ou de graphiques fictifs.
  5. **Mise à jour des spécifications :** Formalisation de `/economy` dans `docs/plan/SPECS.md` §22.
- **Alternatives rejetées :** Synthétiser un indice unique de performance économique (rejeté par R2.8/R2.10), superposer des courbes d'inflation et de prix au kilo sur un même axe sans avertissement (rejeté pour cause d'incompatibilité dimensionnelle).
- **Conséquences :** Expérience utilisateur fluide et pédagogique, clarté absolue sur la provenance et les limites méthodologiques des données macroéconomiques et de marché.

## ADR-071 : extension des contrats d'API, pagination normative, export CSV et exposition systématique des métadonnées de qualification (R2.9)

- **Date/statut :** 2026-10-16 UTC, adopté avant code R2.9 ; Phase R2.
- **Contexte :** La phase R2 requiert l'exposition uniforme des séries macroéconomiques, de couverture de marché, de disponibilité temporelle et de qualification à travers l'API REST sans rupture pour les clients existants (directive R2.9). De plus, les règles de rigueur et d'intégrité doivent être strictement partagées entre les formats JSON et CSV, la pagination doit être stable et prédictible, et les endpoints administratifs doivent rester protégés.
- **Décision :**
  1. **Extension non-cassante des routes existantes :** Ajout des paramètres de pagination standardisés `limit` (défaut 100, minimum 1, maximum 1000) et `offset` (défaut 0, minimum 0) sur `/v1/macro`, `/v1/market/coverage`, et `/v1/economic/indicators`.
  2. **Parité stricte CSV / JSON :** Ajout du paramètre `format=json|csv` sur les routes de séries (`/v1/macro`, `/v1/market/coverage`, `/v1/economic/indicators`). L'export CSV applique les mêmes filtres, pagination, préservations des valeurs nulles et sérialisations de listes que le JSON, avec en-têtes HTTP `Content-Type: text/csv` et `Content-Disposition`.
  3. **Exposition exhaustive des métadonnées de qualification :** Chaque observation exposée maintient son typage d'observation (`observed_or_imputed`, `value_kind`), son unité physique et devise, sa résolution géographique réelle (sans assignation aveugle), sa temporalité native (`period_start`, `period_end`, `frequency`, `base_period`) et ses jalons de disponibilité (`published_at`, `first_available_at`).
  4. **Contrôle d'accès et non-exposition publique d'administration :** Les routes `/v1/admin/*` exigent strictement le rôle `admin` et ne sont jamais exposées publiquement sans authentification.
  5. **Synchronisation du schéma OpenAPI :** Régénération systématique de `web/src/lib/api/openapi.json` et des types TypeScript correspondants dans `web/src/lib/api/schema.d.ts`.
- **Alternatives rejetées :** Création d'une nouvelle version majeure d'API /v2 (rejeté, complexité injustifiée, clients existants préservés), exclusion du format CSV pour les séries macro (rejeté, parité exigée par SPECS §19).
- **Conséquences :** API totalement homogène, contrats de pagination et d'export robustes, intégration front-end garantie par TypeScript strict.

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

