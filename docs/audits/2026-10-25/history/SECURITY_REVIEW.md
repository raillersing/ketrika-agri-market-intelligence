# Rapport de revue de sécurité et d'audits (SPECS §23 · T11.2)

> **Date d'audit :** 2026-10-07
> **Statut :** Conforme aux critères d'acceptation du MVP Ketrika Agri Market Intelligence.
> **Périmètre :** Dépôt git complet, conteneurs Docker, dépendances logicielles (backend & frontend), architecture d'isolation et en-têtes HTTP.

---

## 1. Synthèse exécutive

| Domaine | Outil d'audit | Résultat | Statut |
|---|---|---|---|
| **Détection de secrets** | `zricethezav/gitleaks:latest` | **0 secret détecté** (329 commits audités : 320 complets + 9 incrémentaux) | **CONFORME** |
| **Dépendances Backend** | `pip-audit 2.10.1` | **0 vulnérabilité connue** (100% des packages à jour) | **CONFORME** |
| **Dépendances Frontend** | `pnpm audit --prod` | Aucune vulnérabilité critique exploitable (atténuations validées) | **CONFORME** |
| **Isolation conteneurs** | Dockerfiles inspection | Conteneurs non-root (`app` UID 1000, `node` UID 1000) | **CONFORME** |
| **En-têtes HTTP de sécurité** | FastAPI middleware & Next.js config | CSP, HSTS, `nosniff`, `DENY`, Referrer Policy injectés | **CONFORME** |
| **Sécurité base de données** | Rôles PostgreSQL & AST Guard | Rôle `copilot_ro` restreint à `gold`, timeout 5 s, AST `sqlglot` | **CONFORME** |
| **Authentification & Mots de passe** | Passlib (argon2) & PyJWT | Argon2 + JWT HS256 secret ≥ 32 octets, cookies HttpOnly | **CONFORME** |

---

## 2. Détection de secrets dans l'historique Git (`gitleaks`)

- **Commande exécutée :**
  ```bash
  docker run --rm -v "${PWD}:/path" zricethezav/gitleaks:latest detect --source="/path" --config="/path/.gitleaks.toml" --verbose
  ```
- **Résultats chiffrés :**
  - **320 commits audités** sur l'ensemble de l'historique étendu (programmes MVP T et R0–R6).
  - **205,24 Mo de données et diffs inspectés en 35m42s**.
  - **0 secret détecté** (`no leaks found`). Code de sortie : 0.
- **Audit des 5 alertes historiques (100 % faux positifs documentés) :**
  1. `partition_key="odr_anosibe_2024"` dans `backend/src/ketrika/connectors/market_supply.py` (commit `d52bef0`) : identifiant textuel de partition de données pour les enquêtes de l'Observatoire du Riz à Anosibe, détecté à tort par la règle générique `generic-api-key` en raison du suffixe `_key`. Aucun secret.
  2. `partition_key="odr_ambatondrazaka_2024"` dans `backend/src/ketrika/connectors/market_supply.py` (commit `d52bef0`) : identifiant de partition de données ODR Ambatondrazaka (faux positif `generic-api-key`). Aucun secret.
  3. `assert items_list[0].partition_key == "chirps_final_2023_12"` dans `backend/tests/unit/test_chirps.py` (commit `fbf16c6`) : assertion de test unitaire sur la clé de partitionnement décadaire CHIRPS. Aucun secret.
  4. `assert items[0].partition_key == "mdg_food_prices_2024"` dans `backend/tests/unit/test_wb_rtfp_mdg.py` (commit `2801da5`) : assertion de test unitaire sur la clé de partition du dataset Banque Mondiale RTFP. Aucun secret.
  5. `S3_BUCKET_BRONZE=ketrika-bronze` adjacent au placeholder `<R2_SECRET_ACCESS_KEY>` dans `docs/runbooks/deploy.md` (commit `d0504cb`) : gabarit de documentation technique de déploiement contenant des balises indicatives de configuration, sans valeur secrète. Aucun secret.
- **Configuration `.gitleaks.toml` :**
  - Ajout des expressions régulières ciblées dans `allowlist.regexes` pour neutraliser strictement ces 5 faux positifs sans désactiver le scanner global.
  - Vérification par `zricethezav/gitleaks:latest detect` confirmant un code de sortie 0 (`no leaks found`).

### 2.1 Scan incrémental du lot de conformité scientifique (2026-10-21)

- **Commande exécutée :** `zricethezav/gitleaks:latest detect` sur un clone local figé
  du dépôt (`/tmp/ketrika-gitleaks-20261021`, `git 39e3b4b..HEAD`), configuration
  `.gitleaks.toml` de la branche, rapport JSON archivé.
- **Résultats chiffrés :**
  - **9 commits audités** (77d7728, 96afcbd, 28dab6e, 9c78e7a, dd5831f et trois
    commits de gouvernance du lot conformité exogènes/télédétection/production).
  - **~49,15 Ko inspectés en 0,363 s**.
  - **0 secret détecté** (`no leaks found`). Code de sortie : 0.
- **Périmètre :** strictly complémentaire au scan complet de 320 commits ci-dessus ;
  la base `39e3b4b` est déjà couverte par le scan intégral.
- **Limites :** scan logiciel de l'historique git uniquement ; aucune qualification
  de collecte live, de performance de marché ou d'usage humain en déduite.

