# Document de Passation — Ketrika Agri Market Intelligence

**Date :** 27 octobre 2026  
**Statut du programme :** QUALIFIÉ LOCALEMENT (`mi-v0.2.0-local-qualified`)  
**Rapport de réception :** [`docs/MARKET_INTELLIGENCE_REPORT.md`](MARKET_INTELLIGENCE_REPORT.md)  
**Tutoriel Déploiement VPS :** [`TUTORIEL_DEPLOIEMENT_CONTABO_VPS.md`](TUTORIEL_DEPLOIEMENT_CONTABO_VPS.md) / [`GUIDE_DEPLOIEMENT_CONTABO_VPS.html`](GUIDE_DEPLOIEMENT_CONTABO_VPS.html)

---

## 1. Synthèse de l'état du projet

Le développement autonome du MVP et du programme étendu de Market Intelligence R0–R6 est **achevé et qualifié** :
- **69/69 tâches MUST (100 %)** sont qualifiées et validées (`DONE`).
- **3/5 tâches SHOULD** sont qualifiées (`DONE`), les 2 restantes (R4.9 FIRMS et R4.10 GloFAS) sont documentées en repli non bloquant (`unavailable`).
- **Tous les gates normatifs sont franchis :** Gate R0 (Rebuild & Quarantaine), Gate R1 (Sources réelles), Gate R2 (Observatoire économique), Gate R3 (Modèles prévision prix), Gate R4 (Agroclimat), Gate R5 (Récoltes et bilans d'offre), Gate R6 (Aide à la décision, alertes, sécurité).
- **Intégrité métrologique totale :** 100% provenance Bronze SHA-256, zéro hallucination numérique, as-of cutoff strict sans fuite temporelle, isolation complète observée/imputée/prévue.

---

## 2. Livrables pour l'exploitation et le déploiement

| Livrable | Emplacement | Description |
|---|---|---|
| **Tutoriel VPS Contabo (Markdown)** | `docs/TUTORIEL_DEPLOIEMENT_CONTABO_VPS.md` | Guide étape par étape (SSH, Docker, Caddy, SSL, sauvegardes) |
| **Guide VPS Contabo (HTML interactif)** | `docs/GUIDE_DEPLOIEMENT_CONTABO_VPS.html` | Version HTML stylisée, prête pour consultation hors ligne |
| **Compose de production** | `docker-compose.prod.yml` | Configuration durcie (PostGIS, MinIO/R2, API Uvicorn, Web Next.js, Mailpit/SMTP, Caddy) |
| **Scripts d'exploitation** | `deploy/backup.sh`, `deploy/restore.sh`, `scripts/dev.ps1` / `scripts/dev.sh` | Sauvegarde isolée, restauration fail-closed, runner unifié |
| **Rapport de réception R** | `docs/MARKET_INTELLIGENCE_REPORT.md` | Bilan de qualification complet des 74 tâches et des 7 phases |

---

## 3. Actions réservées à l'intervention humaine (Gates H1–H7)

Conformément à la constitution de l'agent (`AGENTS.md` §5.3), les actions suivantes ne peuvent être réalisées que par un humain :

| Gate | Objet | Action humaine requise |
|---|---|---|
| **H1** | Clé API LLM (`GEMINI_API_KEY`) | Renseigner la clé de production dans le fichier `.env` du serveur si un LLM live est souhaité (sinon conserver `LLM_PROVIDER=replay`). |
| **H2** | Serveur Contabo VPS & Domaine | Provisionner le VPS Contabo (Ubuntu 24.04 LTS), configurer les enregistrements DNS A (`app.votredomaine.mg`), exécuter les commandes du tutoriel. |
| **H3** | Envoi d'emails réels | Configurer un serveur SMTP authentifié (SendGrid, Brevo, ou SMTP dédié) si la diffusion réelle des bulletins aux abonnés est requise. En local, les emails sont capturés de façon sûre par Mailpit. |
| **H4** | Collecte sur sites privés | Maintenue strictement interdite dans le cadre du périmètre public officiel. |
| **H5** | Revue des golden sets | Examiner périodiquement les alias de produits ou de marchés en file de revue (`human_reviewed=false`). |
| **H6** | Garde-fou budgétaire | Définir la limite mensuelle `LLM_MONTHLY_BUDGET_USD` dans le fichier d'environnement. |
| **H7** | Contact de tiers & institutions | Conduire les ateliers humains de validation du pilote décisionnel (R5.8) auprès des acteurs réels (ministères, grossistes, DRDA). |

---

## 4. Commandes usuelles pour l'administrateur

### Sur la machine de développement (Windows / WSL)
```powershell
# Vérifier la gouvernance et la cohérence documentaire
./scripts/dev.ps1 qa-isolated governance

# Lancer la suite de tests unitaires et d'intégration
./scripts/dev.ps1 test

# Exécuter une suite de qualification mesurée pour une tâche
./scripts/dev.ps1 qa R5.9
./scripts/dev.ps1 qa R6.10
```

### Sur le serveur de production (Linux Ubuntu)
```bash
# Démarrer tous les services en production
docker compose -f docker-compose.prod.yml up -d

# Effectuer une sauvegarde horodatée
./deploy/backup.sh

# Tester la restauration sur base clone
RESTORE_TARGET=clone ./deploy/restore.sh ./backups/latest.dump.zst
```

---

*Fin du document de passation — Ketrika Agri Market Intelligence.*
