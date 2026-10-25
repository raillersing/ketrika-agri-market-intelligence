# Runbook : Déploiement en production (VPS Ubuntu 24.04)

> Mise à jour2026-10-25 : restore.sh non qualifié pour une restauration fiable (IA-17), configuration prod non reçue ; corriger AU-04/06/07 avant usage ; aucune destination active autorisée. Voir [audit indépendant](../audits/2026-10-25/INDEPENDENT_AUDIT.md) et [plan correctif](../audits/2026-10-25/CORRECTIVE_EXECUTION_PLAN.md).

> **Statut :** Document opérationnel normatif (T11.4).
> Ce guide décrit la mise en production intégrale de la plateforme Ketrika Agri Market Intelligence sur un serveur VPS autonome.

---

## 1. Vue d'ensemble de l'architecture de production

En production, l'architecture se compose de :
- **Reverse Proxy :** [Caddy 2](https://caddyserver.com) assurant la terminaison TLS automatique (Let's Encrypt), la compression HTTP (zstd, gzip), les en-têtes HSTS/sécurité et le routage public. Seuls les ports 80 et 443 sont exposés.
- **Frontend Web :** Next.js 14 en conteneur autonome (port interne 3000).
- **Backend API :** FastAPI servi par Uvicorn multi-workers (port interne 8000).
- **Orchestration Dagster :** `dagster-daemon` et `dagster-webserver` connectés à la base PostGIS. L'interface Dagster (3001) est conservée privée et accessible via tunnel SSH sécurisé.
- **Base de données :** PostgreSQL 17 + PostGIS 3.5 (volume `pgdata`, port interne isolé).
- **Stockage Bronze :** Cloudflare R2 (compatible S3, stockage distribué immuable avec zéro frais d'egress).
- **Réseau :** Réseau Docker bridge isolé `ketrika-prod-net`.

---

## 2. Pré-requis humains (Gate H2)

Avant de lancer le déploiement, l'administrateur système humain doit préparer les éléments suivants :

| Élément | Spécification recommandée | Fournisseur / Note |
|---|---|---|
| **VPS Ubuntu 24.04 LTS** | 4 vCPU, 8 Go RAM, 80 Go NVMe SSD | Hetzner, OVHcloud ou Scaleway |
| **Nom de domaine / DNS** | Enregistrement A : `market.ketrika.ai` $\rightarrow$ IP du VPS | Cloudflare / Registrar |
| **Stockage Bronze S3** | Bucket `ketrika-bronze`, token d'accès S3 | Cloudflare R2 |
| **Fournisseur SMTP** | Hôte SMTP, port 587, utilisateur, mot de passe | Resend, Brevo ou AWS SES |
| **Clés API LLM (H1)** | `GEMINI_API_KEY` ou `ANTHROPIC_API_KEY` | Google AI Studio / Anthropic |

---

## 3. Étape par étape : Déploiement initial

### Étape 1 : Initialisation automatique du serveur VPS (root)

Connectez-vous au VPS fraîchement installé en tant que `root` et exécutez le script d'amorçage :

```bash
# Sur votre machine locale ou directement sur le VPS :
ssh root@<IP_VPS>

# Récupérer et exécuter le script de bootstrap
curl -fsSL https://raw.githubusercontent.com/ketrika/ai-agent/main/deploy/bootstrap-vps.sh -o bootstrap.sh
chmod +x bootstrap.sh
./bootstrap.sh
```

Le script installe Docker, configure l'utilisateur `deploy`, verrouille le pare-feu UFW (seuls les ports 22, 80, 443 sont ouverts) et active `fail2ban` ainsi que les mises à jour de sécurité automatiques.

### Étape 2 : Connexion sous l'utilisateur applicatif

```bash
ssh deploy@<IP_VPS>
cd /opt/ketrika
```

### Étape 3 : Récupération du dépôt

```bash
git clone https://github.com/ketrika/ai-agent.git .
```

### Étape 4 : Configuration du fichier `.env`

Créez le fichier de configuration de production `.env` à partir de `.env.example` :

```bash
cp .env.example .env
nano .env
```

Renseignez impérativement les variables suivantes :

```dotenv
APP_ENV=prod
DOMAIN=market.ketrika.ai
ACME_EMAIL=admin@ketrika.ai

# Base de données
POSTGRES_USER=ketrika
POSTGRES_PASSWORD=<GENERER_MOT_DE_PASSE_FORT_64_CHARS>
POSTGRES_DB=ketrika
DATABASE_URL=postgresql+psycopg://ketrika:<MOT_DE_PASSE>@db:5432/ketrika
COPILOT_DB_PASSWORD=<GENERER_MOT_DE_PASSE_FORT_RO>

# Stockage Bronze (Cloudflare R2)
S3_ENDPOINT_URL=https://<ACCOUNT_ID>.r2.cloudflarestorage.com
S3_ACCESS_KEY=<R2_ACCESS_KEY_ID>
S3_SECRET_KEY=<R2_SECRET_ACCESS_KEY>
S3_BUCKET_BRONZE=ketrika-bronze
S3_REGION=auto

# Clés et sécurité
JWT_SECRET=<GENERER_CLE_HEX_64_CHARS>
CORS_ORIGINS=https://market.ketrika.ai

# LLM
LLM_PROVIDER=gemini
LLM_MODEL_EXTRACT=gemini-2.5-flash
LLM_MODEL_REASON=gemini-2.5-flash
GEMINI_API_KEY=<CLE_API_GEMINI>
LLM_MONTHLY_BUDGET_USD=20

# Notifications
SMTP_HOST=smtp.resend.com
SMTP_PORT=587
SMTP_USER=resend
SMTP_PASSWORD=<CLE_API_SMTP>
SMTP_FROM=bulletin@ketrika.ai
EXTERNAL_SEND_ENABLED=0  # Basculer à 1 uniquement sur validation humaine explicite (H3)
```

### Étape 5 : Construction et premier lancement de la base

```bash
# Construire les images Docker de production
docker compose -f docker-compose.prod.yml build

# Démarrer la base de données PostGIS
docker compose -f docker-compose.prod.yml up -d db

# Attendre que la base soit saine (healthcheck healthy)
docker compose -f docker-compose.prod.yml ps
```

### Étape 6 : Migrations de schéma et chargement des référentiels

```bash
# Appliquer les migrations Alembic (schémas meta, ref, obs, ml, ops, gold, auth...)
docker compose -f docker-compose.prod.yml run --rm api uv run alembic upgrade head

# Charger les référentiels (sources, géographie, taxonomie, utilisateurs initiaux)
docker compose -f docker-compose.prod.yml run --rm api python -m ketrika.core.seed
```

### Étape 7 : Démarrage complet de la stack de production

```bash
docker compose -f docker-compose.prod.yml up -d
```

Vérifier l'état de l'ensemble des conteneurs :

```bash
docker compose -f docker-compose.prod.yml ps
```

Tous les services (`caddy`, `db`, `api`, `web`, `dagster-webserver`, `dagster-daemon`) doivent être à l'état `running` ou `healthy`.

### Étape 8 : Vérification de santé et accès

Testez l'accessibilité publique HTTPS :

```bash
curl -I https://market.ketrika.ai/v1/health
```

Réponse attendue :
```json
HTTP/2 200
content-type: application/json
{
  "status": "ok",
  "version": "0.1.0",
  "database": "connected",
  "storage": "connected"
}
```

---

## 4. Exploitation et maintenance courante

### Accès à l'UI Dagster via tunnel SSH

L'interface de Dagster n'est pas exposée sur internet par mesure de sécurité. Pour superviser les pipelines :

```bash
# Sur votre machine locale :
ssh -N -L 3001:localhost:3001 deploy@<IP_VPS>
```
Ouvrez ensuite `http://localhost:3001` dans votre navigateur.

### Automatisation des sauvegardes (cron)

Ajoutez la tâche cron de sauvegarde automatique quotidienne à 2h00 du matin pour l'utilisateur `deploy` :

```bash
crontab -e
```

Ajoutez la ligne suivante :
```cron
0 2 * * * /opt/ketrika/deploy/backup.sh >> /var/log/ketrika-backup.log 2>&1
```

### Consultation des journaux d'exécution

```bash
# Journaux structurés de l'API
docker compose -f docker-compose.prod.yml logs -f --tail=100 api

# Journaux des ingestions Dagster
docker compose -f docker-compose.prod.yml logs -f --tail=100 dagster-daemon

# Journaux d'accès Caddy
docker compose -f docker-compose.prod.yml logs -f --tail=100 caddy
```

---

## 5. Procédure de mise à jour (Rolling Upgrade)

Lors de la livraison d'une nouvelle version applicative :

```bash
cd /opt/ketrika

# 1. Sauvegarde préventive de la base
./deploy/backup.sh

# 2. Récupération de la nouvelle version
git pull origin main

# 3. Reconstruction des images
docker compose -f docker-compose.prod.yml build

# 4. Application des éventuelles migrations Alembic
docker compose -f docker-compose.prod.yml run --rm api uv run alembic upgrade head

# 5. Redémarrage sans interruption des services
docker compose -f docker-compose.prod.yml up -d --remove-orphans

# 6. Vérification de santé
curl -f https://market.ketrika.ai/v1/health
```
