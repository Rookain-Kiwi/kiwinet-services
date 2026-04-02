# plexbot — Bot Discord + Lavalink

Bot Discord permettant le streaming de musique Plex en vocal.  
PlexBot pilote Lavalink comme moteur audio Java — les deux sont couplés et démarrent ensemble.

---

## Stack

| Container  | Image                              | Rôle                        |
|------------|------------------------------------|-----------------------------|
| `lavalink` | `ghcr.io/lavalink-devs/lavalink:4` | Moteur audio Java           |
| `plexbot`  | `plexbot:latest` (build local)     | Bot Discord                 |

---

## Commandes disponibles

| Commande    | État        | Description                          |
|-------------|-------------|--------------------------------------|
| `/play`     | Fonctionnel | Lecture d'un titre depuis Plex       |
| `/search`   | Désactivé   | Bug upstream Beta 0.9                |
| `/playlist` | Désactivé   | Bug upstream Beta 0.9                |

Note : une dégradation audio est possible sur contenu dense (jitter réseau résidentiel).

---

## Structure

```
plexbot/
├── docker-compose.yml
├── lavalink.yml        ← Config Lavalink (sources audio, filtres)
├── config.fds          ← Config PlexBot (commandes, permissions)
├── .env                ← Tokens Discord/Plex/Lavalink (gitignored)
└── .env.example        ← Template vide
```

---

## Déploiement

PlexBot démarre seulement après que Lavalink soit `healthy` (`depends_on` avec `condition: service_healthy`).

```bash
cd /opt/kiwinet-infra/plexbot

# Démarrage
docker compose up -d

# Logs PlexBot
docker compose logs -f plexbot

# Logs Lavalink
docker compose logs -f lavalink
```

L'image `plexbot:latest` n'est pas disponible sur GHCR — elle est buildée localement sur la VM :

```bash
# Build initial ou après mise à jour
cd /opt/kiwinet-infra/plexbot
git clone https://github.com/<repo-plexbot> /tmp/plexbot-src
docker build -t plexbot:latest -f /tmp/plexbot-src/Install/Docker/Dockerfile /tmp/plexbot-src
docker compose up -d --force-recreate plexbot
```

---

## Variables d'environnement

| Variable            | Description                                      |
|---------------------|--------------------------------------------------|
| `DISCORD_TOKEN`     | Token bot depuis Discord Developer Portal        |
| `PLEX_URL`          | URL interne Plex (`http://172.18.0.1:32400`)     |
| `PLEX_TOKEN`        | Token d'authentification Plex                    |
| `LAVALINK_PASSWORD` | Mot de passe partagé entre Lavalink et PlexBot   |

Créer le `.env` à partir du template :

```bash
cp .env.example .env
# Remplir les valeurs
```

---

## Architecture réseau

Lavalink et PlexBot communiquent sur le réseau `proxy` via le nom de service `lavalink:2333`.  
Aucun port n'est exposé publiquement — le bot se connecte en WebSocket sortant vers l'API Discord.
