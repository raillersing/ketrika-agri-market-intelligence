# Qualification isolée et réhydratation d'archives

## Environnement de tests (R0.2)

`./scripts/dev.ps1 qa-isolated prepare` initialise uniquement le projet fixe
`ketrika-qualification`, la DB `ketrika_qualification` et le bucket versionné
`ketrika-qa-bronze`. Les volumes/réseau doivent porter les labels du projet et
`ketrika.scope=qualification`. Une ressource étrangère portant le même nom est
refusée, jamais supprimée. Aucun port hôte ni `.env` actif n'est utilisé.
L'équivalent Linux est `bash scripts/dev.sh qa-isolated prepare`.

`check`, `test` et `governance` sont les seules autres actions actuellement
acceptées. Un argument `production`, `restore`, `reset`, un bucket/base étranger
ou un profil incomplet échoue avant écriture. Les variables publiques du profil
ne sont pas des secrets d'exploitation ; ne jamais y substituer des clés réelles.

Les données synthétiques restent dans `backend/tests`, jamais dans le code
applicatif. Leur seed valide le mode test, toutes les destinations et l'URL de la
session réellement liée avant le premier SQL. Un flag isolé ne constitue pas
une autorisation. Aucun jeu réel n'est mélangé au dataset test. `demo` refuse
explicitement la certification historique ; le moteur mesuré relève de R0.7.

## Réhydratation d'archives authentiques autorisées

Procédure opérateur : ce document n'autorise aucun restore sur une destination
existante. Le CLI de qualification réelle/rejeu est encore à livrer (R0.7/R0.8).

1. Constituer un manifeste : source institutionnelle, URL vérifiée ou
   `verified:false`, droit/licence, date de publication, date/mode de collecte,
   sha256 des octets, taille, MIME, version parser et provenance de l'archive.
   Rejeter les archives contenant des données personnelles. Conserver les
   originaux et ne pas renommer une fixture synthétique « archive réelle ».
2. Choisir explicitement un nouveau projet, DB, compte S3, bucket versionné,
   réseau et volumes **distincts** du service actif et des tests synthétiques.
   Vérifier l'absence de destination existante/protégée. Pas de `down -v`, reset,
   `--clean` ou terminaison de sessions actives. Désactiver les envois externes.
3. Vérifier les sha256 hors réseau, puis importer les objets comme nouveaux
   objets adressés par contenu, sans overwrite ni suppression. Une divergence
   entre archive/manifeste impose la mise en revue, pas un hash fabriqué.
4. Créer les métadonnées de provenance depuis le manifeste et l'objet réel.
   Rejouer les parsers depuis ces octets, HTTP désactivé. Toute observation doit
   référencer le source_record lié au Bronze. Aucun seed synthétique.
5. Comparer inventaires d'objets/versions, empreintes, comptages et valeurs
   normalisées avant/après. Les contrôles R0.5/R0.8 prouvent la chaîne de bytes
   et le rejeu ; un simple nombre de lignes identique ne suffit pas.
6. Conserver les preuves, droits et erreurs par capacité. Des parsers testés
   hors ligne ne prouvent ni collecte live, ni modèle de marché validé, ni
   revue humaine. Promotion vers l'exploitation après réception applicable
   seulement ; aucun transfert destructif de données historiques.

## Inventaire et mise à l'écart non destructive

L'inventaire SQL R0.2 utilise une transaction `REPEATABLE READ READ ONLY` ;
le script d'empreinte S3 utilise seulement list/GET, versions et marqueurs inclus.
Ne jamais publier les credentials, payloads ou données personnelles.

Les références explicites de test/URL fictive constituent un motif d'exclusion
du corpus décisionnel. Les autres lignes restent **non qualifiées** jusqu'à
preuve d'authenticité et de bytes. Proposition : conserver la stack historique
comme archive non décisionnelle, qualifier un corpus neuf sur une destination
dédiée ; un manifeste latéral d'exclusion peut référencer les UUID historiques
sans UPDATE/DELETE des observations ou objets Bronze. Cette proposition n'est
pas une purge ni une migration exécutée.
