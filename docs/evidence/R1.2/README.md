# Dossier de preuve R1.2 : Découverte de catalogue, pagination bornée et protection anti-SSRF

## 1. Contexte et Objectifs

La tâche **R1.2** s'inscrit dans le programme de requalification R0–R6 de Ketrika Agri Market Intelligence.
Elle porte sur la mise en place d'un moteur générique et sécurisé de découverte de catalogues, index, flux RSS/Atom et APIs pour les sources documentaires (INSTAT, ODR, MinCC, FAO, etc.), conforme aux règles **C1**, **C3** et aux spécifications **SPECS §9, §12**.

### Exigences contractuelles R1.2 :
1. **Protection stricte anti-SSRF & validation des URLs candidates :**
   - Blocage systématique des cibles localhost, loopback (`127.0.0.0/8`, `::1`), adresses privées RFC 1918 (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), link-local IPv4/IPv6 (`169.254.0.0/16`, `fe80::/10`), métadonnées cloud (`169.254.169.254`, `metadata.google.internal`), et suffixes internes (`.internal`, `.local`, `.lan`).
   - Contrôle préventif des domaines autorisés (`allowed_domains`) sur chaque URL candidate.
   - Blocage strict des rebonds de redirection HTTP : vérification de l'URL cible de l'en-tête `Location` avant émission de la requête suivante.
2. **Découverte de catalogue et pagination bornée :**
   - Parcours de catalogues HTML avec pagination bornée (`max_pages <= 20` par sécurité, par défaut 5 pages).
   - Détection des cycles de pagination pour éviter les boucles infinies.
   - Parsing rapide et robuste via `LexborHTMLParser`.
   - Prise en charge des flux RSS/Atom (éléments `<link>`, `<enclosure>`, `<pubDate>`).
3. **Suivi durable des éditions et traçabilité :**
   - Suivi ETag / Last-Modified / SHA-256 du contenu.
   - Gestion du statut HTTP 304 (Not Modified) conservant le lien connu sans création d'artefact redondant.
   - Détection de nouvelles versions si le contenu change pour une même URL (`content_sha256` ou ETag distinct).
   - Discrimination explicite des états d'ingestion :
     - `NEW_EDITIONS_AVAILABLE`
     - `NO_NEW_EDITION`
     - `DISCOVERY_FAILED`
     - `EMPTY_PARSING`
   - Reprise sans doublon après interruption (`filter_known_editions`).

---

## 2. Architecture et Composants Implémentés

### 2.1 Moteur de politique & anti-SSRF (`backend/src/ketrika/core/policy.py`)
- Fonctions ajoutées :
  - `is_loopback_target(hostname: str) -> bool` : identification stricte du loopback local.
  - `is_forbidden_network_target(hostname: str, allow_loopback: bool = False) -> bool` : analyse fine d'IP et de noms d'hôtes (privé, link-local, cloud metadata, suffixe interdit).
  - `validate_candidate_url(url: str, allowed_domains: Any = None, allow_loopback: bool = False) -> str` : validation de l'URL avant toute tentative réseau, levant `PolicyStop` en cas de violation.

### 2.2 Client HTTP avec vérification des sauts de redirection (`backend/src/ketrika/core/http.py`)
- `PoliteHttpClient` :
  - Vérification de l'URL candidate sur chaque appel `get()` ou `head()`.
  - Vérification de l'URL de redirection `Location` avant de suivre le saut (interdiction des attaques SSRF par rebond).
  - Isolation du mode test via `allow_loopback: bool` (pilotable par la variable d'environnement `KETRIKA_ALLOW_TEST_LOOPBACK=1`), maintenant toujours le blocage des métadonnées cloud et adresses link-local.

### 2.3 Moteur de découverte et classification (`backend/src/ketrika/connectors/discovery.py`)
- Modèles et énumérations :
  - `DiscoveryStatus(StrEnum)` : énumération stricte des états de découverte (`new_editions_available`, `no_new_edition`, `discovery_failed`, `empty_parsing`).
  - `DiscoveredEdition` : conteneur typé avec lignée parente (`parent_url`), identifiant d'édition, conditional headers (`etag`, `last_modified`), `content_sha256` et conversion ascendante `to_discovered_item()`.
  - `DiscoveryResult` : synthèse du crawl (statut, nombre de pages scannées, éditions nouvelles et inchangées, erreurs).
- Moteurs :
  - `CatalogDiscoveryEngine` :
    - `discover_html_editions(...)` : crawl borné de pages HTML, extraction des liens d'éditions selon regex, détection de cycle, support des en-têtes conditionnels 304.
    - `discover_rss_editions(...)` : extraction d'éditions depuis un flux RSS ou Atom XML.
    - `filter_known_editions(...)` : comparaison avec l'historique connu pour filtrer les doublons et détecter les mises à jour de contenu.
- Helper de classification :
  - `classify_ingestion_outcome(discovery_result, parse_result) -> DiscoveryStatus` : qualification déterministe du résultat global de découverte et de parsing.

---

## 3. Preuves d'exécution et de validation

### 3.1 Suite de tests unitaires (`backend/tests/unit/test_edition_discovery.py`)
- Commande exécutée dans le conteneur Docker `ketrika-backend:dev` :
  ```bash
  uv run pytest -v tests/unit/test_edition_discovery.py
  ```
- Résultat :
  ```text
  tests/unit/test_edition_discovery.py::test_ssrf_rejection_for_forbidden_targets PASSED [ 12%]
  tests/unit/test_edition_discovery.py::test_domain_whitelist_enforcement PASSED [ 25%]
  tests/unit/test_edition_discovery.py::test_ssrf_redirect_is_blocked_before_emission PASSED [ 37%]
  tests/unit/test_edition_discovery.py::test_html_discovery_bounded_pagination PASSED [ 50%]
  tests/unit/test_edition_discovery.py::test_html_discovery_handles_304_not_modified PASSED [ 62%]
  tests/unit/test_edition_discovery.py::test_rss_feed_discovery PASSED     [ 75%]
  tests/unit/test_edition_discovery.py::test_filter_known_editions_and_deduplication PASSED [ 87%]
  tests/unit/test_edition_discovery.py::test_classify_ingestion_outcomes PASSED [100%]
  ====== 8 passed in 9.31s ======
  ```

### 3.2 Vérification du style de code (Ruff)
- Commande :
  ```bash
  uv run ruff check src/ketrika/core/policy.py src/ketrika/core/http.py src/ketrika/connectors/discovery.py tests/unit/test_edition_discovery.py
  ```
- Résultat :
  ```text
  All checks passed!
  ```

### 3.3 Vérification statique des types (Mypy)
- Commande :
  ```bash
  uv run mypy src/ketrika/core/policy.py src/ketrika/core/http.py src/ketrika/connectors/discovery.py tests/unit/test_edition_discovery.py
  ```
- Résultat :
  ```text
  Success: no issues found in 4 source files
  ```

---

## 4. Garanties de non-régression et isolement
- Aucune mutation de la base de qualification active (`ketrika-qualification-*`).
- Travail cantonné au worktree isolé `/home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep`.
- Respect total des contrats d'isolation et d'architecture sans effet de bord.
