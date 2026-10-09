# R0.1 — gouvernance et bootstrap de qualification

Réception logicielle locale : **verte le 2026-10-09T09:09:25Z**, check Windows complet code 0. Clôture de tâche et commit consignés dans PROGRESS ; aucune certification de données de marché implicite.

## Périmètre

Intégration du programme autorisé dans AGENTS, SPECS, ADR-008 et plan T ; 74 lignes R canoniques dans PROGRESS et miroir dans le plan R. Historique T et tags conservés. Bootstrap minimal du profil de qualification nécessaire au DONE commun, sans réception implicite de R0.2/R0.3.

## Environnement

- Hôte Windows/WSL, dépôt avec espaces et `#` ; Python et Node exclusivement dans Docker.
- Projet `ketrika-qualification`, réseau interne `ketrika_qualification_network`, aucun port publié.
- PostgreSQL `ketrika_qualification`, bucket `ketrika-qa-bronze` versionné, volumes dédiés et identifiants publics de test ; aucun `.env` actif repris.
- LLM replay, SMTP Mailpit, sources hôte en lecture seule. Front copié dans des volumes de qualification.
- Aucun reset, aucune suppression/modification d'objet Bronze ni mutation de la base active.
- Images de tooling existantes : backend:test `55b466bf2dad` (user 0), web:dev `94f7411a5d7c`. Ceci ne qualifie pas un rebuild frais de ces images ni le comportement non-root applicatif ; ces contrôles restent à R0.3/R6.

## Résultats intermédiaires effectivement exécutés

| Contrôle | Commande | Résultat |
|---|---|---|
| Préparation isolée | `bash scripts/dev.sh qa-isolated prepare` | code 0 ; DB/S3/réseau dédiés créés, migrations 0001/0002, seed référentiels 10/15/30/2 |
| Nouveaux tests | `docker compose --env-file scripts/qualification.env --project-name ketrika-qualification -f docker-compose.qualification.yml run --rm --no-deps api sh /workspace/scripts/qa-backend.sh test tests/unit/test_execution_plan.py tests/unit/test_qualification.py` | code 0, 60 passed, 28.61 s, zéro skip |
| Syntaxe PowerShell | `Parser.ParseFile` sur `scripts/dev.ps1` depuis Windows PowerShell | code 0, aucune erreur |
| Refus destructif | `bash scripts/dev.sh reset` et `scripts/dev.ps1 reset` | codes 1 attendus, aucune écriture |
| Refus de destination | `bash scripts/dev.sh qa-isolated production` | code 1 attendu avant initialisation |
| Contrôles backend intermédiaires | `scripts/qa-backend.sh check` dans API dédiée | lint et format verts, 158 fichiers ; mypy code 1 sur retour Any préexistant de demo.py, corrigé puis relance globale |
| Contrôles frontend | `scripts/qa-web.sh check` dans web dédié | code 0 ; lint/types verts, 2 fichiers / 15 tests Vitest passés, build Next réussi (15 routes, pages statiques et dynamiques) |

Le premier essai Windows global a échoué sur les guillemets d'un template Docker des labels. Correction par JSON puis relance réelle de `scripts/dev.ps1 check` ; aucun de ces échecs n'est compté comme un succès.

## Préservation de l'actif

Lecture seule via `docker exec aiagent-db-1 psql -U ketrika -d ketrika -At` : agrégation triée des IDs et valeurs en MD5 (indicateur de préservation, pas hash de certification Bronze).

| Ensemble | Effectif avant/après contrôles intermédiaires | Empreinte avant = après |
|---|---|---|
| meta.source_record | 482 / 482 | `47b4402859acc41e3ae91fdb128e56c6` |
| obs.price_observation | 764 / 764 | `4b2586cb8e422f11c4873ad513d66bc1` |

## Historique avant réception (pas le statut courant)

