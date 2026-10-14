# home-assistant — Home Assistant + Mosquitto

Domotique locale. Accessible via `hub.kiwinet.me`.

> Contexte global : [kiwinet-docs](https://github.com/Rookain-Kiwi/kiwinet-docs)

---

## Stack

| Conteneur        | Réseau                     | Rôle                              |
|------------------|----------------------------|-----------------------------------|
| `home-assistant` | `host`                     | Serveur domotique                 |
| `mosquitto`      | défaut du compose          | Broker MQTT local, authentifié    |

Mosquitto n'est pas sur le réseau `proxy`. Son port est publié sur la boucle
locale (pour Home Assistant, en réseau hôte) et sur l'adresse du réseau local
(`HOST_BIND_IP`).

---

## Structure

```
home-assistant/
├── docker-compose.yml
├── env.example
├── mosquitto/
│   ├── config/
│   │   ├── mosquitto.conf   # versionné
│   │   └── passwd           # comptes MQTT (gitignored, 600)
│   └── data/                # persistance Mosquitto (gitignored)
└── config/                  # données Home Assistant (gitignored)
```

---

## Prérequis

```bash
cd /opt/kiwinet-services/home-assistant

cp env.example .env
chmod 600 .env
nano .env          # HOST_BIND_IP : adresse du serveur sur le réseau local
```

Les données (`config/`, `mosquitto/data/`) sont restaurées **avant** le premier
`docker compose up -d`. Un démarrage sur une configuration vide expose
l'assistant d'accueil (création du compte propriétaire) par la route publique.

---

## Comptes MQTT

Un compte par client (Home Assistant, puis chaque appareil qui publie vers le
broker). Le fichier `passwd` est créé localement, jamais versionné. La saisie du
mot de passe est interactive.

```bash
# Premier compte (crée le fichier)
docker run --rm -it -v "$PWD/mosquitto/config:/mosquitto/config" \
  eclipse-mosquitto:2.1.2-alpine mosquitto_passwd -c /mosquitto/config/passwd <compte>

# Comptes suivants (sans -c)
docker run --rm -it -v "$PWD/mosquitto/config:/mosquitto/config" \
  eclipse-mosquitto:2.1.2-alpine mosquitto_passwd /mosquitto/config/passwd <compte>

# Propriétaire de l'image (uid 1883) et droits stricts
sudo chown 1883:1883 mosquitto/config/passwd
sudo chmod 600 mosquitto/config/passwd
```

Le tag de l'image doit rester identique à celui du compose.

---

## Déploiement

```bash
docker compose config --quiet
docker compose up -d
docker compose logs -f home-assistant
```

---

## Mise à jour

Les images sont épinglées par empreinte : `docker compose pull` ne change rien.

1. Lire les notes de version (changements non rétrocompatibles) et choisir le tag.
   - Home Assistant : version stable sur `https://version.home-assistant.io/stable.json`.
   - Mosquitto : tags sur Docker Hub.
2. Relever l'empreinte de l'**index** du tag.
   ```bash
   # Home Assistant (registre GHCR)
   TOK=$(curl -s "https://ghcr.io/token?scope=repository:home-assistant/home-assistant:pull" | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')
   curl -sI -H "Authorization: Bearer $TOK" \
     -H "Accept: application/vnd.oci.image.index.v1+json" \
     "https://ghcr.io/v2/home-assistant/home-assistant/manifests/<tag>" | grep -i docker-content-digest

   # Mosquitto (Docker Hub) : champ "digest"
   curl -s "https://hub.docker.com/v2/repositories/library/eclipse-mosquitto/tags/<tag>"
   ```
3. Modifier le tag et l'empreinte dans `docker-compose.yml`, commit, push, puis
   `git pull --ff-only` sur le serveur et `docker compose up -d`.

---

## Points critiques

**`network_mode: host`** — obligatoire pour la découverte mDNS (Google Cast,
Chromecast, Nest Hub). Les labels Docker ne fonctionnent pas en mode host.
Home Assistant écoute sur toutes les interfaces du serveur et **ne passe pas
par `DOCKER-USER`** : seul ufw le protège.

**Règles ufw** — autoriser uniquement le réseau local et la plage du réseau
`proxy` vers le port de Home Assistant. Sans elles, la route Traefik renvoie
une erreur 504.

**Route Traefik** — déclarée manuellement dans `../traefik/dynamic.yml`.
L'upstream doit pointer vers la gateway du réseau `proxy` (pas `127.0.0.1`).

**Configuration `http` de Home Assistant** — dans `config/configuration.yaml` :

```yaml
http:
  use_x_forwarded_for: true
  trusted_proxies:
    - 172.18.0.0/16   # plage du réseau proxy : vérifier avec `docker network inspect proxy`
```

**MQTT** — authentification obligatoire. Dans Home Assistant, l'intégration MQTT
vise la boucle locale avec le compte dédié.

**Sauvegardes** — le dossier de sauvegardes de Home Assistant est monté depuis
le disque Data. Si ce disque n'est pas monté, le conteneur ne démarre pas.

**Recorder** — l'historique est stocké dans PostgreSQL (base `home-assistant`,
via la boucle locale). La chaîne de connexion est dans un secret local, jamais
dans Git.

---

## Intégrations actives

- Google Cast (Nest Audio, Nest Mini, Nest Hub, Google TV)
- Jellyfin (intégration native)
- Music Assistant
- Mosquitto MQTT (broker local)
