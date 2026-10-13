# traefik — Reverse proxy

Point d'entrée unique de l'hôte. Aucun service n'est exposé publiquement sans passer par ici.

> Contexte global : [kiwinet-docs](https://github.com/Rookain-Kiwi/kiwinet-docs)

---

## Rôle

- Reverse proxy HTTP/HTTPS avec routing par domaine
- Gestion SSL automatique via Let's Encrypt (HTTP Challenge)
- TCP passthrough pour Minecraft (port 25565) — VPS uniquement
- Création du réseau Docker `proxy` (sous-réseau fixe)
- Accès à l'API Docker en lecture seule via `socket-proxy` (pas de socket monté dans Traefik)

---

## Structure

Ce répertoire contient deux configurations Traefik indépendantes, une par hôte cible.

```
traefik/
├── docker-compose.yml      # Serveur auto-hébergé (x86_64) : Traefik + socket-proxy
├── traefik.yml             # Config statique (serveur auto-hébergé)
├── env.example             # Modèle du .env (HOST_BIND_IP)
├── dynamic/
│   └── dynamic.yml         # Config dynamique (serveur auto-hébergé)
├── .env                    # HOST_BIND_IP (local, gitignored)
├── acme.json               # Certificats TLS (chmod 600, gitignored)
├── .htpasswd               # Auth basic dashboard (gitignored)
│
├── docker-compose.vps.yml  # VPS Scaleway (AMD64)
├── traefik.vps.yml         # Config statique VPS
├── dynamic.vps.yml         # Config dynamique VPS
└── acme.vps.json           # Certificats TLS VPS (chmod 600, gitignored)
```

---

## Déploiement

### Serveur auto-hébergé (x86_64, Debian 13)

```bash
cd /opt/kiwinet-services/traefik

# Prérequis : .env, acme.json et .htpasswd
# (voir « Fichiers locaux à créer avant premier démarrage »)
chmod 600 acme.json .htpasswd

# Contrôle de la configuration, puis démarrage
docker compose config --quiet
docker compose up -d

# Après modification de traefik.yml
docker compose restart

# Après modification de dynamic.yml
docker restart traefik
```

### VPS Scaleway (AMD64)

```bash
cd /opt/kiwinet-services/traefik

# Permissions obligatoires avant premier démarrage
chmod 600 acme.vps.json

# Démarrage
docker compose -f docker-compose.vps.yml up -d

# Après modification de traefik.vps.yml
docker compose -f docker-compose.vps.yml restart

# Après modification de dynamic.vps.yml
docker restart traefik
```

---

## Fichiers locaux à créer avant premier démarrage

### Serveur auto-hébergé

`.env` — adresse LAN de l'hôte sur laquelle publier les ports 80 et 443 :
```bash
cp env.example .env   # puis renseigner HOST_BIND_IP
```

`acme.json` — fichier vide avec permissions strictes :
```bash
touch acme.json && chmod 600 acme.json
```

`.htpasswd` — identifiants dashboard (bcrypt), à créer depuis `traefik/` :
```bash
htpasswd -nB <utilisateur> >> .htpasswd
chmod 600 .htpasswd
```

### VPS Scaleway

`acme.vps.json` — fichier vide avec permissions strictes :
```bash
touch acme.vps.json && chmod 600 acme.vps.json
```

Le dashboard Traefik n'est pas exposé sur le VPS — pas de `.htpasswd` requis.

---

## Middlewares disponibles

Définis dans `dynamic/dynamic.yml` (serveur auto-hébergé) et dans `dynamic.vps.yml` (VPS), référencés via `@file` depuis les labels Docker.

### Serveur auto-hébergé (`dynamic/`)

| Middleware               | Usage                                 |
|--------------------------|---------------------------------------|
| `auth-basic@file`        | Dashboard Traefik                     |
| `secure-headers@file`    | Services publics                      |
| `rate-limit@file`        | Dashboard Traefik, endpoints publics, Home Assistant, Music Assistant |
| `ha-forwardproto@file`   | Home Assistant (X-Forwarded-Proto)    |

### VPS Scaleway (`dynamic.vps.yml`)

| Middleware            | Usage             |
|-----------------------|-------------------|
| `secure-headers@file` | Services publics  |
| `rate-limit@file`     | Endpoints publics |

---

## Points critiques

**Docker lu via `socket-proxy`** — Traefik ne monte plus le socket Docker : il lit la liste des conteneurs par `socket-proxy` (réseau interne, `CONTAINERS=1`, lecture seule). Un service à exposer doit porter `traefik.enable=true` et être sur le réseau `proxy`.

**Ports publiés sur l'adresse LAN** — les ports 80 et 443 sont liés à `HOST_BIND_IP` (pas de `0.0.0.0`, pas d'IPv6). Le démarrage échoue si la variable n'est pas définie.

**Sous-réseaux fixes** — `proxy` (`172.18.0.0/16`) et `socket-proxy` (`172.31.255.0/29`) sont fixés pour que la création des deux réseaux, faite en parallèle, n'échoue pas par chevauchement. Les routes vers Home Assistant et Music Assistant (`network_mode: host`) visent la passerelle `172.18.0.1`. Le pare-feu de l'hôte (ufw) doit autoriser `172.18.0.0/16` vers les ports `8123` (Home Assistant) et `8095` (Music Assistant).

**Rechargement `dynamic.yml` non fiable** — malgré `watch: true`, toujours redémarrer :
```bash
docker restart traefik
```

**Routing vers services en `network_mode: host`** — depuis un container, `127.0.0.1` pointe vers le container lui-même :
```yaml
# Ne fonctionne pas
url: "http://127.0.0.1:8123"
# Correct
url: "http://172.18.0.1:8123"  # gateway réseau proxy
```

**Nettoyage `acme.json` après échec ACME** (rate limit : 5 tentatives/heure/domaine) :
```bash
docker compose down
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

**`dynamic.yml` — une seule section `http:`** — plusieurs sections provoquent des erreurs de parsing silencieuses.