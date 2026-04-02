# kiwinet-infra

Configuration de l'infrastructure centrale de `kiwinet.me`.  
Reverse proxy Traefik, services applicatifs, domotique et bot Discord — un compose par service.

---

## Rôle de ce repo

Ce repo centralise la configuration de tous les services auto-hébergés sur la VM `kiwinet.me`. Chaque service est isolé dans son propre sous-dossier avec son `docker-compose.yml`.

Il fait partie d'un ensemble de quatre repos qui constituent l'infrastructure de `kiwinet.me` :

| Repo                 | Rôle                                  | URL déployée         |
|----------------------|---------------------------------------|----------------------|
| **`kiwinet-infra`**  | Services, reverse proxy, domotique    | —                    |
| `kiwinet-web`        | Site principal Astro + Nginx          | `kiwinet.me`         |
| `kiwinet-status`     | Page de statut Uptime Kuma            | `status.kiwinet.me`  |
| `kiwinet-monitoring` | Stack Prometheus / Loki / Grafana     | `grafana.kiwinet.me` |

---

## Architecture générale

```
Internet
    │
    ▼
82.67.126.108 (IP fixe)
    │
    ├── :80   → Freebox → VM → Traefik  (HTTP Challenge Let's Encrypt + redirection HTTPS)
    ├── :443  → Freebox → VM → Traefik
    │               │
    │               ├── kiwinet.me / www.kiwinet.me  → kiwinet-web (CI/CD auto)
    │               ├── traefik.kiwinet.me           → dashboard Traefik (auth-basic)
    │               ├── plex.kiwinet.me              → Plex natif VM:32400
    │               ├── ha.kiwinet.me                → Home Assistant (network_mode: host)
    │               ├── status.kiwinet.me            → Uptime Kuma (kiwinet-status)
    │               └── grafana.kiwinet.me           → Grafana (kiwinet-monitoring)
    │
    ├── :22    → SSH (hors Docker)
    ├── :25565 → Minecraft (TCP brut via Traefik passthrough)
    └── :1883  → Mosquitto MQTT (LAN uniquement)
```

**Réseaux Docker :**
- `proxy` (bridge, externe) — créé par `traefik/`, partagé par tous les services exposés
- `monitoring` (bridge, interne) — isolé entre Prometheus, Loki, Grafana, exporters (géré par `kiwinet-monitoring`)

---

## Structure du repo

```
kiwinet-infra/
├── traefik/                    ← Reverse proxy — point d'entrée unique
│   ├── docker-compose.yml
│   ├── traefik.yml             ← Config statique (restart requis si modifié)
│   ├── dynamic.yml             ← Config dynamique (routers, services, middlewares)
│   └── acme.json               ← Certificats Let's Encrypt (chmod 600, gitignored)
├── minecraft/                  ← Serveur Minecraft Java Edition
│   ├── docker-compose.yml
│   └── .env                    ← RCON_PASSWORD (gitignored)
├── plexbot/                    ← Bot Discord + moteur audio Lavalink
│   ├── docker-compose.yml
│   ├── lavalink.yml
│   ├── config.fds
│   ├── .env                    ← Tokens Discord/Plex/Lavalink (gitignored)
│   └── .env.example            ← Template vide commité
└── ha/                         ← Home Assistant + Mosquitto MQTT
    ├── docker-compose.yml
    ├── mosquitto/config/mosquitto.conf
    └── config/                 ← Données HA (gitignored)
```

---

## Déploiement

Chaque service se gère indépendamment depuis son sous-dossier :

```bash
# Traefik en premier (crée le réseau proxy)
cd traefik && docker compose up -d

# Puis les services dans n'importe quel ordre
cd minecraft && docker compose up -d
cd plexbot   && docker compose up -d
cd ha        && docker compose up -d
```

Workflow de mise à jour :

```bash
# Machine locale
git push origin main

# VM
cd /opt/kiwinet-infra
git pull
cd <service> && docker compose up -d --force-recreate
```

---

## Réseau proxy

Le réseau `proxy` est créé par `traefik/docker-compose.yml`. Tous les autres services le déclarent comme `external: true` — ils ne le créent pas.

**Traefik doit toujours démarrer en premier.**

---

## Gestion SSL

### Stratégie : HTTP Challenge (Let's Encrypt)

