# pgadmin

Interface d'administration PostgreSQL — accès web à l'instance mutualisée Kiwinet.

Exposé sur `pgadmin.kiwinet.me` via Traefik, protégé par authentification native PgAdmin.

## Prérequis

- Réseau Docker `proxy` et `db` existants
- Instance PostgreSQL démarrée (`postgres/docker-compose.yml`)

## Démarrage

```bash
cp .env.example .env
# Éditer .env avec email et mot de passe souhaités
docker compose up -d
```

## Connexion à PostgreSQL depuis PgAdmin

Lors de la première connexion sur `https://pgadmin.kiwinet.me` :

1. Ajouter un nouveau serveur
2. Onglet **General** : nom `Kiwinet`
3. Onglet **Connection** :
   - Host : `postgres` (nom du container — résolution DNS Docker)
   - Port : `5432`
   - Username : valeur de `POSTGRES_USER` dans `postgres/.env`
   - Password : valeur de `POSTGRES_PASSWORD` dans `postgres/.env`

## Notes

- `PGADMIN_CONFIG_MASTER_PASSWORD_REQUIRED: False` — le mot de passe maître PgAdmin est désactivé pour simplifier l'accès mono-utilisateur
- Le volume `pgadmin-data` persiste la configuration des serveurs enregistrés
- `traefik.docker.network=proxy` est obligatoire car PgAdmin est sur deux réseaux — sans cette directive Traefik ne sait pas lequel utiliser pour le routage
