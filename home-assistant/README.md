# ha — Home Assistant + Mosquitto

Domotique locale. Accessible via `hub.kiwinet.me`.

> Contexte global : [kiwinet-docs](https://github.com/Rookain-Kiwi/kiwinet-docs)

---

## Stack

| Container       | Réseau  | Rôle              |
|-----------------|---------|-------------------|
| `homeassistant` | `host`  | Serveur domotique |
| `mosquitto`     | `proxy` | Broker MQTT local |

---

## Structure

```
ha/
├── docker-compose.yml
├── mosquitto/config/mosquitto.conf
└── config/             # Données HA (gitignored)
```

---

## Déploiement

```bash
cd /opt/kiwinet-services/ha

docker compose up -d
docker compose logs -f homeassistant

# Mise à jour
docker compose pull && docker compose up -d
```

---

## Premier démarrage

Home Assistant démarre sur `http://localhost:8123` (accès local uniquement).

1. Créer le compte administrateur
2. Ajouter dans `ha/config/configuration.yaml` :

```yaml
http:
  use_x_forwarded_for: true
  trusted_proxies:
    - 172.18.0.0/16   # Réseau proxy Traefik
```

3. Redémarrer HA — `hub.kiwinet.me` est alors accessible

---

## Points critiques

**`network_mode: host`** — obligatoire pour la découverte mDNS (Google Cast, Chromecast, Nest Hub). Les labels Docker ne fonctionnent pas en mode host.

**Route Traefik** — déclarée manuellement dans `../traefik/dynamic.yml`. L'upstream doit pointer vers la gateway du réseau `proxy` (pas `127.0.0.1`).

**MQTT** — Mosquitto écoute sur le port 1883, accessible LAN uniquement.

---

## Intégrations actives

- Google Cast (Nest Audio, Nest Mini, Nest Hub, Google TV)
- Plex via `plex.kiwinet.me`
- Mosquitto MQTT (broker local)
