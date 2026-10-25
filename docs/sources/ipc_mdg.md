# ipc_mdg : Cadre Intégré de Classification de la Sécurité Alimentaire (IPC Madagascar)

> Audit indépendant2026-10-25 : registre `active`, SQL `absent`. Pas de réception live actuelle déduite de la présence du code. Les dates/HTTP/droits/annotations ci-dessous sont des descriptions historiques, non revérifiées par cet audit. Réception à suivre dans [la matrice](../audits/2026-10-25/TASK_CAPABILITY_MATRIX.md) et le [plan correctif](../audits/2026-10-25/CORRECTIVE_EXECUTION_PLAN.md).

- **Propriétaire / licence / attribution :** IPC Global Partnership / Comité National IPC Madagascar (FAO, PAM, Gouvernement de Madagascar). Attribution : « Cadre Intégré de Classification de la Sécurité Alimentaire (IPC) Madagascar ».
- **Famille de source (`source_family`) :** `un_agencies` (partenariat multilatéral ONU / Gouvernement).
- **URL vérifiées (date, code HTTP) :**
  - https://www.ipcinfo.org/ipc-country-analysis/details-map/fr/c/1156820/ (2026-10-10, HTTP 200, verified: true).
- **robots.txt :** `User-agent: * Allow: /`
- **CGU & Qualification légale (C1 / R1.1) :** Données ouvertes et consensuelles d'intérêt humanitaire et de planification agricole. `pii_class: none`.
- **Format(s) et structure :** Données tabulaires JSON et synthèses cartographiques par district : phase IPC courante, phase projetée, pourcentages et populations en insécurité aiguë.
- **Cadences distinctes (R1.1) :**
  - Collecte technique (`collection_cadence`) : `quarterly`
  - Observation sous-jacente (`observation_cadence`) : `quarterly`
  - Publication éditeur (`publication_cadence`) : `quarterly`
- **Couverture :** Districts ruraux de Madagascar (notamment régions du Sud et de l'Est).
- **Pièges connus :** Ne jamais mélanger phase observée courante et phase projetée à 3 ou 6 mois ; étanchéité absolue des périodes.
- **Stratégie d'extraction :** Connecteur `FewsnetIpcConnector` (`ketrika.connectors.fewsnet_ipc`).
- **Mapping vers les tables cibles :** `obs.climate_event`, `obs.ipc_phase_summary`.
