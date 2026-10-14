# Identité prix et rapprochement historique (ADR-062)

Ce lot ne requalifie ni une source publique, ni une statistique historique,
ni une performance de marché. Aucun backfill ni migration active.

## Grain et chargement

PriceRecord utilise price_identity_v2, SHA de frame JSON ASCII compacte :
version, source, produit brut, variété, lieu brut, acteur, début/fin ISO,
statistique point/min/max/avg, unité brute, devise brute, observed/imputed.
Valeurs exactes : NULL, vide et "None" sont distincts ; aucun trim/case-fold.
Autres records inchangés. Prix différent à grain identique = révision ;
variété/statistique/unité/devise/origine différente = coexistence.

Le loader normalisé, le loader historique de replay et l'ancien batch de
normalisation utilisent le même pont. Verrou PostgreSQL transactionnel source
avant recherche/écriture ; il reste tenu jusqu'au commit/rollback caller.
Les verrous natifs run/source de lot A restent inchangés.

## Historique

Recherche source-scopée de lignes courantes, toutes dimensions comparées,
sans se fier au digest concaténé ancien. La statistique doit être explicite
dans normalization.value_kind ou price_identity.statistical_kind ; des preuves
contradictoires sont inconnues. Aucun défaut "point" appliqué à l'historique.
Une seule correspondance connue : idempotence ou supersession atomique.
Anciennes valeurs/clés/preuves ne changent pas, sauf superseded_by autorisé.

Un candidat inconnu ou plusieurs correspondances : action review_required,
aucune insertion/supersession de prix ; revue extraction_conflict contenant
source, clé cible et IDs candidats, human_reviewed=false, liée au SourceRecord.
Même payload/référence ne duplique pas la revue. Une nouvelle pièce peut
créer sa propre revue. Le pont ne résout pas cette revue humainement.

Loader normalisé : observation_id=NULL dans ce cas, review_items compte
seulement les nouvelles revues. Loader historique : UUID retourné = review_id,
jamais un observation_id lorsque action=review_required. Batch ancien :
compteur rejected ; replay rebuild : records_rejected. Aucun compteur skipped
ne masque le rejet. Revue durable seulement après commit ; rollback l'annule.

## Tentatives natives

Silver compte n_rejected/n_review et persiste les compteurs du run ; success
signifie fin du traitement, pas que chaque prix a été accepté. Lire les compteurs.
Le cache de success vérifie aussi n_rejected avec le run SQL. Membre prix reçu
price_normalizer_v2 ; normalisation insérée version=2. Les reçus v1 restent
historiques : même UUID success retourne son reçu original sans parsing.
Un traitement v2 exige un nouveau replay document explicite ; aucune reprise
automatique d'un succès terminal et aucune réécriture des membres existants.

## Réception

Tests isolés test_price_identity_bridge : coexistence/retry/révision, pont
explicite, inconnu/multiple/contradiction, collision historique, rollback et
connexion indépendante bloquée 55P03, compteurs/reçu v2/cache natifs.
Ils utilisent Bronze QA immuable et des sources synthétiques verified=false.
Un check complet du lot figé reste obligatoire avant réception main.
