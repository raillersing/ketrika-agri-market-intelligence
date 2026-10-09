# DECISIONS (Architecture Decision Records - ADR)

> Format : `ADR-NNN | date | statut | contexte | décision | alternatives | conséquences`

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

