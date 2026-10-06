# Référentiel Géographique de Madagascar (Ketrika Agri Market Intelligence)

## 1. Provenance et métadonnées
- **Source principale :** OCHA Madagascar / BNGRC / Foiben-Taosarintanin'i Madagasikara (FTM)
- **Jeu de données :** Common Operational Datasets on Administrative Boundaries (COD-AB)
- **Identifiant source :** `ocha_codab_mdg` (HDX)
- **Date de publication du référentiel :** 2024
- **Version des limites (`boundary_version`) :** `2024.1`
- **Système de coordonnées :** WGS 84 (EPSG:4326)

## 2. Niveaux administratifs et dénombrement
| Niveau | Type d'entité | Nombre d'entités | Identifiant canonique | Exemple |
|---|---|---|---|---|
| **Admin 0** | Pays (National) | 1 | `MDG` | Madagascar |
| **Admin 1** | Région | 23 | `MDG11` à `MDG72` | Analamanga, Vakinankaratra, Atsinanana |
| **Admin 2** | District | 119 | `MDG1101` à `...` | Antananarivo Renivohitra, Toamasina I |
| **Admin 3** | Commune | ~1 695 | Codes P-Code FTM | Anosibe, Ambohimanarina |
| **Market** | Marché de détail/gros | ~150 | `MKT_<CODE>` | Bazar Be, Anosibe, Asabotsy |

## 3. Analyse du découpage régional (22 vs 23 vs 24 régions)
- **Historique 22 régions (2004–2021) :** Madagascar comptait initialement 22 régions administratives.
- **Découpage officiel à 23 régions (Loi n° 2021-010) :** La région Vatovavy-Fitovinany a été scindée en deux entités distinctes :
  1. Région Vatovavy (P-Code `MDG23`, chef-lieu Mananjary)
  2. Région Fitovinany (P-Code `MDG24`, chef-lieu Manakara)
  Ce découpage à **23 régions** constitue le standard retenu par OCHA COD-AB et par les institutions statistiques (INSTAT, ODR).
- **Évolution vers 24 régions (2024) :** La loi portant création de la région Ambatosoa (scindée d'Analanjirofo) a été votée récemment. Toutefois, les séries historiques de données de marché (World Bank RTFP, WFP HDX, ODR 2007–2024) ne disposent pas d'historique individualisé pour cette 24ème entité.
- **Stratégie retenue pour le MVP :**
  - Le référentiel spatial primaire adopte **strictement les 23 régions OCHA COD-AB**.
  - Une table de correspondances et d'alias (`location_aliases.yaml`) gère la compatibilité ascendante et descendante (ex: association de l'ancien code `Vatovavy-Fitovinany` vers ses composantes avec confiance documentée).

## 4. Fichiers géographiques simplifiés
- `geo/processed/admin0.geojson` : Contour national simplifié (≤ 100 Ko).
- `geo/processed/admin1.geojson` : Les 23 polygones régionaux officiels (≤ 500 Ko).
- `geo/processed/admin2.geojson` : Échantillon et centroïdes des districts de référence (≤ 1 Mo).
- `geo/processed/admin3.geojson` : Échantillon des communes urbaines de référence (≤ 1 Mo).

