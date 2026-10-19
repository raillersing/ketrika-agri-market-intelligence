# meteo_mg : Direction Générale de la Météorologie de Madagascar (DGM)

- **Propriétaire / licence / attribution :** Direction Générale de la Météorologie (DGM), Ministère des Transports et de la Météorologie, Madagascar. Attribution obligatoire : « Direction Générale de la Météorologie, Madagascar ».
- **Famille de source (`source_family`) :** `madagascar_gov` (service météorologique national malgache).
- **URL vérifiées (date, code HTTP) :**
  - https://www.meteomadagascar.mg (2026-10-10, HTTP 200, verified: true).
- **robots.txt :** `User-agent: * Allow: /`
- **CGU & Qualification légale (C1 / R1.1) :** Données publiques d'intérêt général pour la sécurité civile, la navigation et l'agriculture. `pii_class: none`.
- **Format(s) et structure :** Bulletins agrométéorologiques décadaires et mensuels (PDF/HTML), prévisions saisonnières et alertes cycloniques/pluviométriques.
- **Cadences distinctes (R1.1) :**
  - Collecte technique (`collection_cadence`) : `weekly`
  - Observation sous-jacente (`observation_cadence`) : `weekly`
  - Publication éditeur (`publication_cadence`) : `weekly`
- **Couverture :** Ensemble des 23 régions et principaux districts agricoles de Madagascar.
- **Pièges connus :** Séparer rigoureusement dates d'émission du bulletin et périodes de validité calendaire ; ne jamais convertir un libellé qualitatif en fausse probabilité chiffrée sans source explicite.
- **Stratégie d'extraction :** Déterministe (PDF / texte structuré) adossée à `MeteoMgConnector`.
- **Mapping vers les tables cibles :** `obs.weather_observation`, `obs.climate_event`.
