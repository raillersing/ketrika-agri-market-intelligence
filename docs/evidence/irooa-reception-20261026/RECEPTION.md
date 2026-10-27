# AU-06, AU-07 et Navigation Irooa — réception logicielle du 26 octobre 2026

**Clarification de traçabilité du27 octobre2026 (DP-0) :** les originaux backend
et frontend de ce dossier portent le commit `4e455ed` et l'empreinte
`cf7cf73dad71a496ca11306704066db7c1d6fe09319279d4be99643c2572e624` ; le reçu
navigateur porte `cd77a26` et l'empreinte `79205eca5139574880ed60f765a9e47fd8c80812b6c675e6198b555348a39680`.
Ce dossier regroupe donc des preuves de deux gels et ne constitue pas un check
complet unique de `cd77a26`. La formulation historique ci-dessous ne réétiquette
aucun original ; les effectifs et statuts historiques sont conservés. Le nouveau
contenu applicatif DP-1 doit recevoir son propre check complet et ses E2E exacts.
Comparaison : [identités des reçus](../data-product-research-20261027/receipt-bindings.json).

Source figée `cd77a26194cef60c1dbb456a94ba38bf68d38461`, empreinte `79205eca5139574880ed60f765a9e47fd8c80812b6c675e6198b555348a39680`. Base reçue `a0fac30` ; dépendances actualisées, gardes de restauration avec fidélité des ACL, navigation accessible, thèmes clair/sombre Irooa, page publique `/about` et bytecode Python optimisé. Contrats et ADRs : ADR-124, ADR-125, ADR-126, ADR-127, ADR-128, ADR-129, ADR-130.

## Preuves originales

- **Backend :** 2464 tests, zéro échec / erreur / skip ; 168 intégrations, inventaire exactement égal au JUnit. Couvertures `core` 92,4205 %, `extraction` 87,7660 %, `normalize` 88,2151 % (toutes ≥ 80 %).
  - Résolution de B-R090 : l'activation de `uv --compile-bytecode` (ADR-130) et des environnements `r05` a réduit les latences d'importation de 29,281 s à 10,172 s. La contre-épreuve de révocation de session inter-processus réussit en 18,93 s (seuil 30 s inchangé) et la latence P95 de `/v1/products` reste sous 1000 ms.
  - Les originaux JUnit (`backend-tests.xml.gz`), inventaire (`backend-inventory.json.gz`) et couverture (`backend-coverage.json.gz`) sont archivés dans ce répertoire.
- **Frontend :** 68 tests dans 11 suites, lint / typecheck / build tous code 0 (exécution `c6a7d771-7845-4542-a77c-3d93d24e3479`). Pile mise à jour : Next.js 15.5.28, React 19.3.1, Vitest 5.0.5, MapLibre GL 6.16, ECharts 6.1. Audit npm : 0 avis critique ou élevé applicable.
  - Le reçu natif (`frontend-receipt.json`) et le rapport Vitest (`frontend-tests.json.gz`) sont archivés.
- **Navigateur (Playwright E2E) :** 19 scénarios explicites, 443,711 s, zéro exception JS (exécution `62ab1a8b7cb64e27bca4482aa7587b79`).
  - Thème clair / sombre persistant après rechargement et sur pages publiques ;
  - Identité Irooa et Ketrikay sur la page publique `/about` sans exposition des données métier ;
  - Redirection de l'interface protégée sans session ; rejet et nettoyage d'un cookie arbitraire ;
  - Authentification formulaire établissant le cookie `session_token` HttpOnly ; rétention après reload ; profil authentifié ;
  - Appel API prix same-origin authentifié ;
  - Navigation de bureau hiérarchisée par tâches, groupant la gestion des données et marquant la page courante ;
  - Palette de commande / recherche de pages au clavier (`Ctrl+K`, navigation réelle, restauration du focus) ;
  - Explorateur de prix rendu sans anomalies visuelles ;
  - Page Économie rapportant explicitement l'état non qualifié après reload sans tableau fictif ;
  - Responsive mobile 390 px sans débordement de contenu, avec tiroir de navigation mobile accessible, fermeture par Escape et piège de focus ;
  - Déconnexion par l'interface supprimant le cookie de session, rejet immédiat des requêtes API après logout, rejet de la réutilisation du jeton révoqué, rejet et nettoyage d'un cookie révoqué restauré, interface protégée après déconnexion.
  - Captures (`prices.png`, `economy.png`, `economy_mobile_390px.png`) et reçu natif (`browser-receipt.json`) archivés ; trace Playwright SHA-256 `bbd1838736a8ad1e950fc5275fecf90e879d20259af5f2a665ac32dec12ea325` conservée dans le volume navigateur isolé.
- **Restauration de base de données (AU-07) :**
  - Vérification de la cible : refus strict de restauration sur une base active ou déjà existante sans clone explicite consenti ;
  - Tout code de sortie non-zéro de `pg_restore` est fatal et annule la transaction ;
  - Préservation intégrale des propriétaires et privilèges/ACL SQL (options `--no-owner` et `--no-privileges` retirées conformément à ADR-126) ;
  - Démonstration sur cluster isolé `ketrika-restore-audit-20261026-db` avec 78 tables, 17542 lignes et comparaison des empreintes SHA-256 et droits effectifs.

## Statuts et portée

- **AU-06 :** DONE (logiciel `cd77a26`, 68 frontend / 2464 backend / 19 E2E, audit npm et pip-audit sans vulnérabilités critiques applicables).
- **AU-07 :** DONE (logiciel `cd77a26`, gardes d'échec effectifs, fidélité ACL et tests de clone réussis).
- **B-R090 :** RESOLVED_FIXED (optimisation bytecode et r05, suites complètes vertes sans dérogation de seuil).
- **Limites conservées :** ce lot clôture les exigences logicielles des lots AU-06 et AU-07. Il ne qualifie ni de nouvelles données de marché live, ni la réparation historique du ledger Bronze (AU-08), ni la reconstruction intégrale hors ligne (AU-09). Les statuts R restent régis par leurs critères normatifs.
