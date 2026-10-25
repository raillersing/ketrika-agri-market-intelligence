# Ketrika Market Intelligence — bilan PARTIAL

État2026-10-25 UTC, lot logiciel R0.8 reçu et fusionné par PR1. Ce document
n'est pas le rapport de clôture R6.11. Aucune qualification globale, aucun
déploiement ni essai humain n'est revendiqué.

## État canonique

PROGRESS et le miroir du plan R indiquent74 tâches :7 DONE,
52 IN_PROGRESS et15 TODO (69 MUST,5 SHOULD). Les affirmations historiques
«74 tâches MUST DONE» et «programme officiellement clôturé» sont retirées.
Les tags historiques ne sont ni déplacés ni utilisés comme preuve actuelle.

## Implémentation et limites

Audit readonly du Bronze original le2026-10-25 :684 versions relues,
tailles et empreintes cohérentes, aucune mutation pendant l'audit.
La concordance du registre SQL échoue :164 clés absentes sur485 entrées,
dont129 empreintes manifestement non SHA256. Les234 prix liés sont tous
auto-supersédés, aucun courant. Ce résultat négatif est conservé (B-R085) ;
il interdit de déclarer la provenance globale et le rebuild qualifiés.

Le dépôt contient collecte conforme, Bronze immuable, normalisation,
contrôles Gold, API et dashboard, prévisions, agroclimat, approvisionnement,
copilote, bulletins et alertes. Leur présence n'établit ni fraîcheur des
sources, ni couverture économique, ni performance des modèles.

Les corrections C022 ont une réception logicielle historique sur dd5831f.
Les changements ultérieurs A012 ont reçu les corrections et contrôles
complets6735/8021 puis52578/87920. Les tests ciblés/HTTP200 d'A012 seuls
ne prouvaient pas cette réception. Les références de rendement/conversion restent non
vérifiées et les usages institutionnels NOT_EVALUATED.

## Lot actuel

Source stabilisée1a6641c, branche work/r0-reception-20261024 : disponibilité
Gold explicite (503/code gold_not_published vs200 réellement vide), refus
des cycles de révision, relecture SHA/taille des copies Bronze et contrôle
de destination du recalcul. Check6735 FINAL0 :2393 backend/50 frontend,
build16 pages,167 intégrations ; E2E8021 FINAL0 :12 scénarios/57,305s,
zéro erreur JS. Originaux et limites : R0.8_RECEPTION_20261024.md.

Le check82d7e28 était vert (2393 backend/50 frontend), puis le navigateur
a révélé une régression A012 : le503 Économie était affiché comme absence
de données.1a6641c rétablit l'avertissement ; sa réception6735 est verte.
Le résultat vert précédent ne reçoit pas cette correction ultérieure ;
6735 et8021 portent sur1a6641c et la reçoivent comme logiciel uniquement.

Rejeux de développement : synthétique et échantillon WB identiques, sans
réseau, mais PARTIAL. Le clone WB contient quinze lignes historiques
imputées ; zéro révision réelle et aucun candidat Gold/prévision éligible
dans ce clone. Les octets nouvellement acquis sont identiques à l'archive.

Une seconde acquisition bornée a récupéré120 estimations WB sur81 périodes,
2020-01 à2026-10. Inspection hors réseau :120 lignes avec preuves contre
le contexte d'étude officiel. Aucun chargement actif, droits/authenticité
et normalisation non qualifiés. Le connecteur récent est préparé séparément
surac11e47 et reçu par27111 (2398 backend/50 web/build16) et76823
(12 parcours navigateur). Ce paquet n'est pas une révision
authentique du même produit/lieu/période.

La CI distante40034974447 avait échoué sur une image MinIO retirée. La
construction source figée (ADR119) est reçue :check52578,2398 backend/50 web,
build16 et E2E87920,12 parcours. Après correction du disque du runner CI,
CI40109568864 est entièrement verte, empreinte applicative identique.
PR1 fusionnée sur main2250c7b ; stockage actif préservé.

Le2026-10-24, clic WB réel sur main local3fec099 :120 nouvelles estimations,
zéro rejet/publication réussie, reçu SQL/API identique après reload et zéro
erreur JS. La base contient135 lignes WB courantes, toutes imputées, jusqu'à
2026-10 ; API200/96 points mensuels agrégés. Aucun essai humain ni modèle
qualifié déduit. Le filtrage par dates500 et le libellé de portée hérité15
sont corrigés dans le lot reçu52578/87920 et fusionné sur main.

Audit actif readonly :728 observations portent un auto-lien de remplacement
(B-R084) ; aucune correction active effectuée. Cette base ne prouve pas un
corpus authentique de révisions. Détails, SQL reproductible, originaux et
limites dans [l'audit A012](evidence/R0.8_A012_AUDIT_20261024.md).

## Réception restante

Terminer R0.8 avec corpus/révisions authentiques, inventaires et recalcul
reçus ; passer R0.9 ; qualifier les sources R1 ; poursuivre les gates
économie, prévisions, agroclimat, approvisionnement et décision selon leurs
dépendances. Les données ou autorisations manquantes et critères de
déblocage figurent dans [HANDOFF](HANDOFF.md). Aucun gate H1–H7 n'est levé.

Le rapport historique initial est conservé intégralement dans
[l'archive non reçue](evidence/MARKET_INTELLIGENCE_REPORT_20261017_HISTORICAL_UNRECEIVED.md),
comme contexte seulement, pas comme état actuel ni preuve de qualification.
