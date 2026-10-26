# Diagnostic du démarrage Python — ADR130

Profil readonly du même ordre d'import SQLAlchemy/ORM/auth/errors, sans SQL ni application construite :29,281s avant compilation des distributions,10,172s après. Mesure ponctuelle sur machine partagée, pas garantie de performance générale.

L'image r05 utilise `uv sync --locked --compile-bytecode`, sans changer les versions ni les seuils. Contre-épreuve réelle `test_revocation_survives_new_connection_and_process` : code0,1 test en18,93s ; le processus fils conserve sa limite30s et doit lire la révocation SQLite existante. Ce ciblé ne remplace pas le check complet.

Premier lancement diagnostique r05 : plugins pytest_mock/pytest_timeout non déclarés, échec avant collecte. Commande corrigée avec les quatre plugins du runner existant ; aucun test/dépendance ajouté pour contourner cet échec. Les originaux rouges du check bace9c0 sont conservés séparément.
