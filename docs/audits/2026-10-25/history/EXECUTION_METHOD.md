# Méthode d'exécution accélérée — ADR-057

Autorisation utilisateur du 2026-10-13. AGENTS §3.3 est normatif ; ce guide
organise le travail sans modifier les critères produit, l'isolement ou H1–H7.

## Cycle standard

1. Lire la dernière preuve consolidée, le diff courant et le blocage réel.
   Ne pas relancer 36 minutes de tests simplement pour répondre « continues ».
2. Définir un résultat fonctionnel complet et ses tests avant code. Helpers,
   branchements et cas négatifs constituent des sous-étapes, pas des réceptions
   distinctes. Mini-plan <=10 lignes, travail dans un seul worktree dédié.
3. Pendant développement : lint/types ciblés puis tests nouveaux/régressions
   impactées. Petits commits worktree verts ; aucune prétention de livraison main.
4. Quand le résultat est complet : une réception globale sur sources figées,
   critères métier et check complet. Ne pas refaire mécaniquement QA cumulée
   si le JUnit global prouve déjà les mêmes fichiers/cas et leurs minima.
5. Archiver originaux, vérifier source/scope/empreintes, scanner les secrets,
   recevoir le lot sur main puis une clôture documentaire cohérente.

Rien ne permet de retirer les fits réels, l'anti-fuite, les tests SQL/S3, le build
ou un gate obligatoire. Pas de suite mutante concurrente sur la même DB/bucket.
Si une réception échoue, corriger sa cause puis recommencer sur le nouveau
contenu ; ne pas arrêter un check vert en cours pour préparer un helper.

## Lots restants R0.6

| Lot | Résultat attendu | Réception |
|---|---|---|
| A — résilience native | Consommation du lot enregistré, tentatives durables, reprise explicite et identités/partitions de document-version ; inclure les préparations ADR-056 dans ce résultat plutôt qu'une livraison isolée de cinq lignes | SQL/S3 succès, erreur, concurrence, crash/reprise sans refetch, retry idempotent ; check complet unique du lot |
| B — publication sûre | Garde structurelle SQL/CLI cohérente avec Dagster ; traiter le risque d'identité BL-016 dans les limites du contrat R2.1, sans deviner le type des 764 anciennes observations | Cas négatifs de publication et collisions, révisions append-only ; ADR/SPECS avant extension, check complet |
| C — collecte conforme | Robots automatique, redirections/retries contrôlés et budgets ; intégrer les primitives de débit au comportement réel | Serveur HTTP local, refus = zéro requête interdite, quotas/restart, check complet |

Ces lots ne créent pas de nouvelles tâches R et n'autorisent aucune dépendance
future à être contournée. R0.6 reste IN_PROGRESS jusqu'à tous ses critères.

## Mesurer plutôt que supposer

`./scripts/dev.ps1 qa-profile docs/evidence/R0.6/increment-13-backend-check-tests.xml`

Linux : même argument à `./scripts/dev.sh qa-profile`. La commande lit uniquement
le rapport existant dans Docker, sans réseau, services, seed ni réexécution.
Les paramètres de tests sont masqués. Les durées additionnées sont celles des
testcases JUnit (incluant leurs phases), pas forcément le temps mur du runner.
Un rapport de profiling ne qualifie aucune capacité ni aucune tâche.

Suivre par lot : nombre de checks complets, durée du lot, temps des validations,
tests dominants, annulations et régressions. Objectif d'organisation : un check
complet par lot vert (davantage si une correction invalide sa preuve), zéro
double check de reprise. Aucun gain d'entraînement revendiqué avant mesure.
