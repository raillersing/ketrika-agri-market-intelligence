# Fiche source : Office Malgache des Hydrocarbures (OMH Public)

## 1. Identité et métadonnées

| Champ | Valeur |
|---|---|
| **source_id** | `omh_public` |
| **Nom complet** | Office Malgache des Hydrocarbures (OMH) – Prix des Carburants et Événements Réglementaires |
| **Institution émettrice** | Office Malgache des Hydrocarbures (OMH) |
| **source_family** | `omh` |
| **Priorité** | `P1` (MUST pour le coût du fret routier et le transport vivrier) |
| **Statut** | `active` |
| **Type de données (data_kinds)** | `macro` |
| **Méthode d'accès** | `file` (téléchargement et consultation de barèmes officiels et communiqués HTML/CSV/PDF) |
| **URL d'atterrissage** | `https://www.omh.mg/prix-des-carburants` |
| **Licence** | Données publiques officielles gouvernementales |
| **Cadences** | Collection : `monthly` \| Observation : `event` \| Publication : `event` |
| **Freshness SLA** | 62 jours |
| **Partitionnement Bronze** | `per_document` |

---

## 2. Rôle économique et articulation avec le transport des vivres

1. **Coût du fret routier (Corridors RN2, RN7, RN4) :**
   À Madagascar, le transport de marchandises vivrières (notamment le riz depuis Toamasina par la RN2 ou depuis Ambatondrazaka par la RN44) s'effectue quasi-exclusivement par camions diesel. Le prix du gazole à la pompe constitue une composante déterminante du coût de transport à la tonne-kilomètre et de la marge des grossistes.

2. **Produits pétroliers suivis :**
   - **Gazole (Gasoil) :** Déterminant direct du coût du transport et de la logistique vivrière.
   - **Super Carburant (Essence sans plomb SP95) :** Déterminant du transport léger urbain.
   - **Pétrole lampant (Kérosène) :** Éclairage et énergie des ménages modestes et ruraux, suivi pour la sensibilité sociale.

3. **Distinction capitale : Prix réglementé vs Prix observé vs Événement d'application :**
   Conformément aux directives de `MARKET_INTELLIGENCE_EXECUTION_PLAN.md` §R2.7 :
   - Le **prix maximal réglementé** (prix plafond à la pompe fixé par l'État/OMH) est explicitement identifié (`is_administered: true`, `rate_type: "ceiling"`).
   - La **date d'effet / d'entrée en vigueur** (`effective_date` ou `period_start`) est rigoureusement dissociée de la **date de publication** du communiqué (`published_at`).
   - L'absence de publication d'un nouveau barème ne vaut pas "stabilité démontrée" : aucune rupture ni stabilité n'est inventée sans acte officiel ou relevé constaté.

---

## 3. Séries et indicateurs extraits

| Code indicateur | Libellé | Fréquence | Unité | Scope | Description / Caractère réglementaire |
|---|---|---|---|---|---|
| `FUEL_DIESEL_CEILING_MGA` | Prix Plafond Réglementé Gazole (MGA/L) | `event` | `MGA/L` | `national` | Prix maximal officiel à la pompe pour le Gazole |
| `FUEL_SUPER95_CEILING_MGA` | Prix Plafond Réglementé Super 95 (MGA/L) | `event` | `MGA/L` | `national` | Prix maximal officiel pour le Super Carburant |
| `FUEL_KEROSENE_CEILING_MGA` | Prix Plafond Réglementé Pétrole Lampant (MGA/L) | `event` | `MGA/L` | `national` | Prix maximal officiel pour le Pétrole Lampant |
| `FUEL_PRICE_EVENT` | Événement Réglementaire Hydrocarbures | `event` | `text` | `national` | Description de l'acte réglementaire (Décret, Arrêté, Communiqué) |

---

## 4. Invariants stricts de modélisation

1. **Dissociation temporelle (Date d'effet vs Publication) :**
   - `period_start` : Date exacte d'entrée en vigueur du barème (ex. application à minuit le 2026-06-01).
   - `published_at` : Date de signature ou de diffusion publique du communiqué OMH (ex. 2026-05-30).
   - `first_available_at` : Timestamp conservateur d'accès effectif au public.

2. **Immuabilité et non-écrasement des observations antérieures :**
   - Un nouveau communiqué révisant les prix ne modifie pas les enregistrements de l'ancien barème. L'ancien barème reste valide sur son intervalle calendaire historique (`period_start` à la veille du nouveau barème).

3. **Indicateur explicitement réglementaire :**
   - Le métadonnée `evidence` documente obligatoirement :
     ```json
     {
       "primary_institution": "Office Malgache des Hydrocarbures",
       "regulatory_act": "Arrêté Interministériel N°124/2026-MEH",
       "is_administered": true,
       "effective_date": "2026-06-01"
     }
     ```
