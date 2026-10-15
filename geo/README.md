# Référentiel Géographique de Madagascar (Ketrika Agri Market Intelligence)

> **Statut de qualification R1.10 (2026-10-15) :**
> - Référentiel géographique, résolutions spatiales et manifestes : **QUALIFIÉ & VALIDÉ (DONE)**.
> - Découpage officiel pivot : **23 régions administratives** selon la Loi n° 2021-010 et le standard OCHA COD-AB.
> - Règle de non-assignation aveugle vérifiée : toute entité non résolue retourne strictement `None` et est envoyée en revue humaine sans jamais tomber par défaut sur `MDG1101` (Antananarivo Renivohitra) ou une région par défaut.
> - Bounding box Madagascar validée mécaniquement sur 100% des polygones et centroïdes.
> - Manifeste machine `geo/manifest.json` liant fichiers GeoJSON, versions et empreintes SHA-256.

## 1. Provenance et métadonnées
- **Source principale :** OCHA Madagascar / BNGRC / Foiben-Taosarintanin'i Madagasikara (FTM)
- **Jeu de données :** Common Operational Datasets on Administrative Boundaries (COD-AB)
- **Identifiant source :** `ocha_codab_mdg` (HDX)
- **Date de publication du référentiel :** 2024
- **Version des limites (`boundary_version`) :** `2024.1`
- **Système de coordonnées :** WGS 84 (EPSG:4326)
- **Boîte englobante nationale :** Longitude [43.1, 50.6], Latitude [-25.7, -11.9]

## 2. Niveaux administratifs et dénombrement
| Niveau | Type d'entité | Nombre d'entités | Identifiant canonique | Exemple |
|---|---|---|---|---|
| **Admin 0** | Pays (National) | 1 | `MDG` | Madagascar |
| **Admin 1** | Région | 23 | `MDG11` à `MDG72` | Analamanga, Vakinankaratra, Atsinanana |
| **Admin 2** | District | 119 | `MDG1101` à `...` | Antananarivo Renivohitra, Toamasina I |
| **Admin 3** | Commune | ~1 695 | Codes P-Code FTM | Anosibe, Ambohimanarina |
| **Market** | Marché de détail/gros | ~150 | `MKT_<CODE>` | Bazar Be, Anosibe, Asabotsy |

## 3. Analyse du découpage régional et traçabilité des divergences (22 vs 23 vs 24 régions)
- **Historique 22 régions (2004–2021) :** Madagascar comptait initialement 22 régions administratives.
- **Découpage officiel à 23 régions (Loi n° 2021-010) :** La région Vatovavy-Fitovinany a été scindée en deux entités distinctes :
  1. Région Vatovavy (P-Code `MDG23`, chef-lieu Mananjary)
  2. Région Fitovinany (P-Code `MDG24`, chef-lieu Manakara)
  Ce découpage à **23 régions** constitue le standard pivot retenu par OCHA COD-AB et par les institutions statistiques (INSTAT, ODR).
- **Évolution vers 24 régions (2024) :** La loi portant création de la région Ambatosoa (scindée d'Analanjirofo) a été votée récemment. Toutefois, les séries historiques de données de marché (World Bank RTFP, WFP HDX, ODR 2007–2024) ne disposent pas d'historique individualisé pour cette 24ème entité.
- **Stratégie retenue dans Ketrika (R1.10) :**
  - Le référentiel spatial primaire adopte **strictement les 23 régions OCHA COD-AB**.
  - Une table de correspondances et d'alias (`taxonomy/location_aliases.yaml`) gère la compatibilité ascendante et descendante :
    - L'ancien toponyme composite `Vatovavy-Fitovinany` est résolu vers `MDG23` avec une confiance documentée de 0.85.
    - La 24ème région `Ambatosoa` est rattachée à sa région parente d'origine `Analanjirofo` (`MDG32`).
  - **Refus formel d'attribution arbitraire :** Tout toponyme non reconnu ou ambigu est conservé en anomalie (`unresolved_location_needs_review`) et ne reçoit aucun code arbitraire ni rattachement aveugle à la capitale.

## 4. Fichiers géographiques et manifestes
- `geo/manifest.json` : Manifeste machine certifiant les versions, hashes sha256 et comptes de features.
- `geo/processed/admin0.geojson` : Contour national simplifié (1 feature, sha256: `068239dd...`).
- `geo/processed/admin1.geojson` : Les 23 polygones régionaux officiels (23 features, sha256: `96060f6d...`).
- `geo/processed/admin2.geojson` : Échantillon et centroïdes des districts de référence (3 features, sha256: `a2bc1d38...`).
- `geo/processed/admin3.geojson` : Échantillon des communes urbaines de référence (3 features, sha256: `04eb1316...`).
