# Réception R0.5 — cellules source, pas qualification opérationnelle

État : IN_PROGRESS. Les résultats ci-dessous ne remplacent pas le check global
courant ni son code final. Aucun tag de phase n'est autorisé par ce document.

| Critère du plan R0.5 | Preuve implémentée | Limite |
|---|---|---|
| Observation → référence → clé → octets → SHA | provenance.py, provenance_audit.py, provenance_bronze.py ; tests unitaires et SQL/MinIO | Les octets prouvent l'intégrité, pas l'authenticité institutionnelle |
| FK absente, pseudo-hash, objet absent ou altéré refusés | test_provenance.py, test_provenance_audit.py, test_gold_publication_provenance.py | Négatifs par store simulé/flux mémoire ; aucun objet réel détruit |
| Mauvaise ligne/chiffre rejetés | test_native_provenance.py, test_provenance_tables.py, test_provenance_json_lexemes.py | Coordonnées et valeurs brutes exactes ; conversions/actor-level restent distincts |
| Artefact authentique relu | tests/authentic/test_provenance_wdi.py, manifeste corpus/acquisition WDI | GDP vérifié comme artefact, jamais transformé en faux prix Silver/Gold ; H5=false |
| Objets partagés lus une fois par lot | test_provenance_grouped.py et tests de provenance | Nouveau lot = nouvelle lecture ; pas de cache cumulatif de réussite |
| Audit complet et incrémental séparés | audit_observation_provenance(mode=complete/incremental), DQ persistés | Supersessions historiques incluses dans audit complet, pas une certification implicite |
| Aucun chiffre extrait par LLM non vérifié en Gold | test_provenance_llm.py et binder/extrait/coordonnées mécaniques | Tests/replay ; aucune clé LLM ni performance opérationnelle qualifiée |
| Mauvaise provenance bloque publication | init WITH NO DATA + garde avant refresh ; intégration PostgreSQL/MinIO | Sources historiques sans preuve refusées, pas réparées avec des fixtures |
| Numérateur/dénominateur des observations publiées | increment-8-publication-result.json : 250/250 observations synthétiques | Ce ne sont pas 250 cellules individuelles ; pas une mesure de marché |
| Publication sans cache dépendant ancien, rollback partiel | ADR-028, test_gold_publication_provenance.py | Ancêtres Gold inclus dans même lot ; modèle/conversions non certifiés |

La migration 0005 et les empreintes avant/après sont archivées séparément.
Les tests de parseurs historiques conservent le vrai rejeu Silver et ses
assertions de valeurs/effectifs/révisions, puis exigent le refus Gold ou, dans
quatre cas autorisés explicitement, un Gold réellement vide, taux NULL et
effectifs 0/0 (normalisation encore manquante, BL-013). Ils ne
recertifient aucun tag T, aucune capacité native R1 ni le rebuild complet R0.8.

QA élargie courante : 327 tests / vingt intégrations, code final 0,
reçu 95241682d1be4234990838e307335fbc archivé increment-8-qa-final.

Check Windows intégral 21289 code final 0 reçu le 2026-10-10T17:27:54Z :
718 backend / 2223,69 s, zéro failure/error/skip, cinq avertissements ;
40 intégrations par dossier / 40 par marqueur / union 44.
Couvertures core 93,59968968192398 %, extraction 86,3768115942029 %,
normalize 84,85523385300668 % ; lint/format 198 fichiers, types 197 codes 0.
Frontend 35 tests / quatre suites / 7,13 s ; reçu
84bc6869-c602-4f04-95c9-c82e3408bdc4, lint/types/tests/build codes 0,
build 214764 ms. Empreintes actives finales identiques, reçu séparé archivé.
À recevoir avant clôture : scan staged et commit atomique. PROGRESS et plan R restent canoniques.
