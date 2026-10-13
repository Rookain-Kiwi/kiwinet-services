# pgadmin

Interface d'administration PostgreSQL — accès web à l'instance mutualisée Kiwinet.

Exposé sur `pgadmin.kiwinet.me` via Traefik. Exposition publique **provisoire**, jusqu'à la validation de l'accès d'administration par WireGuard. Trois barrières successives :

1. limitation de débit (middleware `rate-limit` de Traefik) ;
2. authentification de base (middleware `auth-basic` de Traefik, avant même d'atteindre PgAdmin) ;
3. connexion PgAdmin, avec double authentification TOTP obligatoire.

## Prérequis

- Réseaux Docker `proxy` et `db` existants
- Instance PostgreSQL démarrée (`postgres/docker-compose.yml`)
- Middlewares `rate-limit` et `auth-basic` définis dans la configuration dynamique de Traefik

## Démarrage

```bash
cp env.example .env
chmod 600 .env
# Éditer .env avec email et mot de passe souhaités
docker compose up -d
```

`docker compose` refuse de démarrer si `PGADMIN_EMAIL` ou `PGADMIN_PASSWORD` manque dans `.env`.

## Première connexion

Sur `https://pgadmin.kiwinet.me` :

1. Saisir les identifiants de l'authentification de base (ceux du tableau de bord Traefik).
2. Se connecter à PgAdmin avec l'email et le mot de passe de `.env`.
3. Enrôler la double authentification : scanner le code QR avec une application TOTP. L'enrôlement est imposé à la première connexion.

## Connexion à PostgreSQL depuis PgAdmin

1. Ajouter un nouveau serveur
2. Onglet **General** : nom `Kiwinet`
3. Onglet **Connection** :
   - Host : `postgres` (nom du container — résolution DNS Docker)
   - Port : `5432`
   - Username : valeur de `POSTGRES_USER` dans `postgres/.env`
   - Password : mot de passe de ce rôle

## Mise à jour

L'image est épinglée par empreinte : elle ne change jamais toute seule. Pour mettre à jour, choisir une version, relever son empreinte, modifier la ligne `image` du compose, puis `docker compose pull` et `docker compose up -d`.

## Notes

- Le mot de passe maître PgAdmin ne s'applique pas ici : il ne concerne que le mode bureau, ou le mode serveur avec une authentification OAuth2, Kerberos ou Webserver.
- Le volume `pgadmin-data` persiste la configuration des serveurs enregistrés.
- `traefik.docker.network=proxy` est obligatoire car PgAdmin est sur deux réseaux — sans cette directive Traefik ne sait pas lequel utiliser pour le routage.
- Sous `no-new-privileges`, PgAdmin ne peut pas écouter sur le port privilégié 80 : son port d'écoute est fixé à 8080 (`PGADMIN_LISTEN_PORT`) et Traefik route vers ce port.
- Le message `sudo: The "no new privileges" flag is set` dans les journaux au démarrage est attendu avec ce réglage.
- Aucun port n'est publié sur l'hôte : l'accès passe uniquement par Traefik.
