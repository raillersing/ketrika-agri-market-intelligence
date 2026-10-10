# R0.5 — couverture et limites de provenance

État du 2026-10-10 : incrément pur reçu dans 30d0a837 ; liaison SQL/DQ ciblée
reçue dans 180cc77 (104 tests / deux intégrations, check Windows complet code 0,
515 backend / 35 frontend / build). Les formats préparatoires restent hors dépôt principal.
Cette matrice n'est ni une réception totale R0.5 ni une qualification de marché.

## Formats

| Format | Contrôle pur des octets/cellules | Liaison SQL actuelle |
|---|---|---|
| CSV | SHA réel, ligne zéro-indexée hors en-tête, colonnes nommées, identité et valeur dans la même ligne | Champs autorisés, dates ISO littérales ; autres représentations de période nécessitent un adaptateur testé |
| JSON | SHA réel, scope_path, chemins littéraux sous le même enregistrement, Decimal | Attentes issues de SQL ; raw_expected exige une cellule textuelle, pas une sérialisation supposée d'un token numérique |
| PDF | Non pris en charge, échec fermé | Page/tableau/ligne/cellule et métadonnées de période restent à implémenter |
| HTML | Non pris en charge, échec fermé | Tableau/ligne/cellule et métadonnées restent à implémenter |
| XLSX | Non pris en charge, échec fermé | Feuille/ligne/colonne, date et politique de formule restent à implémenter |

Le JSON WDI authentique vérifie les deux enregistrements macroéconomiques et leurs
cellules indépendamment annotées dans le vérificateur pur. Il n'a pas été chargé
dans Bronze/Silver et n'est pas détourné en prix PPN. Aucun PDF généré n'est authentique.

## Champs SQL actuellement liés

Toutes les valeurs non nulles des listes ci-dessous et les identités non nulles
du type sont exigées. Aucun champ arbitraire ou expected issu du document n'est accepté.
L'absence de valeur ou de preuve échoue ; les lignes ne sont pas retirées du contrôle complet.

| Table | Valeurs source liées | Identités |
|---|---|---|
| price_observation | price_value, avec price_raw exact | product_raw, location_raw, period_start, unit_raw, currency_raw |
| stock_observation | quantity_value/quantity_raw, coverage_days, stock_status | product_raw, location_raw, period_start, unit_raw |
| trade_flow | value_mga, value_usd, weight_kg/weight_raw | product_raw, period_start, flow, hs_code, partner_raw |
| production_observation | value | product_raw, period_start, element, unit_raw |
| weather_observation | value, mais aucune preuve structurée stockée actuellement : échec explicite | date, variable, provider ; raccordement géographique restant |
| cpi_observation | index_value | series_code, series_label, geo_scope, period_start, base_period |

## Limites obligatoires avant réception totale

- Pas de garde Gold branchée dans le deuxième incrément. Ne pas assimiler ce module
  à une validation des nombres convertis price_mga_per_base, quantity_base ou des
  calculs Gold/ML ; périodes finales, acteur et classification d'origine doivent aussi
  être liés par les adaptateurs métier avant qualification complète.
- Pas de conversion implicite de date, de libellé, de devise, de poids ou d'unité.
  Une source sans ces cellules littérales est refusée jusqu'à un adaptateur contractuel.
- value_raw du commerce n'est pas encore rattaché aux deux devises ; value_raw de
  production et evidence/extraction_method météo ne sont pas conservés par le schéma
  actuel. Résoudre explicitement les contrats, sans réécriture destructive des observations.
- llm_verified, dual_agree, human et méthode inconnue ne passent pas l'auditeur actuel.
  Leur étiquette n'est pas une preuve ; page/extrait relus et identité ancrée restent requis.
- Audit complet : toutes les six tables, y compris historique et sources disabled.
  Cela prouve le périmètre sélectionné, pas l'autorisation de collecte d'une source.
  Incrémental : couples table/UUID explicites, absences comptées. Résultats DQ sans
  commit forcé, métrique NULL pour un lot vide, sans valeur/extrait/URL/exception brute.
- Provenance technique, authenticité, droits, collecte live, disponibilité temporelle,
  conversions, validation de modèle et essai humain restent des qualifications distinctes.
