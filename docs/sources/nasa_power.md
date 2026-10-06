# nasa_power : NASA POWER Agroclimatology Daily Point API

- **Propriétaire / licence / attribution :** NASA Langley Research Center. Licence : Public Domain (US Government Open Data). Attribution : "NASA POWER Project, NASA Langley Research Center".
- **URL vérifiées (date, code HTTP) :**
  - https://power.larc.nasa.gov/api/temporal/daily/point (2026-10-06, HTTP 200).
- **robots.txt (extrait pertinent, date) :** `User-agent: * Allow: /` (vérifié 2026-10-06).
- **CGU (URL, sha256, résumé des clauses de réutilisation) :** https://power.larc.nasa.gov/docs/services/api/. Accès public illimité avec respect d'un débit modéré (max ~1 req/s recommandé).
- **Format(s) et structure (avec exemples réels, pages, colonnes) :** API REST GeoJSON / JSON. Paramètres : communauté `AG` (agroclimatology), paramètres `PRECTOTCORR` (précipitations corrigées en mm/jour), `T2M` (température moyenne à 2m en °C), `RH2M` (humidité relative). Structure de réponse : dictionnaire horodaté `properties.parameter.<PARAM>.<YYYYMMDD>`.
- **Cadence constatée (dates des 6 dernières publications) :** Quotidienne avec latence de 2 à 3 jours pour les données définitives.
- **Couverture :** Données ponctuelles sur l'ensemble des coordonnées géographiques des marchés vivriers de Madagascar.
- **Pièges connus :** Valeurs sentinelles `-999` pour les données manquantes qu'il convient de convertir en NULL.
- **Stratégie d'extraction :** Déterministe (Client HTTP REST).
- **Mapping vers les tables cibles :** `obs.weather` rattaché à `ref.geographies` et `ref.markets`.
- **Échantillons :** `backend/tests/fixtures/nasa_power/nasa_power_point_sample.json`.
- **Statut et incidents :** Actif, aucun incident.
