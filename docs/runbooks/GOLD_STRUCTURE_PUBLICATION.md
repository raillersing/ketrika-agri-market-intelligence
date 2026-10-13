# Publication Gold : contrats de structure explicites

ADR-061, développement lot B. Aucun contrat public n'est qualifié par les
tests synthétiques. Le registre par défaut est vide : un candidat sans
déclaration source/parseur/MIME est refusé, jamais accepté implicitement.

## Déclarer un format

Dans `core/schema_contracts.py`, ajouter une déclaration versionnée à
`DEFAULT_SCHEMA_CONTRACT_REGISTRY`, après examen explicite d'un document
de référence autorisé et consignation de sa preuve dans la fiche source.
Utiliser `SchemaContractBinding(source_id, parser_version, mime_type, contract)`.
Les contrats existants sont `CSVSchemaContract` (colonnes requises/options,
délimiteur) et `JSONSchemaContract`/`JSONShape` (forme fermée et types).
Version de contrat distincte de version de parseur. Aucun wildcard ni lecture
du Bronze pour apprendre la baseline ; `allowed_fields` n'est pas un contrat.

Une nouvelle version de parseur ou un MIME différent exige une déclaration
exacte. Les déclarations historiques peuvent coexister avec celles du format
actuel. Ne pas reclasser/réécrire les anciens SourceRecord ni leurs octets.
La déclaration atteste une structure attendue, pas l'authenticité, les droits,
la fraîcheur, les conversions ou la validité du modèle économique.

## Contrôle de publication

`refresh_gold_views` inclut les ancêtres Gold, sélectionne les candidats de
provenance sous LOCK SHARE puis capture leurs SourceRecord. Structure fraîche
mesurée par source sur ces seules références ; tous les audits précèdent
le premier REFRESH. Les lignes superseded et prix pending/non normalisés
ne deviennent pas candidats ; audit historique Dagster les conserve.

Source inconnue/parseur non déclaré, dérive, octets illisibles, SHA invalide
refusent le lot. `GoldSchemaRejected.receipts` expose les diagnostics fixes,
sans texte collecté. `ops.dq_result` porte schema_drift et scope
publication_candidate_artifacts. Le helper ne commit pas : si le caller
rollback, le reçu disparaît. Ne pas revendiquer une journalisation durable
après rollback ; un caller peut explicitement conserver le diagnostic.

Succès : `structure_state`, `structure_dq_ids`, `structure_artifacts_total`,
`structure_artifacts_valid`, `structure_scope` séparés de provenance.
Empty et metadata_only n'attestent pas de structure vérifiée, effectifs zéro.
Un override historique de check Dagster ne permet pas le refresh direct :
il faut aussi une déclaration du registre commun.

## Validation et sécurité

Tests synthétiques déclarent des formes code-owned avant inspection et isolent
le registre par scénario ; aucune exception produit basée sur dummy/fixture.
Les refus vérifient zéro REFRESH et préservation des caches/Silver/Bronze.
SQL/S3 exclusivement dans le profil de qualification dédié ; aucune migration,
aucun rebuild/restore/reset ni modification de la destination active.
La garde ne corrige pas BL-016 et ne qualifie pas les sources live.
