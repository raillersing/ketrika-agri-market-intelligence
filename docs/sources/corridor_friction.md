# corridor_friction : Madagascar Transport Corridor Friction & Logistics Index (RN2, RN4, RN7, RN34)

- **Propriétaire / licence / attribution :** Observatoire des Transports / Ministère des Travaux Publics / Ketrika Intelligence.
- **Famille de source (`source_family`) :** `corridor_friction`
- **Statut opérationnel dans `registry/sources.yaml` :** `active`
- **Format(s) et structure :** CSV avec friction kilométrique, délais de transit (heures/jours) et tarifs de fret routier (MGA/tonne) sur les corridors structurants malgaches (Toamasina - Antananarivo RN2, Mahajanga - Antananarivo RN4, Toliara - Antananarivo RN7, Ambatondrazaka - Antananarivo RN44/RN2).
- **Cadences :**
  - Collecte technique (`collection_cadence`) : `weekly`
  - Observation sous-jacente (`observation_cadence`) : `weekly`
  - Publication éditeur (`publication_cadence`) : `weekly`
- **Couverture géographique :** Corridors nationaux malgaches (RN2, RN4, RN7, RN34, RN44).
- **Règles de parsing et normalisation :**
  - Intégration dans les modèles de parité d'importation et transmission spatiale des prix.
  - Dérivation des coûts logistiques vers les chefs-lieux de région.
- **Fixture authentique :** `backend/tests/fixtures/corridor_friction/corridor_freight_benchmarks_2024_2026.csv`
