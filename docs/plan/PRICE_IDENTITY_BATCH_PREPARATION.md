# R0.6 B2 — identité métier des prix : préparation uniquement

Analyse readonly du 2026-10-13 pendant la réception B1. Aucun ADR nouveau
adopté, aucun code/test/migration implémenté par ce document. HTTP/budgets
restent à Antigravity ; B1 reste figé sur a6a1abb jusqu'au résultat Windows.

## Écarts confirmés

- PriceRecord.natural_key_fields omet variété et type statistique ; RecordBase
  concatène les chaînes avec `|` et rend NULL comme le texte `None`.
- Le loader normalisé compare variété et normalization.value_kind, mais
  après recherche par clé : deux grains différents peuvent se superséder.
- Le loader historique runner.py utilise la même clé et ne conserve pas le
  type statistique comme contrat de grain complet.
- Lecture SQL active readonly 9207d9 FINAL 0 : 764 prix, zéro type statistique
  explicite, 764 absents dans evidence.normalization.value_kind. Ne pas
  supposer « point » pour rapprocher cet historique.
- Prototype privé price_identity.py du worktree r06-http-identity-20261011 :
  frame versionnée et tests purs, mais pas de raccordement ni bridge legacy.
  Ne pas copier les anciens loaders, la gouvernance ou déclarer BL-016 résolu.

## Réalisation suivante proposée

1. ADR/SPECS avant code : frame typée/versionnée, source et dimensions brutes,
   NULL distinct de texte, variété et statistique point/min/max/avg distinctes.
   Arrêter explicitement grain unité/devise/origine ; aucune normalisation
   silencieuse des bruts ni classification historique inventée.
2. Raccorder l'identité aux deux chemins prix (normalisé et historique), pas
   seulement compute_natural_key ou un helper sans consommation.
3. Définir recherche canonique puis rapprochement legacy source-scopé sous
   verrou : comparer les dimensions complètes, jamais seulement le digest
   concaténé. Plusieurs candidats/inconnu doivent refuser la supersession.
4. Repli ambiguïté explicite et durable : file de revue avec provenance,
   compteurs/état véridiques ; ne pas présenter une omission comme ingestion
   réussie complète. Contracter l'action du loader/stages si nécessaire.
5. Aucun UPDATE de valeur ou natural_key héritée. Une révision connue peut
   uniquement créer une nouvelle ligne et relier superseded_by atomiquement.
6. Versionner l'identité de traitement/normalizer et ses reçus sans réécrire
   ceux du lot A ; relecture des anciens succès distincte de rejeu avec le
   nouveau code. Contrats et tests du cache de succès restent obligatoires.
7. SQL/S3 isolés : coexistence variétés/statistiques ; séparateurs/NULL ;
   retry sans doublon ; révision exacte ; legacy type connu/absent/ambigu ;
   faux rapprochement refusé ; rollback/concurrence ; preuves et bruts stables.
8. Regrouper helper, raccordements, bridge et revue en résultat fonctionnel,
   puis une réception complète unique. Aucun test SQL concurrent à B1.

## Limites de portée

R2.1 (temps/origine/colonnes/API/UI) n'est pas commencé : dépend R1.1.
Ce correctif de collision R0.6 ne doit pas servir à contourner ces dépendances
ni à qualifier une statistique source à partir d'un défaut PriceRecord.
Toute extension de contrat exige adoption explicite, pas ce seul brouillon.
Les 764 lignes actives et le Bronze restent intacts ; revue H5 non réalisée
ne peut être annoncée acceptée. BL-016 reste ouvert.
