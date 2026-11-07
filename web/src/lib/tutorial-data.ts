/**
 * Données et logique métier du Tutoriel Interactif Gamifié (Académie Irooa Ketrika).
 * Contient l'intégralité des détails d'audit, les briefings de mission,
 * les checklists d'objectifs, les téléportations, et les mini-défis de validation.
 */

export interface QuestStep {
  id: string;
  label: string;
  description: string;
  actionUrl?: string;
  actionLabel?: string;
}

export interface QuestQuiz {
  question: string;
  options: string[];
  correctIndex: number;
  explanation: string;
}

export interface QuestMission {
  id: string;
  number: number;
  title: string;
  subtitle: string;
  category: "Exploration" | "Prédictions" | "Territoires" | "DataOps" | "Macroclimat" | "IA & Copilote" | "Gouvernance";
  icon: string;
  badgeName: string;
  badgeIcon: string;
  xpReward: number;
  estimatedMinutes: number;
  briefing: {
    context: string;
    keyPoints: string[];
    technicalRules: string[];
    warnings?: string;
  };
  steps: QuestStep[];
  quiz: QuestQuiz;
  teleportUrl: string;
  teleportLabel: string;
}

export const QUEST_MISSIONS: QuestMission[] = [
  {
    id: "quest-1-prices",
    number: 1,
    title: "L'Observateur des Marchés",
    subtitle: "Explorer les cours réels et comprendre la qualification des données",
    category: "Exploration",
    icon: "TrendingUp",
    badgeName: "Gardien de la Provenance",
    badgeIcon: "🛡️",
    xpReward: 150,
    estimatedMinutes: 4,
    briefing: {
      context:
        "Sur les marchés vivriers malgaches, les prix au détail du riz, du maïs ou de l'huile fluctuent fortement selon les saisons (périodes de soudure vs grandes récoltes). L'application Irooa Ketrika vous donne accès aux séries mensuelles réelles consolidées.",
      keyPoints: [
        "Un prix médian mensuel est calculé à partir des relevés de terrain réels (en Ariary par kg ou litre).",
        "L'amplitude [Min – Max] mesure la dispersion des prix constatés entre les différents marchés pour un même mois.",
        "Le bandeau de filtres en haut permet de basculer instantanément entre Riz local, Huile, Sucre, Farine, Maïs, etc.",
      ],
      technicalRules: [
        "Badge vert 'Observé' : Donnée directement constatée sur un marché physique et traçable dans MinIO Bronze via son empreinte SHA-256.",
        "Badge violet 'Imputé' : Donnée estimée par régression ou parité nationale lorsque le relevé spécifique est manquant (conformité Principe 9 AGENTS.md).",
        "Badge orange 'Prévu' : Projection statistique pour les mois futurs.",
      ],
      warnings:
        "Ne confondez jamais une valeur imputée avec un relevé de terrain. La plateforme affiche toujours explicitement la nature de chaque valeur pour une transparence totale.",
    },
    steps: [
      {
        id: "step-1-1",
        label: "Ouvrir l'explorateur de prix",
        description: "Rendez-vous sur la page des prix vivriers pour accéder au tableau de bord des séries.",
        actionUrl: "/prices",
        actionLabel: "Aller sur /prices",
      },
      {
        id: "step-1-2",
        label: "Sélectionner le Riz blanc local",
        description: "Dans le filtre supérieur, choisissez 'Riz blanc local' (RICE_WHITE_LOCAL) pour charger sa série historique.",
        actionUrl: "/prices?product=RICE_WHITE_LOCAL",
        actionLabel: "Filtrer sur le Riz Local",
      },
      {
        id: "step-1-3",
        label: "Examiner la fourchette de dispersion",
        description: "Survolez la courbe du graphique interactif pour observer les prix minimums, médians et maximums d'un mois.",
      },
    ],
    quiz: {
      question: "Que garantit obligatoirement un badge vert 'Observé' à côté d'un prix de 3 400 Ar/kg ?",
      options: [
        "C'est une estimation calculée par une intelligence artificielle.",
        "C'est un relevé de marché réel directement vérifié, relié à un document brut immuable dans MinIO Bronze.",
        "C'est un prix moyen national sans origine précise.",
        "C'est un prix d'annonce indicatif trouvé sur les réseaux sociaux.",
      ],
      correctIndex: 1,
      explanation:
        "Exactement ! Conformément au Principe 1 d'AGENTS.md, chaque valeur observée dispose d'une provenance Bronze à 100% avec son empreinte SHA-256 infalsifiable.",
    },
    teleportUrl: "/prices?product=RICE_WHITE_LOCAL",
    teleportLabel: "Se téléporter sur les Prix",
  },
  {
    id: "quest-2-forecasts",
    number: 2,
    title: "L'Oracle Prédictif",
    subtitle: "Maîtriser les extrapolations à 12 mois et la matrice comparative",
    category: "Prédictions",
    icon: "Sparkles",
    badgeName: "Oracle des Séries Temporelles",
    badgeIcon: "📈",
    xpReward: 150,
    estimatedMinutes: 5,
    briefing: {
      context:
        "Pour anticiper les tensions alimentaires jusqu'à un an à l'avance, la plateforme entraîne en parallèle plusieurs familles d'algorithmes statistiques et économétriques indépendants.",
      keyPoints: [
        "Curseur d'horizon temporel : permet de projeter la courbe de 1 à 12 mois dans le futur.",
        "Modèle ⭐ Recommandé (Vainqueur) : sélectionne automatiquement la technique ayant obtenu la plus faible erreur (MAPE minimal) lors du backtest rigoureux sur les 6 dernières fenêtres glissantes.",
        "Modèle 🌟 Consensus (Ensemble) : combine les prévisions pondérées de tous les modèles pour minimiser le risque d'erreur unitaire.",
        "AutoARIMA & AutoETS : capturent les tendances dynamiques et la saisonnalité agricole cyclique.",
        "Saisonnalité Naïve (SNaïf) : reporte les variations constatées exactement 12 mois plus tôt (idéal pour calibrer l'effet de soudure).",
      ],
      technicalRules: [
        "La Matrice Comparative déroulante affiche côte-à-côte les trajectoires chiffrées de tous les modèles mois par mois.",
        "Les bornes [P10 – P90] définissent l'intervalle de confiance conforme à 80% : il y a 80% de probabilité que le cours réel s'inscrive dans cette fourchette.",
        "Règle constitutionnelle d'abstention : tout produit ayant moins de 24 mois réels d'historique s'abstient pour ne générer aucun chiffre imaginaire.",
      ],
      warnings:
        "Une prévision n'est jamais une certitude absolue. Utilisez toujours la matrice comparative pour vérifier si les modèles convergent vers la même direction.",
    },
    steps: [
      {
        id: "step-2-1",
        label: "Régler l'horizon sur 12 mois",
        description: "Sur la page des prix, cliquez sur le bouton '+12 mois' ou glissez le curseur au maximum pour voir la projection sur 1 an.",
        actionUrl: "/prices?product=RICE_WHITE_LOCAL",
        actionLabel: "Ouvrir les prévisions",
      },
      {
        id: "step-2-2",
        label: "Comparer le Vainqueur et le Consensus",
        description: "Basculez entre l'onglet '⭐ Sélection Recommandée' et '🌟 Consensus Multi-Modèles' pour voir comment la courbe projetée s'adapte.",
      },
      {
        id: "step-2-3",
        label: "Dérouler la Matrice Comparative",
        description: "Cliquez sur 'Afficher la matrice comparative de tous les modèles' pour observer le tableau exhaustif mois par mois.",
      },
    ],
    quiz: {
      question: "À quoi sert la fourchette [P10 – P90] affichée sous chaque prix projeté ?",
      options: [
        "Au prix le moins cher et le plus cher du marché mondial.",
        "À un intervalle de confiance à 80% qui encadre les scénarios réalistes haut et bas sans affirmer une certitude illusoire.",
        "Aux taxes douanières minimales et maximales applicables.",
        "À la marge bénéficiaire des grossistes.",
      ],
      correctIndex: 1,
      explanation:
        "Parfait ! L'intervalle conforme [P10 – P90] évite les faux sentiments de certitude et modélise rigoureusement la dispersion probable du marché.",
    },
    teleportUrl: "/prices?product=RICE_WHITE_LOCAL",
    teleportLabel: "Se téléporter sur la Matrice",
  },
  {
    id: "quest-3-territories",
    number: 3,
    title: "Le Cartographe des 23 Régions",
    subtitle: "Explorer les disparités territoriales et les bassins de production",
    category: "Territoires",
    icon: "Map",
    badgeName: "Explorateur des Terroirs",
    badgeIcon: "🗺️",
    xpReward: 150,
    estimatedMinutes: 4,
    briefing: {
      context:
        "Madagascar présente d'immenses disparités géographiques de prix : les bassins greniers (ex: lac Alaotra) affichent des prix bord champ avantageux, tandis que les zones enclavées ou le grand Sud subissent de lourds surcoûts logistiques.",
      keyPoints: [
        "Carte choroplèthe interactive des 23 régions administratives (codes officiels P-codes MDG11 à MDG72).",
        "Coloration thermique : du vert (marchés plus abordables) vers l'orange et le rouge (marchés plus onéreux).",
        "Comparateur avec le repère national : permet d'identifier immédiatement si une région est en surcoût (+X%) ou en décote par rapport à la médiane nationale.",
      ],
      technicalRules: [
        "Principe de vérité territoriale : si une région n'a fait l'objet d'aucune collecte réelle sur le mois, elle reste grisée avec la mention 'Non renseigné'.",
        "L'application interdit d'inventer des prix régionaux pour 'remplir la carte'.",
      ],
    },
    steps: [
      {
        id: "step-3-1",
        label: "Accéder à la carte des territoires",
        description: "Rendez-vous sur la page '/map' pour charger la carte choroplèthe de Madagascar.",
        actionUrl: "/map",
        actionLabel: "Aller sur /map",
      },
      {
        id: "step-3-2",
        label: "Sélectionner une région sur la carte",
        description: "Cliquez sur une région (ex: Alaotra-Mangoro ou Analamanga) pour faire apparaître le volet de détail.",
      },
      {
        id: "step-3-3",
        label: "Comparer à l'indice national",
        description: "Examinez l'encart repère national pour situer le prix régional par rapport à l'ensemble du pays.",
      },
    ],
    quiz: {
      question: "Pourquoi certaines régions apparaissent-elles en gris neutre sans coloration sur la carte ?",
      options: [
        "Parce que la région n'a plus d'habitants.",
        "Parce qu'aucun relevé réel n'y a été collecté : le système refuse d'inventer des données fictives.",
        "Parce que les produits y sont gratuits.",
        "Parce que la région est en rupture de stock définitive.",
      ],
      correctIndex: 1,
      explanation:
        "Exactement ! Une zone grise indique une absence de données réelles vérifiées. L'application préfère la vérité de l'incomplétude à la fiction d'une donnée inventée.",
    },
    teleportUrl: "/map?product=RICE_WHITE_LOCAL",
    teleportLabel: "Se téléporter sur la Carte",
  },
  {
    id: "quest-4-catalog",
    number: 4,
    title: "L'Alchimiste du Catalogue",
    subtitle: "Ajouter un produit et injecter des relevés avec preuve Bronze SHA-256",
    category: "DataOps",
    icon: "Package",
    badgeName: "Maître du Catalogue Bronze",
    badgeIcon: "📦",
    xpReward: 150,
    estimatedMinutes: 5,
    briefing: {
      context:
        "Vous avez besoin de suivre une denrée qui n'était pas dans le catalogue initial (ex: oignon rouge, girofle, vanille, pomme de terre, café) ? L'application vous permet de créer dynamiquement le produit et d'ingérer vos propres relevés réels de terrain !",
      keyPoints: [
        "Création de produit : définit le code canonique (ex: ONION_LOCAL), le nom français, la catégorie vivrière, l'unité légale et les synonymes (alias).",
        "Synchronisation miroir YAML : chaque produit et alias créé est automatiquement consigné dans taxonomy/products.yaml et taxonomy/aliases.yaml pour une rejouabilité totale hors ligne (Principe 4 AGENTS.md).",
        "Ingestion de relevés : stocke le fichier brut dans MinIO Bronze avec son empreinte SHA-256 immuable, insère l'observation Silver et recalcule instantanément les vues Gold.",
      ],
      technicalRules: [
        "Preuve de reçu : chaque lot d'observations renvoie son empreinte bronze_content_hash (ex: 30dd849eaaa...).",
        "Délai d'apprentissage : les nouveaux produits nécessitent 24 mois réels de données avant de débloquer les extrapolations prédictives multi-modèles.",
      ],
    },
    steps: [
      {
        id: "step-4-1",
        label: "Ouvrir la gestion des produits",
        description: "Rendez-vous sur '/products' ou cliquez sur '+ Gérer' dans le bandeau de filtre supérieur.",
        actionUrl: "/products",
        actionLabel: "Aller sur /products",
      },
      {
        id: "step-4-2",
        label: "Explorer la modale '+ Nouveau Produit'",
        description: "Cliquez sur '+ Nouveau Produit' pour découvrir les champs de code, nom officiel, catégorie et alias.",
      },
      {
        id: "step-4-3",
        label: "Tester l'importation de relevés",
        description: "Cliquez sur 'Importer des relevés' sur un produit pour voir comment enregistrer un prix avec preuve Bronze.",
      },
    ],
    quiz: {
      question: "Pourquoi un nouveau produit créé avec seulement 3 mois de données n'affiche-t-il pas encore de prévision ML à 12 mois ?",
      options: [
        "Parce que le serveur est en panne.",
        "Parce que les modèles économétriques et d'apprentissage exigent au minimum 24 mois réels pour extrapoler sans fabriquer de données fictives.",
        "Parce qu'il faut payer un supplément d'abonnement.",
        "Parce que l'importation a échoué.",
      ],
      correctIndex: 1,
      explanation:
        "Très juste ! En vertu de la constitution AGENTS.md §4, la plateforme s'abstient d'extrapoler sur des séries trop courtes pour garantir que chaque projection repose sur un entraînement solide.",
    },
    teleportUrl: "/products",
    teleportLabel: "Se téléporter sur les Produits",
  },
  {
    id: "quest-5-macroclimate",
    number: 5,
    title: "L'Économiste Conjoncturel",
    subtitle: "Décrypter l'observatoire macroéconomique, les carburants et la météo",
    category: "Macroclimat",
    icon: "BarChart3",
    badgeName: "Analyste Macro & Agroclimat",
    badgeIcon: "🌾",
    xpReward: 150,
    estimatedMinutes: 5,
    briefing: {
      context:
        "Les prix du riz et des PPN à Madagascar ne vivent pas en vase clos : ils dépendent directement du taux de change du dollar (BFM), des prix du gasoil pour le transport routier (OMH), des importations douanières et des pluies sur les rizières (CHIRPS).",
      keyPoints: [
        "Observatoire Macroéconomique (/economy) : regroupe 5 dimensions (Inflation NIPC INSTAT, Taux de change BFM USD/EUR, Carburants OMH, Douanes, Activité réelle TBE).",
        "14 fiches métriques normatives : chaque indicateur dispose d'une formule mathématique documentée, de sa source et de ses limites méthodologiques.",
        "Agroclimatologie (/climate) : suivi des précipitations décadaires, calcul des anomalies de sécheresse et calendriers culturaux (semis, floraison, pic de récolte).",
      ],
      technicalRules: [
        "Transparence sur les sources facultatives : les sources satellites non encore stabilisées (ex: GloFAS ou FIRMS) sont signalées 'unavailable' sans faux zéro.",
        "Export CSV direct disponible pour vos modélisations externes.",
      ],
    },
    steps: [
      {
        id: "step-5-1",
        label: "Explorer l'observatoire économique",
        description: "Rendez-vous sur '/economy' pour consulter les parités de change et les prix plafonds des carburants.",
        actionUrl: "/economy",
        actionLabel: "Aller sur /economy",
      },
      {
        id: "step-5-2",
        label: "Consulter une fiche métrique normative",
        description: "Cliquez sur une fiche pour déployer sa formule mathématique exacte et sa source institutionnelle.",
      },
      {
        id: "step-5-3",
        label: "Vérifier la pluviométrie régionale",
        description: "Visitez la page '/climate' pour observer les précipitations et les calendriers culturaux du riz.",
        actionUrl: "/climate",
        actionLabel: "Aller sur /climate",
      },
    ],
    quiz: {
      question: "Quelle institution officielle fixe le barème des prix plafonds des carburants (gazole, super, pétrole) à Madagascar ?",
      options: [
        "L'INSTAT (Institut National de la Statistique).",
        "L'OMH (Office Malgache des Hydrocarbures).",
        "La FAO (Organisation des Nations Unies).",
        "Les compagnies pétrolières de façon arbitraire.",
      ],
      correctIndex: 1,
      explanation:
        "Absolument ! L'OMH publie les barèmes officiels qui déterminent directement le coût du transport kilométrique sur les grands corridors routiers (RN2, RN4, RN7).",
    },
    teleportUrl: "/economy",
    teleportLabel: "Se téléporter sur l'Économie",
  },
  {
    id: "quest-6-copilot",
    number: 6,
    title: "L'Inquisiteur Sans Hallucination",
    subtitle: "Défier le Copilote Analyste avec des requêtes en langage naturel",
    category: "IA & Copilote",
    icon: "MessageSquare",
    badgeName: "Compagnon de l'IA Sobre",
    badgeIcon: "🤖",
    xpReward: 150,
    estimatedMinutes: 4,
    briefing: {
      context:
        "Contrairement aux IA conversationnelles génériques qui inventent des chiffres plausibles mais faux, le Copilote d'Irooa Ketrika est bridé par un SQL Guard strict : il n'écrit JAMAIS un nombre qui ne provient pas d'une requête SQL SELECT exécutée sur les données réelles.",
      keyPoints: [
        "Langage naturel en français : posez des questions telles que 'Quel est le prix médian du riz à Analamanga ?' ou 'Quels ont été les tonnages importés au dernier trimestre ?'.",
        "Citations systématiques : chaque fait est accompagné de la référence précise de l'observation source.",
        "Console SQL d'audit : vous pouvez déplier l'onglet technique pour examiner le code SQL qui a produit le résultat.",
      ],
      technicalRules: [
        "SQL en lecture seule : aucune commande d'écriture (INSERT, UPDATE, DROP) n'est autorisée.",
        "Fidélité absolue (Principe 6 & 7) : si une donnée est absente de la base, le copilote l'indique explicitement au lieu de deviner.",
      ],
    },
    steps: [
      {
        id: "step-6-1",
        label: "Accéder au Copilote Analyste",
        description: "Rendez-vous sur '/copilot' pour ouvrir l'interface de dialogue.",
        actionUrl: "/copilot",
        actionLabel: "Aller sur /copilot",
      },
      {
        id: "step-6-2",
        label: "Tester une question métier",
        description: "Cliquez sur une question suggérée ou tapez votre propre requête dans la zone de texte.",
      },
      {
        id: "step-6-3",
        label: "Déployer la console d'audit SQL",
        description: "Examinez la requête SQL générée sous le capot pour vérifier la transparence complète de la réponse.",
      },
    ],
    quiz: {
      question: "Que fait le Copilote Analyste si vous lui demandez le prix du riz dans une ville où aucune collecte n'a eu lieu ?",
      options: [
        "Il invente un chiffre approximatif basé sur les pays voisins.",
        "Il refuse de générer un nombre fictif et stipule clairement que la donnée est non disponible dans la base.",
        "Il supprime la question de l'utilisateur.",
        "Il génère une blague.",
      ],
      correctIndex: 1,
      explanation:
        "Exactement ! La constitution AGENTS.md §4 interdit formellement d'inventer des chiffres. Le copilote pratique une sobriété et une fidélité absolues.",
    },
    teleportUrl: "/copilot",
    teleportLabel: "Se téléporter sur le Copilote",
  },
  {
    id: "quest-7-governance",
    number: 7,
    title: "La Vigie Institutionnelle",
    subtitle: "Gérer le cycle des alertes précoces et approuver les bulletins",
    category: "Gouvernance",
    icon: "Bell",
    badgeName: "Grand Chancelier de la Veille",
    badgeIcon: "📜",
    xpReward: 100,
    estimatedMinutes: 4,
    briefing: {
      context:
        "La veille de marché prend toute sa valeur quand elle permet d'alerter les décideurs avant une crise et de diffuser des bulletins périodiques rigoureusement validés.",
      keyPoints: [
        "Module d'Alertes (/alerts) : détecte les flambées brutales (+15% en un mois), les anomalies de parité d'importation et les sécheresses menaçant la floraison.",
        "Gestion du cycle de vie des alertes : 'open' (à examiner) ➔ 'acknowledged' (prise en compte par l'équipe) ➔ 'resolved' (clôturée).",
        "Bulletins de veille (/bulletins) : génération automatique hebdomadaire avec traçabilité unitaire de chaque fait chiffré vers sa pièce d'origine ('Pièce 1', 'Pièce 2').",
        "Validation éditoriale : les administrateurs disposent du bouton formel 'Approuver le bulletin' avant toute diffusion.",
      ],
      technicalRules: [
        "Séparation des rôles (RBAC) : la modification des statuts d'alerte et l'approbation des bulletins requièrent un rôle administrateur ou analyste qualifié.",
        "Zéro envoi externe incontrôlé : les brouillons restent confinés dans l'environnement sécurisé (Mailpit).",
      ],
    },
    steps: [
      {
        id: "step-7-1",
        label: "Consulter les alertes enregistrées",
        description: "Rendez-vous sur '/alerts' pour examiner les signaux précoces ouverts.",
        actionUrl: "/alerts",
        actionLabel: "Aller sur /alerts",
      },
      {
        id: "step-7-2",
        label: "Examiner les preuves d'un signal",
        description: "Sélectionnez une alerte pour lire la règle déclenchée et ses dates de constatation.",
      },
      {
        id: "step-7-3",
        label: "Explorer les bulletins hebdomadaires",
        description: "Visitez '/bulletins' pour ouvrir un bulletin et découvrir les liens vers les pièces justificatives d'origine.",
        actionUrl: "/bulletins",
        actionLabel: "Aller sur /bulletins",
      },
    ],
    quiz: {
      question: "Quel rôle a le statut d'approbation d'un bulletin par un administrateur ?",
      options: [
        "Il permet de modifier rétroactivement les prix réels.",
        "Il enregistre une validation éditoriale formelle des faits rédigés avant leur archivage ou diffusion institutionnelle.",
        "Il envoie immédiatement des emails à des millions de destinataires inconnus.",
        "Il désactive les alertes du système.",
      ],
      correctIndex: 1,
      explanation:
        "Bravo ! L'approbation est un jalon de gouvernance éditoriale garantissant qu'un humain qualifié a relu et validé les faits extraits avant communication.",
    },
    teleportUrl: "/alerts",
    teleportLabel: "Se téléporter sur les Alertes",
  },
];

