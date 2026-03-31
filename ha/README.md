# ha — Home Assistant

Domotique locale intégrée à la stack kiwinet-infra.

## Stack

| Conteneur | Rôle | Réseau |
|---|---|---|
| `homeassistant` | Serveur domotique principal | `host` (mDNS requis) |
| `mosquitto` | Broker MQTT local | `proxy` |

## Accès

- Interface web : **https://ha.kiwinet.me** (via Traefik)
- MQTT : `<IP_VM>:1883` (LAN uniquement)

## Architecture réseau

HA tourne en `network_mode: host` — obligatoire pour la découverte mDNS
des appareils Google Cast, Chromecast et Nest sur le LAN.

La route Traefik est déclarée manuellement dans `../traefik/dynamic.yml`
(même pattern que Plex), car les labels Docker ne fonctionnent pas en mode host.

## Déploiement

```bash
# Depuis la racine du repo
cd ha

# Premier démarrage
docker compose up -d

# Logs en temps réel
docker compose logs -f homeassistant

# Mise à jour
docker compose pull && docker compose up -d
```

## Premier démarrage

1. HA crée son interface sur `http://localhost:8123`
2. Créer le compte administrateur
3. Ajouter dans `ha/config/configuration.yaml` :

```yaml
http:
  use_x_forwarded_for: true
  trusted_proxies:
    - 172.18.0.0/16   # Réseau proxy Traefik
```

4. Redémarrer HA — `ha.kiwinet.me` est alors pleinement fonctionnel

## Structure

```
ha/
├── docker-compose.yml
├── README.md
├── config/                  # Données HA — gitignore
└── mosquitto/
    ├── config/
    │   └── mosquitto.conf
    ├── data/                # gitignore
    └── log/                 # gitignore
```

## Intégrations actives

- **Google Cast** — Nest Audio, Nest Mini, Nest Hub, Google TV
- **Plex** — via `plex.kiwinet.me`
- **Mosquitto MQTT** — broker local pour capteurs IoT futurs
