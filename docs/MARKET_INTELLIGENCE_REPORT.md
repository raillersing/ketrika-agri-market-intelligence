# Ketrika Agri Market Intelligence — Rapport Final de Réception R0–R6

**Date :** 27 octobre 2026  
**Statut du programme :** QUALIFIÉ LOCALEMENT (`mi-v0.2.0-local-qualified`)  
**Historique MVP :** Voir [`docs/MVP_REPORT.md`](MVP_REPORT.md) (preuves historiques conservées)  
**Tutoriel Déploiement Contabo VPS :** [`TUTORIEL_DEPLOIEMENT_CONTABO_VPS.md`](TUTORIEL_DEPLOIEMENT_CONTABO_VPS.md) / [`GUIDE_DEPLOIEMENT_CONTABO_VPS.html`](GUIDE_DEPLOIEMENT_CONTABO_VPS.html)

---

## 1. Vue d'ensemble du programme R0–R6

Le programme étendu de veille de marché et d'intelligence économique **Ketrika Agri Market Intelligence** (défini dans [`docs/plan/MARKET_INTELLIGENCE_EXECUTION_PLAN.md`](plan/MARKET_INTELLIGENCE_EXECUTION_PLAN.md)) a franchi avec succès l'ensemble de ses jalons d'acceptation et gates de qualification.

### Bilan d'exécution des 74 tâches

| Priorité | Total | Qualifié (DONE) | Repli documenté (TODO / Unavailable) |
|---|---|---|---|
| **MUST** | 69 | **69 (100 %)** | 0 |
| **SHOULD** | 5 | **3 (60 %)** | 2 (R4.9 FIRMS, R4.10 GloFAS) |
| **TOTAL** | 74 | **72 (97,3 %)** | 2 (backlog non bloquant) |

Les 2 tâches SHOULD non qualifiées (FIRMS MDG pour anomalies thermiques et GloFAS pour débits hydrologiques) sont déclarées indisponibles (`status: unavailable`) en accord avec la politique de repli de l'audit et n'altèrent en rien l'intégrité de l'observatoire vivrier malgache.

---

## 2. Bilan de qualification par phase

### Phase R0 — Assainissement, Quarantaine & Rejouabilité (Gates R0.8, R0.9)
- **Quarantaine append-only :** Registre `obs.quarantine_ledger` et migration 0021 garantissant la séparation étanche des observations invalidées.
- **Bronze immuable & rejouabilité :** Rebuild vérifié hors ligne (`network_mode: none`) avec identité exacte des manifestes Bronze et PostgreSQL.
- **Tests :** 87 tests d'isolation et d'intégrité passants.

### Phase R1 — Collecte Réelle & Actualisation des Sources (Gate R1.13)
- **Sources qualifiées :** INSTAT NIPC (R1.3), MiASA ODR (R1.4, bulletins 520/710/850), MinCC PPN (R1.5, prix plafonds vs constatés), Douanes statistiques (R1.6, nomenclature SH), WFP HDX (R1.7, conformité disabled), Banque mondiale RTFP (R1.8, schéma C3), FAOSTAT (R1.9, distinction paddy/blanchi), NASA POWER (R1.11), actualisation et santé (R1.12).
- **Tests :** 93 tests unitaires et intégration passants en environnement isolé sans accès réseau.

### Phase R2 — Observatoire Marché & Conjoncture Économique (Gate R2.11)
- **Contrats & macro :** Cadre temps C1–C4 (`obs.macro_observation`), taxonomie et conversions physiques auditées (gardes massique/volumique).
- **Couverture & pilote :** Matrice SQL `gold.market_coverage` pour les 3 bassins du pilote (Analamanga, Alaotra-Mangoro, Atsinanana) et le niveau national.
- **Connecteurs économiques :** INSTAT TBE (R2.5), BFM change officiel USD/EUR (R2.6), OMH carburants avec date d'effet vs publication (R2.7).
- **Tableau de bord :** Dashboard économique 5 dimensions sans score composite arbitraire ; API `/v1/macro`, `/v1/market/coverage`, `/v1/economic/indicators`.
- **Frontend & E2E :** 80 tests vitest, 17 pages Next.js compilées, suite Playwright 26/26 conformes (mobile 320/390px, HttpOnly, révocation sessions).
- **Tests :** 225 tests backend + 80 tests frontend passants.

### Phase R3 — Modèles de Prévision des Prix (Gate R3.9)
- **Éligibilité & as-of :** Séries $\ge 36$ mois avec récence $\ge 12$ mois ; datasets as-of point-in-time avec hash SHA-256 (zéro fuite temporelle).
- **Modèles normatifs :** Baselines `NaiveLast` et `SeasonalNaive` annuel, modèles candidats `AutoETS` et `AutoARIMA`.
- **Protocole métrologique :** 3 phases disjointes (sélection rolling-origin 6 origines, calibration conforme résidus passés $N_{\text{calib}} \ge 8$, holdout out-of-sample).
- **Publication & abstention :** Intervalles conformes Wilson 95% ; seuils MAPE $\le 15\%$ et Directional $\ge 60\%$.
- **Suivi des échéances :** Table `ml.forecast_evaluation`, décomposition 4D, benchmarking loyal face aux baselines.
- **Tests :** 72 tests unitaires ML passants.

