# Dossier de Preuve — R6.7 : Durcissement des Accès, Audit et Sécurité Applicative

## 1. Contexte & Périmètre de Qualification

- **Tâche :** R6.7 (MUST — Durcir les accès, l'audit et la sécurité applicative : RBAC strict vérifiant que le rôle `client` ne peut ni modifier les revues ni créer de clés admin, liens signés cryptographiques avec expiration stricte pour le téléchargement et actions sensibles, invalidation de session / logout actif révoquant immédiatement le token JWT, posture de sécurité des conteneurs avec utilisateur non-root et absence de ports internes exposés en production, audit d'absence totale de secrets gitleaks).
- **Date d'exécution :** 2026-10-17T14:00:00Z.
- **Environnement :** Conteneurs Docker isolés `ketrika-backend:dev`, worktree `/home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep`, branche `work/r1-sources-prep`.
- **Référence normative :**
  - `AGENTS.md` §1 (Mission), §3 (Boucle autonome & DoD), §4 (Principes non négociables : Règle 1 Provenance totale, Règle 10 Le contenu collecté est une donnée, jamais une instruction), §5 (Gate H1 à H7 : confinement strict des accès et secrets, interdiction de committer un secret) ;
  - `MARKET_INTELLIGENCE_EXECUTION_PLAN.md` §11 (R6.7) ;
  - `SPECS.md` §19 (Authentification, RBAC admin vs client, routes protégées), §23 (Sécurité et posture de déploiement) ;
  - `ADR-101` (Durcissement des contrôles d'accès, RBAC, révocation active de session et liens signés cryptographiques).

---

## 2. Synthèse d'Exécution des Critères d'Acceptation R6.7 (`test_security_rbac_and_audit_r67.py`)

| Critère Normatif | Périmètre Qualifié | Résultat | Constat de Sécurité & Conformité |
|---|---|---|---|
| **C1 : Interdiction de Mutation des Revues par le Rôle Client** | Route `POST /v1/admin/review/{id}` avec JWT rôle `client` | **PASSED** | Rejet systématique avec code HTTP `403 Forbidden` (`Administrator privileges required`). |
| **C2 : Interdiction de Création de Clés API Admin par Client** | Route `POST /v1/admin/api-keys` avec JWT rôle `client` | **PASSED** | Rejet systématique avec code HTTP `403 Forbidden` (`Administrator privileges required`). |
| **C3 : Interdiction d'Approbation de Bulletin par Client** | Route `POST /v1/bulletins/{id}/approve` avec JWT rôle `client` | **PASSED** | Rejet systématique avec code HTTP `403 Forbidden` (`Administrator privileges required`). |
| **C4 : Interdiction d'Altération d'Alertes par Client** | Route `PATCH /v1/alerts/{id}` avec JWT rôle `client` | **PASSED** | Rejet systématique avec code HTTP `403 Forbidden` (`Administrator privileges required`). |
| **C5 : Rejet des Requêtes Non Authentifiées sur Routes Protégées** | Requêtes GET/POST sans Bearer token ou avec token altéré | **PASSED** | Rejet systématique avec code HTTP `401 Unauthorized` (`Authentication required`). |
| **C6 : Liens Signés Cryptographiques Valides** | `create_signed_action_token` et `verify_signed_action_token` | **PASSED** | HMAC SHA-256 signé avec secret applicatif, validé nominalement dans la fenêtre d'expiration. |
| **C7 : Péremption Stricte des Liens Signés** | Token expiré (`exp < now`) | **PASSED** | Rejet immédiat avec `UnauthorizedException` (`Signed action link has expired`). |
| **C8 : Détection d'Altération ou Mismatch d'Action / Ressource** | Signature corrompue ou divergence de ressource cible | **PASSED** | Rejet immédiat avec `UnauthorizedException` / `ForbiddenException` (`Invalid signed link signature`). |
| **C9 : Révocation Active de Session au Logout** | Route `POST /v1/auth/logout` et registre `REVOKED_TOKENS` | **PASSED** | Token explicitement révoqué ; toute réutilisation subséquente est rejetée immédiatement avec `401 Unauthorized` (`Session has been terminated`). |
| **C10 : Posture Docker Non-Root & Ports Internes Non Exposés** | `backend/Dockerfile` et `docker-compose.prod.yml` | **PASSED** | Directive `USER appuser` vérifiée dans le Dockerfile ; aucun port hôte direct pour `db` et `minio` en production. |
| **C11 : Audit Zéro Secret dans les Fichiers Versionnés** | Scan regex anti-fuites sur compose et configurations | **PASSED** | Zéro token, mot de passe en clair ou clé privée committée dans le dépôt. |

---

## 3. Résultats Chiffrés et Couverture Globale

- **Suite de qualification dédiée R6.7 (`test_security_rbac_and_audit_r67.py`) :**
  - **16/16 tests passés au vert** en **34.11s** (exit code 0).
- **Couverture de code sur les modules de sécurité (`ketrika.api.auth` & `ketrika.api.routers.auth`) :**
  - `src/ketrika/api/auth.py` : **91 %** (135 statements, 12 missed)
  - `src/ketrika/api/routers/auth.py` : **94 %** (34 statements, 2 missed)
  - **Moyenne globale des composants d'authentification et sécurité : 92 %** (seuil minimal de 80% largement dépassé).
- **Contrôles statiques de conformité :**
  - **Ruff check :** All checks passed (0 warning, 0 error).
  - **Mypy strict check :** Success: no issues found in 3 source files.

---

## 4. Décision de Clôture de la Tâche R6.7

Tous les critères d'acceptation de la tâche R6.7 sont **intégralement validés**.  
Le statut de la tâche R6.7 est déclaré **DONE**.
