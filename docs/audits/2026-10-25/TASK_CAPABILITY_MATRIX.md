# Matrice indépendante des74 tâches et capacités

Date2026-10-25, source b7e63ee. Statut historique ≠ présence du code ≠ qualification réelle.
Les statuts de PROGRESS et du miroir sont conservés ; ce document ne reçoit aucun gate.
Dépendances exactes/conditionnelles : task_matrix.json et plan R normatif. Les chemins et réceptions par lot figurent dans CORRECTIVE_EXECUTION_PLAN.md.

| Tâche | Priorité / statut canonique | Objectif | Constat indépendant | Suite |
|---|---|---|---|---|
| R0.1 | MUST / DONE | Intégrer le programme dans la gouvernance | Réception historique conservée, non recertifiée | AU-01 à AU-09 si impact |
| R0.2 | MUST / DONE | Isoler l'environnement de qualification | Réception historique conservée, non recertifiée | AU-01 à AU-09 si impact |
| R0.3 | MUST / DONE | Rendre les contrôles qualité complets et fiables | Réception historique conservée, non recertifiée | AU-01 à AU-09 si impact |
| R0.4 | MUST / DONE | Étiqueter les fixtures et construire un jeu authentique | Réception historique conservée, non recertifiée | AU-01 à AU-09 si impact |
| R0.5 | MUST / DONE | Vérifier la provenance de bout en bout | Réception historique conservée, non recertifiée | AU-01 à AU-09 si impact |
| R0.6 | MUST / DONE | Corriger la lignée Dagster et les erreurs silencieuses | Réception historique conservée, non recertifiée | AU-01 à AU-09 si impact |
| R0.7 | MUST / DONE | Remplacer la certification déclarative | Réception historique conservée, non recertifiée | AU-01 à AU-09 si impact |
| R0.8 | MUST / IN_PROGRESS | Prouver le rebuild hors ligne sur le contenu | Partiel : défauts bloquants / corpus incomplet | AU-01 à AU-09 |
| R0.9 | MUST / TODO | Gate de fiabilité | Gate non reçu | AU-09 |
| R1.1 | MUST / TODO | Requalifier le registre et les permissions | Code/référentiels présents, qualification actuelle à compléter | AU-10 |
| R1.2 | MUST / TODO | Développer découverte et suivi des éditions | Code/référentiels présents, qualification actuelle à compléter | AU-10 |
| R1.3 | MUST / TODO | Qualifier INSTAT NIPC | Code présent ; politique de source arrêtée à respecter | AU-11 |
| R1.4 | MUST / TODO | Qualifier l'Observatoire du Riz | Code présent ; réception opérationnelle non prouvée ici | AU-11 |
| R1.5 | MUST / TODO | Qualifier les publications MinCC/PPN | Code présent ; réception opérationnelle non prouvée ici | AU-11 |
| R1.6 | MUST / TODO | Qualifier les statistiques douanières | Code présent ; réception opérationnelle non prouvée ici | AU-11 |
| R1.7 | MUST / TODO | Qualifier WFP/HDX sous politique stricte | Code présent ; politique de source arrêtée à respecter | AU-11 |
| R1.8 | MUST / TODO | Qualifier Banque mondiale RTFP | WB partiellement live vérifiée, estimations imputées seulement | AU-11 |
| R1.9 | MUST / TODO | Qualifier FAOSTAT | Code présent ; réception opérationnelle non prouvée ici | AU-11 |
| R1.10 | MUST / TODO | Requalifier géographie et résolution | Code/référentiels présents, qualification actuelle à compléter | AU-10 |
| R1.11 | MUST / TODO | Qualifier NASA POWER et ses révisions | Code présent ; politique de source arrêtée à respecter | AU-11 |
| R1.12 | MUST / IN_PROGRESS | Qualifier actualisation, reprise et santé des sources | Code présent ; réception opérationnelle non prouvée ici | AU-11 |
| R1.13 | MUST / TODO | Gate de collecte réelle | Gate non reçu | AU-11 |
| R2.1 | MUST / IN_PROGRESS | Formaliser les contrats temps, origine et macroéconomie | Contrats/helpers présents ; réception données et parcours incomplète | AU-12 |
| R2.2 | MUST / IN_PROGRESS | Auditer taxonomie, unités et grains | Contrats/helpers présents ; réception données et parcours incomplète | AU-12 |
| R2.3 | MUST / IN_PROGRESS | Qualifier DQ, agrégations et indépendance | Contrats/helpers présents ; réception données et parcours incomplète | AU-12 |
| R2.4 | MUST / IN_PROGRESS | Mesurer couverture et choisir le pilote | Contrats/helpers présents ; réception données et parcours incomplète | AU-12 |
| R2.5 | MUST / IN_PROGRESS | Intégrer INSTAT Tableau de bord économique | Connecteur présent ; aucune ligne macro dans la base sondée | AU-12 |
| R2.6 | MUST / IN_PROGRESS | Intégrer change et contexte monétaire BFM | Connecteur présent ; aucune ligne macro dans la base sondée | AU-12 |
| R2.7 | MUST / IN_PROGRESS | Intégrer carburants OMH et événements réglementaires | Connecteur présent ; aucune ligne macro dans la base sondée | AU-12 |
| R2.8 | MUST / IN_PROGRESS | Construire le tableau économique interprétable | Code présent ; publication retenue avec503, non qualifiée | AU-12 |
| R2.9 | MUST / IN_PROGRESS | Exposer les données et leurs limites dans l'API | Contrats/helpers présents ; réception données et parcours incomplète | AU-12 |
| R2.10 | MUST / IN_PROGRESS | Livrer les vues marché et économie | UI partielle : faux accueil, carte et filtres à corriger | AU-01 / AU-13 |
| R2.11 | MUST / IN_PROGRESS | Gate observatoire décisionnel | Gate non reçu | AU-13 |
| R3.1 | MUST / IN_PROGRESS | Appliquer l'éligibilité et le calendrier des séries | Éligibilité présente, cohorte réelle à recevoir | AU-14 |
| R3.2 | MUST / IN_PROGRESS | Construire les datasets historiques as-of | Chemin SQL as-of en échec, helper non raccordé au pipeline | AU-14 |
| R3.3 | MUST / IN_PROGRESS | Implémenter références et modèles conformes | Algorithmes présents ; raccordement protocole à recevoir | AU-15 |
| R3.4 | MUST / IN_PROGRESS | Séparer sélection, calibration et évaluation finale | Algorithmes présents ; raccordement protocole à recevoir | AU-15 |
| R3.5 | MUST / IN_PROGRESS | Calibrer les intervalles et surveiller leur couverture | Algorithmes présents ; raccordement protocole à recevoir | AU-15 |
| R3.6 | SHOULD / IN_PROGRESS | Évaluer l'apport des variables économiques/agroclimatiques | Algorithmes présents ; raccordement protocole à recevoir | AU-15 |
| R3.7 | MUST / IN_PROGRESS | Publier prévisions, limites et abstentions | Publication héritée non qualifiée / évaluation réelle absente | AU-16 |
| R3.8 | MUST / IN_PROGRESS | Produire l'évaluation réelle et le suivi des erreurs maturées | Publication héritée non qualifiée / évaluation réelle absente | AU-16 |
| R3.9 | MUST / IN_PROGRESS | Gate de prévision des prix | Gate non reçu | AU-16 |
| R4.1 | MUST / IN_PROGRESS | Formaliser les contrats géospatiaux et agroclimatiques | Connecteur/contrat présent ; données réelles et versions à recevoir | AU-17 |
| R4.2 | MUST / IN_PROGRESS | Qualifier CHIRPS et ses versions | Connecteur/contrat présent ; données réelles et versions à recevoir | AU-17 |
| R4.3 | MUST / IN_PROGRESS | Qualifier les bulletins Météo Madagascar | Connecteur/contrat présent ; données réelles et versions à recevoir | AU-17 |
| R4.4 | MUST / IN_PROGRESS | Intégrer événements et perspectives FEWS NET/IPC | Connecteur/contrat présent ; données réelles et versions à recevoir | AU-17 |
| R4.5 | MUST / IN_PROGRESS | Qualifier une météo prévue archivable | Connecteur/contrat présent ; données réelles et versions à recevoir | AU-17 |
| R4.6 | MUST / IN_PROGRESS | Calculer anomalies et agrégations zonales correctement | Calcul/référentiel présent ; preuves réelles insuffisantes | AU-18 |
| R4.7 | MUST / IN_PROGRESS | Versionner les calendriers culturaux | Calcul/référentiel présent ; preuves réelles insuffisantes | AU-18 |
| R4.8 | SHOULD / IN_PROGRESS | Évaluer l'état des cultures par télédétection | Calcul NDVI/VCI présent ; acquisition/persistance absentes du parcours | AU-19 |
| R4.9 | SHOULD / TODO | Qualifier les signaux de feu FIRMS | Connecteur absent, statut unavailable explicite | AU-19 |
| R4.10 | SHOULD / TODO | Qualifier un indicateur d'inondation hydrologique | Connecteur absent, statut unavailable explicite | AU-19 |
| R4.11 | MUST / IN_PROGRESS | Livrer la vue agroclimatique explicable | API/UI présentes mais réponses de repli fabriquées | AU-02 / AU-18 |
| R4.12 | MUST / IN_PROGRESS | Gate agroclimat/météo | Gate non reçu | AU-18 |
| R5.1 | MUST / IN_PROGRESS | Définir les cibles et le protocole de relevé | Contrat/parseur/bilan présent ; corpus quantitatif recevable à acquérir | AU-20 |
| R5.2 | MUST / IN_PROGRESS | Importer les quantités légalement disponibles | Contrat/parseur/bilan présent ; corpus quantitatif recevable à acquérir | AU-20 |
| R5.3 | MUST / IN_PROGRESS | Contrôler les quantités et leur couverture | Contrat/parseur/bilan présent ; corpus quantitatif recevable à acquérir | AU-20 |
| R5.4 | MUST / IN_PROGRESS | Produire une fenêtre de récolte vérifiable | Calcul présent ; références/validation et raccordements incomplets | AU-03 / AU-21 |
| R5.5 | SHOULD / IN_PROGRESS | Évaluer superficie et rendement prévisionnels | Calcul présent ; références/validation et raccordements incomplets | AU-03 / AU-21 |
| R5.6 | MUST / IN_PROGRESS | Construire un bilan d'offre sans double comptage | Contrat/parseur/bilan présent ; corpus quantitatif recevable à acquérir | AU-20 |
| R5.7 | MUST / IN_PROGRESS | Prévoir les fenêtres d'approvisionnement et leurs pics | Calcul présent ; références/validation et raccordements incomplets | AU-03 / AU-21 |
| R5.8 | MUST / IN_PROGRESS | Préparer les scénarios et le pilote décisionnel | Parcours préparés / gate non reçu, entrées fixes à retirer | AU-03 / AU-22 |
| R5.9 | MUST / IN_PROGRESS | Gate disponibilité et abondance | Parcours préparés / gate non reçu, entrées fixes à retirer | AU-03 / AU-22 |
| R6.1 | MUST / IN_PROGRESS | Sécuriser les outils de lecture | Parcours/helpers présents ; intégration opérationnelle non reçue | AU-22 |
| R6.2 | MUST / IN_PROGRESS | Borner les workflows IA et leurs reprises | Parcours/helpers présents ; intégration opérationnelle non reçue | AU-22 |
| R6.3 | MUST / IN_PROGRESS | Répondre avec des résultats exécutés et référencés | Parcours/helpers présents ; intégration opérationnelle non reçue | AU-22 |
| R6.4 | MUST / IN_PROGRESS | Évaluer le copilote sur des questions métier indépendantes | Parcours/helpers présents ; intégration opérationnelle non reçue | AU-22 |
| R6.5 | MUST / IN_PROGRESS | Qualifier le bulletin sans hallucination numérique ou sémantique | Code présent ; contenus réels et notification sûre à recevoir | AU-05 / AU-23 |
| R6.6 | MUST / IN_PROGRESS | Évaluer les alertes et les scénarios de risque | Code présent ; contenus réels et notification sûre à recevoir | AU-05 / AU-23 |
| R6.7 | MUST / IN_PROGRESS | Durcir accès, audit et sécurité applicative | Défauts sécurité confirmés, gate non reçu | AU-04 / AU-06 / AU-25 |
| R6.8 | MUST / IN_PROGRESS | Qualifier sauvegarde et restauration isolée | Helpers/scripts présents mais garde/erreurs insuffisants | AU-07 / AU-24 |
| R6.9 | MUST / IN_PROGRESS | Superviser fraîcheur, dérive, dépenses et incidents | Supervision en mémoire, raccordement durable manquant | AU-24 |
| R6.10 | MUST / IN_PROGRESS | Mesurer performance et préparer le déploiement humain | Paquet préparé ; performance et durcissement non reçus ici | AU-25 |
| R6.11 | MUST / IN_PROGRESS | Réception finale, rapport et passation | Réception finale non atteinte | AU-26 |

