# IROOA — R7 : Production Readiness & Operational Excellence

2026-11-24 — Orientation approuvée par le porteur du projet. Extension de réception opérationnelle, distincte des 74 tâches R0–R6. Aucune tâche R7 reçue à ce stade. Les gates H1–H7 et les interdits d'AGENTS.md restent applicables ; aucune activation ni accès aux données actives n'est induit par ce document.

## Périmètre et ordre

La sécurité et l'exploitation peuvent progresser en parallèle des travaux métier sur des environnements isolés. R0.9 reste le premier MUST R0–R6. Les critères ci-dessous sont des cibles proposées de recette, non des mesures observées.

| ID | Priorité | Statut | Livrable / preuve requise |
|---|---|---|---|
| R7.01 | P0 | TODO | Audit OWASP ASVS : matrice applicable et corrections vérifiées ; aucune vulnérabilité critique/haute non traitée. |
| R7.02 | P0 | TODO | Matrice RBAC et tests négatifs par rôle, isolation des données, revue des ACL historiques B-R098. |
| R7.03 | P0 | TODO | Inventaire des secrets, rotation contrôlée et absence de secrets dans les artefacts ; aucun secret actif lu par l'agent. |
| R7.04 | P0 | TODO | Sauvegardes quotidiennes chiffrées hors VPS, rétention et contrôles d'intégrité, sans suppression de Bronze. |
| R7.05 | P0 | TODO | Restauration sur clone PostgreSQL et stockage objet ; RPO <=24 h, RTO <=4 h mesurés. |
| R7.06 | P0 | TODO | Préflight des migrations et validation sur clone, plan de retour arrière compatible avec les données. |
| R7.07 | P0 | TODO | Staging isolé : réseau, bases, identités, buckets et secrets distincts. |
| R7.08 | P1 | TODO | CI/CD reproductible, SHA/digests figés, rollback démontré hors production. |
| R7.09 | P1 | TODO | Supervision réelle des services, fraîcheur, ressources, latence et disponibilité ; SLO cible 99,9 % mensuel. |
| R7.10 | P1 | TODO | Journaux assainis et alertes testées en capture locale ; aucun destinataire réel sans gate. |
| R7.11 | P1 | TODO | Tests de charge sur staging, P95 API <1 s sur endpoints qualifiés et capacité mesurée. |
| R7.12 | P0 | TODO | Vérifier l'isolation des ressources, réseau, domaines et limites avec Casino-MDG sur l'hôte partagé. |
| R7.13 | P1 | TODO | Runbooks d'incidents, reprise, exercice de panne et procédures d'escalade. |
| R7.14 | P1 | TODO | Recette métier humaine explicite sur fonctionnalités qualifiées, pas de substitution par fixtures. |
| R7.15 | P1 | TODO | Documentation d'exploitation, limites, responsables et registre de preuves. |
| R7.16 | P0 | TODO | Revue go/no-go, version immuable, déploiement progressif après gates applicables, vérifications post-déploiement et rollback. |

## Réception

- Staging : aucun engagement client ; preuves isolées.
- Pilote : uniquement capacités qualifiées, sécurité, sauvegardes/restauration, supervision et rollback reçus ; signaler les limites et désactiver les fonctionnalités non qualifiées.
- Institutionnel : tous les MUST R0–R6, R6.11 et R7 applicables reçus, performances et sécurité mesurées, revue humaine et déploiement effectivement constatés.
- Une CI verte n'atteste ni une source live, ni un modèle de marché, ni la disponibilité du VPS.
- Aucune modification active sans préflight, sauvegarde vérifiée, procédure de retour et gates applicables. Aucune qualification déduite de cette documentation.

Références externes : [Google SRE — Launch checklist](https://sre.google/sre-book/launch-checklist/), [Production launch planning](https://sre.google/resources/practices-and-processes/production-launch-planning/). Les objectifs numériques sont des choix de recette IROOA.
