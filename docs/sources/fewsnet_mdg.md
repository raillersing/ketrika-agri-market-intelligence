# fewsnet_mdg : FEWS NET Madagascar Food Security Outlook & Price Watch

> Audit indépendant2026-10-25 : registre `active`, SQL `absent`. Pas de réception live actuelle déduite de la présence du code. Les dates/HTTP/droits/annotations ci-dessous sont des descriptions historiques, non revérifiées par cet audit. Réception à suivre dans [la matrice](../audits/2026-10-25/TASK_CAPABILITY_MATRIX.md) et le [plan correctif](../audits/2026-10-25/CORRECTIVE_EXECUTION_PLAN.md).

- **Propriétaire / licence / attribution :** Famine Early Warning Systems Network (FEWS NET / USAID). Licence : Public Domain / US Government Work. Attribution : « FEWS NET / USAID ».
- **Famille de source (`source_family`) :** `fews_net` (réseau international de surveillance de la sécurité alimentaire).
- **URL vérifiées (date, code HTTP) :**
  - https://fews.net/east-africa/madagascar (2026-10-10, HTTP 200, verified: true).
- **robots.txt :** `User-agent: * Allow: /`
- **CGU & Qualification légale (C1 / R1.1) :** Rapports publics d'alerte précoce et de perspectives alimentaires. `pii_class: none`.
- **Format(s) et structure :** Rapports Food Security Outlook (PDF / JSON / HTML), perspectives de récoltes et analyses de marché (Sud de Madagascar, Grand Sud, zones à déficit vivrier).
- **Cadences distinctes (R1.1) :**
  - Collecte technique (`collection_cadence`) : `monthly`
  - Observation sous-jacente (`observation_cadence`) : `monthly`
  - Publication éditeur (`publication_cadence`) : `monthly`
- **Couverture :** Districts vulnérables du Sud (Androy, Anosy, Atsimo Andrefana) et zones rizicoles majeures.
- **Pièges connus :** Séparation stricte entre situation observée présente et projections de phases d'insécurité alimentaire futures (IPC Phase 1 à 5).
- **Stratégie d'extraction :** Connecteur `FewsnetIpcConnector` (`ketrika.connectors.fewsnet_ipc`).
- **Mapping vers les tables cibles :** `obs.climate_event`, `obs.food_security_outlook`.
