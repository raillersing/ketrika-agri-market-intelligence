# Protocole d'Enquête et de Relevé de l'Approvisionnement des Marchés Vivriers à Madagascar

> **Statut :** Document méthodologique et opérationnel (R5.1, ADR-088, SPECS §27).  
> **Gouvernance :** Conforme aux principes de protection des données personnelles (AGENTS.md §8.3, aucun nom, numéro de téléphone ni PII).

---

## 1. Objectifs Métrologiques

Le présent protocole définit la méthodologie de relevé des quantités physiques sur les marchés vivriers de Madagascar pour trois objectifs distincts et non cumulables :
1. **Suivi des flux d'arrivages (`inflow_arrival`) :** quantifier les tonnages entrants sur les marchés de gros et demi-gros (ex: Anosibe, Marovoay, Ambatondrazaka).
2. **Évaluation des stocks disponibles (`stock_inventory`) :** mesurer à date fixe le niveau d'inventaire physique dans les dépôts et hangars des marchés.
3. **Estimation des volumes récoltés (`harvest_volume`) :** consolider les déclarations de récolte au niveau des bassins de production agricole.

---

## 2. Principes d'Anonymisation et Règle Zéro PII

En application stricte de la constitution du projet (`AGENTS.md` §8.3) :
- **Aucune donnée personnelle n'est collectée.**
- Il est **formellement interdit** de renseigner sur les fiches d'enquête :
  - Le nom, prénom ou surnom d'un commerçant, collecteur ou transporteur.
  - Le numéro de téléphone ou l'adresse email.
  - La plaque d'immatriculation d'un camion ou véhicule de livraison.
  - Le numéro de Carte d'Identité Nationale (CIN) ou identifiant fiscal (NIF/STAT).
- **Identifiants autorisés :**
  - Code du marché public (ex: `MKT_ANOSIBE_TANA`, `MKT_AMBATONDRAZAKA_CENTRE`).
  - Code P-code de la commune ou district (ex: `MDG1101`).
  - Code de rôle de l'enquêteur anonyme (ex: `ENQ_ANOSIBE_01`).
  - Type de point de vente : grossiste, demi-grossiste, détaillant.

---

## 3. Typologie des Unités et Table de Conversion Standardisée

Les quantités collectées doivent toujours mentionner l'unité d'origine (`unit_raw`) et sont converties mécaniquement en kilogrammes métriques (`quantity_kg`) :

| Unité Brute | Libellé Local | Poids Standard Riz (kg) | Poids Standard Maïs (kg) | Poids Standard Manioc (kg) |
|---|---|---|---|---|
| `kg` | Kilogramme | 1.000 | 1.000 | 1.000 |
| `tonne` | Tonne métrique | 1000.000 | 1000.000 | 1000.000 |
| `bag_50kg` | Sac usiné 50 kg | 50.000 | 50.000 | 50.000 |
| `bag_100kg` | Sac jute 100 kg | 100.000 | 100.000 | 100.000 |
| `gony` | Gony malagasy | 50.000 (usiné) / 48.000 (paddy) | 45.000 | 50.000 (frais) |
| `kapoaka` | Boîte de 300 ml | 0.260 (usiné) / 0.280 (paddy) | 0.240 | 0.200 (cossettes) |

---

## 4. Modes de Mesure et Qualité des Données

L'enquêteur doit obligatoirement qualifier le mode de mesure :
- **`measured_scale` (Pesée effective) :** la marchandise a été pesée sur un pont-bascule, une bascule romaine ou un pèse-colis étalonné. Confiance métrologique maximale.
- **`declared_trader` (Déclaration commerçant) :** le volume repose sur le bordereau de livraison ou l'affirmation verbale du commerçant/chauffeur sans pesée directe.
- **`estimated_survey` (Dénombrement visuel) :** l'enquêteur compte le nombre de sacs ou de paniers déchargés et applique la masse unitaire nominale.

---

## 5. Prévention du Double Comptage

- **Règle 1 :** Ne **JAMAIS** additionner les arrivages journaliers avec les stocks d'inventaire. Un arrivage entre en magasin et devient ensuite stock : leur sommation compterait deux fois la même marchandise.
- **Règle 2 :** L'analyse temporelle des flux (cumul hebdomadaire ou mensuel) n'est valide que si les jours d'enquête couvrent la totalité de la période sans trou, ou avec un ratio de couverture d'échantillonnage documenté.
- **Règle 3 :** La production au champ (`harvest_volume`) ne doit jamais être additionnée aux arrivages sur les marchés urbains.
