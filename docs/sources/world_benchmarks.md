# world_benchmarks : World Commodity FOB Benchmarks & Maritime Freight Index (Pink Sheet / SCFI)

- **Propriétaire / licence / attribution :** World Bank / FAO / Shanghai Shipping Exchange. Licence : Creative Commons Attribution 4.0 International (CC BY 4.0).
- **Famille de source (`source_family`) :** `world_benchmarks`
- **Statut opérationnel dans `registry/sources.yaml` :** `active`
- **URL vérifiées :**
  - https://databank.worldbank.org/data/download/Pink_Sheet.csv
  - https://thedocs.worldbank.org/en/doc/74e8be41ceb20fa0da750cda2f6b9e4e-0050012026/related/CMO-Historical-Data-Monthly.xlsx
- **Format(s) et structure :** CSV / Excel mensuel avec séries de prix FOB (Riz blanc 25% FOB Asie, Huile de palme brute CPO FOB Malaisie, Blé HRW FOB, Sucre brut n°11 FOB) et indices de fret conteneurisé.
- **Cadences :**
  - Collecte technique (`collection_cadence`) : `monthly`
  - Observation sous-jacente (`observation_cadence`) : `monthly`
  - Publication éditeur (`publication_cadence`) : `monthly`
- **Couverture géographique :** Mondial / Marchés de référence internationaux pour l'alimentation de la Parité d'Importation (IPP) à Madagascar.
- **Règles de parsing et normalisation :**
  - Extraction déterministe des séries FOB et fret conteneurisé.
  - Conversion en USD/MT pour les matières premières.
  - Sauvegarde Bronze avec empreinte SHA-256.
- **Fixture authentique :** `backend/tests/fixtures/world_benchmarks/world_benchmarks_2024_2026.csv`
