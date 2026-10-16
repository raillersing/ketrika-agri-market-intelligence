# Audit Antigravity R1–R2 — réception refusée en l'état

## Périmètre et résultat

Worktree observé : `/home/raillersing/projects/ketrika-qa-worktrees/r1-sources-prep`,
branche `work/r1-sources-prep`, HEAD `6f11f5d` (code R2.10 `bb62799`).
Une modification non committée de PROGRESS appartient à Antigravity et reste intacte.
Audit ciblé de code/contrats/preuves, complété par deux probes Docker readonly,
sans réseau, base ni S3. Ce n'est ni un audit exhaustif ni une réception globale.

Des livrables utiles existent : connecteurs, contrats macro, couverture, fiches
métriques, API/CSV et vue économie à cinq dimensions. Ils sont conservés.
Leurs statuts locaux DONE/QUALIFIED ne sont pas acceptés sur main : les écarts
ci-dessous touchent les principes de provenance et les critères de réception.

## Écarts prioritaires

### P0 — chiffres macro publiables sans contrôle de provenance

`backend/src/ketrika/gold/provenance_gate.py`, VIEW_TABLES :
`economic_dashboard: frozenset()` ; la fonction retourne `metadata_only` avant
toute requête. Pourtant `gold/sql/014_economic_dashboard.sql` sélectionne des
valeurs et variations depuis `obs.macro_observation`.
Probe réelle du garde : `economic_gate_state=metadata_only, sql_calls=0`.
Aucune politique macro dans `core/provenance_audit.py` observée sur cette branche.

**Correction :** définir binder/politique/audit macro et contrôle structurel,
inclure les observations contributrices dans les gardes avant refresh et dans
les projections rebuild. À défaut, refuser explicitement la publication macro.
Tester sur SQL/S3 isolés une preuve valide, absente, falsifiée et des octets
corrompus ; refus avant publication, pas de contournement par liste vide.

### P1 — documents générés présentés comme archives institutionnelles

`tests/fixtures/instat_nipc/generate_authentic_fixtures.py` crée les indices avec
des formules de tendance/saisonnalité et inscrit une mention de libre réutilisation.
`tests/fixtures/instat_tbe/generate_authentic_tbe_fixtures.py` construit aussi
les valeurs et leurs révisions. `docs/evidence/R1.3/README.md` les décrit pourtant
comme fichiers institutionnels et observations authentiques.

**Correction :** conserver ces fixtures, mais les qualifier synthetic et retirer
les affirmations d'acquisition/droits non prouvées. Ne pas régénérer ou modifier
des archives Bronze. Obtenir séparément octets originaux, URL vérifiée, reçu HTTP,
SHA, droits et annotation indépendante pour qualifier une source réelle.
R1.13 ne peut pas déduire sept sources live opérationnelles de ces tests.

### P1 — faux positif d'authenticité du pilote

`core/pilot.py:check_pilot_authenticity` utilise la source autorisée et un préfixe
de natural_key. Une clé hachée de fixture ne commence pas par synthetic/test_.
Probe : retour SQL simulé `(wb_rtfp_mdg, a*64, 1)`, sans reçu ni octets ni droits,
donne `is_authentic=True, status=QUALIFIED_AUTHENTIC`.

**Correction :** exiger une chaîne d'acquisition/authenticité vérifiable liée
aux SourceRecords réellement utilisés. Une source reconnue ou review_status
accepted ne prouve pas l'origine des octets. Sans preuve : unverified/partial,
jamais QUALIFIED_AUTHENTIC. Tester une fixture au nom de source officiel et à
natural_key hachée, plus une archive réellement qualifiée.

### P1 — variations SQL mélangent grains, unités et sources

Dans `014_economic_dashboard.sql`, les auto-jointures p1m/p12m utilisent uniquement
indicator_code, geo_scope et period_month. Elles ignorent source, fréquence et
unité ; plusieurs observations quotidiennes d'un même mois peuvent multiplier
les lignes et comparer des séries distinctes. Le contrôle de base dans CASE ne
rétablit pas un grain correct. Constat statique, pas mesure d'une base réelle.

