# Matrice de répartition après audit indépendant

Date2026-10-25. Comparaison de complexité, **pas attribution ni lancement d'agent**. Les directives précises, fichiers, dépendances et critères sont dans [le plan26 lots](../audits/2026-10-25/CORRECTIVE_EXECUTION_PLAN.md). Priorités R conservées ; une tâche SHOULD ne passe pas avant un MUST éligible.

| Lots | Complexité relative | Compétence adaptée | Réservation / couplage |
|---|---|---|---|
| AU-01 | Moyenne | Frontend + API | Accueil/filtres, coordonner composants communs avec AU-13 |
| AU-02 | Moyenne | Backend/Geo | Route climat/DTO, coordonner schemas avec AU-03/04 |
| AU-03 | Moyenne à élevée | Backend/Agri | Offre/scénarios et schéma stock ; pas de faux calendrier de repli |
| AU-04 | Élevée | Sécurité/Backend | Auth globale, sessions partagées, migrations et matrice de permissions |
| AU-05 | Moyenne | Backend/Sécurité | Frontière SMTP/Telegram, transport négatif intercepté, Mailpit réel positif |
| AU-06 | Élevée | Dépendances frontend/backend | Locks partagés exclusifs, ADR avant majeure ; recevoir nouvelle image |
| AU-07 | Élevée | Ops/SQL | Refus de cible avant toute commande ; aucun test sur actif |
| AU-08 | Élevée | SQL/provenance, propriétaire unique | Quarantaine/migrations/triggers/manifeste ; clone dédié obligatoire |
| AU-09 | Élevée et dépendante du corpus | QA/Data | Vraies éditions, worker sans réseau, inventaire/Gold/ML distincts |
| AU-10 | Moyenne | Data/registre | Sources, géographie, définitions ; aucun changement de disabled implicite |
| AU-11 | Élevée | Collecte/Data | Décomposer par source mais un contrat commun, aucune acquisition concurrente non coordonnée |
| AU-12 | Élevée | Data/Backend | Macro/DQ/contrats/coverage ; pas d'édition concurrente des mêmes DTO |
| AU-13 | Moyenne | Frontend/Geo | Carte GeoJSON, provenance, filtres ; API stabilisée avant intégration |
| AU-14–16 | Élevée | ML/Data | Dataset, protocole et publication ; geler critères avant résultats |
| AU-17–18 | Élevée | Geo/Agri | Rasters/temps/calendriers, authenticité et agrégats |
| AU-19 | Élevée, facultative | Geo | Acquisitions absentes ; seulement si aucun MUST éligible |
| AU-20–21 | Élevée | Data/Agri/ML | Quantités réelles, campagnes et bilans ; pas de quantité inférée des prix |
| AU-22 | Élevée | Produit/Backend | Parcours/personas/copilote ; preuve utilisateur distincte |
| AU-23 | Moyenne à élevée | Backend/Data | Bulletin/alertes et citations ; gate H3 fermé |
| AU-24 | Élevée | Ops/Backend | Supervision durable/outbox/restore, sans mutation de données actives |
| AU-25 | Moyenne à élevée | QA/Ops/Frontend | Performance et accessibilité mesurées sur contenu figé |
| AU-26 | Élevée | Coordinateur/QA | Gates et preuves ; aucun auto-DONE provenant d'un sous-agent |

Travaux documentaires simples : relire les liens, comparer les74 statuts, classer les avis de dépendances, rapprocher les18 fiches sources et les reçus. Ils peuvent être répartis sur périmètre readonly si une délégation est autorisée ; ils ne remplacent pas une réception produit.

L'ancien lot R0.6 C d'Antigravity est historique ; ne pas lui redemander de reconstruire HTTP. Proposition A013 à traiter dans AU-08, avec les réserves B-R084/B-R085 et le trigger actuel. Une correction déclarée par agent doit être relue au commit exact puis reçue.

Historique : [ancienne matrice](../audits/2026-10-25/history/DELEGATION_MATRIX.md).
