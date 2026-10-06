# miasa_odr : MiASA Observatoire du Riz (ODR) – Bulletins Périodiques

- **Propriétaire / licence / attribution :** Ministère de l'Agriculture et de l'Élevage (MiASA) / Observatoire du Riz (ODR). Licence : Données publiques officielles gouvernementales. Attribution : "Observatoire du Riz (ODR), Madagascar".
- **URL vérifiées (date, code HTTP) :**
  - http://www.agriculture.gov.mg (2026-10-06, HTTP 200).
- **robots.txt (extrait pertinent, date) :** `User-agent: * Allow: /`
- **CGU (URL, sha256, résumé des clauses de réutilisation) :** Données ouvertes d'intérêt public agricole pour le suivi de la sécurité alimentaire.
- **Format(s) et structure (avec exemples réels, pages, colonnes) :** Bulletins hebdomadaires et mensuels au format PDF (2 à 4 pages). Tableaux récapitulatifs par région/district pour : Paddy, Riz blanc local (vary gasy, makalioka, tsipala), Riz importé (riz blanc 25% brisures). Prix au kg en Ariary (MGA), variations hebdomadaires en %.
- **Cadence constatée (dates des 6 dernières publications) :** Hebdomadaire (avec interruptions lors des vacances ou remaniements administratifs).
- **Couverture :** Ensemble des 23 régions de Madagascar, marchés producteurs et marchés consommateurs.
- **Pièges connus :** PDF scannés ou semi-vectorisés selon les époques, variation des dénominations de variétés de riz, tableaux multi-colonnes avec fusions.
- **Stratégie d'extraction :** Dual : parseur déterministe `pdfplumber` prioritaire avec extraction tabulaire ; repli LLM multimodal avec preuve textuelle et coordonnées de page pour les éditions complexes.
- **Mapping vers les tables cibles :** `obs.prices` avec type de produit canonique (`RICE_PADDY`, `RICE_WHITE_LOCAL`, `RICE_WHITE_IMPORTED`).
- **Échantillons :** `backend/tests/fixtures/miasa_odr/odr_bulletin_sample.txt`.
- **Statut et incidents :** Actif, aucun incident.
