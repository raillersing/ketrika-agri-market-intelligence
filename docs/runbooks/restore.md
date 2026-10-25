# Runbook : Procédures de sauvegarde et de restauration (SPECS §25 · T11.3)

> Mise à jour2026-10-25 : restore.sh non qualifié pour une restauration fiable (IA-17), configuration prod non reçue ; corriger AU-04/06/07 avant usage ; aucune destination active autorisée. Voir [audit indépendant](../audits/2026-10-25/INDEPENDENT_AUDIT.md) et [plan correctif](../audits/2026-10-25/CORRECTIVE_EXECUTION_PLAN.md).

> **Système :** Ketrika Agri Market Intelligence Madagascar  
> **Cible :** Base de données PostgreSQL (PostGIS) et métadonnées Bronze  
> **Objectif RPO / RTO :** RPO < 24 h (sauvegarde quotidienne chiffrée), RTO < 15 min.

---

## 1. Vue d'ensemble de la stratégie de sauvegarde

1. **Format :** Dump binaire PostgreSQL personnalisé compressé (`pg_dump -Fc`), portable, autonome et permettant la sélection de tables ou la restauration parallèle.
2. **Emplacement local :** Répertoire `./backups/` à la racine du dépôt.
3. **Rétention automatique :** 7 sauvegardes quotidiennes glissantes et 4 sauvegardes hebdomadaires (gérées par `deploy/backup.sh` et Restic).
4. **Déport distant (Production VPS) :** Chiffrement de bout en bout et envoi vers Cloudflare R2 ou Backblaze B2 via Restic (`RESTIC_REPOSITORY`).
5. **Intégrité :** Chaque archive est scellée par son empreinte cryptographique SHA-256 (`.dump.sha256`).

---

## 2. Déclenchement d'une sauvegarde

### 2.1 En environnement de développement local (Windows / PowerShell)

```powershell
./scripts/dev.ps1 backup
```
- Crée un dump horodaté dans `backups/ketrika_backup_YYYYMMDD_HHMMSS.dump`.
- Met à jour le pointeur `backups/ketrika_backup_latest.dump`.

### 2.2 En environnement Linux / VPS / CI

```bash
./scripts/dev.sh backup
# ou directement le script autonome :
deploy/backup.sh
```

Variables d'environnement optionnelles pour `deploy/backup.sh` :
- `PGHOST` (défaut : `localhost` ou `db`)
- `PGPORT` (défaut : `5432`)
- `PGUSER` (défaut : `ketrika`)
- `PGDATABASE` (défaut : `ketrika`)
- `BACKUP_DIR` (défaut : `./backups`)
- `RESTIC_REPOSITORY` (URL du bucket R2 / B2 distant)
- `RESTIC_PASSWORD` (clé de déchiffrement symétrique)

---

## 3. Procédure de restauration

### 3.1 Restauration en environnement local

Pour restaurer la dernière sauvegarde connue :
```powershell
./scripts/dev.ps1 restore
```

Pour restaurer une archive spécifique :
```powershell
./scripts/dev.ps1 restore "backups/ketrika_backup_20261007_120000.dump"
```

Sous Linux / VPS :
```bash
./scripts/dev.sh restore "backups/ketrika_backup_latest.dump"
# ou
deploy/restore.sh "backups/ketrika_backup_latest.dump"
```

### 3.2 Étapes automatisées exécutées par `deploy/restore.sh`

1. **Vérification de l'intégrité :** Contrôle de l'empreinte SHA-256 de l'archive si le fichier `.sha256` est présent.
2. **Déconnexion des clients actifs :** Termine les connexions résiduelles pour éviter les verrous (`pg_terminate_backend`).
3. **Restauration du schéma et des données :** Exécute `pg_restore --clean --if-exists --no-owner --no-privileges`.
4. **Rafraîchissement Gold :** Déclenche le rafraîchissement topologique des 12 vues matérialisées de la couche Gold (`gold.price_monthly`, `gold.source_health`, etc.).
5. **Vérification des comptages :** Affiche un rapport de comptage immédiat sur les tables pivots.

---

## 4. Vérification et validation de l'intégrité post-restauration

Exécuter la requête de contrôle d'intégrité :

```sql
SELECT
    'meta.source' AS table_name, count(*) AS count FROM meta.source
UNION ALL
SELECT 'meta.source_record', count(*) FROM meta.source_record
UNION ALL
SELECT 'obs.price_observation', count(*) FROM obs.price_observation
UNION ALL
SELECT 'gold.price_monthly', count(*) FROM gold.price_monthly
UNION ALL
SELECT 'gold.source_health', count(*) FROM gold.source_health;
```

Toutes les tables doivent afficher des nombres strictement identiques à ceux consignés avant sinistre.

---

## 5. Procédure de reprise après sinistre (Disaster Recovery VPS)

En cas de perte totale de la machine hôte :
1. Provisionner un nouveau serveur VPS Ubuntu 24.04 (voir [`docs/runbooks/deploy.md`](deploy.md)).
2. Exécuter `deploy/bootstrap-vps.sh`.
3. Récupérer le dernier snapshot Restic :
   ```bash
   restic restore latest --target /tmp/restore
   ```
4. Exécuter `deploy/restore.sh /tmp/restore/ketrika_backup_latest.dump`.
5. Redémarrer les services Docker de production :
   ```bash
   docker compose -f docker-compose.prod.yml up -d
   ```
6. Vérifier l'état de santé :
   ```bash
   curl -s http://localhost:8000/v1/health
   ```
