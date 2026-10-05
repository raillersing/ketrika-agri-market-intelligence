# PROGRESS : registre d'exécution du MVP

> **Mémoire unique et persistante de l'agent autonome** (AGENTS.md §3.1).
> Statuts possibles d'une tâche : `TODO` | `IN_PROGRESS` | `DONE` | `BLOCKED`

---

## 1. Tableau de bord des tâches

| ID | Priorité | Phase | Description | Dépendances | Statut | Commit / Preuve |
|---|---|---|---|---|---|---|
| **T0.1** | MUST | 0 | Initialiser le dépôt et la gouvernance | — | **IN_PROGRESS** | — |
| **T0.2** | MUST | 0 | Squelette du monorepo et outillage qualité | T0.1 | TODO | — |
| **T0.3** | MUST | 0 | Stack Docker de développement | T0.2 | TODO | — |
| **T0.4** | SHOULD | 0 | Configuration CI locale/GitHub Actions | T0.3 | TODO | — |
| **T1.1** | MUST | 1 | Reconnaissance des sources et registre | T0.3 | TODO | — |
| **T1.2** | MUST | 1 | Taxonomie produits et alias | T1.1 | TODO | — |
| **T1.3** | MUST | 1 | Unités et conversions | T1.1 | TODO | — |
| **T1.4** | MUST | 1 | Géographie de référence | T1.1 | TODO | — |
| **T2.1** | MUST | 2 | Migrations de base de données (Alembic) | T0.3 | TODO | — |
| **T2.2** | MUST | 2 | Bibliothèque ketrika.core | T2.1 | TODO | — |
| **T2.3** | MUST | 2 | Framework Connector et factory Dagster | T2.2 | TODO | — |
| **T2.4** | MUST | 2 | Bibliothèque d'extraction (PDF, HTML, LLM) | T2.2 | TODO | — |
| **T2.5** | MUST | 2 | Normalisation et chargement | T2.3, T1.2–T1.4 | TODO | — |
| **T2.6** | MUST | 2 | Commande rebuild et runbook connecteur | T2.3–T2.5 | TODO | — |
| **T3.1** | MUST | 3 | Connecteur WFP Food Prices HDX | T2.6 | TODO | — |
| **T3.2** | MUST | 3 | Connecteur Banque Mondiale RTFP | T2.6 | TODO | — |
| **T3.3** | MUST | 3 | Connecteur FAOSTAT | T2.6 | TODO | — |
| **T3.4** | MUST | 3 | Connecteur NASA POWER Climat | T2.6, T1.4 | TODO | — |
| **T3.5** | MUST | 3 | Connecteur INSTAT NIPC | T2.6 | TODO | — |
| **T4.1** | MUST | 4 | Connecteur MiASA ODR (Bulletins Riz) | T2.6 | TODO | — |
| **T4.2** | MUST | 4 | Connecteur MinCC Prix & Stocks PPN | T2.6 | TODO | — |
| **T4.3** | MUST | 4 | Connecteur Douanes Statistiques | T2.6 | TODO | — |
| **T4.4** | COULD | 4 | Connecteur Événements (PICM, FEWS NET) | T2.6 | TODO | — |
| **T5.1** | MUST | 5 | Vues matérialisées Gold | T3.1–T3.5, T4.1–T4.3 | TODO | — |
| **T5.2** | MUST | 5 | Indicateurs et KPI Gold | T5.1 | TODO | — |
| **T5.3** | MUST | 5 | Cockpit Data Quality (DQ) | T5.1 | TODO | — |
| **T6.1** | MUST | 6 | API FastAPI /v1 | T5.2 | TODO | — |
| **T6.2** | MUST | 6 | Tests de charge et robustesse API | T6.1 | TODO | — |
| **T7.1** | MUST | 7 | Fondations frontend Next.js | T6.1 | TODO | — |
| **T7.2** | MUST | 7 | Pages et vues analytiques web | T7.1 | TODO | — |
| **T7.3** | MUST | 7 | Tests e2e web (Playwright) | T7.2 | TODO | — |
| **T8.1** | MUST | 8 | Moteur d'alertes | T5.2 | TODO | — |
| **T8.2** | MUST | 8 | Générateur de bulletin hebdomadaire PPN | T5.2, T6.1 | TODO | — |
| **T9.1** | MUST | 9 | Modèles de prévision de prix | T5.1 | TODO | — |
| **T9.2** | MUST | 9 | Intégration des anomalies dans les alertes | T9.1, T8.1 | TODO | — |
| **T9.3** | SHOULD | 9 | Connecteur CHIRPS v3 | T5.1, T1.4 | TODO | — |
| **T10.1** | MUST | 10 | Copilote analyste SQL sécurisé | T6.1, T5.2 | TODO | — |
| **T11.1** | MUST | 11 | Observabilité et supervision | Phases 8–10 | TODO | — |
| **T11.2** | MUST | 11 | Revue de sécurité et audits | T11.1 | TODO | — |
| **T11.3** | MUST | 11 | Procédures de sauvegarde et restauration | T11.1 | TODO | — |
| **T11.4** | MUST | 11 | Paquet de déploiement VPS | T11.2 | TODO | — |
| **T11.5** | MUST | 11 | Documentation finale et runbooks | T11.4 | TODO | — |
| **T11.6** | MUST | 11 | Test d'acceptation final du MVP | T11.1–T11.5 | TODO | — |

---

## 2. Journal d'exécution

### [2026-10-05T20:55:00Z] Démarrage de T0.1 : Initialiser le dépôt et la gouvernance
- **Mini-plan T0.1 :**
  1. Vérifier prérequis environnement (git, docker, uv).
  2. Initialiser git repository sur la branche `main`.
  3. Configurer `.gitignore`, `.gitattributes`, `.editorconfig`.
  4. Créer les dossiers de gouvernance et `README.md` minimal.
  5. Vérifier les critères d'acceptation T0.1 et committer `chore(T0.1): bootstrap repository`.
