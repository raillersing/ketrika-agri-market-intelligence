# instat_nipc : INSTAT Madagascar – Indice des Prix à la Consommation (NIPC)

- **Propriétaire / licence / attribution :** Institut National de la Statistique de Madagascar (INSTAT). Licence : Données publiques officielles gouvernementales. Attribution : "INSTAT Madagascar".
- **URL vérifiées (date, code HTTP) :**
  - https://www.instat.mg (2026-10-06, HTTP 200).
- **robots.txt (extrait pertinent, date) :** `User-agent: * Allow: /`
- **CGU (URL, sha256, résumé des clauses de réutilisation) :** https://www.instat.mg/mentions-legales. Publications de statistiques nationales officielles en accès public.
- **Format(s) et structure (avec exemples réels, pages, colonnes) :** Fichiers Excel (XLS/XLSX) et tableaux mensuels publiés sur le portail institutionnel. Indices nationaux et par agglomération, décomposition par fonctions de consommation (COICOP : 01 Produits alimentaires et boissons non alcoolisées).
- **Cadence constatée (dates des 6 dernières publications) :** Mensuelle (parution vers le 20 du mois M+1).
- **Couverture :** Territoire national, agglomération d'Antananarivo et grands centres urbains de province.
- **Pièges connus :** Changements d'années de base de l'indice (base 100), cellules fusionnées dans les tableaux Excel, retards de publication occasionnels.
- **Stratégie d'extraction :** Déterministe (Calamine / openpyxl / pandas).
- **Mapping vers les tables cibles :** `obs.cpi`.
- **Échantillons :** `backend/tests/fixtures/instat_nipc/nipc_sample.csv`.
- **Statut et incidents :** Actif, aucun incident.
