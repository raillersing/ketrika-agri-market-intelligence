# Fiches métriques normatives : Tableau économique interprétable (ADR-070, R2.8)

> **Statut :** Spécification normative des indicateurs macroéconomiques et de contexte de marché pour Ketrika Agri Market Intelligence.
> Conformément à l'ADR-070 et aux directives de `MARKET_INTELLIGENCE_EXECUTION_PLAN.md` §R2.8 :
> 1. **Aucun score composite global inventé :** Les dimensions économiques sont structurellement hétérogènes et sont présentées de façon autonome.
> 2. **Distinction absolue :** L'inflation NIPC (taux de variation d'un panier de consommation des ménages) et la variation des prix de marché vivriers au kg (relevés de terrain) ne sont jamais confondues ni agrégées.
> 3. **Flux commerciaux :** Les volumes (en tonnes métriques) et les valeurs (en MGA ou devises) sont strictement séparés. Tout ratio dérivé exige des unités compatibles certifiées.
> 4. **Ruptures de base :** Tout changement de base indiciaire (ex. base 2016 vs base 2024) interdit tout raccordement implicite ou calcul de variation inter-bases.
> 5. **Nullité explicite :** Tout dénominateur nul, unité incompatible ou série absente produit strictement `NULL` avec un code de raison standardisé.

---

## 1. Répertoire des dimensions économiques

| Dimension | Code dimension | Description et rôle pour la filière vivrière |
|---|---|---|
| **Inflation générale et vivrière** | `inflation` | Pouvoir d'achat global des ménages et évolution générale des prix alimentaires (INSTAT NIPC). |
| **Change et contexte monétaire** | `exchange_rate` | Pression sur le coût d'importation des vivres (notamment le riz blanc importé) via la parité USD/MGA et EUR/MGA (BFM MID). |
| **Carburants et énergie** | `fuel_energy` | Coût du transport routier de fret vivrier (Gazole) et consommation d'énergie domestique/industrielle (OMH, JIRAMA via TBE). |
| **Commerce extérieur vivrier** | `external_trade` | Volumes et valeurs des flux d'importation de riz, coût unitaire d'importation CAF à la frontière et ratio de dépendance (TBE, Douanes, FAOSTAT). |
| **Activité économique réelle** | `real_activity` | Dynamisme conjoncturel de la demande intérieure et de la production (PIB réel, IPI, ciment via TBE). |

---

## 2. Fiches métriques détaillées

### Dimension 1 : Inflation (`inflation`)

#### Fiche M-01 : Inflation d'ensemble (NIPC Général)
- **ID métrique :** `inflation_headline`
- **Intitulé :** Indice des Prix à la Consommation (NIPC) – Ensemble National
- **Définition :** Mesure de l'évolution du niveau général des prix des biens et services consommés par les ménages malgaches.
- **Formule :**
  $$\text{Glissement annuel (a/a)} = \frac{I_t - I_{t-12}}{I_{t-12}} \times 100$$
  $$\text{Glissement mensuel (m/m)} = \frac{I_t - I_{t-1}}{I_{t-1}} \times 100$$
- **Unité :** Indice (base 100) et taux en pourcentage (`%`).
- **Fréquence :** Mensuelle (`monthly`).
- **Périmètre géographique :** National (`geo_scope = 'national'`).
- **Source primaire / Famille :** Institut National de la Statistique (INSTAT) / `instat`.
- **Règles de calcul et de nullité :**
  - Si la base temporelle de $I_t$ diffère de celle de $I_{t-12}$ (ex: passage de la base 2016 à la base 2024), le glissement est strictement `NULL` avec la raison `base_shift`.
  - Si $I_{t-12}$ est nul ou absent, le résultat est `NULL` (`zero_denominator` ou `missing_denominator`).
- **Limites d'interprétation :** Ne mesure pas le prix d'un produit spécifique, mais un panier pondéré selon les structures de dépenses de l'enquête ménage.

