# postgres

Instance PostgreSQL mutualisée — base de données partagée entre les services Kiwinet nécessitant un moteur relationnel.

## Prérequis

Réseau Docker `db` créé sur la VM :

```bash
docker network create db
```

Répertoire de données avec les bonnes permissions (provisionné par Ansible, rôle `db`) :

```bash
sudo mkdir -p /var/lib/postgresql/data
sudo chown -R 999:999 /var/lib/postgresql/data
```

## Démarrage

```bash
cp .env.example .env
# Éditer .env avec les credentials souhaités
docker compose up -d
```

## Ajouter une base pour un nouveau service

```bash
docker exec -it postgres psql -U kiwinet
```

```sql
CREATE DATABASE nomservice;
CREATE USER nomservice WITH PASSWORD 'motdepasse';
GRANT ALL PRIVILEGES ON DATABASE nomservice TO nomservice;
\q
```

## Bases actives

| Base | Service consommateur | Créée le |
|---|---|---|
| `synapse` | Synapse (Matrix) | — |

## Notes

- Aucun port n'est exposé sur l'hôte — accès uniquement via le réseau Docker `db`
- `PGDATA` pointe sur un sous-répertoire `/pgdata` pour éviter les conflits de permissions au premier démarrage
- Le healthcheck `pg_isready` permet aux services dépendants d'utiliser `condition: service_healthy`
