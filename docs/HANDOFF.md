# HANDOFF : Guide de passation et actions humaines attendues

> **Statut :** Document normatif de passation du MVP Ketrika Agri Market Intelligence (AGENTS.md §3.2 & §5.3).
> Ce document récapitule l'état de livraison du MVP, les pré-requis humains pour la phase d'exploitation, ainsi que les gates d'autorité (H1 à H7) nécessitant une intervention humaine.

---

## 1. État de livraison du MVP (v0.1.0)

Le MVP de Ketrika Agri Market Intelligence est **intégralement développé, testé et validé**.
- **100 % des tâches MUST** des Phases 0 à 11 sont `DONE`.
- **Les 11 KPIs d'acceptation** (SPECS §1.3) sont vérifiés et atteints.
- La plateforme est autonome en environnement local (`docker-compose.yml`, MinIO, Mailpit, Dagster, PostGIS, FastAPI, Next.js) et le paquet de déploiement pour VPS Ubuntu 24.04 avec Caddy et Cloudflare R2 (`docker-compose.prod.yml`) est livré et testé.

---

## 2. Matrice des Gates Humains et Actions Attendues

| ID | Domaine | Statut MVP | Action humaine requise avant exploitation commerciale |
|---|---|---|---|
| **H1** | **Clés API LLM** | Mode `replay` ou dev validé | Créer les clés API de production (`GEMINI_API_KEY` ou `ANTHROPIC_API_KEY`) dans Google AI Studio / Anthropic Console. Renseigner les variables dans `.env` sur le VPS. |
| **H2** | **Infrastructure & Hébergement** | Prêt à déployer (`docker-compose.prod.yml`, `bootstrap-vps.sh`) | 1. Provisionner un VPS Ubuntu 24.04 LTS (4 vCPU, 8 Go RAM minimum) chez Hetzner, OVH ou Scaleway.<br>2. Configurer le DNS `market.ketrika.ai` vers l'IP publique du VPS.<br>3. Créer un bucket Cloudflare R2 `ketrika-bronze` et générer les identifiants S3 (`S3_ACCESS_KEY`, `S3_SECRET_KEY`).<br>4. Suivre le runbook [`docs/runbooks/deploy.md`](runbooks/deploy.md). |
| **H3** | **Envoi de notifications réelles** | Verrouillé (`EXTERNAL_SEND_ENABLED=0`, capture Mailpit) | 1. Souscrire à un service SMTP transactionnel (Resend, Brevo ou AWS SES).<br>2. Renseigner `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` dans `.env`.<br>3. Une fois les adresses de diffusion validées, basculer explicitement `EXTERNAL_SEND_ENABLED=1`. |
| **H4** | **Partenariats plateformes privées** | Politique « permission d'abord » appliquée, zéro collecte sauvage | Prendre contact avec les fondateurs de Tantsah à l'aide du modèle [`docs/outreach/tantsah_outreach.md`](outreach/tantsah_outreach.md) pour signer une convention de flux de données mutuelle. |
| **H5** | **Revue humaine des alias & golden sets** | 100% automatisé, drapeaux `human_reviewed=false` | Les analystes métier peuvent utiliser l'interface `/admin/review` pour approuver formellement les nouveaux alias ou réconciliations à confiance < 0,9. |
| **H6** | **Garde-fous budgétaires LLM** | Plafond configuré à 20 $/mois (`BudgetGuard`) | Ajuster `LLM_MONTHLY_BUDGET_USD` selon les volumes réels de bulletins et requêtes copilote mensuelles. |
| **H7** | **Relations institutionnelles** | Modèles rédigés dans `docs/outreach/` | Relire et transmettre par voie officielle les 3 courriers de partenariat aux institutions :<br>- MiASA / ODR ([`docs/outreach/miasa_odr_outreach.md`](outreach/miasa_odr_outreach.md))<br>- MinCC Commerce Intérieur ([`docs/outreach/mincc_outreach.md`](outreach/mincc_outreach.md))<br>- INSTAT ([`docs/outreach/instat_outreach.md`](outreach/instat_outreach.md)). |

---

## 3. Procédures de démarrage pour l'équipe humaine

### 3.1 Prise en main locale immédiate

Pour explorer l'application sur votre poste de travail :
```powershell
# 1. Démarrer tous les services conteneurisés
./scripts/dev.ps1 up

# 2. Exécuter la démonstration d'acceptation automatique
./scripts/dev.ps1 demo

# 3. Ouvrir les interfaces dans le navigateur
# - Web Dashboard : http://localhost:3005 (admin@ketrika.local / change-me)
# - API REST Docs : http://localhost:8090/docs
# - Dagster Cockpit : http://localhost:3010
# - Mailpit Webmail : http://localhost:8025
```

### 3.2 Déploiement sur VPS de production

Suivre pas-à-pas les instructions du runbook opérationnel :
[`docs/runbooks/deploy.md`](runbooks/deploy.md)

### 3.3 Routine de sauvegarde et restauration

- Sauvegarde locale ou distante : `./scripts/dev.ps1 backup` (génère un dump chiffré/scellé sous `backups/`).
- Restauration : `./scripts/dev.ps1 restore [chemin_fichier]` (suivre [`docs/runbooks/restore.md`](runbooks/restore.md)).
- Rotation périodique des secrets : suivre [`docs/runbooks/rotate-secrets.md`](runbooks/rotate-secrets.md).

---

## 4. Points de contact et maintenance

- **Code source et dépôt :** `https://github.com/ketrika/ai-agent`
- **Branche principale stable :** `main`
- **Tag de version MVP :** `mvp-v0.1.0`
- **Documentation d'architecture :** [`README.md`](../README.md) et [`docs/plan/SPECS.md`](plan/SPECS.md)
- **Rapport d'audit de sécurité :** [`docs/SECURITY_REVIEW.md`](SECURITY_REVIEW.md)
- **Rapport final d'acceptation :** [`docs/MVP_REPORT.md`](MVP_REPORT.md)