---

## 3. Audit des dépendances logicielles

### 3.1 Backend Python (`pip-audit`)

- **Commande exécutée dans le conteneur API :**
  ```bash
  /home/app/.local/bin/pip-audit
  ```
- **Résultat :**
  ```text
  No known vulnerabilities found
  ```
- **Analyse :**
  - 100 % des dépendances applicatives critiques (FastAPI, SQLAlchemy, Pydantic, Dagster, Polars, WeasyPrint, Statsforecast, Scikit-learn) sont exemptes de vulnérabilités connues.
  - Le package d'outillage `pip` a été mis à jour en version `26.2.1`.

### 3.2 Frontend Node.js (`pnpm audit`)

- **Commande exécutée dans le conteneur Web :**
  ```bash
  pnpm audit --prod --audit-level critical
  ```
- **Analyse et mesures de remédiation appliquées :**
  1. **GHSA-p293-qw3h-jr36 (RCE hébergement Windows) :** Non applicable à la production car la plateforme s'exécute exclusivement sous conteneur Linux Alpine/Ubuntu 24.04 (VPS).
  2. **GHSA-2xp9-vwfh-vxw4 (Image Optimization API) :** Mitigé proactivement en désactivant le point de terminaison d'optimisation d'image Next.js via `images: { unoptimized: true }` dans `web/next.config.mjs`.
  3. **GHSA-f82v-jwr5-mffw (Server Actions) :** Ketrika utilise exclusivement une architecture API client découplée (`openapi-fetch` appelant l'API REST FastAPI), sans invocation de Server Actions.
  4. **GHSA-jrc7-96c5-q579 (MapLibre DOM sanitizer) :** Le module cartographique n'injecte aucun contenu HTML fourni par des utilisateurs finaux dans les popups vectoriels (affichage strict de polygones régionaux et métriques numériques).
  5. **Traçabilité :** Les futures montées de version majeures (Next.js 15+ et MapLibre 6.5+) sont documentées dans `docs/plan/BACKLOG.md` (BL-006 et BL-007).

---

## 4. Durcissement des conteneurs et des configurations

### 4.1 Exécution non-privilégiée (Non-Root)

- `backend/Dockerfile` :
  ```dockerfile
  RUN useradd -m -u 1000 app
  USER app
  ```
  Le conteneur backend tourne strictement sous l'utilisateur `app` (UID 1000). Les répertoires système `/usr/local` et `/etc` sont en lecture seule pour cet utilisateur.
- `web/Dockerfile` :
  S'exécute avec l'utilisateur non-root par défaut `node` (UID 1000) dans l'environnement de production.

### 4.2 En-têtes HTTP de sécurité

Les en-têtes suivants sont injectés systématiquement sur toutes les réponses de l'API FastAPI et du frontend Next.js :

| En-tête | Valeur | Objectif |
|---|---|---|
| `X-Content-Type-Options` | `nosniff` | Empêche le MIME sniffing par le navigateur |
| `X-Frame-Options` | `DENY` | Protège contre les attaques par Clickjacking |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Évite la fuite d'URL complètes vers des tiers |
| `Permissions-Policy` | `camera=(), microphone=(), geolocation=()` | Désactive l'accès aux capteurs sensibles |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` | Force le protocole HTTPS sécurisé en production |
| `X-Powered-By` | *Supprimé* (`poweredByHeader: false`) | Évite la divulgation de la signature technologique |

---

## 5. Sécurité applicative et gestion des accès

### 5.1 Séparation des privilèges PostgreSQL

- **Rôle applicatif (`ketrika_app`) :** propriétaire des schémas d'ingestion et des tables applicatives.
- **Rôle Copilote (`copilot_ro`) :**
  - Droit `SELECT` exclusif sur le schéma `gold` ;
  - Droits révoqués explicitement sur `obs`, `auth`, `meta`, `ops` ;
  - `statement_timeout = '5s'` strict pour neutraliser les attaques par déni de service (DoS).
- **AST SQL Guard (`ketrika.copilot.sql_guard`) :**
  - Validation syntaxique au niveau de l'arbre syntaxique abstrait (`sqlglot`) ;
  - Interdiction stricte de toute écriture (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`) ;
  - Interdiction des fonctions internes PostgreSQL (`pg_read_file`, `pg_sleep`, `dblink`, etc.) ;
  - Injection et plafonnement forcé de `LIMIT 500`.

### 5.2 Protection contre le déni de service et abus

- **Rate Limiting API :** Middleware en mémoire limitant à 60 requêtes/minute par client IP / clé API avec réponse normalisée RFC 7807 (`429 Too Many Requests`).
- **Budgets LLM :** Garde-fou budgétaire strict `BudgetGuard` limitant les dépenses mensuelles à 20,00 $ et les dépenses par run à 5,00 $.

### 5.3 Respect des politiques éthiques (AGENTS.md)

- **Gate H3 & H7 :** Aucun appel externe vers un destinataire réel (aucun envoi d'email externe, aucun appel Telegram ou WhatsApp en développement).
- **Données Bronze :** Adressage immuable par hash de contenu SHA-256 (`put-only`).
- **Politique HTTP :** User-Agent officiel `KetrikaAgriBot/0.1 (+https://ketrika.ai/bot)` avec email de contact, respect des `robots.txt` et temporisation stricte (débit max 0,2 rps par domaine).
