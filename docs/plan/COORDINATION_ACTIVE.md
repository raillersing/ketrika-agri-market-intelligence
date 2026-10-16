# Coordination active — Codex / Antigravity

Mise à jour 2026-10-15. Ce document ne qualifie aucune tâche produit.

Audit du 2026-10-16 : Antigravity HEAD6f11f5d/codebb62799 (R2.10), non reçu.
Lire `docs/research/2026-10-16-antigravity-r1-r2-audit.md` : sept groupes
d'écarts bloquent l'intégration, dont publication Gold sans provenance macro,
fixtures générées étiquetées authentiques et preuve de qualification surestimée.
Ne pas importer ses statuts/tags ni écraser ADR069–074 de main. Son worktree
et son PROGRESS non committé sont préservés ; corrections à réaliser de son côté.
Le check Codex78714 est terminé FINAL0/1725 backend/35 frontend/build ;
plus de réservation de la destination QA pour cette exécution, aucune relance.

Actualisation 2026-10-16 : Codex reçoit le correctif ADR-074 contexte partagé,
worktree `r08-revision-context-20261016`, branche du même nom préfixée `work/`,
commit `8de251f`, check Windows session `78714`. Source figée et destination
`ketrika-qualification` réservée pendant ce processus ; ne pas y lancer de suite
mutante concurrente. Livraison main précédente `bc0f947` reçue ; les travaux
Antigravity dans son propre worktree restent indépendants et non importés.

- Priorité utilisateur : finir les fonctionnalités prévues dans leur version
  minimale utilisable ; reporter les raffinements hors critères de réception.
  Pas de nouveaux composants alternatifs ni refonte sans blocage concret.
- Codex : R0.8/rejeu, réception puis R0.9 ; branche
  `work/r08-corpus-acquisition-20261015`, worktree Linux homonyme sous
  `/home/raillersing/projects/ketrika-qa-worktrees/`.
- Antigravity travaille simultanément. Worktree observé `r1-sources-prep`, branche
  `work/r1-sources-prep`, HEAD observé `d6057fe`, modifications non committées
  du dashboard sources et de ses tests. Son journal courant indique R1.12
  (actualisation/reprise/santé des sources), après les commits R1.3–R1.11.
  Codex ne modifie ni ne fusionne ce worktree en cours. Les statuts locaux
  resteront à rapprocher des critères du plan lors de la réception commune.
- Les préparations R1 peuvent être auditées sans développer une seconde version.
  Commits et statuts locaux ne remplacent pas l'intégration et les gates partagés.
- Préserver les modifications main préexistantes (huit `__init__.py`,
  `web/src/lib/api/openapi.json`, prompt utilisateur non suivi).
- Une seule réception mutante à la fois sur `ketrika-qualification`. Aucun agent
  ne relance un check sur cette destination pendant le check d'un autre agent.
  L'aperçu prix et le clone de rejeu utilisent chacun leurs propres DB/volumes.
- Chaque livraison indique branche/commit, fichiers, tests ciblés et limites.
  Le coordinateur synchronise PROGRESS et plan ; ne pas remplacer les journaux
  concurrents ni déclarer DONE une capacité encore partielle.
- Lecture ciblée d'intégration : voir ANTIGRAVITY_INTEGRATION_NOTES.md ; conserver
  les fixtures INSTAT générées mais les qualifier synthetic, pas authentic.
