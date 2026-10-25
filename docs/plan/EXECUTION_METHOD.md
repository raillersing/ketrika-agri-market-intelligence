# Méthode d'exécution — état courant après audit du25 octobre2026

AGENTS§3.3 et le plan R restent normatifs. [Audit](../audits/2026-10-25/INDEPENDENT_AUDIT.md), [plan correctif](../audits/2026-10-25/CORRECTIVE_EXECUTION_PLAN.md). Le produit est PARTIAL, pas une succession de petites améliorations d'un produit déjà qualifié.

## Cycle utile

1. Reprendre la dernière preuve connue et le diff exact ; ne pas refaire une baseline complète après un message utilisateur.
2. Choisir le premier lot AU éligible, relié à son parent R et à ses dépendances ; résultat utilisable et critères négatifs dès le départ.
3. ADR/SPECS avant contrat ou dépendance ; un propriétaire par périmètre, worktree distinct du runtime ; SQL/S3 dédiés.
4. Développer avec lint/types et seuls tests nouveaux/impactés. Regrouper helpers, raccordements et cas d'échec dans le résultat fonctionnel.
5. Geler la source, lancer un check complet et critères SQL/S3/E2E applicables ; ne pas refaire qa si mêmes cas/minima sont prouvés dans le JUnit global. Aucun fit/seuil/gate supprimé pour accélérer.
6. Reprendre le même processus final connu, sans toucher à sa source/destination ; un changement applicatif ultérieur invalide la réception pour ce contenu.
7. Archiver les originaux et limitations, scan du delta, réception main puis mise à jour PROGRESS/miroir. Une clôture documentaire sans effet applicatif a ses contrôles ciblés, pas un nouveau check complet.
8. Passer au lot éligible suivant après réception ; ne pas lancer une phase dépendante pour contourner R0.8/R0.9 ni les jeux de données absents.

## Priorité actuelle

AU-01–07 : vérité de l'accueil/climat/offre et sécurité. AU-08–09 : historique et rebuild. Puis sources/observatoire, prévisions, agroclimat, offre et outils de décision selon le plan26 lots et les74 tâches existantes.

La complexité se mesure par couplage/données/réception, pas nombre de lignes. Les fonctions présentes mais non branchées demandent un raccordement, pas une réécriture. Les connecteurs FIRMS/GloFAS et acquisitions satellite sont de vrais manques facultatifs, à distinguer de modules en attente de données.

## Mesures et preuves

Utiliser qa-profile sur les JUnit existants, sans réexécuter les tests. Tenir par lot : contenu reçu, temps de développement/validation, nombre de réceptions et causes de reprises. Aucun gain de vitesse revendiqué sans comparaison mesurée.

Un test positif sur fixture ne prouve ni la vérité du chiffre, ni le chemin SQL réel, ni la collecte live, ni l'utilisateur humain. L'audit20261025 a trouvé des fausses valeurs malgré le check vert : ajouter des assertions de contenu, de données absentes et de reload aux parcours concernés.

[Ancienne méthode et lots R0.6](../audits/2026-10-25/history/EXECUTION_METHOD.md) conservés comme historique.
