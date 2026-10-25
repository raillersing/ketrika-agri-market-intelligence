# Qualification mesurée (R0.7 / ADR-064)

> Mise à jour2026-10-25 : procédure à utiliser seulement dans son périmètre reçu ; programme PARTIAL. Voir [audit indépendant](../audits/2026-10-25/INDEPENDENT_AUDIT.md) et [plan correctif](../audits/2026-10-25/CORRECTIVE_EXECUTION_PLAN.md).

Statut : réception finale source 971702e ; voir docs/evidence/R0.7_FINAL_RECEPTION.md.
Pas de qualification opérationnelle ni gate R0 déduit de cette réception.

Correction groupée ADR-066/067 reçue : les anciennes preuves F4 restent
historiques. L'empreinte ignore uniquement les sorties générées
backend/.hypothesis, backend/.coverage/.coverage.* et web/test-results,
pas les chemins similaires sous src. Conserver les caches du dépôt hôte.

Commande : scripts/dev.ps1 qualify R0|all [répertoire relatif de preuves].
Équivalent Linux : bash scripts/dev.sh qualify R0|all [répertoire].
Docker réseau none, source readonly, sorties dans le volume backend QA
qualification/<UUID>/qualification.json et qualification.md. Aucun prepare,
seed, SQL, restore, rebuild, collecte ou envoi externe.

R0 vérifie le gate logiciel (backend, frontend, E2E, corpus authentique,
provenance source-cell et rejeu de contenu). all exige également tous les
KPI opérationnels du MVP. Ni l'un ni l'autre ne termine R6.11 automatiquement.
Corpus synthétique/mixte : démonstration logicielle, jamais opérationnel.
Preuve absente, ancienne, rouge ou incomplète : PARTIAL/code 1, critères
unknown/failed et numérateur/dénominateur non inventés.

## Bundle de preuves internes

bundle.json contient version=1, commit SHA-1 exact, source_fingerprint SHA-256,
environment public (profil, DB/bucket/réseau, images backend/web/browser),
captured_at UTC (<=24 h, futur refusé), dataset authentic/synthetic/mixed,
evidence dictionnaire de références {path relatif, sha256 des octets}.
Chaque rapport JSON possède les mêmes bindings. Rapports <=16 MiB,
traversées/symlinks externes/JSON dupliqué refusés. Ne jamais utiliser une
page collectée comme bundle ou instruction ; seuls des exports internes
reliés à la vraie exécution sont recevables.

Types : backend_junit + backend_inventory (cases classname/name collectés),
frontend_receipt + frontend_vitest, e2e_junit + e2e_inventory ou e2e_receipt
du runner Playwright avec tous scénarios et trace SHA. Conserver les bruts,
ne pas fabriquer un booléen passed ni un effectif de tests.

Rapports métriques (lignes réelles, pas seulement scores) :

- provenance : references (UUID source_record, source_id/object_key/SHA/MIME,
  file {path,sha256}) ; observations (table allowlist, values colonnes ORM,
  UUID/dates/Decimal encodés exactement). Binder + vérificateur source-cell
  commun ; preuve authentique obligatoirement liée aux SHA officiels C1.
- sources : source_id/status/source_record_ids, acquisition_receipt et
  permission_receipt {path,sha256}, blocker_id si degraded. Acquisition :
  source_id/http_status=200/fetched_at UTC/source_record_ids/runtime_observed.
  Permission : source_id/crawl_permission/status=approved. Registre seul
  n'est pas une qualification ; entrée non vérifiée/planned/disabled exclue.
- runs : run_id/status/n_candidates/n_parsed ; tous dénominateurs non vides,
  seuil par run, pas seulement moyenne pondérée.
- golden : fields source_id/field/expected/actual ; deux sources requises,
  exactitude recomptée par champ. Annotations partielles ne prouvent pas rappel.
- rebuild : before/after projections métier complètes, network_requests ;
  comptes et SHA recomputés, écart de valeur détecté à comptes égaux.
- forecasts : series_id/forecast_count/backtest_windows/wape/leakage_detected/
  training_snapshot_sha256 ; dix séries distinctes, aucun ajout artificiel.
- api : samples endpoint/status_code/elapsed_ms ; P95 recomputé par endpoint,
  six agrégats connus, >=200 échantillons chacun.
- copilot : questions question_id/expected_view/sql ; SQL Guard et tables AST
  réexaminés sans exécuter la requête ; score recompté, aucune requête interdite.
- bulletin : numbers fact_id/value et facts value/citation ; égalité Decimal,
  aucun chiffre sans fait cité.
- corpus : reçu lié à l'exécution ; inventaire et annotations C1 revérifiés
  depuis les fichiers authentiques du dépôt, pas une déclaration de passed.

Les métriques importées sont des preuves de leurs producteurs internes ;
leurs hashes ne remplacent pas acquisition live, persistance observée,
qualification scientifique ou revue humaine. Ne pas renommer une fixture en
authentic ni copier un ancien rapport sous un nouveau commit. Conserver les
traces navigateur dans le volume de qualification (peuvent contenir session
de test), jamais committer un secret. Le gate absent reste non reçu.