```
1. Traefik contacte Let's Encrypt pour un domaine donné
2. Let's Encrypt envoie une requête HTTP sur :80 vers ce domaine
3. Traefik répond avec le token de validation
4. Let's Encrypt vérifie → émet le certificat
5. Traefik stocke le certificat dans acme.json
6. Renouvellement automatique 30 jours avant expiration
```

Un certificat wildcard (`*.kiwinet.me`) aurait nécessité un DNS Challenge — non disponible chez Bluehost (absence d'API DNS publique). Le HTTP Challenge implique un certificat par domaine.

### Certificats gérés

| Domaine               | Renouvellement                    |
|-----------------------|-----------------------------------|
| `kiwinet.me` + `www`  | Automatique (Traefik)             |
| `traefik.kiwinet.me`  | Automatique (Traefik)             |
| `plex.kiwinet.me`     | Automatique (Traefik)             |
| `ha.kiwinet.me`       | Automatique (Traefik)             |
| `status.kiwinet.me`   | Automatique (Traefik)             |
| `grafana.kiwinet.me`  | Automatique (Traefik)             |
| `freebox.kiwinet.me`  | Manuel — Certbot, échéance 15/06/2026 |

`freebox.kiwinet.me` est un cas particulier : la Freebox bloque les connexions depuis le réseau local vers ses ports d'administration. Traefik ne peut pas lui faire de proxy. Le certificat est généré avec Certbot standalone (port 80 libéré temporairement) et importé manuellement dans l'interface Freebox.

---

## Middlewares Traefik disponibles

Définis dans `traefik/dynamic.yml`, référencés via `@file` depuis les labels Docker.

| Middleware            | Usage                                          |
|-----------------------|------------------------------------------------|
| `auth-basic@file`     | Dashboard Traefik                              |
| `secure-headers@file` | Services publics (site, Plex, Grafana...)      |
| `rate-limit@file`     | Endpoints publics                              |
| `ha-forwardproto@file`| Home Assistant (X-Forwarded-Proto)             |

---

## Points critiques

**Routing vers services natifs VM**  
Depuis un container Docker, `127.0.0.1` pointe vers le container lui-même, pas vers l'hôte :

```yaml
# Ne fonctionne pas
url: "http://127.0.0.1:32400"

# Correct — gateway du réseau proxy
url: "http://172.18.0.1:32400"
```

**`dynamic.yml` — rechargement non fiable**  
Bien que `watch: true` soit configuré, le rechargement à chaud n'est pas fiable sur cette infrastructure. Toujours redémarrer Traefik après modification :

```bash
docker restart traefik
```

**`acme.json` — nettoyage après échec**  
En cas d'échec ACME (rate limit, NXDOMAIN), un simple restart ne suffit pas. Supprimer l'entrée défaillante manuellement :

```bash
cd /opt/kiwinet-infra/traefik && docker compose down

python3 -c "
import json
with open('acme.json', 'r') as f:
    data = json.load(f)
for resolver in data:
    data[resolver]['Certificates'] = [
        c for c in data[resolver].get('Certificates', [])
        if c.get('domain', {}).get('main') not in ['domaine-a-supprimer.kiwinet.me']
    ]
with open('acme.json', 'w') as f:
    json.dump(data, f, indent=2)
print('OK')
"

chmod 600 acme.json && docker compose up -d
```

**Rate limit Let's Encrypt**  
5 tentatives échouées par heure par domaine. En cas de boucles d'erreurs, attendre l'expiration indiquée dans le message d'erreur avant de relancer.

---

## Infrastructure VM

| Composant      | Détail                                          |
|----------------|-------------------------------------------------|
| OS             | Debian GNU/Linux 13.3 (Trixie)                  |
| Architecture   | ARM Cortex-A72 — AArch64 (2 vCPU)              |
| RAM            | 12 Go                                           |
| Virtualisation | QEMU / VirtIO (Freebox Delta)                   |
| Domaine        | `kiwinet.me` — DNS géré chez Bluehost           |
| IP publique    | `82.67.126.108` (fixe)                          |

## Ports UFW ouverts

| Port  | Protocole | Usage                                         |
|-------|-----------|-----------------------------------------------|
| 22    | TCP       | SSH                                           |
| 80    | TCP       | HTTP Challenge + redirection HTTPS            |
| 443   | TCP       | HTTPS                                         |
| 25565 | TCP       | Minecraft (passthrough Traefik)               |
| 1883  | TCP       | Mosquitto MQTT (LAN uniquement)               |
| 32400 | TCP       | Plex (natif VM)                               |
