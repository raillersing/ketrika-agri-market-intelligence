# Corpus de qualification et annotation indépendante

R0.4 / ADR-014. Un test logiciel vert n'établit pas une donnée authentique.

## Inventaire

`backend/tests/corpus-manifest.json` couvre fixtures, golden, e2e_data et générateurs.
Les SHA-256 portent sur les octets présents, pas un nom de fichier, une URL ou un hash de format.
Le script Docker `backend/scripts/inventory_corpus.py` produit un inventaire mécanique à examiner ;
il n'authentifie jamais un document. Ne pas le lancer comme remplacement silencieux d'un manifeste
revue/acquisition existant : cela ferait perdre les preuves ajoutées manuellement.

- `synthetic` : générateur identifié dans le dépôt ; usage logiciel seulement. ODR, MinCC,
  douanes et seed E2E sont concernés, même si les libellés ressemblent à des publications.
- `unverified` : fichier historique conservé, origine/droits non prouvés. Cela ne signifie pas
  qu'il est faux, mais interdit son utilisation pour qualifier une performance sur source réelle.
- `authentic` : octets téléchargés officiellement, preuve C1 et droits vérifiables.

Les suites historiques demeurent inchangées. La suite `tests/unit/test_corpus.py` vérifie exhaustivité,
hash, tailles et refus de preuves insuffisantes ; ses reçus temporaires inventés sont des tests
négatifs clairement séparés et ne sont jamais des preuves de collecte.

Exception explicitement bornée ADR-015 : le scénario d'intégration douanier rejoue ses trois UUID
de fixtures courantes, pas toutes les versions historiques du store QA. Il conserve métadonnées
et Bronze, exige zéro objet ignoré et ne constitue pas une preuve de rebuild intégral R0.8.

## Acquisition sûre

Ne jamais écraser une fixture ancienne ni un objet Bronze. Utiliser un conteneur jetable sans
identifiants actifs, montages du dépôt en lecture seule et sortie nouvelle en `/tmp`.
User-Agent déclaré, robots, quotas, HTTPS et redirects autorisés sont obligatoires.
Challenge/401/403 : PolicyStop immédiat. Règle robots refusant une URL : ne jamais la requêter.
Un refus est un résultat, pas une invitation à changer de domaine, de navigateur ou d'identité.

Archiver réponse brute sans transformation sous `tests/fixtures/authentic/` (`-text` Git),
et preuve d'acquisition séparée : origine/catalogue, chaîne autorisée, HTTP/MIME, UTC, taille/SHA,
droits et attribution. Une date de période n'est pas une date de publication ; conserver null
si inconnue. `bronze_object_key: null` explicite un corpus local non ingéré. Les pages de licence
ne prouvent pas la licence des anciennes fixtures. Ne pas archiver des noms/emails de particuliers.

## Annotation

1. Ouvrir l'original sans importer ni exécuter le parseur à qualifier.
2. Définir le périmètre exhaustif ou l'extrait avant transcription.
3. JSON/CSV : référencer une cellule par chemin de clés/indice ou ligne et colonne ; conserver
   le texte brut et les unités documentées. Ne pas confondre météorologie modélisée avec station,
   prix imputé avec observé ou valeur unitaire du commerce avec prix de marché.
4. PDF texte : relever couche pdfplumber puis rendre la page avec pypdfium2 dans Docker et
   inspecter visuellement ; consigner page/extrait. Pas d'attendu dérivé du pipeline testé.
5. Ajouter annotator=agent, human_reviewed=false, UTC, document et SHA ; toute valeur doit
   remonter mécaniquement à la cellule/page conservée.
6. Tester séparément la preuve d'annotation et le parseur ; un extrait ne peut établir le rappel
   global 98 %. Aucune métrique d'accuracy n'est extrapolée aux sources absentes.

H5 reste ouvert. Seule une revue humaine effective peut changer human_reviewed, avec preuve.

## Disponibilité constatée le 2026-10-09

- HDX catalogue : 403 via lecteur web, B-R009 ; aucune relance/contournement, à porter R1.3.
- NASA POWER API : refus robots `/api/`, B-R010 ; aucune requête API de données envoyée,
  à porter à R1.7. La documentation accessible ne lève pas cette règle.
- Les archives encore non acquises ne sont pas remplacées par les jeux générés.
- WDI : réponse publique officielle acquise le 2026-10-09T19:49:48.046199Z, deux valeurs
  annuelles de PIB Madagascar, 510 octets. Golden indépendant : dix cellules identifiées,
  deux records de cette réponse bornée. Ce corpus ne qualifie aucun prix, météo ni collecteur R2.2.
  Le catalogue de licences a répondu 200 ; droits CC BY 4.0 avec termes additionnels/attribution.
  Robots API 404 explicitement enregistré (RFC 9309, absence de règles), pas de refus ignoré.
