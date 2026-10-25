# postgres

Instance PostgreSQL mutualisée — base de données partagée entre les services Kiwinet nécessitant un moteur relationnel.

## Prérequis

Réseau Docker `db` créé sur l'hôte :

```bash
docker network create db
```

Répertoire de données créé à la main sur l'hôte. Le propriétaire est `70:70` (UID/GID de l'utilisateur `postgres` de l'image Alpine), les droits sont `700` :

```bash
sudo mkdir -p /var/lib/postgresql/data
sudo chown 70:70 /var/lib/postgresql/data
sudo chmod 700 /var/lib/postgresql/data
```

## Démarrage

```bash
cp env.example .env
chmod 600 .env
# Éditer .env avec les credentials souhaités
docker compose up -d
```

## Ajouter une base pour un nouveau service

```bash
docker exec -it postgres sh -c 'psql -U "$POSTGRES_USER"'
```

```sql
CREATE USER nomservice WITH PASSWORD 'motdepasse';
CREATE DATABASE nomservice OWNER nomservice;
\q
```

Depuis PostgreSQL 15, seul le propriétaire de la base peut créer des objets dans le schéma `public` : d'où `OWNER` plutôt qu'un `GRANT`.

## Bases actives

| Base | Service consommateur | Créée le |
|---|---|---|
| `grafana` | Grafana (données internes) | — |
| `home-assistant` | Home Assistant (historique, recorder) ; le rôle propriétaire s'appelle `homeassistant` | — |
| `rookain` | Base par défaut de l'administrateur (aucun service) | — |

## Notes

- Le port 5432 est publié sur la boucle locale de l'hôte uniquement (`127.0.0.1`), pour les services en réseau hôte comme Home Assistant. Les autres services passent par le réseau Docker `db`. Aucune exposition sur le LAN ni vers l'extérieur.
- `PGDATA` pointe sur un sous-répertoire `/pgdata` pour éviter les conflits de permissions au premier démarrage.
- Le healthcheck `pg_isready` permet aux services dépendants d'utiliser `condition: service_healthy`.
- `docker compose` refuse de démarrer si `POSTGRES_PASSWORD` est absent ou vide dans `.env`.
