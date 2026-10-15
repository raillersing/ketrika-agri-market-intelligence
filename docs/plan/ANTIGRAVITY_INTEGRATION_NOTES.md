# Note d'intégration ciblée pour Antigravity — 2026-10-15

Objectif utilisateur : version minimale fonctionnelle, pas de perfectionnement
sans effet utile. Poursuivre les lots, conserver les tests et les composants
existants ; ne pas réimplémenter les parcours déjà livrés par Codex.

## Une correction d'intégrité nécessaire, sans refaire le code

Lecture seule de `work/r1-sources-prep` / `d6057fe` :

- `backend/tests/fixtures/instat_nipc/generate_authentic_fixtures.py`, lignes1–5,
  nomme les classeurs "authentic". Les lignes68–73 calculent les indices depuis
  une tendance et une saisonnalité choisies dans le script.
- Ces classeurs sont donc **synthétiques**, pas des documents INSTAT acquis.
  La mention légale écrite en celluleA5 n'est pas une preuve de licence.
- Conserver les fixtures et leurs tests, mais corriger les libellés/script et
  rapports/goldens correspondants : synthetic, logiciel testé, pas qualification
  de source authentique. Ne pas supprimer les tests ni inventer de reçu HTTP.
- Si les originaux institutionnels existent séparément, fournir leurs octets,
  URL acquise, date, SHA et droits ; ne pas reconstruire leurs valeurs par formule.
  Sinon conserver la qualification réelle partielle/bloquée tout en livrant le code.

## Compatibilité et coordination minimale

- Le connecteur WB R1.8 v1.1.0 reste CSV. Le paquet officiel acquis par Codex est
  JSON large, avec `c_rice` et des métadonnées séparées ; le parcours fonctionnel
  `connectors/rtfp_json.py` v2.0.0 résout le contexte depuis le batch immuable.
  Garder les deux chemins/versionnements ; ne pas remplacer ce parcours par le CSV.
- Les scénarios simulés ou `ctx.offline` qui fabriquent une entrée Bronze sont
  utiles, mais ne prouvent pas le rejeu de la chaîne SQL complète. Ne pas les
  renommer "collecte live" ou "qualification source".
- Les statuts R1 de la branche restent à rapprocher du plan et des gates main ;
  ne pas écraser PROGRESS/plan main avec leurs versions historiques de branche.
- Codex garde R0.8/R0.9 et la réception SQL/S3 partagée. Check Windows11394 en cours
  sur source7154d92 : aucune suite mutante concurrente sur ketrika-qualification.
  Worktree R1/UI/tests en cours laissés intacts par Codex.

Ce relevé est ciblé, pas un audit exhaustif des70 fichiers. Les autres critères
restent ceux du plan ; aucun nouveau seuil ou raffinement n'est demandé ici.
