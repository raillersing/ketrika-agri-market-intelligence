# Runbook : Ajouter un nouveau connecteur de données

> **Statut :** Guide opérationnel normatif (MVP_EXECUTION_PLAN T2.6, AGENTS.md §4).
> Toute intégration de source dans Ketrika **DOIT** suivre scrupuleusement les 9 étapes de cette checklist.

---

## Vue d'ensemble du flux de données

Programme R, état de qualification : les statuts historiques du MVP ne sont
pas une preuve actuelle. Pour les assets natifs, la Source doit déjà exister
en SQL avant exécution ; ne pas la créer ni l'activer implicitement pour faire
passer un test. Une construction de définition ne vaut pas autorisation de collecte.
Bronze retourne son lot de références exactes et Silver le consomme sans refetch.
ADR-050 introduit des propriétaires transactionnels : démarrage meta indépendant,
transaction de données séparée, rollback avant reçu failed indépendant. Une
erreur failure_receipt_unavailable ne prouve pas un statut failed en SQL ; vérifier
le run UUID par relecture API/SQL. Un run running après interruption brutale ne
doit pas être déclaré terminé ni repris automatiquement sans ledger qualifié.
Le wrapper historique à transaction fournie par le caller reste distinct.

Les deux checks natifs reçus en R0.6 sont provenance_complete et schema_drift,
mesurés sur les observations et objets Bronze réels ; un contrat CSV/JSON absent
est unknown/refus, pas une structure apprise automatiquement. Les autres checks
listés plus bas sont des exigences à vérifier, pas un inventaire qualifié.
Le blocage Gold reçu concerne le graphe Dagster connecté ; les chemins SQL/CLI
directs, partitions et reprise restent à recevoir. Toute fixture synthétique doit
rester explicitement telle, sans conclure à une collecte officielle live.

```
Source Publique (HTTP / API / RSS)
        │
        ▼ (1. Discover & Fetch)
   Bronze Store (S3 object immuté + meta.source_record)
        │
        ▼ (2. Parse déterministe ou LLM)
  Records typés (ketrika.connectors.records.*)
        │
        ▼ (3. Normalize & Resolve)
  Taxonomie / Unités / Géographie (ref.*)
        │
        ▼ (4. Supersession & Load)
   Silver Layer (obs.*)
        │
        ▼ (5. DQ Checks)
   Cockpit Data Quality (ops.dq_result)
        │
        ▼ (6. Materialize)
   Gold Layer (gold.*)
```

---

## Checklist pas à pas (9 sections obligatoires)

### 1. Fiche source (`docs/sources/<source_id>.md`)
- Rédiger la fiche descriptive de la source :
  - **Identifiant :** `<source_id>` (snake_case unique, ex. `wfp_hdx_mdg`, `miasa_odr_bulletin`).
  - **Organisme émetteur :** Nom, type (public, international, officiel).
  - **Périmètre :** Produits couverts, fréquence de mise à jour, niveau géographique.
  - **URLs officielles :** URL d'accueil, URL API / flux / téléchargement direct.
  - **Conditions d'utilisation :** Licence, CGU, `robots.txt`, respect du secret statistique.
  - **Méthode d'accès :** Direct, API, Wayback si document historique.

### 2. Registre (`registry/sources.yaml`)
- Ajouter l'entrée correspondante dans `registry/sources.yaml` validée par le schéma Pydantic `SourceSpec` :
  ```yaml
  - source_id: <source_id>
    name: "Nom complet de la source"
    publisher: "Organisme"
    type: "csv" # ou "pdf", "api", "html", "excel"
    priority: "P0" # P0 (officiel/majeur) ou P1 (secondaire)
    cadence: "weekly" # daily, weekly, monthly, annual, ad_hoc
    freshness_sla_days: 14
    domain: "exemple.gov.mg"
    entrypoints:
      - "https://exemple.gov.mg/data.csv"
    max_rps: 0.2
    daily_request_budget: 100
    tos_sha256: "..."
    verified: true
  ```
- Valider le schéma :
  ```powershell
  ./scripts/dev.ps1 validate-registry
  ```

### 3. Fixtures représentatives (`backend/tests/fixtures/<source_id>/`)
- Placer au moins un échantillon réel non tronqué du document source :
  - `backend/tests/fixtures/<source_id>/sample.<ext>` (CSV, PDF, XLSX, JSON).
