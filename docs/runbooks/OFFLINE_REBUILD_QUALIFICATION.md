# R0.8 — reconstruction hors ligne et comparaison de contenu

Statut : **IN_PROGRESS**. Aucun rebuild actif, aucune réception R0.8 ou gate
R0.9. Ce document distingue implémentation, tests logiciels et preuve réelle.

## Rejeu logiciel désormais exécutable

`scripts/dev.ps1 rebuild-smoke prepare` initialise explicitement la nouvelle
base ketrika_rebuild_qualification ; `rebuild-smoke replay` rejoue ses deux
éditions synthétiques. Linux : `bash scripts/dev.sh rebuild-smoke ...`.
Les volumes ketrika_rebuild_qualification_* et conteneurs sont conservés.
Prepare refuse une base peuplée ; reprise d'un schéma seul strictement vide
permise, sans effacement. Aucun reset ni nettoyage automatique.

Développement réel : préparation65086 code0 ; rejeu91244 code0, rapport
`/reports/runs/489700d177bd4cf6bf001e188f01db9b/replay.json`, copie originale
docs/evidence/R0.8-offline-smoke-development.json. Docker inspect : réseau
none, toutes capabilities retirées, utilisateur app, montage /copy RW=false.
PostgreSQL relu : deux observations dont une supersédée. Manifestes complets
et références identiques, replay_passed=true ; rapport PARTIAL/synthetic.
Ce résultat de développement ne reçoit ni corpus authentique, ni versions
S3 originales, ni prévisions recalculées. Réception complète encore requise.

Garde réseau/destination : 16 nouveaux cas ; régressions qualificateur et
garde77 verts/14,76 s, types huit fichiers verts88914. Incident initial de
disponibilité PostgreSQL corrigé en exigeant son processus final ; problème
de permissions des nouveaux volumes corrigé par préparation root sans
capabilities, worker non-root et rapports dédiés sticky. Aucun chmod hôte,
cache utilisateur ou volume actif ; aucun objet Bronze S3 supprimé/modifié.

## Éléments implémentés (branche work/r08-offline-rebuild-20261015)

- `core/rebuild_manifest.py` : capture SQL SELECT des sept tables obs et
  douze vues matérialisées Gold, inventaire exact y compris tables vides,
  schéma et toutes colonnes, lignes triées, SHA et diff complet par table.
  Mapping des UUID d'observations et liens de révision ; seul ingested_at
  technique est ignoré. UUID SourceRecord et référentiels conservés : leurs
  inventaires doivent être identiques dans le clone. Aucun chiffre arrondi,
  Decimal encodé sans arrondi par le contexte ; JSON/scalaires typés.
- `core/rebuild_bronze.py` : client GET/HEAD local fermé clé/SHA/taille,
  fichiers SHA.blob, lecture bornée et hash frais à chaque GET. Symlinks,
  corruption, objet inconnu, autre bucket et PUT refusés. Pas de fallback S3.
- `pipelines/rebuild.py` : injection d'un BronzeStore, même lecteur transmis
  aux gardes des deux refresh Gold. Défaut S3 inchangé ; aucune restriction
  source ou absence de données n'est transformée en succès de qualification.

Tests de développement : `test_rebuild_manifest.py` et
`test_rebuild_bronze.py`, 55 cas verts ; lint et mypy trois modules verts.
Ils ne prouvent pas un rejeu PostgreSQL réel ni une acquisition authentique.

## Travail restant dans le même lot fonctionnel

1. **Destination dédiée.** Ajouter un profil de rejeu distinct de la base
   QA historique et de la base active. PostgreSQL et worker `network_mode:
   none`, socket Unix partagée dans un volume dédié ; aucune publication de
   port, montage d'un volume actif, réseau externe ou privilège additionnel.
   Valider nom de base, URL/socket et `current_database()` avant tout wipe.
   Ne jamais restaurer ni tronquer ketrika ou ketrika_qualification existants.
2. **Entrées vérifiables.** Acquérir un corpus compatible avec un parseur,
   sous robots/quotas/arrêt challenge via le client HTTP conforme. Conserver
   octets officiels, preuve C1, droits et annotations indépendantes. Aucune
   réactivation HDX/NASA ni usage du PIB comme prix. Exporter les objets de
   ce corpus avant confinement, vérifier SHA/taille et correspondance exacte
   avec tous les SourceRecord du clone. Deux éditions de source réellement
   révisées requises pour une preuve authentique de révisions ; révision
   synthétique autorisée uniquement comme test explicitement identifié.
3. **Exécution réelle.** Peupler seulement le clone par le chemin normal,
   capturer avant, inventaires SourceRecord/référentiels/Bronze versionné et
   contexte modèle/dataset. Préexporter les objets nécessaires. Couper tout
   réseau IP par Docker, pas seulement HTTP_OFFLINE ; prouver mode réseau
   par inspect et interfaces/absence de route. Lire PostgreSQL par socket
   et Bronze local readonly ; relancer tous les parseurs/normalisation/load,
   sans filtrage opportuniste d'historique ni base non vide court-circuitée.
   Refuser tout SourceRecord ignoré/échec ; garder la source en cas de refus.
4. **Réception complète.** Capturer après, comparer toutes lignes et liens,
   Bronze et inventaires inchangés. Une mutation de valeur à compte égal
   doit produire un diff rouge. Prévisions refaites séparément depuis les
   versions de dataset/modèle ; absence de preuve reste inconnue, pas passée.
   Archiver projections complètes, diff, identité source/image/env, originaux
   de confinement et codes. Un check complet stabilisé seulement, inclusion
   des cas prouvée par JUnit ; ne pas refaire le check R0.7. Réception sur
   main et DONE exclusivement lorsque tous critères R0.8 sont satisfaits.

## Piste de corpus public identifiée, pas encore acquise

Le 15 octobre, lecture de la [fiche officielle RTFP Madagascar](https://microdata.worldbank.org/catalog/8240/study-description)
et de ses liens [accès/conditions](https://microdata.worldbank.org/catalog/8240/get-microdata)
et [métadonnées JSON](https://microdata.worldbank.org/metadata/export/8240/json).
La fiche distingue estimations et mesures : ne pas convertir une estimation
en observation. Les résultats web HTML et JSON consultés portent des versions
différentes (octobre et août) : ils ne constituent pas un paquet C1 cohérent.
Un lien de catalogue ou une consultation web ne prouve ni octets CSV, ni
droits vérifiés sur ces octets, ni compatibilité du parseur actuel. Découvrir
les liens depuis la source, ne pas utiliser l'ancienne constante CSV comme
URL vérifiée. Aucun téléchargement de prix ni historique de révisions reçu.

Le corpus C1 versionné actuel reste deux enregistrements annuels de PIB.
Le logiciel peut continuer à être développé/testé sur fixtures synthétiques
sans clôturer R0.8 ou inventer un blocage humain exclusif.
