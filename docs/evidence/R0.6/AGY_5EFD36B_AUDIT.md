# Audit de la livraison Antigravity 5efd36b

Audit statique en lecture seule du commit `5efd36b1cbe6fac8468a589f48362b264322dff4`, branche `feat/r06-http-conformance-lot-c`, worktree propre observé. Aucun test relancé, aucun fichier de cette branche modifié, aucune fusion effectuée.

## Décision : ne pas intégrer la branche en l'état

La réception coordinateur R0.6 est déjà documentée dans `LOT_C_RECEPTION.md` (produit main `173c41a`, ADR-063, migration 0010). Le rapport d'Agy ne remplace pas cette réception et ne justifie pas un nouveau statut DONE.

| Écart vérifié | Preuve dans le commit Agy | Conséquence |
| --- | --- | --- |
| SQL non raccordé par défaut | `http.py:141` appelle `get_budget_manager()` ; `http_budget.py:300` choisit InMemoryBudgetBackend ; singleton lignes 434–440 | Les quotas du client par défaut ne survivent pas au redémarrage et ne sont pas partagés entre workers. La factory SQL existe mais aucun appel applicatif n'a été trouvé. |
| Réservation non atomique source + domaine | `http_budget.py:377` puis `:380`, deux appels backend, chacun ouvre sa transaction | Un refus du domaine peut laisser la réservation source déjà validée. Ce n'est pas la transaction commune de l'ADR-063. |
| Création du schéma à l'exécution | Constructeur SqlBudgetBackend ligne 50 puis CREATE SCHEMA/TABLE lignes 52–85 | Non compatible avec la migration coordonnée existante ; risque de schéma concurrent divergent. |
| Désactivation seulement en mémoire | `policy.py:169–184`, ensemble `_disabled_origins` | Aucun arrêt persistant après redémarrage démontré par ce chemin. |
| Exceptions de stockage exposées | `http_budget.py:85–89`, interpolation de l'exception et details.error | Risque d'exposer des informations de connexion ; utiliser une erreur publique générique avec diagnostic interne expurgé. |
| PostgreSQL non prouvé et paramètre mal compilé | `test_core_http_conformance.py:545,567,579,613,619` utilisent SQLite ; `http_budget.py:106/120` emploie `:date_utc::DATE` | Diagnostic readonly Docker/SQLAlchemy code 0 : `text("SELECT :date_utc::DATE")` compilé avec le dialecte PostgreSQL conserve littéralement `SELECT :date_utc::DATE`, dictionnaire de paramètres vide. Le paramètre n'est donc pas reconnu ; utiliser `CAST(:date_utc AS DATE)` ou un paramètre DATE typé, puis un vrai test PostgreSQL. Aucun accès à la base dans ce diagnostic. |
| Réception complète absente du brief | 41 tests HTTP ciblés, couverture ciblée et mypy six fichiers revendiqués | Ni check backend/frontend complet, ni intégration PostgreSQL du client par défaut, ni inventaire global attaché n'ont été fournis dans ce brief. Chiffres non réexécutés par cet audit. |
| ADR proposée incompatible avec la numérotation actuelle | ADR-061 déjà occupée sur main ; contrat HTTP actuel ADR-063 | Ne pas écraser les décisions ni les migrations du coordinateur. |

## Apport à conserver séparément

`http.py:46–55` inclut notamment `x-api-key`, `api-key`, `apikey`, `x-auth-token` et `token` dans les en-têtes sensibles. La liste du coordinateur main ne contient pas actuellement ces variantes. Une correction bornée devra vérifier la purge sur la requête finale, après fusion des en-têtes client, ainsi que le maintien des en-têtes sur une requête autorisée de même origine. Ce constat n'est pas déclaré corrigé ici.

## Suite d'exécution

1. Conserver le commit et les tests Agy comme matériau d'audit, sans cherry-pick global.
2. Finaliser la réception R0.7 déjà en cours sur source figée : aucune modification du code ni seconde suite mutante pendant ce check.
3. Traiter séparément la protection additionnelle des en-têtes ; tests négatifs cross-origin/robots et positifs same-origin, puis réception complète du lot stabilisé selon AGENTS §3.3.
4. Réutiliser le backend durable déjà reçu plutôt que réintroduire DDL runtime, mémoire par défaut ou réservations disjointes.

Limites : inspection statique seulement ; ni collecte live, ni preuve de déploiement, ni performance marché, ni essai humain. La branche d'Agy reste intacte.
