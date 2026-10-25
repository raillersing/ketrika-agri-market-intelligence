# Dossier d'audit indépendant — lecture et reproduction

- [Rapport20 constats](INDEPENDENT_AUDIT.md)
- [Plan correctif26 lots, fichiers, dépendances et réceptions](CORRECTIVE_EXECUTION_PLAN.md)
- [Matrice74 tâches/18 sources](TASK_CAPABILITY_MATRIX.md) et [JSON machine](task_matrix.json)
- [Preuves](evidence) et [documents historiques conservés](history)

## Pièces de preuve

| Fichier | Portée |
|---|---|
| runtime.json |60 GET avec/sans session, requêtes SQL READ ONLY, inventaire et erreur du constructeur as-of |
| browser.json et captures PNG |12 pages réelles/390px/cookie invalide ; les huit requêtes de réconciliation sont bloquées, pas une réception de collecte |
| copilot.json | Une question déterministe sur les prix du riz, SQL et réponse observés ; pas d'appel fournisseur LLM |
| safety.json / safety-final.json | Contre-exemples sans réseau : SMTP intercepté, faux dump local, révocation entre processus du même module |
| npm-audit.json / npm-prod-audit.json | Avis déclarés par le registre npm sur le lock, périmètres complet et production séparés |
| python-audit.json | Avis pip-audit sur export runtime+geo+ml du lock ; alias possibles, pas44 exploits indépendants |
| runtime-images.txt / docker-version.txt | Identité des images/services et moteur, sans variables d'environnement ni secrets |
| documentary-validation.json / documentary-quality.txt | Réception documentaire, empreinte applicative, matrice et liens ; aucun gate produit |
| manifest.json | SHA/taille des fichiers du dossier au gel documentaire, hors manifeste lui-même |

Les réponses ne contiennent aucun token/cookie. Aucune trace navigateur avec session n'est publiée. Les captures affichent un compte de développement public du projet, pas des personnes collectées.

## Reproduction prudente

Tout Python/Node/navigateur s'exécute dans Docker. `probe_runtime.py` suppose le réseau de l'API locale et la configuration DB/S3 du service, mais ses requêtes SQL sont READ ONLY. Utiliser un nom de sortie neuf ; vérifier l'identité de destination et le code avant d'exécuter. Il ne lance ni collecte ni publication ni LLM.

`probe_browser.py` utilise http://web:3000 et http://api:8000 sur le réseau local. Il observe les pages, bloque explicitement les GET de collections à effets de bord et écrit seulement dans /out. Les identifiants sont ceux de démonstration déjà publics du dépôt ; ne pas les appliquer à un déploiement.

`probe_safety.py` est à exécuter avec --network none : aucun vrai SMTP ou pg_restore, secrets JWT non imprimés. Le module auth inchangé est importé sans initialisation ASGI complète pour isoler le comportement de révocation ; la différence entre ce contre-exemple et un essai multi-worker déployé est conservée dans le rapport.

`validate_audit.py` contrôle les pièces enregistrées et la cohérence des74 tâches/26 lots/20 constats, calcule l'empreinte applicative et le manifeste. Il ne résout aucun défaut applicatif. `update_documents.py` est une migration documentaire à usage unique déjà appliquée ; sa garde refuse une seconde application. Ne pas la relancer pour mettre à jour une preuve.

Les mesures invalidées par un défaut de sonde et le premier timeout d'import sont exclus, pas convertis en résultats. Les versions des scanners éphémères ne sont pas figées ; figer les outils et refaire les scans au lot correctif avant réception sécurité. Aucun benchmark de performance n'est tiré des durées d'import/compilation de cet audit.
