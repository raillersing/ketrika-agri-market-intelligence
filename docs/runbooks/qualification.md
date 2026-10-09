# Qualification isolée et réhydratation d'archives

## Environnement de tests (R0.2)

`./scripts/dev.ps1 qa-isolated prepare` initialise uniquement le projet fixe
`ketrika-qualification`, la DB `ketrika_qualification` et le bucket versionné
`ketrika-qa-bronze`. Les volumes/réseau doivent porter les labels du projet et
`ketrika.scope=qualification`. Une ressource étrangère portant le même nom est
refusée, jamais supprimée. Aucun port hôte ni `.env` actif n'est utilisé.
L'équivalent Linux est `bash scripts/dev.sh qa-isolated prepare`.

`check`, `test`, `governance`, `qa`, `e2e` et `negative-build` sont les autres actions
implémentées en R0.3 (réception finale requise dans PROGRESS). Un argument `production`, `restore`, `reset`, un bucket/base étranger
ou un profil incomplet échoue avant écriture. Les variables publiques du profil
ne sont pas des secrets d'exploitation ; ne jamais y substituer des clés réelles.

Les données synthétiques restent dans `backend/tests`, jamais dans le code
applicatif. Leur seed valide le mode test, toutes les destinations et l'URL de la
session réellement liée avant le premier SQL. Un flag isolé ne constitue pas
une autorisation. Aucun jeu réel n'est mélangé au dataset test. `demo` refuse
explicitement la certification historique ; le moteur mesuré relève de R0.7.

## Runners et preuves logicielles (R0.3)

1. `./scripts/dev.ps1 qa-build` construit les trois images QA séparées de la
   stack active. Les lockfiles sont obligatoires : uv sync --locked et pnpm
   install --frozen-lockfile. Le navigateur utilise la version Playwright du
   lock Python ; il n'est pas ajouté au runtime applicatif par défaut.
2. `./scripts/dev.ps1 check` exécute lint/format/types, tous les tests backend
   hors réseau et les seuils de couverture, puis lint/types/tests/build front.
   Les dépendances, sources et builds vivent dans les volumes nommés suffixés
   r03 ; les anciens volumes de qualification sont conservés, pas recyclés.
   Le backend s'arrête au premier échec pour en conserver immédiatement la trace.
   Ce run est rouge et incomplet ; seules toutes les suites requises exécutées
   sans échec permettent le succès, jamais un sous-ensemble interrompu.
   Avant ce contrôle, seuls les serveurs api/web du projet QA sont arrêtés
   pour éviter les écritures concurrentes dans les volumes source/build.
   ADR-013 : chaque commande frontend est bornée à 15 minutes, build à
   30 minutes sur hôte partagé. Error/timeout refuse le succès même avec
   un status natif nul ; error_code/signal/timed_out sont conservés au reçu.
3. `./scripts/dev.ps1 qa R0.3` sélectionne les fichiers explicitement déclarés
   dans scripts/qa-manifest.json. ID inconnu/non implémenté, fichier absent,
   suite vide, résultat manquant, erreur/skip obligatoire ou minimum non atteint
   échoue. Un succès de sous-suite ne clôture pas la tâche à lui seul.
4. `./scripts/dev.ps1 qa-isolated negative-build` provoque une erreur de syntaxe
   dans une copie jetable et exige le refus du vrai build Next. Les erreurs
   lint/types/intégration sont injectées dans tmp_path par la sous-suite R0.3.
5. `./scripts/dev.ps1 e2e` lance Chromium dans Docker, aucun Node/Chrome hôte.
   Le scénario utilise le formulaire, jamais un cookie injecté ; il vérifie
   session HttpOnly, reload, API same-origin et déconnexion/refus d'accès.
   Ces deux serveurs QA sont recréés sans leurs dépendances pour recharger les
   sources courantes ; aucune stack active n'est redémarrée. La navigation et
   la connexion ont une attente bornée de 120 s pour la compilation à froid
   du frontend de développement, sans changer les assertions de session.

Chaque sous-suite et front crée un répertoire unique avec reçu JSON. Rapports
backend : .venv/qa-results ; front : node_modules/.qa-results ; navigateur :
.venv/qa-browser-results avec capture et trace. Ils restent dans les volumes QA.
Le check backend expose aussi JUnit et coverage JSON. La CI utilise ces mêmes
commandes ; un fichier CI préparé n'est pas une exécution distante certifiée.
Ces preuves concernent le logiciel, pas les collectes live, les modèles validés
ni un essai humain. Les équivalents Linux utilisent bash scripts/dev.sh.

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