export interface PlayerStats {
  level: number;
  levelTitle: string;
  totalXp: number;
  completedQuests: string[];
  unlockedBadges: string[];
  currentQuestId: string;
}

const STORAGE_KEY = "ketrika_tutorial_player_state_v1";
let memoryStore: Record<string, string> = {};

function getStorageItem(key: string): string | null {
  if (typeof window !== "undefined" && window.localStorage) {
    try {
      return window.localStorage.getItem(key);
    } catch {
      return memoryStore[key] || null;
    }
  }
  return memoryStore[key] || null;
}

function setStorageItem(key: string, value: string): void {
  memoryStore[key] = value;
  if (typeof window !== "undefined" && window.localStorage) {
    try {
      window.localStorage.setItem(key, value);
    } catch {}
  }
}

function removeStorageItem(key: string): void {
  delete memoryStore[key];
  if (typeof window !== "undefined" && window.localStorage) {
    try {
      window.localStorage.removeItem(key);
    } catch {}
  }
}

export function getPlayerLevel(xp: number): { level: number; title: string; nextLevelXp: number; prevLevelXp: number } {
  if (xp < 200) {
    return { level: 1, title: "Apprenti Observateur", nextLevelXp: 200, prevLevelXp: 0 };
  } else if (xp < 500) {
    return { level: 2, title: "Explorateur des Terroirs", nextLevelXp: 500, prevLevelXp: 200 };
  } else if (xp < 800) {
    return { level: 3, title: "Analyste Prévisionniste", nextLevelXp: 800, prevLevelXp: 500 };
  } else {
    return { level: 4, title: "Grand Stratège des Marchés", nextLevelXp: 1000, prevLevelXp: 800 };
  }
}

