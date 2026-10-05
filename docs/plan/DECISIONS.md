# DECISIONS (Architecture Decision Records - ADR)

> Format : `ADR-NNN | date | statut | contexte | décision | alternatives | conséquences`

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
