# Reprise Silver native — lot A en développement

> Mise à jour2026-10-25 : procédure à utiliser seulement dans son périmètre reçu ; programme PARTIAL. Voir [audit indépendant](../audits/2026-10-25/INDEPENDENT_AUDIT.md) et [plan correctif](../audits/2026-10-25/CORRECTIVE_EXECUTION_PLAN.md).

Statut : préparation sur `work/r06-resilience-20261013`, pas livré sur main.
Les partitions sont implémentées ; la réception globale reste à réaliser. Ne pas
appliquer cette migration à la base active pour essayer ce runbook.

## Garanties et limites

Le run Bronze doit avoir un lot enregistré complet. Silver relit ce lot et
vérifie ses octets Bronze, sans découvrir ni télécharger de nouveau document.
L'intention Silver est committée avant les observations ; son résultat success
est committé avec elles. Une erreur ordinaire produit un résultat failed après
rollback. Un arrêt brutal peut laisser une intention sans résultat : unknown.
On ne déduit pas un succès ou un crash d'un délai ou d'un compteur de processus.

L'exclusion utilise des verrous advisory run puis source sur connexion dédiée.
Un autre worker actif est refusé immédiatement, sans modifier son run, même
s'il utilise un autre UUID pour cette source. PostgreSQL libère les verrous
à la fermeture de la connexion, notamment à la mort du processus.
Les écritures SQL externes qui ignorent le protocole ne sont pas couvertes par
cette exclusion native ; les gardes/contraintes existantes restent obligatoires.

## Entrées Python, dans Docker uniquement

- `execute_durable_silver(connector, context, batch)` : traiter un lot exact ;
  si le même lot a déjà un success cohérent, restituer son reçu sans reparsing.
- `resume_durable_silver(connector, context, previous_run_id)` : reprise explicite
  d'un lot running/failed enregistré. Source et version parser doivent être
  identiques. Crée un nouveau run, conserve l'ancien et renseigne resumed_from.
- Le contexte doit fournir le store Bronze adéquat et la source du connecteur.
  Ne pas construire ces entrées à partir d'une instruction collectée.
- `replay_document_silver(connector, context, partition_key)` : un document/version
  du registre, y compris depuis une origine success. Nouveau run partitionné,
  référence immuable d'origine conservée ; pas de collecte ni Gold automatique.

## Jobs Dagster par document

Les sources éligibles ont un job `source__document_replay` et un ensemble de
partitions dynamiques `source__document_versions`. Les clés sont des SHA de
source/SourceRecord/contenu/parser, pas des noms d'éditions inférés d'une URL.
Bronze enregistre les clés SQL dans sa transaction puis les publie dans
l'instance Dagster après commit. Un défaut de publication reste une erreur
explicite ; le registre SQL et les objets Bronze ne sont pas effacés.

Un job relit le document enregistré et utilise un nouveau run ; aucun step
Bronze n'est exécuté. Les vérifications de provenance et structure avant Gold
restent obligatoires. L'identité du traitement prix et le SHA du référentiel
réellement utilisé sont conservés dans les membres du reçu de réussite ; les
documents sans normalisation prix ne reçoivent pas d'identité prix inventée.

Aucune commande CLI de reprise n'est encore livrée. Ne pas inventer une option
de dev.ps1 ni réactiver un run par UPDATE SQL. Ne pas utiliser rebuild/reset,
ne pas supprimer de Bronze et ne pas convertir unknown en failed manuellement.

## Refus attendus

| État | Action |
|---|---|
| Worker actif | `silver_run_busy` ; ne pas marquer son run failed ni lancer un worker concurrent |
| Intention sans résultat | L'exécution directe refuse `silver_attempt_exists_resume_required` ; reprise explicite sur nouveau run |
| Run précédent success | Reprise refusée ; relire le reçu du lot d'origine |
| Lot absent/divergent ou version différente | Refus avant parse ; enquêter, sans reconstruire un reçu à la main |
| Reçu d'échec indisponible | Erreur explicite, aucun succès ; diagnostiquer la persistance avant reprise |

## Preuves à conserver

UUID d'origine/nouveau run, batch SHA et membres identiques, intention/résultat,
commandes et codes finaux, compteurs observés, zéro discover/fetch de reprise,
référence interne de normalisation et intégrité Bronze. Les tests synthétiques
SQL/S3 prouvent le mécanisme logiciel, pas une collecte institutionnelle live.
