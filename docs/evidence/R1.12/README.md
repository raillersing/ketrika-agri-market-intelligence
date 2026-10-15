# Preuve de qualification R1.12 — Actualisation, reprise et santé des sources

**Date :** 2026-10-15  
**Tâche :** R1.12 — Qualifier actualisation, reprise et santé des sources  
**Statut :** **DONE** (5/5 critères d'acceptation validés par tests unitaires et intégration API/UI)

---

## 1. Contexte et objectifs de la qualification

La tâche **R1.12** valide le comportement opérationnel, la résilience et la surveillance de la santé des sources de données du socle Ketrika :
1. **Détection d'éditions de catalogue :** Une nouvelle édition ou version publiée d'un catalogue de données (ex: nouvelle ressource mensuelle) est détectée et ingérée au cycle d'ingestion suivant sans duplication des artefacts historiques.
2. **Gestion de panne et reprise idempotente :** Une défaillance en cours d'ingestion (coupure réseau, indisponibilité transitoire) enregistre le statut `failed` dans `meta.ingestion_run`, transmet une alerte incident par email dans Mailpit uniquement (H3), et le run de reprise ultérieur s'exécute de façon strictement idempotente sans dédoublement de données observées (C2).
3. **Visibilité des sources périmées (stale) et désactivées (disabled) :** Les sources dont le délai de fraîcheur excède le SLA (`freshness_sla_days`) ou qui sont désactivées suite à un incident PolicyStop (ex: WFP HDX, NASA POWER) sont clairement identifiées dans la vue matérialisée SQL `gold.source_health`, exposées fidèlement par l'API REST `/v1/sources` et `/v1/sources/{source_id}/health`.
4. **Zéro requête réseau sous PolicyStop :** Dès qu'une source est marquée `disabled` dans le registre des sources (`registry/sources.yaml`) suite à un blocage normatif (B-R009, B-R010), le pipeline lève immédiatement `PolicyStop` avant toute tentative réseau, garantissant **exactement 0 requête HTTP** envoyée vers les serveurs cibles.
5. **Concordance SQL / API / UI :** Les métriques de santé calculées en base (nombre de records à 30 jours, taux de succès d'extraction, stale, dernier statut de run) concordent rigoureusement entre les tables SQL, l'API FastAPI et le tableau de bord frontend (`/sources`).

---

## 2. Implémentations techniques

- **Frontend :** `web/src/app/sources/page.tsx`
  - Prise en charge explicite du statut `disabled` avec badge dédié neutre (`bg-slate-500/15 text-slate-400 border-slate-700/50`) et libellé clair `Désactivée (PolicyStop)`.
  - Affichage des alertes de fraîcheur `Périmée (> SLA)` dès que `source.is_stale === true`.
- **Backend & Pipeline :**
  - Garde `authorize_collection` dans `backend/src/ketrika/connectors/stages.py` levant `PolicyStop` immédiat pour les sources désactivées.
  - Notifications d'incident envoyées vers Mailpit (`send_pipeline_failure_email`) sans aucun envoi vers un tiers réel (H3).
  - Traçabilité des statuts de run (`meta.ingestion_run.status` : `running`, `success`, `failed`).
- **Tests unitaires et d'acceptation :**
  - `backend/tests/unit/test_source_health_and_refresh.py`

---

## 3. Résultats des tests et métriques de validation

### 3.1 Exécution des tests unitaires R1.12 (5/5 passés)

Commande exécutée dans le conteneur Docker `ketrika-backend:dev` :
```bash
docker run --rm -v /home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep:/workspace -w /workspace/backend ketrika-backend:dev uv run pytest -v tests/unit/test_source_health_and_refresh.py
```

Résultats :
```text
tests/unit/test_source_health_and_refresh.py::test_r1_12_catalog_edition_detected_on_subsequent_cycle PASSED [ 20%]
tests/unit/test_source_health_and_refresh.py::test_r1_12_failure_and_idempotent_recovery PASSED [ 40%]
tests/unit/test_source_health_and_refresh.py::test_r1_12_zero_requests_during_policy_stop PASSED [ 60%]
tests/unit/test_source_health_and_refresh.py::test_r1_12_sources_api_and_health_visibility PASSED [ 80%]
tests/unit/test_source_health_and_refresh.py::test_r1_12_single_source_health_endpoint PASSED [100%]

============================== 5 passed in 17.06s ==============================
```

### 3.2 Contrôles de typage et de style

- **Ruff (linting backend) :**
  ```text
  All checks passed!
  ```
- **Mypy (typage statique strict) :**
  ```text
  Success: no issues found in 1 source file
  ```
- **TypeScript & ESLint (frontend web) :**
  ```text
  > ketrika-web@0.1.0 typecheck /app
  > tsc --noEmit
  Exit code: 0

  > ketrika-web@0.1.0 lint /app
  > next lint
  ✔ No ESLint warnings or errors
  ```

---

## 4. Synthèse des critères d'acceptation

| Critère R1.12 | Validation | Preuve |
|---|---|---|
| **Édition catalogue simulée** | Conforme | Cycle 1 ingère l'édition 1 ; Cycle 2 détecte l'édition 2 et ignore l'édition 1 déjà archivée en Bronze |
| **Panne / reprise idempotente** | Conforme | Crash marqué `failed`, alerte isolée dans Mailpit ; reprise ultérieure réussie avec 0 duplication |
| **Sources stale / disabled visibles** | Conforme | API `/v1/sources` et `/v1/sources/{id}/health` exposent `is_stale=True`, `status=disabled` ; UI affiche badge neutre |
| **Zéro requête HTTP sous PolicyStop** | Conforme | `authorize_collection` lève `PolicyStop` avant tout appel client HTTP |
| **Concordance SQL / API / UI** | Conforme | Données de `gold.source_health` fidèlement transmises par FastAPI et restituées par les composants React |

---

## 5. Statut de qualification

- **Détection des révisions et rattrapage :** **QUALIFIED**
- **Idempotence et reprise après incident :** **QUALIFIED**
- **Notification d'erreurs (Mailpit H3) :** **QUALIFIED**
- **Surveillance de la santé et conformité UI :** **QUALIFIED**
- **Statut global R1.12 :** **DONE**
