## Mise à jour — 19 novembre 2026 : A03/A05 fusionnées ; R0.9 à réceptionner

- A03 / PR #17 : merge `1ed7765fce9e03cb0f4813746c9e3eede68b6735`, runs `44230373225` et `44230392889` success.
- A05 / PR #16 : merge `90b13a29cbe0edcf8cbdfb1515934d1fc6b2422f`, run `44232945792` success.
- Ces preuves sont logicielles (CI), et **ne qualifient pas** les archives originales WB ni R0.9.
- Prochain lot autorisé : ADR-176 et SPECS §28 (contrat de preuve externe). À réaliser : accès explicite **readonly** au paquet existant `ketrika_wb_revision_packet_20261104`, aux reçus d'origine/droits et à son manifeste/annotations ; vérifier tailles/SHA et lignée, ensuite modifier `core.qualify` avec tests fail-closed et reçu de qualification réel.
- Conditions d'arrêt : aucun tag ni DONE R0.9 sans `qualify R0`, check complet et E2E sur le même contenu, clone hors réseau avec corruption détectée. Ne jamais déplacer/copier le corpus vers `tests/fixtures` pour simuler sa présence.
- Les volumes et la sauvegarde du 4 novembre sont **mentionnés dans la passation historique**, mais n'ont pas été lus dans cette session ; leur existence et leur intégrité actuelles ne sont pas confirmées. Les chemins locaux du document historique ne sont pas accessibles dans ce contexte GitHub.

# Passation — programme R PARTIAL

R0.8 est reçu sur le contenu authentique borné. Les74 statuts sont synchronisés :
8 DONE (dont7 historiques),66 IN_PROGRESS. R0.9 reste la prochaine tâche MUST ;
R6.11 n'est pas reçu, aucun tag final ni qualification globale du programme.
AU-01–AU-07 et Irooa/Ketrikay sont dans main, AU-08/Gold-only via PR6–8,
les correctifs de provenance/alias/territoire via PR10 ; corpus ZIP via PR11.

PR12 candidat3a974be reçu par CI41769707448 :2796 backend/301 intégrations,
113 frontend/15 suites,26 E2E, zéro échec/erreur/skip obligatoire/erreur JS.
Trois manifestes natifs et leurs octets/SHA/identités vérifiés, empreinte
7d81deb9b8846d9a3bd1e64f843e493134cff2100ec859f6e0188158b66f68eb.
La publication/merge final doit être vérifiée par ses refs distantes.

Deux ZIP WB originaux2026-09-28/2026-10-05, contexte et annotations conservés
readonly :664 cellules dont60 valeurs. Les163 lignes ingérées conservent81
anciennes versions et82 courantes. Rejeu sur réception puis clone restauré,
non-root/network none : contenus Silver/Gold/ref identiques, quatre objets
Bronze inchangés. Une seule ancienne valeur falsifiée est détectée malgré
163 lignes avant/après ; seule obs.price_observation diffère. Recalcul séparé
versionné, seuil36 intact,3 prévisions par exécution, identiques. B-R073 résolu
sur cette portée nationale c_rice depuis2020, imputée ; aucun marché/modèle,
source fraîche, rétention S3 originale ni revue humaine qualifiés.

Les volumes ketrika_wb_source_archives_20261103_candidates,
ketrika_wb_revision_packet_20261104 et ketrika_wb_replay_* sont préservés,
comme les clusters de contre-épreuve et de clone positif. Une sauvegarde
additive hors Docker conserve originaux et paquet sous
/home/raillersing/projects/ketrika-corpus-backups/wb-originals-and-annotations-20261104.tar.gz,
SHA6be44f393a1cbe4908f639e9b260e9cd29018a4389323c755660bd64f599370a,
ZIP relus et vérifiés. Voir WB_ARCHIVE_REPLAY_RUNBOOK et les originaux comprimés.

R0.9 : le plan R0.4 permet un manifeste externe, mais core.qualify ne consulte
encore que backend/tests/corpus-manifest.json. Raccorder explicitement le paquet
externe avec chemins/SHA/droits/annotations bornés, conserver les identités des
producteurs SQL authentiques et CI synthétiques, puis recevoir le gate complet.
Ne jamais réétiqueter un producteur ou éditer une preuve pour contourner un rejet.

Activation distincte : les migrations0022–0028 ne sont pas appliquées à l'actif.
Le rôle historique B-R098 conserve ses écarts ; aucun GRANT ajouté sur l'actif
pour verdir une preuve. Aucun reset, volume/Bronze supprimé, mot de passe actif
lu/copié/tourné, ni service partagé redémarré. Préserver le checkout utilisateur
et les autres worktrees. Les identifiants anciennement affichés restent dans
l'historique ; rotation opérationnelle à traiter si ces valeurs sont utilisées.

Budgets ODR/WB centraux du3 novembre conservés, aucun reset/identité reconstruite.
FEWS reste arrêté pour robots. L'ancien laboratoire B-R104 n'est pas reconstitué.
H1–H7 inchangés : replay, pas de provisionnement, Mailpit/brouillons, aucune
collecte privée, revue humaine explicite, budgets et aucun contact de tiers.
