# Méthodologie et neutralisation du biais de double comptage des prix multisources

> Document normatif et méthodologique établi dans le cadre de la tâche **IA-DATA-07** (P1 : prix multisources) du plan d'industrialisation `IROOA_PLAN_IMPLEMENTATION_COLLECTE_AUTONOME_2026-11-09.md` et de SPECS §5.2, §14, §15.

---

## 1. Contexte et problématique

Dans le suivi des prix des produits de première nécessité (PPN) vivriers à Madagascar (riz local et importé, maïs, manioc, sucre, farine de blé), plusieurs organismes internationaux et nationaux publient des séries de prix mensuels sub-nationaux :

1. **WFP HDX / HAPI (`wfp_hdx_mdg`)** : Système de suivi des marchés du Programme Alimentaire Mondial (WFP VAM - Vulnerability Analysis and Mapping).
2. **Banque mondiale RTFP (`wb_rtfp_mdg`)** : *High-Frequency Food Price Monitoring* (Banque mondiale, Study 8240).
3. **FAO FPMA (`fao_fpma_mdg`)** : *Food Price Monitoring and Analysis Tool* (FAO GIEWS).
4. **Sources nationales malgaches (`miasa_odr`, `mincc_ppn`, `instat_nipc`)** : Observatoire du Riz, Ministère du Commerce, INSTAT.

Une ingestion naïve qui traiterait ces sources comme des observations indépendantes introduirait un **biais de double comptage majeur** : la même transaction sur un marché d'Anosibe ou de Bazar Be serait enregistrée plusieurs fois sous des étiquettes d'éditeurs différentes, conduisant à une illusion d'échantillonnage et à une distorsion des indicateurs économiques.

---

## 2. Cartographie de la chaîne de transmission des données primaires

L'analyse des méthodologies de collecte de chaque organisme révèle les dépendances suivantes :

```
                  ┌──────────────────────────────────────────────┐
                  │    Relevés terrain primaires (Madagascar)     │
                  │   Enquêteurs WFP VAM & Correspondants ODR    │
                  └──────────────────────┬───────────────────────┘
                                         │
                 ┌───────────────────────┴───────────────────────┐
                 │                                               │
                 ▼                                               ▼
   ┌───────────────────────────┐                   ┌───────────────────────────┐
   │    WFP VAM / HDX HAPI     │                   │   Ministères / ODR / INSTAT│
   │  (Données directes terrain│                   │   (Données nationales     │
   │   par marché physique)    │                   │    administratives)       │
   └─────────────┬─────────────┘                   └─────────────┬─────────────┘
                 │                                               │
                 ├───────────────────────┐                       │
                 │                       ▼                       │
                 │         ┌───────────────────────────┐         │
                 │         │   Banque mondiale RTFP    │         │
                 │         │   (Study 8240 : absorbe   │         │
                 │         │    WFP VAM, applique      │         │
                 │         │    filtre Kalman spatial) │         │
                 │         └───────────────────────────┘         │
                 │                                               │
                 ▼                                               ▼
   ┌───────────────────────────────────────────────────────────────────────────┐
   │                            FAO GIEWS FPMA                                 │
   │      (Consolide les flux WFP et les statistiques des ministères)         │
   └───────────────────────────────────────────────────────────────────────────┘
```

### 2.1. Dépendance WB RTFP ↔ WFP HDX
L'étude méthodologique de la Banque mondiale (Study 8240) explicite que le modèle RTFP s'appuie sur la base de données globale de suivi des prix alimentaires du PAM (WFP Price Database) comme principale source d'observations réelles. La Banque mondiale y applique ensuite une imputation spatiale et un lissage statistique (filtre de Kalman). Par conséquent, **toute observation de prix WB RTFP à l'état `observed` provient directement du réseau d'enquêteurs du WFP**.

### 2.2. Dépendance FAO FPMA ↔ WFP & Ministères
L'outil FPMA de la FAO (Global Information and Early Warning System) collecte ses séries via deux canaux conjoints :
- Les données des ministères de l'Agriculture et du Commerce (via l'ODR pour Madagascar).
- Les bulletins conjoints de vulnérabilité alimentaire publiés avec le PAM (WFP).

---

## 3. Risques statistiques du double comptage

Si les observations de ces trois diffuseurs étaient fusionnées aveuglément ou moyennées :
1. **Réduction artificielle de la variance** : la corrélation parfaite ou quasi-parfaite entre l'observation originale WFP et sa réplique WB/FAO donnerait une fausse impression de stabilité.
2. **Sur-pondération des marchés suivis par le PAM** : les marchés humanitaires suivis par le PAM pèseraient artificiellement deux à trois fois plus lourd dans les indices nationaux que les marchés suivis uniquement par l'ODR ou l'INSTAT.
3. **Confusion entre valeur observée et valeur imputée** : les données interpolées spatialement par la Banque mondiale risqueraient d'écraser ou de masquer les données réelles constatées par les enquêteurs locaux.

---

## 4. Architecture de neutralisation dans Irooa / Ketrika

Pour garantir une intégrité scientifique absolue, Irooa met en œuvre trois niveaux de protection stricts :

### 4.1. Traçabilité complète de l'origine primaire (`evidence`)
Chaque connecteur consigne dans le champ structuré `evidence` de la table `obs.price_observation` :
- `source_family` : `"un_wfp"`, `"world_bank"`, ou `"un_fao"`.
- `underlying_collector` : `"WFP VAM"` pour WFP et WB, `"FAO GIEWS / WFP"` pour FPMA.
- `extraction_method` : `"deterministic"`.

### 4.2. Arbitrage déterministe dans la couche Gold (`gold.price_monthly_best`)
La vue matérialisée `gold.price_monthly_best` applique un partitionnement strict par grain unitaire :
`PARTITION BY product_id, location_id, actor_level, month`

Au lieu de moyenner des prix issus de sources corrélées, elle retient **une seule observation canonique** selon l'ordre de priorité :
1. Source P0 observée (ex: ODR / INSTAT direct).
2. Source P1 observée (ex: WFP HDX observation directe `price_flag = actual`).
3. Source P1 imputée (ex: WB RTFP interpolée spatialement).
4. Autres sources secondaires.

En complément, elle calcule et expose les métadonnées de transparence :
- `n_sources` : nombre total d'éditeurs ayant fourni une valeur.
- `n_families` : nombre de familles indépendantes authentiques.
- `has_conflict` : drapeau booléen déclenché si l'écart entre le prix maximal et minimal dépasse 25 % (`group_spread / min_price >= 0.25`).

### 4.3. Audit d'indépendance des familles de sources (`audit_source_family_independence`)
Dans `backend/src/ketrika/gold/kpi.py`, la fonction `audit_source_family_independence` inspecte les sources contribuant à un indicateur :
- Dès qu'une combinaison inclut simultanément `{wb_rtfp_mdg, wfp_hdx_mdg}`, `{wb_rtfp_mdg, fao_fpma_mdg}` ou `{wfp_hdx_mdg, fao_fpma_mdg}`, elle active immédiatement le drapeau `has_dependent_derivation = True`.
- Le résultat `is_truly_independent` est alors forcé à `False`.
- Les algorithmes de détection d'anomalies (`ml.anomalies`) et de scoring de santé de marché (`gold.kpi`) utilisent ce verdict pour refuser toute prime de corroboration factice.
