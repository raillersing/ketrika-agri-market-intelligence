# HANDOFF : Guide de passation et actions humaines attendues

> **Statut :** Document normatif de passation de Ketrika Agri Market Intelligence (AGENTS.md §3.2 & §5.3, R6.11).  
> **Version finale du programme :** `mi-v0.2.0-local-qualified` (scellé le 2026-10-17T14:48:00Z).  
> **Rapport d'acceptation consolidé :** [`docs/MARKET_INTELLIGENCE_REPORT.md`](MARKET_INTELLIGENCE_REPORT.md).

---

## 1. État de Clôture du Programme Market Intelligence (R0–R6)

Le programme complet Ketrika Agri Market Intelligence est **100 % développé, testé et qualifié** :
- **74/74 tâches MUST (Phases R0 à R6) sont `DONE`**.
- **Tous les gates intermédiaires sont validés et scellés :**
  - `mi-r0-qualified` : Socle de qualification isolée, SQL Guard, intégrité réseau.
  - `mi-r1-qualified` : Normalisation PPN 7 filières, Bronze immuable SHA-256.
  - `mi-r2-qualified` : Observatoires macro-économique, change, carburants, commerce.
  - `mi-r3-qualified` : Modélisation des cours, conformal calibration et baselines WAPE.
  - `mi-r4-qualified` : Marchés régionaux, disparités spatiales et anomalies de prix.
  - `mi-r5-qualified` : Récoltes décadaires, bilan d'offre, flux douaniers et pilote décisionnel 3 profils.
  - `mi-v0.2.0-local-qualified` : Aide à la décision, copilote sans hallucination (65/65 tests), bulletin scellé, alertes anti-faux consensus, durcissement des accès, sauvegarde/restauration certifiée, et performance HTTP P95 < 1s sous 5 clients concurrents.

---

## 2. Matrice des Gates d'Autorité Humaine (H1 à H7) & Actions Requises

Conformément à la constitution de l'agent (`AGENTS.md` §5.3), ces actions sont **exclusivement réservées à l'intervention humaine** :

| ID | Domaine | Statut Actuel | Action Humaine Requise pour Exploitation en Production |
|---|---|---|---|
| **H1** | **Clés API LLM** | Mode `replay` & mock testés au vert (100%) | Renseigner `GEMINI_API_KEY` (ou clé Anthropic/OpenAI) dans le fichier `.env` sur le VPS. |
| **H2** | **Hébergement VPS & Domaine** | `LOCAL_READY` (prêt à déployer) | 1. Provisionner un serveur VPS Ubuntu 24.04 LTS (2 vCPU, 4 Go RAM min) chez un hébergeur.<br>2. Pointer le DNS du domaine (ex. `market.ketrika.mg`) vers l'adresse IP du VPS.<br>3. Configurer les identifiants Cloudflare R2 ou MinIO pour le stockage Bronze.<br>4. Suivre [`docs/runbooks/DEPLOYMENT_RUNBOOK.md`](runbooks/DEPLOYMENT_RUNBOOK.md). |
| **H3** | **Diffusion externe (Emails / Telegram)** | Verrouillé (`EXTERNAL_SEND_ENABLED=0`, Mailpit) | 1. Souscrire à un service SMTP transactionnel sécurisé (ex. Brevo, Resend).<br>2. Renseigner `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` dans `.env`.<br>3. Basculer `EXTERNAL_SEND_ENABLED=1` après validation des listes de diffusion. |
| **H4** | **Partenariats plateformes privées** | Politique éthique « permission d'abord » appliquée | Prendre contact avec les plateformes agricoles partenaires (ex. Tantsah) via le modèle [`docs/outreach/tantsah_outreach.md`](outreach/tantsah_outreach.md). |
| **H5** | **Revue humaine des alias & golden sets** | Étiquetés `human_reviewed=false` | Les analystes du ministère ou de la SPM peuvent se connecter sur `/admin/review` pour approuver formellement les nouveaux alias à confiance < 0,9. |
| **H6** | **Plafond budgétaire LLM & HTTP** | Garde-fous actifs (20 $/mois, 500 req/j) | Ajuster `LLM_MONTHLY_BUDGET_USD` dans `.env` selon les quotas alloués par la direction. |
| **H7** | **Relations institutionnelles** | Courriers officiels rédigés dans `docs/outreach/` | Transmettre par voie hiérarchique les correspondances de partenariat aux institutions :<br>- MiASA / ODR ([`docs/outreach/miasa_odr_outreach.md`](outreach/miasa_odr_outreach.md))<br>- Ministère du Commerce / SPM ([`docs/outreach/mincc_outreach.md`](outreach/mincc_outreach.md))<br>- INSTAT ([`docs/outreach/instat_outreach.md`](outreach/instat_outreach.md)). |

---

## 3. Qualification Terrain & Essai Décisionnel (R5.8)

> **Mention normative loyale (R6.11) :** L'usage institutionnel réel en situation de crise ou de négociation commerciale reste étiqueté `NOT_EVALUATED`.  
> Pour qualifier cet usage en conditions réelles :
> 1. Déployer la stack sur un environnement accessible aux analystes régionaux (DRDA) et régulateurs SPM.
> 2. Dérouler le protocole d'essai humain formalisé dans [`docs/protocols/decision_pilot_protocol.md`](protocols/decision_pilot_protocol.md) avec les 3 profils d'acteurs (Régulateur, Acheteur grossiste, Vulgarisateur agricole).
> 3. Consigner les retours d'expérience pour faire évoluer le statut vers `FIELD_TESTED`.

---

## 4. Runbooks Opérationnels Clés

- **Déploiement en production :** [`docs/runbooks/DEPLOYMENT_RUNBOOK.md`](runbooks/DEPLOYMENT_RUNBOOK.md)
- **Gestion des incidents (panne HTTP, dérive de schéma, budget, forecast, runs) :** [`docs/runbooks/INCIDENT_RUNBOOK.md`](runbooks/INCIDENT_RUNBOOK.md)
- **Sauvegarde et restauration certifiée :** scripts `deploy/backup.sh` et `deploy/restore.sh` (confiné aux clones isolés sous ADR-102).

---

## 5. Dépôt Git & Références

- **Branche principale stable :** `main` (worktree `work/r1-sources-prep`)
- **Tag officiel de clôture :** `mi-v0.2.0-local-qualified`
- **Rapport complet d'acceptation :** [`docs/MARKET_INTELLIGENCE_REPORT.md`](MARKET_INTELLIGENCE_REPORT.md)
- **Rapport d'acceptation MVP historique :** [`docs/MVP_REPORT.md`](MVP_REPORT.md)
