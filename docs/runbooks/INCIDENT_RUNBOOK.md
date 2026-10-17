# Runbook d'Exploitation & Réponse aux Incidents (R6.9, SPECS §25, ADR-103)

## 1. Rôles et Responsabilités Institutionnelles (Gate H7)

> **Important (AGENTS.md Gate H7) :** Ce document formalise les rôles et protocoles internes d'astreinte technique et métier. Aucun message externe (e-mail réel, SMS, WhatsApp, appel) n'est jamais émis de façon autonome par l'agent IA. Les alertes sont confinées au tableau de bord local et aux boîtes de réception de test Mailpit.

| Rôle Institutionnel | Périmètre de Responsabilité | Actions Autorisées |
|---|---|---|
| **Lead DataOps** | Santé des connecteurs, SLA de fraîcheur, dérive de schéma, intégrité des runs d'ingestion | Gel / reprise des pipelines, création de ReviewItems, validation des nouveaux mappings de schémas. |
| **Analyste Marché SPM / MIC** | Cohérence des cours vivriers, validation des alertes de prix et arbitrage des modèles de prévision | Revue humaine des alertes de crise, validation des modèles sous dérive statistique, approbation des bulletins. |
| **Administrateur Système** | Infrastructure hôte, quotas et budgets (HTTP, LLM, stockage raster), sauvegardes et reprise d'activité | Ajustement des plafonds budgétaires, bascule sur clone de secours, rotation des clés d'accès. |

---

## 2. Procédures Opérationnelles par Type d'Incident

### Incident 1 : Panne Réseau ou Endpoint Source Injoignable (`http_outage`)
- **Symptôme :** Erreurs HTTP consécutives (Timeouts, 502, 503, 404) lors de l'exécution d'un collecteur.
- **Politique de réponse :**
  1. Après 3 échecs consécutifs, marquer la source comme `degraded` dans `meta.source.status`.
  2. Si la source est prioritaire (`P0`), geler la publication automatique des agrégats pour cette source (`quarantine_status="frozen"`).
  3. Générer un rapport d'incident dans `ops.incident` et une notification locale confinée à Mailpit.
  4. **Interdiction de faux succès :** ne jamais générer de lignes factices ou masquer l'échec. Laisser le retard de fraîcheur s'afficher loyalement (`is_stale=true`).
  5. En cas de rétablissement constaté, relancer le job d'ingestion de façon idempotente sans écrasement d'historique.

### Incident 2 : Dérive de Schéma Source (`schema_drift`)
- **Symptôme :** Colonnes manquantes, renommées, ou changement inattendu de format de données brutes dans le Bronze.
- **Politique de réponse :**
  1. **Gel immédiat de la publication :** passage immédiat en `quarantine_status="frozen"`. Aucune ligne non normalisée n'entre en Silver.
  2. Enregistrement automatique d'un item de revue `ops.review_item` avec la payload d'origine et le diagnostic d'écart.
  3. L'historique sain antérieur reste intact et continue d'être servi (Règle 3 Ajout seul).
  4. Résolution : le Lead DataOps audite l'écart, met à jour le schéma / extracteur dans le code avec tests de régression, puis valide la reprise.

### Incident 3 : Dépassement de Plafond Budgétaire (`budget_exceeded`)
- **Symptôme :** Atteinte du quota journalier de requêtes HTTP (`http_daily_budget`) ou du plafond mensuel LLM (`llm_monthly_budget_usd`).
- **Politique de réponse :**
  1. Déclenchement automatique du disjoncteur fail-safe : refus catégorique des requêtes subséquentes (`PolicyStop` ou `BudgetExceededError`).
  2. Bascule transparente des tâches d'extraction assistée vers les extracteurs déterministes de secours (ADR-065).
  3. Émission d'une alerte budgétaire pour l'Administrateur Système dans Mailpit.
  4. Réinitialisation automatique au premier jour du mois suivant ou ajustement contrôlé par variable d'environnement après arbitrage budgétaire institutionnel.

### Incident 4 : Dérive Statistique de Prévision (`forecast_drift`)
- **Symptôme :** Dégradation anormale du WAPE (> 35%) ou bond de l'erreur empirique lors de l'évaluation sur actuals mûris.
- **Politique de réponse :**
  1. **Interdiction formelle de remplacement automatique sauvage (ADR-103) :** aucun nouveau modèle candidat non qualifié n'est promu automatiquement en production.
  2. Maintien en service de la baseline calibrée précédente (`SeasonalNaive` ou modèle historique certifié).
  3. Émission d'un rapport de dérive `ForecastDriftPolicyDecision` consigné dans `ml.forecast_evaluation`.
  4. Notification de l'Analyste Marché pour audit approfondi de la rupture de régime (choc exogène, cyclone, mesure d'embargo douanier).

### Incident 5 : Interruption Abrupte de Run d'Ingestion (`run_interrupted`)
- **Symptôme :** Run Dagster ou conteneur arrêté violemment en cours d'ingestion (SIGKILL, redémarrage serveur, OOM).
- **Politique de réponse :**
  1. Le moteur de supervision identifie les runs marqués `running` dont le timestamp dépasse le timeout de sécurité (2 heures).
  2. Transition d'état vers `failed` ou `interrupted`.
  3. **Reprise idempotente garantie :** Les objets déjà sauvegardés dans le stockage Bronze (adressés par sha256) restent immuables. La relance du run saute les objets déjà ingérés sans double comptage dans `obs.price_observation`.
