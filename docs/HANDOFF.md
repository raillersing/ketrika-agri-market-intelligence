# Passation — PARTIAL

État audité le 2026-10-27 à 15:12 UTC. Le programme R0–R6 n'est pas reçu ; les annonces précédentes de 69 MUST qualifiés et de tag final sont retirées, avec originaux conservés dans `docs/evidence/R0.8_CI_GOVERNANCE_64938cf_*_ORIGINAL.gz`.

1. Recevoir le contenu stabilisé de la PR #4 par le check complet backend/frontend et les 26 scénarios E2E, sans erreur ni skip obligatoire. Vérifier les reçus natifs, empreintes de source, couvertures et cas exécutés avant fusion. Les ciblés antérieurs ne remplacent pas cette réception.
2. Reprendre AU-08/R0.8 à la preuve manquante : inventaire Bronze/SQL isolé, diagnostic B-R084/B-R085, conservation de tous les objets et données actifs. Ne jamais restaurer ni reconstruire une destination active pour tester.
3. Pour AU-09/R0.9 et B-R073 : obtenir deux éditions authentiques autorisées avec fichiers source, URL vérifiable, dates de publication/récupération, SHA-256, droits et provenance ; exécuter ensuite le replay complet hors réseau sur stockage et base dédiés. Aucun corpus synthétique ne clôt cette exigence.
4. Auditer chaque critère R1–R6 avec les dépendances réellement reçues. Distinguer logiciel testé, collecte live, modèle validé sur corpus indépendant et pilote humain. Conserver IN_PROGRESS tant que la preuve manque. Les sélections QA ajoutées restent disponibles ; elles ne suffisent pas à qualifier les gates.

H1 : continuer en replay sans clé. H2 : préparation locale uniquement, aucun achat ou provisionnement. H3 : Mailpit/brouillons uniquement ; aucune configuration SMTP ne vaut autorisation d'envoi réel. H4 : aucune collecte privée. H5 : `human_reviewed: false` sans revue effective. H6 : refus au-delà du budget. H7 : aucun contact de tiers par l'agent ; tout pilote humain reste à organiser par une personne autorisée.

Le [guide Contabo](GUIDE_DEPLOIEMENT_CONTABO_VPS.html) est conservé comme documentation préparatoire, sans preuve de déploiement. Références canoniques : [PROGRESS](plan/PROGRESS.md), [BLOCKERS](plan/BLOCKERS.md), [plan R](plan/MARKET_INTELLIGENCE_EXECUTION_PLAN.md), [rapport PARTIAL](MARKET_INTELLIGENCE_REPORT.md).
