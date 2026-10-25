# Mission à transmettre à Antigravity

Statut : PRÊTE À TRANSMETTRE, pas envoyée ni démarrée par Antigravity.
Ce document ne modifie aucun contrat ni statut de tâche.

## Instructions de démarrage

Lire entièrement AGENTS.md, puis docs/plan/PROGRESS.md, BLOCKERS.md,
SPECS.md, MARKET_INTELLIGENCE_EXECUTION_PLAN.md, DECISIONS.md et
EXECUTION_METHOD.md pour les sections concernées. R0.6 est IN_PROGRESS.
Travailler dans une branche/worktree séparé créé depuis le HEAD courant,
sans écraser les préparations ou modifications existantes. Confirmer le
commit de base et les chemins pris en charge avant de modifier le code.

## Lot confié : R0.6 C — collecte HTTP conforme

Résultat attendu : les contrôles robots, redirections, retries et limites
s'appliquent au chemin HTTP réellement utilisé, pas seulement à des helpers.

1. Auditer backend/src/ketrika/core/http.py et ses appels, PolicyEngine,
   les contrats SPECS §12 et les tests existants. Réutiliser ce qui est prouvé.
2. Proposer les éventuelles extensions ADR/SPECS AVANT implémentation.
   Ne pas choisir seul un numéro ADR partagé ; transmettre le projet au
   coordinateur pour incorporation dans les documents canoniques.
3. Raccorder la vérification robots automatique ; un état absent/inconnu
   ne constitue pas une autorisation implicite. Définir les règles exactes
   de cache, erreurs et accès à robots conformément aux contrats adoptés.
4. Contrôler chaque destination de redirection et chaque retry : politique,
   identité User-Agent, débit et quota ; pas de requête interdite préalable.
5. Traiter les budgets/restarts conformément aux contrats. Si une persistance
   nécessite un schéma nouveau, proposer la migration au coordinateur avant
   de coder ; ne pas toucher les migrations ou bases partagées directement.
6. Couvrir les comportements avec un serveur HTTP local/simulé : refus
   robots, redirection interdite, 401/403/challenge, retries bornés, quotas,
   identité du robot et reprise du budget si prévue. Aucune collecte live
   nécessaire pour ces tests et aucune qualification live revendiquée.

## Propriété des fichiers et coordination

- Antigravity : core/http.py, nouveaux modules HTTP internes convenus,
  tests HTTP ciblés et documentation locale du lot dans son worktree.
- Coordinateur : durable_runs.py, durable_phases.py, stages.py,
  batch_ledger.py, identités/partitions, factory.py, Gold et migrations.
- PROGRESS, plan R, ADR, SPECS, manifeste QA, scripts de réception et AGENTS
  restent sous responsabilité du coordinateur. Fournir des propositions
  de modifications, pas de modifications concurrentes de ces fichiers.
- core/policy.py ou tout fichier partagé : signaler le besoin avant édition
  et convenir d'une propriété exclusive. Ne pas modifier les connecteurs
  institutionnels hors nécessité approuvée du lot.

## Validation et retour

Python/Node uniquement dans Docker, dépendances en volumes nommés.
Pendant développement : lint/types et tests nouveaux ou impactés seulement.
Pas de check complet indépendant ni suite mutante sur la QA partagée sans
créneau accordé. Le coordinateur réalise une réception complète unique du
lot intégré et figé ; elle reste obligatoire avant livraison produit.

Retour attendu : commit de base, diff/commits de branche, chemins modifiés,
commandes et codes finaux, effectifs et durées, originaux des rapports,
critères satisfaits/manquants et limites. Un prototype testé n'est pas une
tâche DONE ; R0.6 ne sera clôturée qu'après tous ses critères.

## Hors périmètre

Ne pas démarrer R0.7 et suivants avant leurs dépendances. Ne pas altérer
Bronze, migrer la base active, partager des secrets, contacter des tiers,
envoyer des messages réels, contourner robots/CAPTCHA/authentification,
réduire les tests/seuils ou installer une nouvelle dépendance sans ADR.

Les autres lots pourront être transmis après cette première intégration,
avec une propriété de fichiers et une réception convenues ; pas de prise
en charge globale non coordonnée de toutes les tâches restantes.