## Sources : configuration distincte de qualification

État SQL lu dans runtime.json ; aucune nouvelle collecte ni nouvelle vérification HTTP des URL sources. Une entrée active n'est pas une capacité live reçue.

| Source | Registre | SQL | Module déclaré présent | Limite actuelle |
|---|---|---|---|---|
| ocha_codab_mdg | active | active | non (référentiel/import à examiner) | Pas de réception live actuelle déduite de la présence du code |
| wfp_hdx_mdg | disabled | disabled | oui | Source arrêtée : aucune relance, archives autorisées seulement |
| wb_rtfp_mdg | active | active | oui | WB :135 prix courants imputés ; périmètre partiel |
| faostat | active | active | oui | Pas de réception live actuelle déduite de la présence du code |
| nasa_power | disabled | disabled | oui | Source arrêtée : aucune relance, archives autorisées seulement |
| instat_nipc | disabled | active | oui | Source arrêtée : aucune relance, archives autorisées seulement |
| instat_tbe | active | absent de la lecture SQL | oui | Pas de réception live actuelle déduite de la présence du code |
| bfm_public | active | absent de la lecture SQL | oui | Pas de réception live actuelle déduite de la présence du code |
| omh_public | active | absent de la lecture SQL | oui | Pas de réception live actuelle déduite de la présence du code |
| miasa_odr | active | active | oui | Pas de réception live actuelle déduite de la présence du code |
| mincc_ppn | active | active | oui | Pas de réception live actuelle déduite de la présence du code |
| douanes_stats | active | active | oui | Pas de réception live actuelle déduite de la présence du code |
| chirps | planned | planned | oui | Pas de réception live actuelle déduite de la présence du code |
| meteo_mg | planned | absent de la lecture SQL | oui | Pas de réception live actuelle déduite de la présence du code |
| fewsnet_mdg | active | absent de la lecture SQL | oui | Pas de réception live actuelle déduite de la présence du code |
| ipc_mdg | active | absent de la lecture SQL | oui | Pas de réception live actuelle déduite de la présence du code |
| ecmwf_open | active | absent de la lecture SQL | oui | Pas de réception live actuelle déduite de la présence du code |
| market_supply | active | absent de la lecture SQL | oui | Pas de réception live actuelle déduite de la présence du code |

## Lecture des absences

FIRMS et GloFAS : pas de connecteur enregistré. Copernicus NDVI : fonctions de calcul présentes, acquisition et chaîne publiée non réalisées dans le parcours inspecté. Carte géographique : composant actuel en cartes textuelles, rendu GeoJSON non implémenté. Supervision : helpers en mémoire, persistance/raccordement manquants. Les autres modules ont du code ; les réécrire intégralement serait redondant.
