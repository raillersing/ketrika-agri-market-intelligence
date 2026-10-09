# BLOCKERS : registre des blocages et incidents

> Format : `ID | tâche | date | symptôme | cause supposée | tentatives (1, 2, 3) | repli appliqué | statut`
> Statut : `INVESTIGATING` | `RESOLVED_FALLBACK` | `RESOLVED_FIXED` | `BLOCKED`

| ID | Tâche | Date | Symptôme | Cause | Tentatives | Repli appliqué | Statut |
|---|---|---|---|---|---|---|---|
| B-R003 | R0.2 | 2026-10-09 | Deux lancements PowerShell check code 1, `WSL UtilAcceptVsock accept4 failed 110`, aucun contrôle démarré | Socket WSL_INTEROP=/run/WSL/56256_interop défaillant ; socket système /run/WSL/2_interop répond à PowerShell 5.1 | 1 : lancement ; 2 : relance ; correction : sélectionner le socket système par commande ; check complet final code 0 | Aucun service actif redémarré ; diagnostic Linux interrompu volontairement dans son seul conteneur QA ; réception finale 290 backend / 15 web / build verts | RESOLVED_FIXED |
| B-R001 | R0.1 | 2026-10-09 | Check interrompu : 183/275 tests passés, backtest anti-fuite temporelle trop long ; KeyboardInterrupt dans scipy.optimize._optimize.py:196 | Optimisation scientifique lente sur 13 séries ; causalité exhaustive non établie | 1 : interruption ; 2 : diagnostic ciblé 4 tests passés ; réception finale 275 passed en 1761.11 s | Threads à 1, caches dédiés et source snapshot ; check Windows complet code 0 le 2026-10-09, aucun modèle/test/seuil retiré | RESOLVED_FIXED |
| B-R002 | R0.1 | 2026-10-09 | Tests verts puis runner code 1, et check ancien exit 127 après seed | Modification par l'agent du fichier sh monté pendant son exécution | 1 : relance ciblée ; 2 : check lancé avant snapshot ; réception sur runner stabilisé code 0 | Snapshot des runners dans /tmp avant lecture ; sources Python/Node en volumes dédiés ; pas de modification pendant le check final | RESOLVED_FIXED |
