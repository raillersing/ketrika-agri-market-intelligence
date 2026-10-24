# MinIO de qualification construit depuis source

Image locale `ketrika-minio:qa-r0`, construite par `scripts/dev.sh qa-build`
ou `scripts/dev.ps1 qa-build`. Le Compose dev construit la même recette sous
`ketrika-minio:dev`. Aucun binaire tiers ni registre MinIO requis.

Sources officielles figées, licence GNU AGPLv3 :

- Serveur : https://github.com/minio/minio/tree/07c3a429bfed433e49018cb0f78a52145d4bedeb
- Client : https://github.com/minio/mc/tree/7394ce0dd2a80935aded936b09fa12cbb3cb8096

La recette Dockerfile de ce dossier contient les commits et le digest Go.
Les licences sont incluses dans `/usr/share/licenses/{minio,mc}/LICENSE`.
La compilation conserve les métadonnées VCS ; `minio --version` et
`mc --version` peuvent annoncer un build de développement, les commits
ci-dessus identifient précisément le code utilisé. Aucun fichier source modifié.

Destinée aux tests isolés et au développement local. Cette recette ne migre
pas les données actives, ne remplace pas leurs volumes et ne reçoit aucun
déploiement de production.