#### Fiche M-02 : Inflation des produits alimentaires (NIPC Vivrier/Alimentaire)
- **ID métrique :** `inflation_food`
- **Intitulé :** NIPC – Produits alimentaires et boissons non alcoolisées
- **Définition :** Indice des prix spécifique à la composante alimentaire du panier de consommation des ménages.
- **Formule :** Identique à M-01 sur la série spécifique des produits alimentaires.
- **Unité :** Indice et taux en pourcentage (`%`).
- **Fréquence :** Mensuelle (`monthly`).
- **Périmètre géographique :** National (`geo_scope = 'national'`).
- **Source primaire / Famille :** INSTAT / `instat`.
- **Règles de calcul et de nullité :** Identique à M-01 (`base_shift` en cas de changement de base).
- **Limites d'interprétation :** Distinct formellement des relevés de marché direct au kg : l'inflation vivrière est une moyenne pondérée d'indices urbains, tandis que les prix de marché reflètent les transactions effectives au niveau des marchés de détail ou de gros.

---

### Dimension 2 : Change et contexte monétaire (`exchange_rate`)

#### Fiche M-03 : Cours de référence Dollar Américain (USD/MGA)
- **ID métrique :** `fx_usd_mga`
- **Intitulé :** Cours moyen pondéré du Dollar Américain sur le Marché Interbancaire de Devises (MID)
- **Définition :** Taux de change officiel de référence pour les transactions d'importation de produits vivriers (notamment le riz blanc importé d'Inde ou du Pakistan facturé en USD).
- **Formule :** Taux moyen pondéré publié par BFM pour les jours ouvrés réels.
- **Unité :** Ariary par Dollar (`MGA/USD`).
- **Fréquence :** Journalière (`daily`).
- **Périmètre géographique :** National.
- **Source primaire / Famille :** Banky Foiben'i Madagasikara (BFM) / `bfm`.
- **Règles de calcul et de nullité :**
  - Jours fériés et week-ends : Non cotés, strictement absents de la base (interdiction d'interpolation ou de forward-fill).
  - Taux inverse calculé : `1 / fx_usd_mga` certifié avec invariant $\text{taux} \times \text{inverse} = 1.0 \pm 10^{-5}$.
  - Absence de publication BFM : Valeur `NULL` avec raison `missing_series`.
- **Limites d'interprétation :** Cours interbancaire de gros ; ne prend pas en compte les commissions bancaires de détail ni les taux du marché parallèle.

#### Fiche M-04 : Cours de référence Euro (EUR/MGA)
- **ID métrique :** `fx_eur_mga`
- **Intitulé :** Cours moyen pondéré de l'Euro sur le MID
- **Définition :** Taux de change de référence pour les échanges régionaux de l'Océan Indien et les importations en provenance de la zone Euro.
- **Formule :** Taux moyen pondéré officiel BFM.
- **Unité :** Ariary par Euro (`MGA/EUR`).
- **Fréquence :** Journalière (`daily`).
- **Source primaire / Famille :** BFM / `bfm`.
- **Règles de calcul et de nullité :** Identique à M-03.

---

### Dimension 3 : Carburants et énergie (`fuel_energy`)

#### Fiche M-05 : Prix maximal réglementé du Gazole (Gasoil)
- **ID métrique :** `fuel_diesel`
- **Intitulé :** Prix plafond réglementé du Gazole à la pompe (OMH)
- **Définition :** Prix de vente maximal autorisé à la pompe pour le gazole, principal déterminant du coût du fret routier sur les corridors vivriers (RN2, RN7, RN4).
- **Formule :** Barème fixé par arrêté interministériel et diffusé par l'Office Malgache des Hydrocarbures.
- **Unité :** Ariary par litre (`MGA/L`).
- **Fréquence :** Événementielle / mensuelle (`event` / `monthly`).
- **Périmètre géographique :** National (ou par zone de distribution littorale/haute-terre).
- **Source primaire / Famille :** Office Malgache des Hydrocarbures (OMH) / `omh`.
- **Règles de calcul et de nullité :**
  - Date d'effet (`period_start`) obligatoirement dissociée de la date de publication (`published_at`).
  - Marqueur obligatoire : `is_administered = true`, `rate_type = "ceiling"`.
  - Pas d'extrapolation : L'absence de nouveau barème n'autorise pas à déclarer une rupture d'approvisionnement ou une stabilité garantie.
- **Limites d'interprétation :** Prix plafond légal ; en cas de pénurie locale ou de rationnement, le prix réel de transaction informel peut différer du barème officiel.

#### Fiche M-06 : Prix maximal réglementé du Super Carburant (SP95)
- **ID métrique :** `fuel_sp95`
- **Intitulé :** Prix plafond réglementé du Super 95 à la pompe
- **Définition :** Prix plafond pour le transport urbain léger et la motoculture.
- **Unité :** Ariary par litre (`MGA/L`).
- **Fréquence :** Événementielle / mensuelle.
- **Source primaire / Famille :** OMH / `omh`.
- **Règles de calcul et de nullité :** Identique à M-05.

#### Fiche M-07 : Prix maximal réglementé du Pétrole Lampant
- **ID métrique :** `fuel_kerosene`
- **Intitulé :** Prix plafond réglementé du Pétrole Lampant
- **Définition :** Énergie d'éclairage et de base des ménages ruraux et vulnérables.
- **Unité :** Ariary par litre (`MGA/L`).
- **Source primaire / Famille :** OMH / `omh`.
- **Règles de calcul et de nullité :** Identique à M-05.

---

### Dimension 4 : Commerce extérieur vivrier (`external_trade`)

#### Fiche M-08 : Volume des importations de riz
- **ID métrique :** `rice_import_volume`
- **Intitulé :** Importations de riz blanc – Volume physique mensuel
- **Définition :** Quantité totale de riz déclarée aux douanes et débarquée dans les ports malgaches (principalement Toamasina).
- **Formule :** Somme mensuelle des flux douaniers ou relevé TBE :
  $$V_{\text{riz}} = \sum \text{tonnes}$$
- **Unité :** Tonnes métriques (`tons`).
- **Fréquence :** Mensuelle (`monthly`).
- **Source primaire / Famille :** Direction Générale des Douanes / INSTAT TBE / `douanes` ou `instat`.
- **Limites d'interprétation :** Ne couvre que les entrées portuaires enregistrées sous le code HS 1006.

#### Fiche M-09 : Valeur CAF des importations de riz
- **ID métrique :** `rice_import_value`
- **Intitulé :** Valeur CAF (Coût, Assurance, Fret) des importations de riz
- **Définition :** Valeur totale déclarée à la frontière des importations de riz en Ariary.
- **Unité :** Millions d'Ariary (`million_MGA`) ou Ariary (`MGA`).
- **Fréquence :** Mensuelle (`monthly`).
- **Source primaire / Famille :** Douanes / INSTAT TBE.

#### Fiche M-10 : Coût unitaire d'importation CAF du riz (Prix frontière unitaire)
- **ID métrique :** `rice_import_unit_cost`
- **Intitulé :** Prix unitaire d'importation CAF du riz (MGA/kg)
- **Définition :** Ratio de la valeur CAF totale sur le volume total importé converti en kilogrammes.
- **Formule :**
  $$\text{Prix CAF (MGA/kg)} = \frac{\text{Valeur CAF (MGA)}}{\text{Volume (kg)}} = \frac{\text{Valeur CAF (MGA)}}{\text{Volume (tonnes)} \times 1000}$$
- **Unité :** Ariary par kilogramme (`MGA/kg`).
- **Fréquence :** Mensuelle (`monthly`).
- **Règles de calcul et de nullité :**
  - Si le volume en tonnes est $\le 0$ ou absent $\Rightarrow$ `NULL` avec raison `zero_denominator` ou `missing_denominator`.
  - Si les unités sont incompatibles (ex. tentative d'utiliser des litres ou des boîtes sans conversion certifiée) $\Rightarrow$ `NULL` avec raison `incompatible_units`.
- **Limites d'interprétation :** Représente le coût à la frontière portuaire (hors droits de douane, taxes portuaires, coût de débarquement et marge des importateurs). Ne doit jamais être assimilé directement au prix de gros ou de détail.

#### Fiche M-11 : Ratio de dépendance aux importations de riz
- **ID métrique :** `rice_import_dependency_ratio`
- **Intitulé :** Ratio de dépendance aux importations de riz (IDR)
- **Définition :** Part des importations nettes dans la disponibilité apparente annuelle du riz.
- **Formule :**
  $$\text{IDR} = \frac{\text{Imports (tonnes)}}{\text{Production (tonnes)} + \text{Imports (tonnes)} - \text{Exports (tonnes)}}$$
- **Unité :** Ratio adimensionnel compris entre 0.0 et 1.0 (ou exprimé en `%`).
- **Fréquence :** Annuelle (`annual`).
- **Règles de calcul et de nullité :**
  - Dénominateur (disponibilité apparente) $\le 0$ $\Rightarrow$ `NULL` avec raison `zero_denominator`.
  - Périodes temporelles décalées (ex. production 2024 et imports 2026) $\Rightarrow$ `NULL` avec raison `unaligned_period`.

---

### Dimension 5 : Activité économique réelle (`real_activity`)

#### Fiche M-12 : Croissance trimestrielle du PIB réel
- **ID métrique :** `gdp_growth_real`
- **Intitulé :** Taux de croissance trimestriel du Produit Intérieur Brut réel (en volume)
- **Définition :** Variation en pourcentage du PIB réel par rapport au même trimestre de l'année précédente (glissement annuel).
- **Formule :** Publication officielle de l'INSTAT (TBE).
- **Unité :** Pourcentage (`%`).
- **Fréquence :** Trimestrielle stricte (`quarterly`).
- **Règles de calcul et de nullité :**
  - Conservation absolue de la fréquence trimestrielle : Interdiction formelle de diviser par 3 pour créer de faux mois calendaires.
  - Absence de publication : `NULL` avec raison `missing_series`.

#### Fiche M-13 : Indice de la Production Industrielle (IPI)
- **ID métrique :** `ipi_industrial_production`
- **Intitulé :** Indice de la Production Industrielle (IPI hors énergie)
- **Définition :** Mesure de l'activité manufacturière et agro-alimentaire malgache.
- **Unité :** Indice (base 100).
- **Fréquence :** Trimestrielle ou mensuelle selon édition TBE.
- **Source primaire / Famille :** INSTAT / `instat`.

---

## 3. Matrice de gouvernance et détection de nullité

| Code de nullité (`null_reason`) | Signification opérationnelle | Action du système |
|---|---|---|
| `zero_denominator` | Dénominateur mathématique égal à 0 (évitement de division par zéro) | Valeur fixée à `NULL`, alerte d'audit |
| `missing_denominator` | Dénominateur requis non présent dans les observations | Valeur fixée à `NULL`, statut `partial` |
| `missing_series` | Aucune observation disponible pour cette série dans la période | Valeur fixée à `NULL`, statut `partial` |
| `unaligned_period` | Les composantes du calcul appartiennent à des périodes temporelles distinctes | Calcul refusé, valeur `NULL` |
| `incompatible_units` | Tentative d'opération sur des grandeurs physiques non homogènes sans facteur certifié | Calcul refusé, valeur `NULL` |
| `base_shift` | Rupture de base indiciaire constatée sans clé de raccordement officielle | Calcul de variation refusé, valeur `NULL` |

---

## 4. Articulation avec le Pilote Rizicole (R2.4)

Dans le cadre du pilote rizicole restreint aux trois zones complémentaires (`Analamanga`, `Alaotra-Mangoro`, `Atsinanana`) et à la référence nationale :

1. **Transmission Carburant $\rightarrow$ Riz Local :**
   Le corridor RN44 (Ambatondrazaka $\rightarrow$ Antananarivo) transporte le riz blanc local (`RICE_WHITE_LOCAL`). Le prix plafond du gazole (`fuel_diesel`) constitue la composante variable majeure du fret par camion.
2. **Transmission Change $\rightarrow$ Riz Importé :**
   Le corridor RN2 (Toamasina $\rightarrow$ Antananarivo) achemine le riz blanc importé (`RICE_WHITE_IMPORTED`). Le cours USD/MGA (`fx_usd_mga`) détermine le coût de dédouanement et le prix unitaire CAF frontière (`rice_import_unit_cost`), qui sert de borne inférieure au prix de gros à Toamasina et de détail à Antananarivo.
3. **Indépendance d'analyse :**
   L'analyse économique met en regard ces variables sans jamais prétendre à une relation de causalité instantanée ou statistique artificielle non prouvée empiriquement.
