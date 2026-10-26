# AU-07 — fidélité SQL, développement reçu partiellement

ADR126. La première archive positive conservait les valeurs mais perdait les ACL sous `--no-owner --no-privileges` ; elle ne suffit pas à recevoir AU-07. Ces options sont retirées. Aucun rôle n'est créé ou remappé par la restauration.

Sur le seul cluster privé `ketrika-restore-audit-20261026-db`, sans ports ni Bronze : restauration dans `ketrika_restore_acl_positive` code0 ; une archive valide contenant un GRANT vers un rôle absent échoue réellement code1 et annule la transaction (`ops.restore_probe` absent). Les rôles temporaires sont des fixtures de ce cluster privé uniquement, pas des créations du produit.

Comparaison SQL readonly : toutes les tables archivées, valeurs triées avec SHA-256, propriétaires/ACL de schémas, relations et fonctions, ACL par défaut et colonnes, indicateurs RLS, droits effectifs `ketrika_app`/`copilot_ro`. Les seuls objets exclus `public.restore_fail_fixture` et `public.restore_fail_check` ont été ajoutés à la source après l'archive positive pour le contre-exemple COPY ; ils ne figurent pas dans cette archive. Les deux rapports sont strictement identiques : SHA-256 `1ce39e1216f293738aa6f36b6cb270baedf7bc24a12366f131cb80f9614c1eda`.

PowerShell5.1 natif : point d’entrée restauré sans changement de politique Windows, code0 ; même comparaison intégrale, même empreinte SHA-256 sur ketrika_restore_ps_acl.
Ruff/format verts et 37 tests ciblés passent en26,74s sur image r04, sans réseau. Le premier lancement ciblé a échoué sur un cache Ruff readonly ; la variable de cache temporaire a été corrigée, aucune assertion retirée. Ce contrôle de développement ne remplace pas le check complet du nouveau contenu figé ni l'E2E. Le corpus économique, les objets Bronze, les rôles de production et la reprise opérationnelle de l'actif restent hors de cette preuve.

La comparaison initiale en échec n'est pas effacée : l'ancien clone perdait les ACL de schémas et relations, même si ses compteurs et valeurs étaient identiques. La nouvelle comparaison exclut explicitement les deux seuls objets négatifs créés après sauvegarde ; elle ne revendique pas l'identité d'un état source ultérieur complet.

Sur le même script corrigé, l'archive au CHECK délibérément impossible échoue réellement sur COPY (code1) ; le clone `ketrika_restore_acl_copy_failure` ne contient pas `ops.restore_probe` après rollback. Le log original est conservé compressé. Aucun clone existant ni archive n'a été supprimé.
