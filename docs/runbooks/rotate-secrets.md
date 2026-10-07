# Runbook : Rotation des secrets et identifiants

> **Statut :** Document opérationnel normatif (T11.4).
> Ce runbook définit les protocoles stricts de renouvellement régulier ou d'urgence (suite à compromission suspectée) de l'ensemble des clés, mots de passe et jetons d'accès de la plateforme Ketrika Agri Market Intelligence.

---

## 1. Inventaire des secrets de production

| Secret | Fichier / Variable | Portée d'impact | Fréquence recommandée |
|---|---|---|---|
| Mot de passe PostgreSQL principal | `POSTGRES_PASSWORD`, `DATABASE_URL` | Accès DB `ketrika_app` (API, Dagster) | 90 jours ou urgence |
| Mot de passe copilote lecture seule | `COPILOT_DB_PASSWORD` | Accès DB `copilot_ro` (requêtes NL2SQL) | 90 jours |
| Secret de signature JWT | `JWT_SECRET` | Signature des tokens de session utilisateur | 180 jours |
| Clés Cloudflare R2 (S3) | `S3_ACCESS_KEY`, `S3_SECRET_KEY` | Écriture / lecture Bronze immuable | 180 jours |
| Clé API LLM | `GEMINI_API_KEY` / `ANTHROPIC_API_KEY` | Inférence extraction, copilote, bulletins | Immédiate si fuite |
| Mot de passe SMTP | `SMTP_PASSWORD` | Expédition des alertes et bulletins | 180 jours |

---

## 2. Procédures de rotation pas-à-pas

### 2.1 Rotation du mot de passe de la base de données (`POSTGRES_PASSWORD`)

1. Générer une nouvelle chaîne de mot de passe cryptographiquement forte :
   ```bash
   openssl rand -hex 32
   ```

2. Se connecter en `superuser` sur l'instance PostgreSQL conteneurisée et modifier le rôle applicatif :
   ```bash
   docker compose -f docker-compose.prod.yml exec db psql -U postgres -c "ALTER ROLE ketrika WITH PASSWORD '<NOUVEAU_MOT_DE_PASSE>';"
   ```

3. Mettre à jour `/opt/ketrika/.env` :
   ```dotenv
   POSTGRES_PASSWORD=<NOUVEAU_MOT_DE_PASSE>
   DATABASE_URL=postgresql+psycopg://ketrika:<NOUVEAU_MOT_DE_PASSE>@db:5432/ketrika
   ```

4. Redémarrer les services dépendants avec prise en compte immédiate :
   ```bash
   docker compose -f docker-compose.prod.yml up -d --force-recreate api dagster-webserver dagster-daemon
   ```

5. Vérifier la santé du service :
   ```bash
   curl -f http://localhost:8000/v1/health
   ```

---

### 2.2 Rotation du mot de passe du copilote (`COPILOT_DB_PASSWORD`)

Le rôle `copilot_ro` est strictement confiné en lecture seule sur le schéma `gold`.

1. Générer le nouveau secret :
   ```bash
   openssl rand -hex 32
   ```

2. Modifier le rôle dans PostgreSQL :
   ```bash
   docker compose -f docker-compose.prod.yml exec db psql -U postgres -d ketrika -c "ALTER ROLE copilot_ro WITH PASSWORD '<NOUVEAU_MOT_DE_PASSE_RO>';"
   ```

3. Mettre à jour `/opt/ketrika/.env` :
   ```dotenv
   COPILOT_DB_PASSWORD=<NOUVEAU_MOT_DE_PASSE_RO>
   ```

4. Redémarrer l'API :
   ```bash
   docker compose -f docker-compose.prod.yml up -d --force-recreate api
   ```

---

### 2.3 Rotation du secret JWT (`JWT_SECRET`)

> [!WARNING]
> La rotation du secret JWT invalide instantanément tous les jetons d'accès existants. Les utilisateurs connectés devront se réauthentifier.

1. Générer une clé de signature de 64 caractères hexadécimaux :
   ```bash
   openssl rand -hex 32
   ```

2. Mettre à jour `/opt/ketrika/.env` :
   ```dotenv
   JWT_SECRET=<NOUVELLE_CLE_JWT>
   ```

3. Redémarrer l'API :
   ```bash
   docker compose -f docker-compose.prod.yml up -d --force-recreate api
   ```

---

### 2.4 Rotation des clés Cloudflare R2 (Stockage Bronze)

Pour éviter toute interruption de service lors du basculement R2 :

1. Sur la console Cloudflare R2 (R2 $\rightarrow$ Manage R2 API Tokens) :
   - Créer un **nouveau token API** avec permissions d'accès au bucket `ketrika-bronze` (lecture/écriture d'objets, pas de suppression).
   - Conserver temporairement l'ancien token actif.

2. Mettre à jour `/opt/ketrika/.env` :
   ```dotenv
   S3_ACCESS_KEY=<NOUVEAU_KEY_ID>
   S3_SECRET_KEY=<NOUVEAU_SECRET_KEY>
   ```

3. Redémarrer l'API et Dagster :
   ```bash
   docker compose -f docker-compose.prod.yml up -d --force-recreate api dagster-daemon dagster-webserver
   ```

4. Tester le bon accès au stockage Bronze :
   ```bash
   docker compose -f docker-compose.prod.yml exec api python -c "from ketrika.core.bronze import BronzeStore; store = BronzeStore(); print('Bronze storage OK')"
   ```

5. Une fois le bon fonctionnement validé, **révoquer immédiatement** l'ancien token sur la console Cloudflare.

---

### 2.5 Rotation des clés API LLM (`GEMINI_API_KEY`, etc.)

1. Créer une nouvelle clé d'API sur Google AI Studio (ou console Anthropic / OpenAI).
2. Vérifier que les quotas et plafonds de dépense sont configurés.
3. Remplacer la variable dans `/opt/ketrika/.env` :
   ```dotenv
   GEMINI_API_KEY=<NOUVELLE_CLE_API>
   ```
4. Recharger les conteneurs :
   ```bash
   docker compose -f docker-compose.prod.yml up -d --force-recreate api dagster-daemon
   ```
5. Révoquer l'ancienne clé d'API dans la console fournisseur.

---

## 3. Checklist post-rotation

Après toute opération de renouvellement d'identifiants, exécuter la checklist de validation suivante :

- [ ] L'API répond `200 OK` avec `"database": "connected"` et `"storage": "connected"` sur `/v1/health`
- [ ] L'authentification `POST /v1/auth/token` fonctionne correctement
- [ ] L'interrogation du copilote SQL répond sans erreur d'authentification de base de données
- [ ] Le démon Dagster s'exécute sans erreur de connexion dans ses journaux (`docker compose -f docker-compose.prod.yml logs dagster-daemon`)
- [ ] Les anciens secrets compromis ou périmés ont été définitivement révoqués chez le fournisseur tiers.
