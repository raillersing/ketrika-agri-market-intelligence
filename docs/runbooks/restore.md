# Sauvegarde et restauration sur clone neuf

AU-07 en développement : les tests négatifs ne réceptionnent pas encore le lot complet. Aucun déploiement ni corpus historique n'est qualifié. Voir [plan préalable](../audits/2026-10-25/RESTORE_IMPLEMENTATION_PLAN.md) et ADR124.

Une sauvegarde utilisable comprend l'archive PostgreSQL personnalisée, son `.dump.sha256` et son manifeste `.dump.meta.json` (ou `.meta.json`). Les trois doivent désigner les mêmes octets, taille, nom d'archive et base source. L'alias `latest` possède ses propres compagnons cohérents. `backup` passe par le script vérifiant réellement `pg_restore --list`, sans activer Restic depuis le point d'entrée local. Les anciennes archives sans compagnons restent conservées ; elles ne sont pas déclarées vérifiées automatiquement.

La restauration exige une instance PostgreSQL dédiée sur un réseau Docker interne portant le label `ketrika.scope=restore-qualification`. Préparer cette instance indépendamment de la pile active, sans ports publiés et sans volume Bronze. Configurer explicitement `KETRIKA_RESTORE_NETWORK`, `PGHOST`, `PGPORT`, `PGUSER`, le secret de connexion local, `PGDATABASE=ketrika_restore_<identifiant_unique>` et `RESTORE_CONFIRM_DATABASE` égal à ce même nom. Ne pas utiliser le service DB actif comme destination. Le client PostgreSQL `postgis/postgis:17-3.5` doit déjà être disponible localement ; aucun téléchargement implicite au lancement.

Puis utiliser le point d'entrée unique :

```bash
bash scripts/dev.sh restore backups/ketrika_backup_latest.dump
```

Sous PowerShell, après configuration des mêmes variables d'environnement :

```powershell
./scripts/dev.ps1 restore backups/ketrika_backup_latest.dump
```

Les wrappers montent uniquement code et dossier de sauvegarde en lecture seule dans le client isolé. Le script refuse les preuves manquantes, l'archive illisible, une cible non confirmée, active, identique à la source ou déjà existante. Il crée atomiquement une nouvelle base, restaure dans une transaction et s'arrête sur tout statut non zéro. Aucune connexion n'est interrompue, aucun schéma existant nettoyé, aucun Gold recalculé automatiquement. Un clone échoué reste disponible au diagnostic ; choisir un autre nom après correction, sans effacer une base pour contourner le garde. `ALLOW_ACTIVE_DB_OVERWRITE=1` est refusé.

Après réussite, comparer sur ce clone les lignes, valeurs, clés, révisions et parents Bronze avec les preuves de la sauvegarde ; le seul comptage ne suffit pas. Vérifier séparément la lisibilité et les empreintes des objets Bronze, les migrations et les permissions applicatives. Le contrôle de fichier ne prouve ni authenticité des données ni continuité métier. Les objectifs RPO<24h/RTO<15min doivent être mesurés sur le scénario reçu ; ils ne sont pas des résultats déjà acquis.

Les helpers Python refusent outil/manifeste/checksum manquants. Le mode explicite `check_pg_restore=False` vérifie uniquement les métadonnées et annonce sa limite ; il ne constitue pas une archive restaurable qualifiée. La création d'un manifeste sans contrôle structurel porte `verified_readable=false`. Toute erreur de comptage SQL reste un échec, jamais un zéro.
