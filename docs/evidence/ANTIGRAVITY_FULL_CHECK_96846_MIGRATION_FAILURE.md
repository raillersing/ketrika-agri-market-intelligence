# Réception Antigravity — échec de préparation PostgreSQL

- Source figée : `925c105`, branche `fix/agy-publication-audit-20261016`.
- Commande : PowerShell `scripts/dev.ps1 check` depuis le worktree isolé
  `agy-publication-audit-20261016`, session `96846`.
- Environnement : projet Docker `ketrika-qualification`, base et bucket QA,
  aucune migration sur la destination active.
- Stade : `qa-backend.sh prepare`, migration depuis `0010_http_policy_budget`.
- Erreur PostgreSQL : `StringDataRightTruncation: value too long for type character varying(32)`.
- Instruction refusée : mise à jour de `alembic_version.version_num` vers
  `0011_macro_observation_and_time_contracts`.
- Cause : cet identifiant et celui de 0012 dépassent la taille standard du
  champ de suivi Alembic. Transaction PostgreSQL annulée ; les tests et le
  frontend n'ont pas commencé, aucun ancien JUnit ne doit être réutilisé.
- Incident : `B-R074`, première tentative. Correction prévue : élargissement
  additif du champ de suivi, sans renommer les identifiants de migration ni
  modifier une valeur observée. Nouvelle réception complète requise.
- Terminaison hôte : FINAL1 observé, sans interruption du processus. Lecture
  SQL après échec : version0010, table macro absente, zéro autre requête active.
  Ce rapport consigne une réception rouge, pas une réussite logicielle.