export function loadPlayerStats(): PlayerStats {
  try {
    const raw = getStorageItem(STORAGE_KEY);
    if (!raw) {
      return {
        level: 1,
        levelTitle: "Apprenti Observateur",
        totalXp: 0,
        completedQuests: [],
        unlockedBadges: [],
        currentQuestId: QUEST_MISSIONS[0].id,
      };
    }
    const parsed = JSON.parse(raw);
    const lvlInfo = getPlayerLevel(parsed.totalXp || 0);
    return {
      level: lvlInfo.level,
      levelTitle: lvlInfo.title,
      totalXp: parsed.totalXp || 0,
      completedQuests: parsed.completedQuests || [],
      unlockedBadges: parsed.unlockedBadges || [],
      currentQuestId: parsed.currentQuestId || QUEST_MISSIONS[0].id,
    };
  } catch {
    return {
      level: 1,
      levelTitle: "Apprenti Observateur",
      totalXp: 0,
      completedQuests: [],
      unlockedBadges: [],
      currentQuestId: QUEST_MISSIONS[0].id,
    };
  }
}

export function savePlayerStats(stats: PlayerStats): void {
  try {
    setStorageItem(STORAGE_KEY, JSON.stringify(stats));
  } catch {}
}

export function resetPlayerStats(): PlayerStats {
  try {
    removeStorageItem(STORAGE_KEY);
  } catch {}
  return {
    level: 1,
    levelTitle: "Apprenti Observateur",
    totalXp: 0,
    completedQuests: [],
    unlockedBadges: [],
    currentQuestId: QUEST_MISSIONS[0].id,
  };
}
