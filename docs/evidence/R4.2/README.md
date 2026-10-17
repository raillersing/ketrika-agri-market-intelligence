# Dossier de Preuve — R4.2 : Qualification de CHIRPS et de ses versions

## 1. Contexte & Périmètre

- **Tâche :** R4.2 (MUST) — Qualifier CHIRPS et ses versions, double cycle préliminaire/final, nodata vs 0 mm, découpage raster Madagascar.
- **Date d'exécution :** 2026-10-16T21:00:00Z.
- **Environnement :** Conteneur Docker `ketrika-backend:dev`, worktree `/home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep`, branche `work/r1-sources-prep`.
- **Référence normative :** `AGENTS.md` §1, §4 (règles 1, 3, 8, 9), §10 ; `MARKET_INTELLIGENCE_EXECUTION_PLAN.md` §9 (R4.2) ; `SPECS.md` §26 ; `ADR-080`, `ADR-081`.

---

## 2. Principes Métrologiques & Garanties Scientifiques (ADR-081)

1. **Double cycle fournisseur sans écrasement destructif (C2/C4) :**
   - Version préliminaire (`stage='preliminary'`, ex: `chirps-v2.0.prelim`) disponible 2 à 5 jours après fin de mois pour réactivité opérationnelle.
   - Version définitive (`stage='final'`, ex: `chirps-v2.0.final`) disponible vers le 15 du mois suivant après assimilation des stations pluviométriques au sol.
   - L'arrivée de la version finale ne supprime ni n'écrase la version préliminaire : elle l'archive avec `superseded_by` pointant vers la définitive, garantissant l'auditabilité des séries as-of et le principe d'Append-only.
2. **Distinction physique stricte pluie nulle ($0{,}0\text{ mm}$) vs Nodata ($-9999{,}0$) :**
   - En zone aride ou lors de la saison sèche (ex: Toliara ou Androy dans le Grand Sud), une précipitation de $0{,}0\text{ mm}$ est une observation climatologique avérée (sécheresse). Elle est scrupuleusement préservée et entre dans le calcul de la moyenne.
   - La valeur sentinelle $-9999{,}0$ (pixels hors masque maritime ou sans acquisition satellitaire) est filtrée et exclue des moyennes zonales, évitant toute corruption des indicateurs pluviométriques.
3. **Plafond budgétaire de stockage Bronze raster :**
   - Vérification stricte du plafond de $50\text{ Mo}$ (`MAX_RASTER_FILE_SIZE_BYTES`). Tout flux dépassant cette limite lève immédiatement une exception `PolicyStop`.
   - Sous-ensemble optimisé Afrique (`africa_monthly`) privilégié par défaut (10x plus léger que la grille mondiale).
4. **Découpage spatial sur Madagascar :**
   - Découpage borné sur la BBOX Madagascar `[43.0, -25.8, 50.8, -11.8]`.
   - Agrégation zonale (`zonal_mean`) par région (`admin1`) et district (`admin2`) avec calcul du `coverage_ratio`.

---

## 3. Résultats des Tests & Couverture de Code (`test_chirps.py`)

- **Commande exécutée :**
  `docker run --rm -v /home/.../r1-sources-prep:/workspace -w /workspace/backend ketrika-backend:dev uv run pytest -v tests/unit/test_chirps.py --cov=ketrika.connectors.chirps --cov-report=term-missing`
- **Résultats :** 7/7 tests passés en 16.52s (exit code 0).
  - `test_chirps_connector_discovery` : PASSED
  - `test_chirps_parse_preliminary_and_final` : PASSED
  - `test_strict_distinction_zero_rain_vs_nodata` : PASSED
  - `test_raster_budget_limit_enforcement` : PASSED
  - `test_double_version_supersession_c2_c4` : PASSED
  - `test_chirps_gzip_compressed_payload_and_binary_fallback` : PASSED
  - `test_chirps_discover_overrides_and_list_stages` : PASSED
- **Couverture de code `ketrika.connectors.chirps` :** **85 %** (exigence $\ge 80\%$).
- **Contrôles statiques :**
  - Ruff : All checks passed! 0 warning, formaté.
  - Mypy strict : Success: no issues found in 4 source files.

---

## 4. Conclusion

La tâche R4.2 est **entièrement qualifiée et validée (DONE)**.
Le connecteur CHIRPS v2.0 est opérationnel, garantissant le double cycle temporel préliminaire/définitif et la véracité métrologique des précipitations.
