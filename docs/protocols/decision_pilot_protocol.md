# Protocole d'Essai Humain et Questionnaire Pilote Décisionnel (R5.8, ADR-094)

## 1. Contexte & Objectifs

Le module d'aide à la décision de Ketrika Agri Market Intelligence prépare des scénarios d'approvisionnement et d'évaluation d'impacts pour les trois profils décisionnels majeurs de la filière vivrière malgache :
1. **Institution Publique / Régulateur de Marché :** State Procurement of Madagascar (SPM), Ministère de l'Industrialisation et du Commerce (MIC), Observatoire du Riz (OdR).
2. **Acheteur Commercial / Agro-industriel :** Minoteries, rizeries industrielles, coopératives et grands grossistes du marché d'Anosibe.
3. **Planificateur Agricole / Vulgarisation :** Ministère de l'Agriculture et de l'Élevage (MinAE), Directions Régionales (DRDA), FOFIFA.

Conformément à `AGENTS.md` §5 (Gate H7), l'agent autonome prépare l'ensemble des parcours techniques, des scénarios déterministes et des formulaires d'évaluation **sans jamais contacter directement des tiers**. Le statut des scénarios demeure rigoureusement étiqueté `human_reviewed: false` et `evaluation_status: "NOT_EVALUATED"` jusqu'à la tenue effective des séances de test avec les acteurs humains.

---

## 2. Déroulement d'une Séance d'Essai Pilote

### A. Format de la séance
- **Durée :** 90 minutes par institution ou entreprise.
- **Support :** Démonstration guidée sur des données authentiques historiques (campagne 2024), suivie d'une simulation interactive de scénarios de crise (stress hydrique, blocage logistique portuaire).
- **Principe d'indépendance :** L'évaluateur teste le système en « revue à froid » sur des situations passées dont le dénouement réel est connu, afin de confronter les recommandations du système aux décisions effectivement prises sur le terrain.

### B. Parcours testés

#### Parcours 1 : Régulateur Public (Tension d'approvisionnement et stock de sécurité)
- **Objectif :** Évaluer si le calcul automatisé du déficit urbain mensuel (besoins incompressibles de 2,5 millions d'habitants @ 350 g/j vs flux de camions constatés) permet d'anticiper une flambée des cours au détail au moins 3 semaines avant le pic de tension.
- **Action simulée :** Alerte SPM, simulation de constitution d'un stock régulateur de 30 jours, déclenchement d'un quota d'importation d'appoint.
- **Garde-fou :** Le système refuse formellement de générer un bon d'achat autonome (`order_generation_prohibited: true`).

#### Parcours 2 : Acheteur Commercial (Optimisation de la fenêtre de collecte)
- **Objectif :** Vérifier que l'alignement du calendrier d'achat sur la décade de pic d'arrivages prévue par le modèle (ex: mai D3 à Anosibe) permet de réaliser une décote d'achat de 8% à 15% par rapport aux achats éparpillés en période de soudure.
- **Action simulée :** Planification des capacités d'entreposage (8 000 t) et cadencement des camions de collecte depuis l'Alaotra.

#### Parcours 3 : Vulgarisateur Agricole (Choc hydrique et élongation de la soudure)
- **Objectif :** Mesurer l'impact d'un déficit pluviométrique précoce de 35% en début de saison sur le décalage de la récolte (+2 décades) et l'élongation de la soudure paysanne (+2,9 semaines).
- **Action simulée :** Recommandation de variétés à cycle court (Mailaka) et mobilisation des motopompes sur périmètres irrigués.

---

## 3. Grille d'Évaluation Humaine (Questionnaire Pilote)

Chaque critère est noté de **1 (Très insatisfaisant)** à **5 (Remarquable)** par l'analyste ou décideur humain.

| ID | Dimension Évaluée | Question Normative | Seuil d'Acceptation |
|---|---|---|---|
| **Q1** | **Pertinence Métier** | Les indicateurs d'impacts calculés (déficit mensuel, décote de pic, durée de soudure) correspondent-ils directement à vos besoins décisionnels réels ? | $\ge 4 / 5$ |
| **Q2** | **Explicabilité Mathématique** | Chaque chiffre présenté est-il directement rattaché à une formule physique claire et à une source vérifiée, sans « boîte noire » ? | $\ge 4 / 5$ |
| **Q3** | **Transparence des Limites** | Les notes d'incertitude et la distinction entre faits observés et hypothèses de scénarios sont-elles immédiatement compréhensibles ? | $\ge 4 / 5$ |
| **Q4** | **Garde-fous & Sécurité** | Approuvez-vous le principe constitutionnel interdisant à l'outil de générer des ordres financiers ou d'achat autonomes ? | $\ge 4 / 5$ |
| **Q5** | **Adoption Opérationnelle** | Recommanderiez-vous l'intégration de ce copilote décisionnel dans votre routine hebdomadaire d'analyse de marché ? | $\ge 4 / 5$ |

---

## 4. Critères de Déblocage du Statut `HUMAN_EVALUATED`

1. Au moins 3 séances documentées conduites avec des représentants distincts (1 institutionnel, 1 grossiste, 1 agronome).
2. Fiche de synthèse signée consignée dans `docs/pilot/evaluations/`.
3. Score moyen sur l'ensemble des 5 critères $\ge 3.8 / 5$, et aucun critère $< 3 / 5$.
4. Tant que ces séances ne sont pas réalisées, le système maintient honnêtement `evaluation_status: "NOT_EVALUATED"`.
