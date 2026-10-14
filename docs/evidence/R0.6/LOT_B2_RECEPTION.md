# Lot B2 — réception logicielle locale

Code figé : 9d2076b (base fc3bcda, fondation 12433bd), branche
work/r06-price-identity-20261013. Environnement ketrika-qualification :
SQL/S3/réseau dédiés, replay, Mailpit, aucune destination active migrée.
Intégration main atomique 03e5750, source identique (8310 FINAL 0/quinze
fichiers) ; conflits documentaires seuls, journaux conservés. Scan
88712 FINAL 0/526392 octets, gouvernance 74 cohérente. Actif après réception
1295 FINAL 0 : 482 SourceRecord/764 prix/674 versions Bronze inchangés,
head 0002, zéro delete markers.

## Résultats

- Windows réel `scripts/dev.ps1 check`, processus 48496, code final 0 :
  lint/format 276 fichiers, types 275 ; 1396 tests backend / 3018,54 s,
  zéro échec/erreur/skip, cinq warnings de dépendances ; 140 intégrations
  par dossier, 140 par marqueur, union 144.
- Couvertures core 94,46163366336634 %, extraction 86,3768115942029 %,
  normalize 90,37758830694276 %. price_identity et price_bridge : 100 %.
- Frontend : 35 tests/quatre suites/6,57 s, quatre étapes lint/types/tests/build
  de code 0, aucune interruption/erreur/timeout ; quinze pages statiques.
  Reçu original 1f6f9424-1188-42af-8efb-5ec925760e14 vérifié 86204 FINAL 0.
- Inclusion 77065 FINAL 0 dans le JUnit global : 59 fichiers/732 cas/108
  intégrations, zéro fichier absent ; 29 nouvelles unités et 18 nouveaux SQL.
  Aucun `qa R0.6` cumulé supplémentaire exécuté. XML SHA
  1ab22917bf81d76b440eb30c675ed3afea27caec50920de8a805f74ed0fc7d22.
- Snapshot réellement exécuté : 92100 FINAL 0, quinze fichiers backend
  modifiés identiques à 9d2076b. Rapports originaux conservés sans transformation.

## Critères B2

Identité versionnée exacte, variétés/statistiques/unités/devises/origines
distinctes ; NULL/vide/chaîne et séparateurs protégés. Les loaders normalisé,
historique et batch utilisent le même rapprochement source-scopé sous verrou.
Historique inconnu/multiple/contradictoire : revue sans prix nouveau ni
supersession, compteurs de rejet explicites et retry sans revue dupliquée.
Révision connue ajout-seul, rollback et connexion indépendante 55P03 vérifiés.
Reçu natif v2 et retour du reçu original à UUID terminal identique vérifiés.

Commande de réception complémentaire 94435 FINAL 0, script
verify_b2_revision_provenance.py : vraie révision sur deux objets Bronze QA
distincts et deux SourceRecord distincts ; ancienne clé/preuve/valeur inchangées,
nouveau prix venant du nouveau JSON, supersession puis retry idempotent.
Audit numérique fresh : deux observations valides sur deux, deux objets lus.
Cette commande ajoute une preuve d'exécution du même code, pas une nouvelle
version applicative ni une qualification des sources synthétiques.

## Portée et suite

Logiciel testé uniquement : pas de collecte live, modèle de marché validé,
déploiement, essai navigateur ou acceptation humaine. Les 764 prix historiques
sans statistique explicite ne sont pas reclassés. Le programme n'est pas terminé.
R0.6 reste IN_PROGRESS tant que le lot C HTTP/budgets d'Antigravity n'est pas
reçu ; R0.7 ne peut pas démarrer selon ses dépendances. Aucun tag final.
Voir lot-b2-reception.json et les quatre originaux backend/frontend.
