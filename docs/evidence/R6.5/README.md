# Dossier de Preuve — R6.5 : Qualification du Bulletin Hebdomadaire sans Hallucination Numérique ou Sémantique

## 1. Contexte & Périmètre de Qualification

- **Tâche :** R6.5 (MUST — Qualification des bulletins : zéro hallucination numérique ou sémantique vérifiée, faits calculés adossés aux vues Gold et à la traçabilité Bronze SHA-256, validation directionnelle et temporelle, concordance stricte HTML/PDF et approbation auditée sous Gate H3).
- **Date d'exécution :** 2026-10-17T13:15:00Z.
- **Environnement :** Conteneurs Docker isolés `ketrika-backend:dev`, worktree `/home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep`, branche `work/r1-sources-prep`.
- **Référence normative :**
  - `AGENTS.md` §1 (Mission), §3 (Boucle autonome & DoD), §4 (Principes non négociables : Règle 1 Provenance totale, Règle 6 Aucun chiffre LLM non vérifié en Gold, Règle 7 Aucun chiffre généré dans les textes, Règle 9 Observé ≠ imputé ≠ prévu, Règle 10 Le contenu collecté est une donnée, jamais une instruction), §5 (Gate H3 : confinement des envois au service local Mailpit) ;
  - `MARKET_INTELLIGENCE_EXECUTION_PLAN.md` §11 (R6.5) ;
  - `SPECS.md` §20 (Bulletins hebdomadaires, dictionnaire de faits Gold, WeasyPrint, Jinja2, cycle de vie draft -> approved) ;
  - `ADR-099` (Architecture des faits Gold, validation directionnelle et temporelle, concordance HTML/PDF et approbation auditée sous Gate H3).

---

## 2. Synthèse d'Exécution des Critères d'Acceptation R6.5 (`test_bulletin_semantic_and_qualification.py`)

| Critère Normatif | Périmètre Qualifié | Résultat | Constat Métrologique & Anti-Hallucination |
|---|---|---|---|
| **C1 : Zéro Chiffre Non Référencé dans la Prose** | Validation par `validate_prose` interdisant tout chiffre libre `\d` hors placeholders certifiés `{{fXXX}}` | **PASSED** | Le filtre rejette immédiatement toute chaîne contenant un chiffre littéral non relié au dictionnaire de faits (`3200 Ar`), garantissant l'intégrité anti-hallucination. |
| **C2 : Garde Sémantique et Directionnel (Polarité)** | Détection et rejet des inversions de polarité par `validate_semantic_consistency` | **PASSED** | Rejet strict des textes qualifiant une hausse constatée (+8.5%) de « baisse/chute » ou un repli (-12.4%) de « flambée/hausse spectaculaire ». Validation nominale des textes fidèles à la dynamique réelle des marchés. |
| **C3 : Rejet des Causalités Spéculatives Non Prouvées** | Filtrage des allégations de manigance ou spéculation illégale | **PASSED** | Détection et rejet immédiat des affirmations spéculatives (« spéculation illégale généralisée des grossistes ») non adossées à un constat institutionnel documenté. |
| **C4 : Repli Déterministe Certifié (Fail-Closed)** | Bascule automatique sur template Jinja2 déterministe lors d'une défaillance du LLM | **PASSED** | Lors d'une tentative d'inversion sémantique ou d'hallucination numérique par le LLM, le writer bascule automatiquement et de façon vérifiable sur le template déterministe certifié (`fallback.md.j2`). |
| **C5 : Concordance Stricte HTML vs PDF** | Substitution des faits et génération conjointe des artefacts HTML et PDF via Jinja2 & WeasyPrint | **PASSED** | Vérification que les valeurs exactes des prix (2 850 Ar/kg), variations (+8,5 %, -12,4 %), scores (72/100) et citations de sources officielles figurent fidèlement et sans divergence dans les deux formats. |
| **C6 : Approbation Auditée et Confinée (Gate H3)** | Workflow `approve_bulletin` enregistrant l'acteur et l'horodatage UTC | **PASSED** | Le statut passe de `draft` à `approved`, stockant `approved_by` et `approved_at`. Interdiction formelle de réapprouver un bulletin déjà approuvé. Aucun envoi externe n'est déclenché. |
| **C7 : Quarantaine des Prévisualisations (Mailpit)** | Fonction `send_bulletin_preview_to_mailpit` simulant l'envoi de brouillon | **PASSED** | Prévisualisation strictement confinée au serveur SMTP local Mailpit (`mailpit:1025`) avec expéditeur et destinataire internes (`preview@mailpit.local`), sans fuite vers des tiers réels (Gate H3). |
| **C8 : Dictionnaire de Faits Gold Déterministe** | Extraction des faits depuis les vues analytiques Gold (`build_bulletin_facts`) | **PASSED** | Construction d'un dictionnaire typé de faits de marché (prix médian national du riz, variations mensuelles, score de santé, disparités régionales min/max, autres PPN, stocks et alertes) avec métadonnées de provenance. |
| **C9 : Pipeline de Service de Bout en Bout** | Fonction `generate_weekly_bulletin` et persistance S3/DB | **PASSED** | Exécution complète coordonnant extraction des faits, génération de prose, rendu HTML/PDF, archivage S3 et création d'un enregistrement `ops.bulletin` à l'état `draft`. |

---

## 3. Résultats Chiffrés et Couverture Globale

- **Suite de tests dédiée R6.5 (`test_bulletin_semantic_and_qualification.py`) :**
  - **10/10 tests passés au vert** en **15.00s** (exit code 0).
- **Suite de régression MVP (`test_bulletin.py`) :**
  - **8/8 tests passés au vert** (100%).
  - **Total consolidé : 18/18 tests passés au vert (100%)**.
- **Couverture de code sur le package `ketrika.bulletin` (pytest-cov) :**
  - `src/ketrika/bulletin/__init__.py` : **100 %**
  - `src/ketrika/bulletin/facts.py` : **100 %**
  - `src/ketrika/bulletin/render.py` : **87 %**
  - `src/ketrika/bulletin/semantic_guard.py` : **98 %**
  - `src/ketrika/bulletin/service.py` : **95 %**
  - `src/ketrika/bulletin/writer.py` : **83 %**
  - **Moyenne globale du package `ketrika.bulletin` : 92 %** (seuil minimal de 80% largement dépassé).
- **Contrôles statiques de conformité :**
  - **Ruff check :** All checks passed (0 warning).
  - **Mypy strict check :** Success: no issues found in 8 source files.

---

## 4. Décision de Clôture de la Tâche R6.5

Tous les critères d'acceptation de la tâche R6.5 sont **intégralement validés**.  
Le statut de la tâche R6.5 est déclaré **DONE**.