**Correction :** spécifier un grain explicite par indicateur, préserver la
fréquence native, séparer les sources/unités/bases et borner les agrégations
justifiées. Test SQL avec plusieurs jours, deux sources, deux unités et une
rupture de base : aucune multiplication, aucune variation incompatible.

### P1 — provenance et type de valeur perdus dans la réponse économique

La vue ne sélectionne pas observation_id/source_record_id ;
`api/schemas.py:IndicatorObservationOut` n'expose pas observation_id ni
observed_or_imputed, contrairement à la page économie qui attend ces champs.
Le lien ProvenanceLink n'apparaît que si observation_id existe : il peut donc
disparaître pour toutes les valeurs, sans erreur de typage front locale.

**Correction :** relier chaque valeur aux observations contributrices et objets
source, transmettre son type réel, adapter OpenAPI/types/front ensemble. Une
valeur agrégée doit garder toutes ses références, pas une observation arbitraire.
Valider API → chiffre UI → provenance → document → reload avec valeurs exactes.

### P1 — filtres calendaires non liés ; erreurs SQL masquées en absence de données

`gold/coverage.py` construit `:from_month::date` et `:to_month::date`.
Probe sur le SQL réellement construit : `declared_binds=[]`, alors que les
paramètres fournis sont from_month/to_month. Le cast doit être explicite via
CAST(:from_month AS date) ou un paramètre date typé.
`gold/economic.py:query_economic_dashboard_from_db` attrape toute exception et
retourne [] : une panne SQL devient un tableau vide plutôt qu'une erreur visible.

**Correction :** tester les filtres dans PostgreSQL réel ; propager une erreur
applicative expurgée pour l'indisponibilité, réserver no_data à une requête
réussie sans résultat. Vérifier l'API et l'affichage d'erreur, pas seulement mocks.

### P1 — réception et statuts surestimés

R2.10 appelle « non-régression globale » une sélection de143 tests backend ;
ses quatre nouveaux tests web vérifient proxy/formatters, pas le rendu de page.
Le script Playwright modifié ne constitue pas un reçu d'exécution navigateur.
Le dossier ne fournit pas la réception complète et le parcours exigés par R2.10.
Le tag local mi-r1-qualified est observé, mais n'est pas accepté comme preuve.

**Correction :** distinguer implémenté/testé hors ligne/live vérifié/accepté.
Conserver les preuves et tags historiques, sans déplacer ni supprimer un tag
publié ; publier une rectification et suspendre les nouvelles qualifications
non étayées. Une seule réception complète du lot corrigé stabilisé, avec
JUnit lié au commit, couvertures, frontend/build et vrai parcours Playwright.

## Ordre de correction et intégration

1. Sur le worktree Antigravity uniquement, figer l'état applicatif et conserver
   le journal non committé ; rectifier les revendications de données réelles.
2. Fermer le contournement Gold et la qualification du pilote sans preuves.
3. Corriger grains/jointures, provenance/type API et erreurs/filtres SQL ensemble.
4. Réconcilier les ADR : ses069–072 désignent d'autres décisions que celles de
   main. Réserver des IDs libres, mettre à jour références SPECS/code/rapports ;
   ne pas écraser les décisions069–074 déjà reçues par le coordinateur.
5. Réconcilier ses migrations/gardes avec le chemin JSON WB natif et les lots
   durables de main ; ne pas remplacer notre parseur JSON par le seul CSV.
6. Réception complète sur source figée puis audit d'intégration. Aucun merge
   global de cette branche avant ces corrections ; aucun statut R1/R2 DONE
   importé automatiquement dans le plan canonique.

Codex poursuit séparément la réception du correctif R0.8 `8de251f`, dont la
suite complète78714 a terminé code0 (1725 backend,35 frontend/build).
Les travaux sûrs de préparation peuvent continuer ; aucun gate final anticipé.