- S'assurer que la fixture contient les cas nominaux et les cas limites :
  - Valeurs manquantes (`ND`, `NA`, tirets, cellules vides).
  - Variantes orthographiques de produits ou de lieux malgaches.
  - Plusieurs périodes temporelles ou marchés.

### 4. Golden Test (`tests/golden/<source_id>/<doc_id>.expected.json`)
- Créer le fichier d'annotations de référence vérifié manuellement :
  - Contient les enregistrements attendus avec leurs champs bruts et normalisés.
  - Métadonnées obligatoires : `annotator`, `human_reviewed: false`, `annotated_at`.
  - Au moins 30 valeurs vérifiées par source (exigence CC2).
  - Objectif de conformité : exactitude par champ ≥ 99 % et rappel par enregistrement ≥ 98 %.

### 5. Implémentation du connecteur (`backend/src/ketrika/connectors/<source_id>.py`)
- Implémenter le protocole `Connector` (`ketrika.connectors.base.Connector`) :
  ```python
  from collections.abc import Iterable
  from typing import ClassVar
  from ketrika.connectors.base import DiscoveredItem, ParseResult, RawArtifact, RunContext
  from ketrika.connectors.records import PriceRecord # ou autre modèle Record

  class MyConnector:
      source_id: ClassVar[str] = "<source_id>"
      parser_version: ClassVar[str] = "1.0.0"

      def discover(self, ctx: RunContext) -> Iterable[DiscoveredItem]:
          # Émet les URLs et partition_keys
          yield DiscoveredItem(url="...", partition_key="...")

      def fetch(self, item: DiscoveredItem, ctx: RunContext) -> RawArtifact:
          # Téléchargement poli et stockage Bronze
          return ctx.fetch_and_store(item, mime_type="...")

      def parse(self, artifact: RawArtifact, ctx: RunContext) -> ParseResult:
          # Déterministe d'abord, LLM avec preuve si nécessaire
          ...
  ```
- Enregistrer le connecteur dans `backend/src/ketrika/connectors/registry.py` :
  ```python
  from ketrika.connectors.<source_id> import MyConnector
  register_connector("<source_id>", MyConnector)
  ```

### 6. Tests unitaires et d'intégration (`tests/unit/test_<source_id>.py`)
- Tester :
  - Le parsing unitaire de la fixture (vérification des champs extraits, dates, devises, unités).
  - La gestion des anomalies (caractères spéciaux, espaces insécables, encodages UTF-8 / Latin-1).
  - Le golden test comparant la sortie de `parse()` au JSON attendu.
  - La conformité à la politique HTTP (pas d'appels réseau non autorisés en mode test).

### 7. Backfill (`python -m ketrika.pipelines.backfill <source_id>`)
- Exécuter le pipeline d'ingestion historique ou complet :
  ```powershell
  ./scripts/dev.ps1 backfill <source_id>
  ```
- Vérifier :
  - Nombre d'artefacts Bronze stockés.
  - Nombre d'observations insérées dans la table Silver cible (`obs.price_observation`, etc.).
  - Idempotence : une seconde exécution n'insère aucune nouvelle ligne.

### 8. Contrôle Data Quality (DQ)
- Vérifier l'exécution des asset checks Dagster (SPECS §14) :
  - `provenance_complete` : 100 % des observations ont un `source_record_id`.
  - `parse_success_rate` : ≥ 99 %.
  - `required_fields_completeness` : ≥ 95 %.
  - `duplicate_rate` : < 2 %.
  - `price_range_sanity` : pas d'aberration de prix non revue.

### 9. Journalisation dans `docs/plan/PROGRESS.md`
- Mettre à jour `docs/plan/PROGRESS.md` :
  - Statut de la tâche passé à `DONE`.
  - Preuves chiffrées : nombre d'enregistrements ingérés, période couverte, nombre de produits et marchés, résultats des tests DQ.
  - Hash du commit Conventional Commit : `feat(<task_id>): connecteur <source_id>`.

---

## Règles d'or non négociables

1. **Bronze Immuable :** Ne jamais tenter de modifier ou supprimer un objet S3.
2. **Provenance 100 % :** Aucune ligne dans `obs.*` sans `source_record_id` lié.
3. **HTTP Poli :** User-Agent officiel obligatoire, respect strict des quotas `max_rps` et `PolicyStop` immédiat sur CAPTCHA/challenge.
4. **Offline Replay :** Le connecteur doit pouvoir être rejoué à 100 % depuis le Bronze sans connexion internet via `./scripts/dev.ps1 rebuild`.
