# R0.6 lot B — préparation de publication sûre

Audit statique du 2026-10-13. Aucun contrat nouveau adopté, code ou test
implémenté par ce document. Réception du lot A 459f5a2/27517 encore en cours.

## Écarts confirmés dans le code actuel

- `gold/refresh.py` utilise `require_gold_provenance` avant les REFRESH,
  mais ne vérifie pas la structure des documents. Un appel direct échappe
  donc aux checks Dagster de structure.
- `pipelines/schema_check.py` utilise `audit_source_schema` et un contrat
  passé à la construction. `factory.py` laisse ce contrat à None par défaut.
- `core/models/source.py` ne porte pas de contrat structurel explicite ;
  `allowed_fields` n'est pas une baseline CSV/JSON et ne doit pas en devenir
  une implicitement.
- `schema_audit.py` audite les artefacts référencés de la source, y compris
  l'historique. Le périmètre doit être arrêté avant d'utiliser ce résultat
  comme garde de publication des observations effectivement sélectionnées.
- BL-016 couvre une autre identité : observation métier, pas partition
  document. Les clés document/version du lot A ne corrigent pas les collisions
  variété/statistique/séparateurs des clés prix existantes.

## Ordre de réalisation proposé

1. ADR/SPECS avant code : origine de confiance des contrats versionnés,
   acquisition manuelle explicite, absence = inconnu/refus, formats supportés.
   Ne pas générer de baseline depuis le document que l'on veut certifier.
2. Définir une résolution de contrat commune à Dagster et publication directe,
   sans introduire une exception spécifique aux tests ou sources synthetic.
3. Utiliser les mêmes observations candidates que la garde de provenance ;
   verrouiller leur périmètre jusqu'au refresh. Définir explicitement le
   traitement des versions de schéma historiques et formats non supportés.
4. Persister les mesures DQ et refuser avant tout refresh en cas de contrat
   absent, structure divergente, contenu illisible ou SHA incorrect.
5. Tester SQL/S3 refus direct et Dagster, conservation des vues et données,
   métadonnées seules, données vides, contrats explicitement fournis. Faire
   évoluer les fixtures pour déclarer leurs vrais contrats synthétiques,
   sans apprendre ces contrats de leurs réponses ni masquer des échecs.
6. BL-016 : cadrer une identité canonique et un rapprochement historique
   explicites. Préserver les bruts et les 764 observations actives ; aucune
   réécriture de clé ni classification point/mean/max inventée. Les extensions
   de type et temps de R2.1 restent soumises à leurs contrats et dépendances.
7. Réception complète unique du lot B figé ; réutiliser les checks qui tournent
   déjà dans cette réception, pas une QA cumulée en doublon.

## Propriété et limites

Lot B : coordinateur. HTTP/robots/budgets : Antigravity, lot C, worktree séparé.
Les contrats communs, migrations et statuts doivent être coordonnés avant
intégration. Les nouvelles migrations du lot A occupent 0007–0009 et les ADR
056/058–060 ; ceci ne vaut pas déploiement ou réception de ces migrations.

Ne pas implémenter ici R2.1 ni prétendre que les sources publiques disposent
déjà de baselines qualifiées. Les vérifications software, source live, modèle
et usage humain restent distinctes.
