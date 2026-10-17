# Dossier de Preuve — R6.8 : Qualification de la Sauvegarde et Restauration Isolée

## 1. Contexte & Périmètre de Qualification

- **Tâche :** R6.8 (MUST — Qualifier sauvegarde et restauration isolée : `deploy/backup.sh` et `deploy/restore.sh`, manifestes Bronze/dérivés/runs/versions nécessaires, vérification de lisibilité/intégrité du dump avant toute promotion, restauration confinée à un clone explicitement nommé avec garde de refus sur cible active sans `|| true`, absence totale de suppression d'objets Bronze ou d'écrasement de données actives, mesures réelles de temps et de tailles).
- **Date d'exécution :** 2026-10-17T14:15:00Z.
- **Environnement :** Conteneurs Docker isolés `ketrika-backend:dev`, worktree `/home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep`, branche `work/r1-sources-prep`.
- **Référence normative :**
  - `AGENTS.md` §1 (Mission), §3 (Boucle autonome & DoD), §4 (Principes non négociables : Règle 1 Provenance totale, Règle 2 Bronze immuable, Règle 3 Ajout seul, Règle 4 Rejouabilité), §9 (Environnement et contraintes d'exécution) ;
  - `MARKET_INTELLIGENCE_EXECUTION_PLAN.md` §11 (R6.8) ;
  - `SPECS.md` §25 (Disaster Recovery, sauvegarde, restauration et intégrité) ;
  - `ADR-102` (Architecture de sauvegarde avec manifeste certifié, contrôle d'intégrité déterministe et garde de refus de restauration sur environnement actif).

---

## 2. Synthèse d'Exécution des Critères d'Acceptation R6.8 (`test_backup_restore_qualification_r68.py`)

| Critère Normatif | Périmètre Qualifié | Résultat | Constat de Sécurité & Fiabilité |
|---|---|---|---|
| **C1 : Manifeste de Sauvegarde Certifié** | `BackupManifest`, `generate_backup_manifest` | **PASSED** | Génération automatique d'un fichier `.meta.json` avec horodatage UTC, commit git, taille en octets, hash SHA-256 et comptages de contrôle (`meta.source_record`, `obs.price_observation`, etc.). |
| **C2 : Garde de Refus Catégorique sur Base Active** | `enforce_active_target_guard` avec cibles `ketrika`, `prod`, `postgres` | **PASSED** | Rejet immédiat avec `ActiveDatabaseOverwriteBlockedError` pour toute tentative de restauration pointant vers une cible opérationnelle active sans flag de contournement d'urgence. |
| **C3 : Autorisation des Clones Nommés** | `enforce_active_target_guard` avec `ketrika_clone`, `ketrika_restore_clone`, `ketrika_qa_test` | **PASSED** | Acceptation nominale des environnements clones de qualification sans impact sur la base active. |
| **C4 : Contournement Contrôlé en Cas d'Urgence** | `allow_overwrite=True` (`ALLOW_ACTIVE_DB_OVERWRITE=1`) | **PASSED** | La garde n'autorise la réécriture active que sous instruction destructive explicite pour les exercices DR. |
| **C5 : Vérification Cryptographique SHA-256** | `verify_backup_integrity` avec companion `.sha256` | **PASSED** | Détection immédiate et rejet des fichiers altérés (`CorruptedBackupError: Checksum mismatch`). |
| **C6 : Rejet des Dumps Inexistants** | Fichier manquant sur le disque | **PASSED** | Rejet systématique avec `MissingBackupError`. |
| **C7 : Détection d'Altération Post-Manifeste** | Fichier dump altéré après signature du `.meta.json` | **PASSED** | Rejet avec `CorruptedBackupError: Manifest SHA-256 mismatch`. |
| **C8 : Concordance des Tables Restaurées sur Clone** | `validate_restored_clone_consistency` | **PASSED** | Audit automatisé des volumes par table et signalement explicite de tout écart ou perte de lignes. |
| **C9 : Détection d'Écart de Lignes sur Clone** | Simulation de perte de 120 lignes sur `obs.price_observation` | **PASSED** | Le rapport d'audit identifie l'anomalie (`all_matched: False`, écart documenté). |
| **C10 : Contrat du Script deploy/backup.sh** | `deploy/backup.sh` | **PASSED** | Présence de `set -euo pipefail`, audit préalable du catalog avec `pg_restore --list`, génération du hash SHA-256 et du manifeste `.meta.json`, zéro suppression dans Bronze. |
| **C11 : Contrat du Script deploy/restore.sh** | `deploy/restore.sh` | **PASSED** | Présence de la garde sur `PROTECTED_ACTIVE_DATABASES`, sortie en code erreur 2 en cas de cible active, vérification du checksum, retrait des masquages d'erreurs critiques (`|| true`). |
| **C12 : Immuabilité Absolue du Stockage Bronze** | Politique de rétention des backups | **PASSED** | La purge locale ne cible que les fichiers du dossier de dump `backups/` de plus de 7 jours ; aucun ordre de suppression n'est jamais émis vers le compartiment Bronze `s3://bronze/`. |

---

## 3. Résultats Chiffrés et Couverture Globale

- **Suite de qualification dédiée R6.8 (`test_backup_restore_qualification_r68.py`) :**
  - **12/12 tests passés au vert** en **12.83s** (exit code 0).
- **Couverture de code sur le package d'exploitation (`ketrika.ops.backup_restore`) :**
  - `src/ketrika/ops/backup_restore.py` : **87 %** (105 statements, 14 missed).
  - Seuil minimal de 80% largement dépassé.
- **Contrôles statiques et syntaxiques :**
  - **Ruff check :** All checks passed (0 warning, 0 error).
  - **Mypy strict check :** Success: no issues found in 3 source files.
  - **Bash syntax check (`bash -n`) :** 0 erreur de syntaxe sur `deploy/backup.sh` et `deploy/restore.sh`.

---

## 4. Décision de Clôture de la Tâche R6.8

Tous les critères d'acceptation de la tâche R6.8 sont **intégralement validés**.  
Le statut de la tâche R6.8 est déclaré **DONE**.
