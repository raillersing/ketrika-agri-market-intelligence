# Ketrika Agri Market Intelligence

Plateforme locale d'intelligence de marché sur les PPN vivriers à Madagascar : collecte publique autorisée, provenance Bronze/Silver, API, dashboard, prévisions, agroclimat et aide à la décision.

**État au25 octobre2026 : PARTIAL, requalification en cours.** L'audit indépendant révèle des chiffres de démonstration affichés comme réels, des replis météo fabriqués et des défauts de sécurité/provenance. L'application ne doit pas encore servir de référence pour une décision institutionnelle.

- [Audit indépendant et preuves](docs/audits/2026-10-25/INDEPENDENT_AUDIT.md)
- [Plan correctif détaillé :26 lots et réceptions](docs/audits/2026-10-25/CORRECTIVE_EXECUTION_PLAN.md)
- [Matrice des74 tâches et18 sources](docs/audits/2026-10-25/TASK_CAPABILITY_MATRIX.md)
- [Progression canonique](docs/plan/PROGRESS.md), [plan R normatif](docs/plan/MARKET_INTELLIGENCE_EXECUTION_PLAN.md), [passation](docs/HANDOFF.md)

## Capacités et limites constatées

| Domaine | Présence | Qualification actuelle |
|---|---|---|
| Collecte conforme, objets Bronze, normalisation, Gold | Code et tests logiciels reçus historiquement | Rebuild global non qualifié :164 références manquantes et lignée historique à réparer |
| Banque mondiale RTFP | Collecte réelle en un clic, reçu durable |135 prix courants imputés, couverture partielle ; pas des cours observés nationaux |
| Accueil, prix, carte | Pages accessibles | Accueil contient des constantes ; codes produit incohérents ; vraie carte GeoJSON à construire |
| Économie | Connecteurs et calculs présents | Aucune ligne macro dans la base sondée ; publication retenue avec503 |
| Prix prévus | Modules et39 prévisions héritées exposées | Dataset SQL as-of et calibration à corriger, résultats historiques non qualifiés |
| Météo, calendriers, approvisionnement | Connecteurs et fonctions présents | Données de repli et entrées fixes à retirer ; validation réelle manquante |
| Copilote, bulletins, alertes | Parcours et garde-fous partiellement présents | Résultats réels et usage humain à recevoir ; envois externes interdits |
| FIRMS, GloFAS, acquisition satellite | Absents ou calcul seul | Facultatifs, indisponibles explicitement |

La provenance100% est une **exigence**, pas une garantie atteinte dans l'état actuel. Le statut d'une tâche, la présence du code, un test synthétique, une collecte live et un modèle validé sont cinq preuves différentes.

## Démarrage et environnement

Python, Node et Playwright s'exécutent exclusivement dans Docker. Les dépendances vivent dans des volumes nommés ; le chemin Windows contient espaces et `#`.

Point d'entrée unique : `./scripts/dev.ps1` sous PowerShell, `bash scripts/dev.sh` sous Linux. Lire [AGENTS.md](AGENTS.md) et les runbooks avant toute opération. Conserver bases et volumes existants ; aucune réinitialisation/reconstruction de test sur actif.

Services locaux configurés : interface `http://localhost:3005`, API `http://localhost:8090/v1/health`, documentation API `/v1/docs`, Dagster expert `http://localhost:3010`, Mailpit `http://localhost:8025`. Leur démarrage dépend de Docker et des montages source ; une URL documentée n'est pas une sonde de disponibilité permanente.

La configuration de production, les secrets, les transports externes et les scripts de restauration ont des réserves ouvertes. Ne pas exécuter l'ancien `restore.sh` sur une destination active. Aucun déploiement n'est déclaré reçu.

## Construction et validation

Réutiliser les modules existants ; corriger/raccorder avant de réécrire. Développement par lots fonctionnels, tests ciblés puis un check complet sur source figée à la réception. L'audit documentaire ne relance pas toutes les suites et ne qualifie aucun nouveau gate.

Les tâches R gardent leur état canonique :7 DONE historiques,52 IN_PROGRESS,15 TODO. Le programme finit selon R6.11, pas selon l'ancien rapport MVP. Les documents historiques et leurs captures sont conservés ; ils ne prouvent pas les chiffres actuels.

Dépôt : [raillersing/ketrika-agri-market-intelligence](https://github.com/raillersing/ketrika-agri-market-intelligence). Les accès GitHub dépendent des permissions du dépôt privé.

Travail correctif en cours (ADR121) : [plan avant implémentation AU-01–03](docs/audits/2026-10-25/SAFE_FACTS_IMPLEMENTATION_PLAN.md). L'accueil réel, les valeurs météo absentes et l'abstention des scénarios sont corrigés sur branche isolée ; leur réception complète et leur activation restent à prouver dans PROGRESS. Les constats de la base auditée ci-dessus restent des preuves historiques, pas l'état supposé du nouveau contenu.
