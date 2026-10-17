# Runbook de Déploiement & Préparation VPS (R6.10, SPECS §23, §24, Gate H2)

## 1. Statut de Déploiement : LOCAL_READY (Gate H2)

> **Important (AGENTS.md Gate H2) :** La plateforme Ketrika Agri Market Intelligence est entièrement configurée, testée et prête pour le déploiement (`LOCAL_READY`). Conformément à la matrice d'autorité d'AGENTS.md §5 (Gate H2), l'agent autonome n'achète aucun nom de domaine, ne provisionne aucun VPS et ne configure aucune clé Cloudflare R2 externe sans intervention humaine. Aucun statut fallacieux « déployé en production » ne peut être revendiqué sans fourniture des identifiants et validation humaine de Gate H2.

---

## 2. Architecture de Déploiement Cible

- **Hôte cible :** VPS Ubuntu 24.04 LTS (2 vCPU, 4 Go RAM minimum).
- **Orchestration :** Docker Compose production (`docker-compose.prod.yml`).
- **Reverse Proxy :** Caddy 2 (`deploy/Caddyfile`) gérant automatiquement les certificats TLS / Let's Encrypt et la compression HTTP/2 zstd/gzip.
- **Réseau interne hermétique :**
  - PostgreSQL (`db` port 5432) : aucun port mappé sur l'hôte `0.0.0.0`.
  - MinIO S3 (`minio` ports 9000/9001) : accessible uniquement sur le réseau Docker privé `ketrika-prod-net`.
  - Dagster Daemon & Webserver : cloisonnés en réseau interne.
  - Seul Caddy écoute publiquement sur les ports 80 et 443.

---

## 3. Procédure de Déploiement Étape par Étape

### Étape 1 : Initialisation du VPS
Exécuter en tant que root sur le nouveau serveur :
```bash
curl -fsSL https://raw.githubusercontent.com/ketrika/ketrika/main/deploy/bootstrap-vps.sh | bash
```
Le script configure :
- Mise à jour du système et installation de Docker Engine + Compose
- Création de l'utilisateur `deploy` avec droits sudo
- Pare-feu UFW activé (seuls 22, 80, 443 sont ouverts)
- Protection anti-bruteforce Fail2ban
- Répertoire `/opt/ketrika` prêt.

### Étape 2 : Configuration des Secrets Applicatifs
Se connecter en tant qu'utilisateur `deploy` dans `/opt/ketrika` :
```bash
cp .env.example .env
chmod 600 .env
nano .env
```
Renseigner obligatoirement :
- `DOMAIN` : Nom de domaine officiel (ex. `market.ketrika.mg`)
- `POSTGRES_PASSWORD` : Mot de passe fort aléatoire
- `JWT_SECRET` : Clé de chiffrement HMAC de 64 caractères
- `S3_ENDPOINT_URL`, `S3_ACCESS_KEY`, `S3_SECRET_KEY` (identifiants Cloudflare R2 ou MinIO)
- `GEMINI_API_KEY` (sous Gate H1)

### Étape 3 : Démarrage de la Stack Production
```bash
docker compose -f docker-compose.prod.yml up -d --build
```

### Étape 4 : Vérification des Healthchecks & Services
```bash
docker compose -f docker-compose.prod.yml ps
curl -fsSL https://<VOTRE_DOMAINE>/v1/health
```

### Étape 5 : Sauvegarde Initiale & Surveillance
Exécuter un premier backup certifié :
```bash
./deploy/backup.sh
```
Vérifier la création du dump et du manifeste `.meta.json` dans `/opt/ketrika/backups/`.
