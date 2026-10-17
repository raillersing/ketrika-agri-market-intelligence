# Qualification Evidence — R2.11 : Gate de l'Observatoire Décisionnel (Phase R2)

## 1. Contexte et Objectifs du Gate

Le **Gate R2.11** clôture la **Phase R2 (« Qualité et observatoire marché/économie »)** du programme Ketrika Market Intelligence.
Conformément aux directives de `docs/plan/MARKET_INTELLIGENCE_EXECUTION_PLAN.md`, ce gate valide :
1. La formulation et la vérification mécanique d'au moins **5 questions décisionnelles calculables** sur le pilote rizicole (R2.4).
2. L'absence de chiffres inventés ou de scores composites globaux artificiels (ADR-070).
3. Le maintien strict du statut `unavailable` ou des codes de raison standardisés pour toute donnée absente.
4. L'adéquation des interfaces de restitution (API REST paginée, export CSV, UI Next.js `/economy` et `/prices`).
5. La conformité de la chaîne de qualification (149 tests backend passants, 39 tests vitest passants, couverture > 80 %, linters et typage stricts).

---

## 2. Vérification des 5 Questions Décisionnelles du Pilote Rizicole

Chaque question a été formellement formalisée, exécutée et validée par la suite de tests `backend/tests/unit/test_gate_r2_decision_observatory.py` :

### Question Q1 — Prix vivrier et dispersion géographique
- **Question :** Quel est le prix médian observé du riz blanc local (`RICE_WHITE_LOCAL`) au détail (`retail`) dans la région Analamanga (`MDG11`) pour la période de référence du pilote (2024-01-01), quelle est sa fourchette, et quel est son statut de qualification ?
- **Réponse calculée :**
  - Prix médian : **3 000 Ar/kg**
  - Fourchette min-max : **[2 900 Ar/kg ; 3 100 Ar/kg]** (dispersion 200 Ar/kg)
  - Statut : **observé** (`observed_or_imputed: "observed"`, `imputed_share: 0.0`)
  - Source primaire : `miasa_odr` (famille `madagascar_gov`)
- **Preuve :** `test_gate_q1_rice_retail_price_analamanga` (PASSED).

### Question Q2 — Audit des lacunes et continuité calendaire de la série
- **Question :** Quelle est la complétude calendaire de la série de prix du riz blanc local à Analamanga sur les 36 mois d'évaluation, quels sont les mois manquants, et la série est-elle candidate au pilote ML ?
- **Réponse calculée :**
  - Mois attendus : **36 mois**
  - Mois observés : **34 mois** (complétude : **94,4 %**)
  - Mois manquants recensés : **2 mois** (`2022-04-01`, `2023-08-01`)
  - Éligibilité ML : **Candidat Pilote** (`is_pilot_candidate: true`)
  - Familles de sources : `madagascar_gov`, `world_bank`
- **Preuve :** `test_gate_q2_series_continuity_and_gap_audit` (PASSED).

### Question Q3 — Contexte monétaire et taux de change officiel BFM
- **Question :** Quel est le cours moyen pondéré MID du dollar américain (USD/MGA) et de l'euro (EUR/MGA) publié par la Banky Foiben'i Madagasikara (BFM) au 18 mai 2026, et la réciprocité mathématique inverse est-elle certifiée ?
- **Réponse calculée :**
  - USD/MGA MID : **4 550,0 MGA/USD**
  - EUR/MGA MID : **4 920,0 MGA/EUR**
  - Parité inverse : vérifiée ($\text{rate} \times \text{inverse} = 1.0$)
  - Traçabilité C3 : source `bfm_public`, institution primaire Banky Foiben'i Madagasikara
- **Preuve :** `test_gate_q3_bfm_monetary_exchange_rates` (PASSED).

### Question Q4 — Énergie OMH et statut de prix administré
- **Question :** Quel est le prix plafond réglementé à la pompe pour le Gazole arrêté par l'Office Malgache des Hydrocarbures (OMH), quelle est la séparation entre date d'effet juridique et date de publication, et quel est son statut réglementaire ?
- **Réponse calculée :**
  - Prix plafond : **4 900 Ar/L**
  - Statut réglementaire : **Prix administré** (`is_administered: true`, `rate_type: "ceiling"`)
  - Date d'effet juridique : **2026-06-01** (`period_start`)
  - Date de publication du communiqué : **2026-05-30** (`published_at`)
  - Règle de non-inférence : aucune rupture d'approvisionnement déduite du prix plafond seul
- **Preuve :** `test_gate_q4_omh_fuel_ceiling_and_regulatory_dates` (PASSED).

### Question Q5 — Coût unitaire d'importation CAF et transmission de marge
- **Question :** Quel est le coût unitaire CAF d'importation du riz calculé depuis les déclarations douanières (MGA/kg), comment s'articule-t-il avec le prix de détail local, et quel est le taux de dépendance aux importations de la période ?
- **Réponse calculée :**
  - Valeur CAF déclarée : 52 000 000 000 MGA pour 20 000 tonnes nettes
  - Coût unitaire CAF : **2 600,00 MGA/kg**
  - Marge brute de transmission locale (prix détail 3 000 Ar/kg - coût CAF) : **+400,00 MGA/kg**
  - Taux de dépendance aux importations : **25,0 %** (20 000 t importées / 80 000 t disponibles)
  - Gardes physiques : validation stricte de l'alignement temporel et rejet si unités incompatibles
- **Preuve :** `test_gate_q5_customs_import_cif_cost_and_transmission` (PASSED).

---

## 3. Synthèse des Contrôles de Fin de Phase

| Domaine | Contrôle | Résultat | Statut |
|---|---|---|---|
| **Backend Tests** | `uv run pytest -v tests/unit/...` | 149/149 tests passés en 50.10s | **SUCCESS** |
| **Couverture R2** | `pytest --cov=ketrika.gold.economic --cov=ketrika.api.routers.economic` | 96 % de couverture (191/199 statements) | **SUCCESS** (seuil $\ge 80\%$) |
| **Linters & Types Backend** | `ruff check` + `mypy strict` | 0 avertissement, 0 erreur | **SUCCESS** |
| **Frontend Tests** | `npm run test` (Vitest) | 39/39 tests passés en 5 fichiers | **SUCCESS** |
| **Frontend Typage & Lint** | `npm run typecheck` + `npm run lint` | 0 erreur TypeScript, 0 warning ESLint | **SUCCESS** |
| **Frontend Build** | `npm run build` (Next.js) | 16/16 pages compilées avec succès | **SUCCESS** |
| **Mobile & Accessibilité** | Viewport mobile 390px + WCAG AA | Validé dans `scripts/qa-e2e.py` | **SUCCESS** |
| **Intégrité Conceptuelle** | Séparation des 5 dimensions | Zéro score global composite inventé | **SUCCESS** |

---

## 4. Décision de Clôture du Gate R2

Toutes les 11 tâches de la Phase R2 (**R2.1 à R2.11**) sont `DONE`.
Le Gate R2 est **ACCEPTÉ et QUALIFIÉ**.
Le tag de version intermédiaire prévu par la constitution `AGENTS.md` §7 est : **`mi-r2-qualified`**.
