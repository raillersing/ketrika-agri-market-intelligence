# MODÈLE DE CONVENTION — Partenariat Institutionnel de Collecte et de Partage des Données d'Approvisionnement Vivrier

> **Statut :** Projet documentaire préparatoire (ADR-088, R5.1).  
> **Avertissement :** Ce document est un modèle destiné à l'équipe humaine responsable de l'exploitation de la plateforme. En conformité avec les règles H3 et H7 d'AGENTS.md, **aucun envoi ni contact de tiers n'est réalisé par l'agent autonome**.

---

## ENTRE LES SOUSSIGNÉS :

1. **L'Opérateur de la Plateforme Ketrika Agri Market Intelligence**, représenté par son équipe de direction technique,  
   *Ci-après dénommé « La Plateforme Ketrika »*,

D'une part,

ET

2. **L'Institution Partenaire** (Direction Régionale de l'Agriculture et de l'Élevage / Observatoire du Riz / Commune Urbaine / Association des Grossistes),  
   *Ci-après dénommée « Le Partenaire Fournisseur »*,

D'autre part.

---

## PRÉAMBULE

Considérant l'importance stratégique de disposer d'informations fiables, transparentes et vérifiables sur les flux d'approvisionnement des produits vivriers de première nécessité (riz, maïs, manioc, sucre, huile, farine, légumineuses) à Madagascar pour éclairer les politiques publiques et renforcer la résilience des marchés ;

Considérant la nécessité absolue de garantir l'anonymisation intégrale des données et de protéger le secret commercial des opérateurs économiques locaux ;

Il a été convenu ce qui suit :

---

## ARTICLE 1 : OBJET DE LA CONVENTION

La présente convention a pour objet de définir les modalités techniques, juridiques et méthodologiques selon lesquelles Le Partenaire Fournisseur transmet à La Plateforme Ketrika des données anonymisées relatives :
- Aux volumes d'arrivages constatés sur les marchés publics désignés ;
- Aux états des stocks globaux périodiques ;
- Aux estimations de récoltes consolidées par bassin.

---

## ARTICLE 2 : PROTECTION STRICTE DES DONNÉES PERSONNELLES (ZÉRO PII)

1. Les Parties conviennent qu'aucune donnée à caractère personnel (nom, prénom, numéro de téléphone, plaque d'immatriculation, identifiant fiscal ou bancaire de commerçant ou de transporteur) ne doit figurer dans les bordereaux ou fichiers transmis.
2. Tout fichier contenant par inadvertance des données nominatives sera immédiatement et automatiquement rejeté par le moteur d'ingestion de Ketrika avec notification d'incident et suppression sans copie.
3. Seuls sont enregistrés les volumes physiques agrégés par marché public, date, produit et modalité de constat (pesée, déclaration ou estimation).

---

## ARTICLE 3 : DROITS D'USAGE, LICENCE ET REDISTRIBUTION

1. Le Partenaire Fournisseur concède à La Plateforme Ketrika une licence non exclusive, gratuite et irrévocable d'ingestion, de normalisation, d'agrégation et de diffusion publique des données anonymisées dans le cadre de la mission d'intérêt général de transparence des marchés.
2. La Plateforme Ketrika s'engage à citer systématiquement Le Partenaire Fournisseur comme source officielle de la donnée dans les interfaces, bulletins et exports API.

---

## ARTICLE 4 : PRÉVENTION DU DOUBLE COMPTAGE ET INTÉGRITÉ SCIENTIFIQUE

Les Parties s'engagent à respecter le protocole de relevé méthodologique de Ketrika :
- Distinction formelle entre arrivages entrants (`inflow_arrival`) et inventaires de stocks (`stock_inventory`).
- Spécification claire des unités physiques d'origine et des modes de pesée ou d'échantillonnage.
- Aucune extrapolation arbitraire non documentée.

---

Fait à Antananarivo, le ____________________  
En deux exemplaires originaux.

**Pour La Plateforme Ketrika**  
*(Représentant dûment habilité)*

**Pour Le Partenaire Fournisseur**  
*(Représentant institutionnel)*
