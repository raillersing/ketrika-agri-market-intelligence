# AU-04 — réception logicielle du26 octobre2026

Source figée `2a6ec4e0d72c28afc007accfec50269c4627ddf0`, empreinte `1adbd671c8bfbe1300b570902bb94d0201952ddefb2bf8e15f7ca5790b643493`. Aucun changement de source pendant réception. Base reçue7924600 ; auth additive0019 et contrats ADR123.

## Preuves originales

- Backend :2439 tests, zéro échec/erreur/skip ;168 intégrations, inventaire exactement égal au JUnit. Couvertures core92,4205%, extraction87,7660%, normalize88,2151%. Les trois originaux sont conservés gzip, non remplacés par des compteurs.
- Frontend : exécution47aba285-0ded-454b-9ee3-a58e46a96bd1,57 tests/neuf suites, lint/typecheck/build tous code0. Reçu natif et JSON Vitest conservés ; image/commit/empreinte relus par qualification_reports check-frontend.
- Navigateur :15 scénarios explicites,310,806s, zéro exception JS ; anonyme401/prix authentifiés200, formulaire réel/HttpOnly/reload/profil/proxy, cookie arbitraire et cookie révoqué refusés, logout et rejeu du JWT, navigation mobile/Escape/390px. Reçu natif stdout conservé sans modification ; trace brute non publiée car elle contient une session synthétique, SHA indiqué dans le reçu.
- Les validations des originaux backend/frontend ont été reprises à leur première preuve manquante, sans rejouer leurs suites vertes. Le navigateur a été exécuté après restauration du seul proxy Docker/WSL ; moteur, applications et données actives conservés.

## Identité et portée

Profil `ketrika-qualification-main-final`, DB/bucket/réseau/volumes dédiés, images exactes dans les reçus. Aucun test sur DB/S3 actifs, aucun changement de corpus ni envoi externe. Migration0019 sur QA uniquement. Les deux intégrations SQL ciblées et les contre-exemples unitaires initiaux restent conservés, y compris le premier rouge corrigé avant gel.

AU-04 est reçu logiciellement sur cette branche. Main/runtime ne sont pas encore modifiés par cette réception ; l'activation et sa migration additive exigent une étape distincte. Cela ne qualifie ni un déploiement, ni la collecte de sources, ni les modèles de marché, ni le programme R0.8 complet.
