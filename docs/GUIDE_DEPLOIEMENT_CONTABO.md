# Guide de Déploiement en Production : Irooa Ketrika sur Serveur Contabo (Multi-Applications & irooa.store)

> **Document complet disponible au format HTML stylisé :** [`docs/GUIDE_DEPLOIEMENT_CONTABO.html`](GUIDE_DEPLOIEMENT_CONTABO.html)

Ce guide détaille la mise en production de la plateforme sur un **VPS Contabo sous Linux (Ubuntu)** sur lequel **une autre application est déjà hébergée**, en utilisant le nom de domaine **`irooa.store`** avec certificat HTTPS Let's Encrypt automatique.

---

## 1. Principe de non-collision (Zéro Conflit de Ports)

Lorsque votre serveur Contabo héberge déjà une application, les ports 80 et 443 sont généralement déjà pris par le serveur web principal (souvent **Nginx** ou **Apache**).

Pour que les deux applications cohabitent en parfaite harmonie sans interruption de service :
1. **Conteneurs Irooa isolés :**
   - Le Frontend Next.js écoute en local uniquement sur `127.0.0.1:3005`.
   - L'API FastAPI écoute en local uniquement sur `127.0.0.1:8090`.
   - PostgreSQL et MinIO Bronze restent confinés dans leur réseau Docker interne privé `irooa-net` sans exposer le port 5432 sur l'hôte.
2. **Nginx Hôte en chef d'orchestre :**
   - Nginx reçoit tout le trafic 80/443 de la machine.
   - Si la requête vise votre ancienne application ➔ il la transmet vers votre ancienne application.
   - Si la requête vise `irooa.store` ou `www.irooa.store` ➔ il la transmet en proxy inverse vers `http://127.0.0.1:3005`.

---

## 2. Les 9 Étapes Clés du Déploiement

1. **Étape 1 : Diagnostic & Swap 4 Go :** Audit des ports occupés (`ss -tulpn`) et activation du Swap pour éviter les saturations de RAM sur Contabo.
2. **Étape 2 : Configuration DNS :** Création des entrées `A` pour `@` et `www` pointant vers l'IP de votre VPS Contabo.
3. **Étape 3 : Installation sur le VPS :** Clonage du dépôt dans `/var/www/irooa-ketrika`.
4. **Étape 4 : Fichier `docker-compose.contabo.yml` :** Configuration Docker avec ports locaux confinés (`3005` et `8090`) et variables de production `.env`.
5. **Étape 5 : Configuration Nginx de `irooa.store` :** Création du bloc virtuel `/etc/nginx/sites-available/irooa.store` avec timeouts étendus pour les calculs d'extrapolations ML.
6. **Étape 6 : Activation SSL Let's Encrypt :** Obtention du certificat HTTPS avec `certbot --nginx -d irooa.store -d www.irooa.store`.
7. **Étape 7 : Lancement de la Stack :** Démarrage avec `docker compose -f docker-compose.contabo.yml up -d --build`.
8. **Étape 8 : Création du compte administrateur :** Commande Python pour enregistrer l'analyste/admin de production.
9. **Étape 9 : Vérification et Maintenance :** Commandes de mise à jour quotidienne (`git pull`) et sauvegardes automatiques.

---

> [!TIP]
> Ouvrez le fichier [`GUIDE_DEPLOIEMENT_CONTABO.html`](file:///mnt/c/Users/raillersing/Documents/%23Entreprise/Ketrika%20AI/AI%20Agent/docs/GUIDE_DEPLOIEMENT_CONTABO.html) dans votre navigateur pour profiter d'un design interactif avec boutons de copie des commandes terminal en un clic !
