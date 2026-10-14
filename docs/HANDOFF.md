# HANDOFF : Guide de passation et actions humaines attendues

> **Statut :** Document normatif de passation du MVP Ketrika Agri Market Intelligence (AGENTS.md §3.2 & §5.3).
> Ce document récapitule l'état de livraison du MVP, les pré-requis humains pour la phase d'exploitation, ainsi que les gates d'autorité (H1 à H7) nécessitant une intervention humaine.

## État courant du programme autorisé R0–R6 — 2026-10-14

Lot B2 reçu et intégré atomiquement main 03e5750 : Windows 48496 FINAL 0
sur code 9d2076b, 1396 backend/35 frontend/build, manifest R0.6 inclus
59 fichiers/732 cas/108 intégrations. Identité prix v2, pont historique prudent
et revues/counters/reçus raccordés ; BL-016 RESOLVED_FIXED. Source-cell
complémentaire 2/2 sur deux véritables objets Bronze QA, ancienne clé/preuve/
valeur préservées. Aucune reclassification/backfill ni migration active.
Rapports originaux et LOT_B2_RECEPTION.md/json dans docs/evidence/R0.6.

Reprise C explicitement autorisée par l'utilisateur : worktree coordinateur
work/r06-http-takeover-20261014, base a573f90. Antigravity 186ab4a/cinq dirty
préservés dans docs/evidence/R0.6/antigravity_snapshot, sans mutation.
ADR-063/SPECS et migration QA 0010 précèdent le nouveau garde SQL atomique,
arrêt durable, HTTP/robots/redirect/retry et binding collecte. C reçu et intégré
main 173c41a : Windows 80378 FINAL 0/1462 backend/35 web/build, inclusion
63 fichiers/805 cas/118 intégrations, vingt fichiers exacts. Originaux dans
LOT_C_RECEPTION.md/json ; aucun transfert de l'ancien commit non qualifié.
R0.6 DONE logiciel ; R0.7 désormais éligible, programme R non terminé.
Ne pas relancer les checks reçus après seules clôtures documentaires.
Les 482 références/764 prix/674 versions Bronze actifs sont inchangés,
schéma actif 0002. Migration active non autorisée/exécutée : le nouveau garde
SQL refuse toute acquisition tant que ses tables manquent ; le déploiement
requiert migration contrôlée séparée. Pas de tag final ni qualification
live/modèle/usage humain.

Méthode révisée à la demande utilisateur le 2026-10-13 : AGENTS §3.3 et
EXECUTION_METHOD.md/ADR-057 prévalent pour organiser les prochaines réalisations.
Ne pas relancer le check de base à chaque « continues » ; auditer les preuves,
développer un résultat fonctionnel complet puis recevoir ce lot. La préparation
ADR-056 rejoint le lot résilience native, pas une réception isolée automatique.
Tous critères produit/gates/couvertures conservés. `qa-profile` mesure les
rapports existants en lecture seule ; aucune nouvelle qualification délivrée.

Les sections MVP ci-dessous décrivent la livraison historique T. Elles ne
constituent pas une qualification actuelle des sources, des modèles, du
déploiement ou d'un usage humain. Le programme R n'est pas terminé :
R0.1–R0.5 sont DONE ; R0.6 reste IN_PROGRESS et R0.7–R6.11 restent TODO.

Lot B1 reçu main 97f8eb8 le 2026-10-13 : f7b3b32/Windows 76875 FINAL 0,
1348 backend/35 frontend/build ; inclusion R0.6 57 fichiers/684 cas/90
intégrations vérifiée. Publication directe Gold contrôle aussi la structure
sur candidats exacts sous verrous ; registre source/parseur/MIME commun avec
Dagster. Défaut public vide : aucun format réel qualifié par ces fixtures.
Les reçus structure suivent la transaction caller, pas une persistance après
rollback. HTTP/budget Antigravity non reçus ; B2/BL-016 clos le 2026-10-14 (ci-dessus).
SQL/S3 actifs préservés ; schéma actif 0002, migrations nouvelles QA seulement.
Ne pas revendiquer de déploiement ou de performance de marché validée.

Mise à jour 2026-10-13 : lot A intégré ddb848f (reprise native, reçus immuables,
partitions document/version et jobs de rejeu). Check Windows 27517 FINAL 0 :
1321 backend, 35 frontend et build verts ; inclusion R0.6 vérifiée 657/80.
Publication sûre (lot B) et HTTP Antigravity (lot C) restent à recevoir.
Migrations 0007–0009 appliquées uniquement en QA ; base active toujours 0002,
482 références, 764 prix et 674 versions Bronze inchangés. Ne pas confondre
cette réception logicielle avec une migration active ou une qualification live.
PROGRESS.md est canonique ; le plan R en est le miroir.

Dernier incrément reçu : b139c90 (registre Bronze ADR-055, QA 591/60,
check Windows complet 3975 code final 0/1236 backend/35 web/build ;
gouvernance/snapshot/préservation/scan verts). R0.6 n'est pas terminée.
Ce snapshot ne qualifie pas la provenance institutionnelle des référentiels ;
Le snapshot est consommé par les prix du batch Silver dans la transaction
verrouillée ; les appelants historiques sans contexte ne revendiquent pas cette preuve.
Ledger, partitions/reprise,
robots automatique et garde structurelle SQL directe restent requis.

Incrément 13 ADR-055 reçu et committé : registre SQL immuable des
lots Bronze/header/membres et persistance native avant commit. QA Windows
75087 FINAL 0/591 tests/60 intégrations/243,13 s, originaux archivés ; relecture
81743 FINAL 0/huit runs exacts/six lots et six GET SHA/deux pannes Bronze sans
lot. Check Windows intégral 3975 FINAL 0, origine/snapshot/préservation/
gouvernance/diff/scan verts ; commit b139c90d0ccbebbd9c9af3f717b908d82191ff25.
Ne pas considérer la migration QA 0006 ou ces sous-ensembles comme tâche DONE,
reprise automatique, partition ou qualification de source. Préparation ADR-056
uniquement dans worktree r06-ledger-20261013 : cinq unités supplémentaires,
44 unités/10,99 s/types verts, aucun transfert principal ni SQL concurrent.

Après fin du check principal, trois SQL/S3 préparatoires ADR-056 reçus dans
ce worktree : 30934 FINAL 0/20,35 s/refus avant parse, aucun transfert principal.
Adopter les contrats puis reprendre la réception principale QA 599/63 et
check complet avant de revendiquer la consommation du registre par Silver.

Attention à la séparation runtime : la base active reste au head historique
0002_gold_views (lecture readonly b5df39), tandis que seule la qualification
est migrée vers 0006_ingestion_batch. API active en --reload/bind et daemon
Dagster n'ont pas été arrêtés ni leur base migrée. La réception isolée ne
constitue donc pas une qualification des routes ou workflows de cette stack
active ; ne pas y exécuter migration/rebuild/restore de test.

Les gates H1–H7 d'AGENTS.md prévalent : replay/local QA, aucune collecte
privée, aucune émission réelle, aucun contact de tiers ou provisionnement
effectué par l'agent. Les actions d'exploitation ci-dessous sont historiques,
réservées à une décision humaine ; elles ne sont pas une autorisation nouvelle.

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