Le check Windows a été interrompu volontairement après 183/275 tests passés, 2621.97 s, pendant le second backtest anti-fuite temporelle ; trace SciPy optimize ligne 196. B-R001 était alors INVESTIGATING. Relance ciblée avec threads numériques bornés à 1, cache Numba nommé et diagnostic faulthandler ; aucun modèle/test/critère retiré. Le résultat interrompu n'est pas un succès.

Mise à jour 2026-10-09 : la relance ciblée passe les 4 tests de prévision en 1123.43 s, avec 13 séries / 39 prévisions dans chaque run et contrôle anti-fuite temporelle. Le runner termine toutefois code 1 à cause de sa modification pendant l'exécution ; B-R002 documente ce défaut, puis une seconde manifestation sur un check démarré avant le correctif. Les runners sont maintenant figés dans /tmp ; la réception complète repart sans modification de leur code.

Snapshot backend sur `ketrika_qualification_backend_source`, entrée hôte RO et liste de copie sans .env/dépendances hôte ; quatre plugins pytest déclarés explicitement. Sur cette configuration : governance code 0, validateurs 60 passed en 9.35 s, code 0. Check Windows stabilisé : lint/format 158 fichiers, mypy 157 fichiers et graphe 74 tâches verts ; 275 tests collectés et backtest encore en cours. Rapports couverture/JUnit écrits dans le volume nommé de dépendances, pas sur l'hôte.

Réception du check Windows complet (types backend, tous tests/intégration, couverture ≥ 80 % séparément pour core/extraction/normalize, build frontend), cohérence documentaire finale, comparaison active finale, commit atomique vert et clôture synchronisée du plan/PROGRESS.

## Réception finale exécutée

- Commande : `powershell.exe -NoProfile -ExecutionPolicy Bypass -File 'C:\Users\raillersing\Documents\#Entreprise\Ketrika AI\AI Agent\scripts\dev.ps1' check` ; **code 0** sur les versions stabilisées, sans modification de code en cours de test.
- Backend : lint/format 158 fichiers ; mypy 157 fichiers sans erreur ; **275 passed en 1761.11 s**, 243 unitaires / 32 intégrations, zéro failure/error/skip. Lecture indépendante du rapport JUnit pour ces effectifs.
- Couverture réelle par package : core **91.48418491484185 %**, extraction **86.3768115942029 %**, normalize **84.85523385300668 %**, tous ≥ 80 %. Ensemble mesuré : 2183 / 2438 statements. SHA-256 du JSON persistant : `b0c72c48f4a0df6d60ab7cd0e65ae963088bf7b0f5c3076039dd338ded950ae7`.
- Frontend : lint et types verts, Vitest 2 fichiers / 15 tests passés ; build Next code 0, 15 routes. Pas de preuve E2E navigateur dans cette tâche.
- Contrôle documentaire : 74 tâches / 69 MUST / 5 SHOULD ; dépendances et miroirs cohérents. Comparaison git : **43 lignes T strictement inchangées**. Les 13 tags historiques restent présents ; aucun tag R créé.
- Empreinte de l'actif finale : mêmes 482 source_records / 764 prix et mêmes digests qu'avant, lecture seule. Aucun reset/restore/rebuild sur actif.
- Actionlint et shellcheck : codes 0. Gitleaks sur changements préparés stabilisés : code 0, 222189 octets, zéro fuite ; renouvelé à la clôture si la documentation évolue.
- Rapports persistants dans `ketrika_qualification_backend_venv` : `qa-tests.xml`, `qa-coverage.json`. Résumé versionné : `check-summary.json`. Le volume peut recevoir un futur rapport ; le hash et les effectifs de cette réception restent dans la preuve versionnée.
- B-R001/B-R002 : check final vert après diagnostic de durée, threads/caches contrôlés et snapshot de runners/sources ; aucun test, modèle ou seuil de réception retiré. Les échecs/interruption précédents restent dans le journal et ne comptent pas comme succès.

## Limites

Preuves de logiciel et d'isolation uniquement. Aucune collecte live, provenance réelle exhaustive, performance de marché, validation humaine ou livraison déployée qualifiée. `qa`/`qualify` refusent encore explicitement ; R0.2/R0.3 restent TODO.
