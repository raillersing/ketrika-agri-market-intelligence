# Fiche source : Banky Foiben'i Madagasikara (BFM Public)

> Audit indépendant2026-10-25 : registre `active`, SQL `absent`. Pas de réception live actuelle déduite de la présence du code. Les dates/HTTP/droits/annotations ci-dessous sont des descriptions historiques, non revérifiées par cet audit. Réception à suivre dans [la matrice](../audits/2026-10-25/TASK_CAPABILITY_MATRIX.md) et le [plan correctif](../audits/2026-10-25/CORRECTIVE_EXECUTION_PLAN.md).

## 1. Identité et métadonnées

| Champ | Valeur |
|---|---|
| **source_id** | `bfm_public` |
| **Nom complet** | Banky Foiben'i Madagasikara – Cours de Change et Données Monétaires Publiques |
| **Institution émettrice** | Banky Foiben'i Madagasikara (Banque Centrale de Madagascar) |
| **source_family** | `bfm` |
| **Priorité** | `P1` (MUST pour le contexte macroéconomique et la parité d'importation) |
| **Statut** | `active` |
| **Type de données (data_kinds)** | `macro` |
| **Méthode d'accès** | `file` (téléchargement et consultation de séries officielles HTML/CSV/Excel) |
| **URL d'atterrissage** | `https://www.banky-foibe.mg/cours-de-change` |
| **Licence** | Données publiques officielles de la Banque Centrale |
| **Cadences** | Collection : `daily` \| Observation : `daily` \| Publication : `daily` (jours ouvrés) |
| **Freshness SLA** | 5 jours (couvrant week-ends et jours fériés bancaires) |
| **Partitionnement Bronze** | `per_document` / `daily` |

---

## 2. Rôle économique et articulation avec le marché vivrier

1. **Parité d'importation du riz vivrier ("Vary Tsinjo") :**
   Madagascar importe annuellement entre 400 000 et 700 000 tonnes de riz blanchi, facturé principalement en dollars américains (USD). Le cours de référence officiel USD/Ariary publié par la BFM détermine directement le coût d'atterrissage CAF à Toamasina et la transmission des prix vers les marchés de gros (Analamanga, Atsinanana).

2. **Étalon de référence contre le franc CFA et l'Euro :**
   L'Euro (EUR/MGA) sert de référence pour les flux commerciaux avec la zone européenne et les partenaires régionaux de l'Océan Indien.

3. **Indépendance stricte vis-à-vis des taux douaniers et transactionnels :**
   Le cours de référence BFM est issu du **Marché Interbancaire de Devises (MID)**. Conformément à `MARKET_INTELLIGENCE_EXECUTION_PLAN.md` §R2.6, aucun taux douanier administratif (taux de liquidation douanière) ni taux informel transactionnel n'est substitué au cours de référence de la BFM.

---

## 3. Séries et indicateurs extraits

| Code indicateur | Libellé | Fréquence | Unité | Scope | Description / Notes |
|---|---|---|---|---|---|
| `EXCHANGE_RATE_USD_MGA` | Cours de change USD/MGA (Moyen) | `daily` | `MGA` | `national` | 1 USD en Ariary (taux moyen pondéré MID) |
| `EXCHANGE_RATE_USD_MGA_BUY` | Cours de change USD/MGA (Achat) | `daily` | `MGA` | `national` | Cours acheteur indicatif |
| `EXCHANGE_RATE_USD_MGA_SELL` | Cours de change USD/MGA (Vente) | `daily` | `MGA` | `national` | Cours vendeur indicatif |
| `EXCHANGE_RATE_EUR_MGA` | Cours de change EUR/MGA (Moyen) | `daily` | `MGA` | `national` | 1 EUR en Ariary (taux moyen pondéré MID) |
| `EXCHANGE_RATE_EUR_MGA_BUY` | Cours de change EUR/MGA (Achat) | `daily` | `MGA` | `national` | Cours acheteur indicatif |
| `EXCHANGE_RATE_EUR_MGA_SELL` | Cours de change EUR/MGA (Vente) | `daily` | `MGA` | `national` | Cours vendeur indicatif |
| `POLICY_RATE_BFM_PCT` | Taux Directeur BFM | `event` / `monthly` | `percent` | `national` | Taux des facilités de dépôt/prêt marginal |

---

## 4. Invariants stricts de modélisation (Anti-flaterie & Anti-interpolation)

1. **Jours ouvrés stricts et absence d'interpolation silencieuse :**
   - Le MID ne fonctionne que les jours ouvrés bancaires (lundi au vendredi, hors jours fériés malagasy).
   - Les samedis, dimanches et jours fériés **ne portent aucune observation** et doivent demeurer absents dans la base de données.
   - **Interdiction formelle :** Tout forward-fill, interpolation linéaire ou réplication aveugle sur les week-ends est rigoureusement interdit.

2. **Convention inverse prouvée (USD/MGA vs MGA/USD) :**
   - La convention officielle retenue dans le système est le nombre d'Ariary pour une unité de devise étrangère :
     $$\text{Taux} = \frac{\text{MGA}}{1\text{ USD}}$$
   - Pour toute conversion analytique ou demande d'affichage inverse (USD pour 1 MGA), le calcul inverse est rigoureusement certifié :
     $$\text{Taux inverse} = \frac{1}{\text{Taux}} \quad (\text{avec } \text{Taux} > 0)$$
   - L'unité stockée est toujours explicitement `MGA` (MGA par USD) sans confusion d'échelle.

3. **Distinction explicite achat / vente / moyen :**
   - Le spread bancaire (vente - achat) ne doit jamais être confondu avec le cours moyen pondéré du marché.
   - Les trois séries portent des `indicator_code` distincts.

4. **Non-antidatage C2 :**
   - `first_available_at` est fixé au jour ouvré suivant la cotation à 09:00 UTC (ouverture des marchés et publication des cours officiels de la veille ou du jour).

---

## 5. Gouvernance et politique de collecte

- **Robots.txt & limitation de débit :** Respect scrupuleux des directives robots.txt du serveur de la Banque Centrale (`max_rps: 0.2`, `daily_request_budget: 100`).
- **Arrêt d'urgence (PolicyStop) :** En cas d'inaccessibilité, d'erreur 403 ou de restriction d'accès, arrêt immédiat sans contournement, passage en statut dégradé/désactivé et maintien des contextes "inconnu".
