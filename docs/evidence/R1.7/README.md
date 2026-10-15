# Preuve de qualification R1.7 — WFP / HDX sous politique stricte

**Date :** 2026-10-15  
**Tâche :** R1.7 — Qualifier WFP/HDX sous politique stricte  
**Statut opérationnel :** Connecteur qualifié (règles & parsing offline). Collecte live : **BLOCKED** (B-R009).  

---

## 1. Contexte et objectifs

WFP HDX (`wfp_hdx_mdg`) est le jeu de données historique de suivi des prix alimentaires du PAM pour Madagascar hébergé sur Humanitarian Data Exchange.
Lors de l'audit R0.4 (2026-10-09), l'accès direct aux endpoints HDX a rencontré des codes HTTP 403 (Cloudflare Bot Management), consigné sous l'incident B-R009.
Conformément aux règles AGENTS §8.1 et §6 :
- Tout contournement de CAPTCHA ou de protection anti-bot est strictement interdit.
- La source a été marquée `status: disabled` dans `registry/sources.yaml`.
- La tâche R1.7 qualifie le connecteur sous politique stricte (gestion offline, rejouabilité Bronze, conformité aux contrats de données), tout en actant que la collecte live est formellement **BLOCKED** sans contournement.

---

## 2. Règles strictes implémentées dans le connecteur

Le connecteur `WfpHdxMdgConnector` (`backend/src/ketrika/connectors/wfp_hdx_mdg.py`, version 1.1.0) applique les garde-fous suivants :

1. **Garde-fou réseau absolu (`fetch`) :**
   - Si la source est marquée `status: disabled` dans `registry/sources.yaml` et qu'une requête réseau directe est tentée (hors mode `offline=True`), une exception `PolicyStop` est immédiatement levée.
   - Aucun appel réseau non autorisé n'est émis.

2. **Parsing HXL robuste :**
   - Détection et élimination déterministe des lignes commençant par `#` (ligne de tags HXL `#date, #adm1+name...`).
   - Aucune création de faux enregistrement ni plantage.

3. **Dérivation du niveau d'acteur (`actor_level`) :**
   - `Retail` -> `"retail"`
   - `Wholesale` -> `"wholesale"`

4. **Distinction stricte `observed` vs `imputed` :**
   - `priceflag` contenant `"actual"` -> `observed_or_imputed="observed"`, `confidence=1.0`.
   - `priceflag` contenant `"forecast"`, `"imputed"` ou `"estimated"` -> `observed_or_imputed="imputed"`, `confidence=0.8`.

5. **Résolution des marchés et refus d'imputation aveugle :**
   - Si le champ `market` est manquant ou ambigu, le connecteur n'invente **aucun P-code** et n'assigne **jamais arbitrairement le marché à la région parente** (`admin1`).
   - Il émet une anomalie documentée dans `issues` : `kind="unresolved_market_needs_review"`.

6. **Conservation intégrale du brut :**
   - Les champs `product_raw`, `location_raw`, `price_raw`, `unit_raw` (ex. `"KG"`, `"L"`), et `currency_raw` sont préservés exactement tels qu'émis dans la source.

---

## 3. Résultats des tests et métriques de validation

Tests exécutés dans le conteneur Docker `ketrika-backend:dev` :

```bash
docker run --rm -v /home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep:/workspace -w /workspace/backend ketrika-backend:dev uv run pytest -v tests/unit/test_wfp_hdx_mdg.py
```

### Résultats d'exécution :
- `test_wfp_hdx_parse_fixture` : **PASSED** (36 enregistrements parsés, 33 retail, 3 wholesale, prix riz/maïs/manioc/haricot/huile/sucre).
- `test_wfp_hdx_golden_test` : **PASSED** (Golden set 36 enregistrements, 252 champs comparés, Exactitude = 100 %, Rappel = 100 %).
- `test_wfp_policy_stop_on_disabled_live_network` : **PASSED** (levée de `PolicyStop` dès qu'un fetch live est tenté sur source disabled).
- `test_wfp_unresolved_market_never_assigned_to_default_region` : **PASSED** (émission de `unresolved_market_needs_review`, 0 PriceRecord avec fallback région).
- `test_wfp_priceflag_distinguishes_observed_vs_imputed` : **PASSED** (`priceflag=forecast` -> `imputed` avec confiance 0.8).
- `test_wfp_fetch_offline_into_bronze` : **PASSED** (stockage de la fixture dans BronzeStore en mode offline).

### Couverture du code :
- Fichier : `backend/src/ketrika/connectors/wfp_hdx_mdg.py`
- Statements : 97
- Miss : 12
- **Couverture : 88 %** (seuil exigé : >= 80 %).

---

## 4. Statut de qualification

- **Connecteur (code & parsing) :** `QUALIFIED`
- **Collecte live :** `BLOCKED` (B-R009 — HTTP 403 persistant Cloudflare sur HDX, sans contournement possible sous AGENTS §8.1).
- **Prochaine étape du plan :** Poursuite avec la tâche éligible suivante : **R1.8 — Qualifier Banque mondiale RTFP**.