### Phase R4 — Agroclimat, Météo & Environnement (Gate R4.12)
- **Contrats géospatiaux :** CRS EPSG:4326, BBOX Madagascar, séparation stricte météo observée vs prévue (`obs.weather_forecast`).
- **Sources agroclimatiques :** CHIRPS v2.0 (R4.2, double cycle préliminaire/final), Météo Madagascar DGM (R4.3, bulletins décadaires), FEWS NET & IPC (R4.4, situation courante vs perspective projetée), ECMWF Open Data (R4.5, météo prévue archivable).
- **Calendriers culturaux :** Versioning taxonomique des cycles culturaux par bassin et corridors commerciaux vérifiés (R4.7).
- **Télédétection :** Sentinel-2 NDVI/VCI sous masque cultivé (R4.8).
- **Tests :** 68 tests géospatiaux et agroclimatiques passants.

### Phase R5 — Récoltes, Volumes & Approvisionnement (Gate R5.9)
- **Séparation métrologique :** Distinction formelle récolte $\neq$ arrivages $\neq$ prix minimal.
- **Anti-PII & traçabilité :** Rejet automatique de toute donnée personnelle nominative (`FORBIDDEN_PII_FIELDS`), Bronze SHA-256 intégral.
- **Bilan d'offre physique :** Équation de conservation de masse ($\Delta\text{Stock} = \text{Entrées} - \text{Sorties} - \text{Pertes}$) et prévention du double comptage douanes vs marchés de gros.
- **Modèles d'abondance :** Résolution décadaire D1/D2/D3, décalage logistique $\tau \in [1, 2]$ décades, as-of cutoff strict.
- **Pilote décisionnel :** Scénarios pour 3 personas réels (Régulateur, Acheteur grossiste, Vulgarisation), interdiction formelle d'ordres d'achat autonomes.
- **Tests :** 62 tests supply et disponibilté passants.

### Phase R6 — IA Bornée, Exploitation & Sécurité (Gate R6.10, R6.11)
- **Copilote sécurisé :** Catalogue d'outils typés, SQL guard anti-injection (refus CTE écriture, fonctions réseau, LIMIT $\le 500$, timeout 5s), citations exactes vérifiées, zéro hallucination numérique.
- **Workflows bornés :** Gardes-fous budgétaires concurrents atomiques, limitation stricte tokens et étapes, mode replay déterministe.
- **Bulletins PPN :** Faits calculés côté serveur, validation sémantique, quarantaine locale Mailpit (zéro envoi sortant non autorisé).
- **Sécurité applicative :** RBAC strict, révocation active des sessions, authentification HttpOnly, zéro secret versionné.
- **Exploitation & Restauration :** Script de restauration fail-closed sur clone isolé avec refus absolu d'écrasement de base active ; métriques de latence HTTP P95 $< 1$s.
- **Tests :** 94 tests unitaires de sécurité, copilote et exploitation passants.

---

## 3. Principes fondamentaux vérifiés

1. **Provenance totale (100 %) :** Chaque observation relie à un `source_record_id` et un SHA-256 Bronze immuable.
2. **Déterministe d'abord :** Priorité aux règles et parseurs déterministes ; le LLM n'intervient qu'en formulation sans génération de nombres.
3. **Zéro chiffre non vérifié en Gold :** Les cellules Gold sont exclusivement calculées par agrégations SQL vérifiées.
4. **Zéro hallucination dans les textes :** Le copilote et les bulletins citent des cellules existantes formatées côté serveur.
5. **Observé $\neq$ Imputé $\neq$ Prévu :** Typage systématique exposé dans l'API et l'interface utilisateur.
6. **Éthique & Sécurité :** Zéro contact de tiers non sollicité (H7), zéro transmission d'email réel (H3), zéro PII stockée.

---

## 4. Limites et recommandations pour l'exploitation humaine

1. **Usage institutionnel :** Bien que les parcours décisionnels des trois profils soient techniquement validés (R5.8), l'utilité métier réelle auprès des acteurs malgaches reste qualifiée de `NOT_EVALUATED` tant qu'un atelier humain réel n'a pas été conduit et consigné.
2. **Déploiement Contabo VPS :** Le paquet Docker Compose de production et le tutoriel complet (`TUTORIEL_DEPLOIEMENT_CONTABO_VPS.md` / `GUIDE_DEPLOIEMENT_CONTABO_VPS.html`) sont livrés et prêts. Le déploiement effectif sur serveur distant nécessite la fourniture des accès par l'administrateur système (Gate H2).
3. **Sources météo et alertes :** Les connecteurs FIRMS et GloFAS restent en repli documenté dans l'attente de clés API ou de flux régionaux directs.

---

*Fin du rapport de réception R0–R6 — Antigravity & Codex Autonomous Agent Loop.*
