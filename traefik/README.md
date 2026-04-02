# traefik — Reverse Proxy

Point d'entrée unique de la VM pour tout le trafic HTTP/HTTPS entrant.  
Aucun service n'est exposé publiquement sans passer par ici.

---

## Rôle

Traefik remplit trois fonctions :

- **Reverse proxy HTTP/HTTPS** — routing vers les containers selon le domaine
- **Gestion SSL automatique** — certificats Let's Encrypt via HTTP Challenge
- **TCP passthrough** — Minecraft Java Edition sur le port 25565

---

## Structure

```
traefik/
├── docker-compose.yml  ← Démarrage du container + création du réseau proxy
├── traefik.yml         ← Config statique (restart requis si modifié)
├── dynamic.yml         ← Config dynamique (routers, services, middlewares)
└── acme.json           ← Certificats Let's Encrypt (chmod 600, gitignored)
```

---

## Déploiement

Traefik doit démarrer en premier — il crée le réseau `proxy` dont tous les autres services dépendent.

```bash
cd /opt/kiwinet-infra/traefik

# Premier démarrage
chmod 600 acme.json
docker compose up -d

# Mise à jour image
docker compose pull && docker compose up -d

# Après modification de traefik.yml
docker compose restart

# Après modification de dynamic.yml
docker restart traefik
```

---

## Config statique (`traefik.yml`)

Chargée au démarrage — tout changement nécessite un restart du container.

| Paramètre              | Valeur                          |
|------------------------|---------------------------------|
| Entrypoint HTTP        | `:80` (redirection → HTTPS)     |
| Entrypoint HTTPS       | `:443`                          |
| Entrypoint Minecraft   | `:25565` (TCP)                  |
| SSL resolver           | Let's Encrypt HTTP Challenge    |
| Docker provider        | `exposedByDefault: false`       |
| Dashboard              | `traefik.kiwinet.me` (auth-basic) |

---

## Config dynamique (`dynamic.yml`)

Rechargée à chaud (`watch: true`) — en théorie. En pratique, un `docker restart traefik` reste nécessaire sur cette infrastructure.

Contient :
- **Middlewares** : `auth-basic`, `secure-headers`, `rate-limit`, `ha-forwardproto`
- **Routers** : Plex, Home Assistant (services en `network_mode: host` ou natifs VM)
- **Services** : upstream vers `172.18.0.1` (gateway réseau `proxy`)

---

## Middlewares disponibles

| Middleware              | Référence label               | Usage                       |
|-------------------------|-------------------------------|-----------------------------|
| `auth-basic@file`       | `middlewares=auth-basic@file` | Dashboard Traefik           |
| `secure-headers@file`   | `middlewares=secure-headers@file` | Services publics        |
| `rate-limit@file`       | `middlewares=rate-limit@file` | Endpoints publics           |
| `ha-forwardproto@file`  | `middlewares=ha-forwardproto@file` | Home Assistant         |

---

## acme.json

Fichier critique — contient les clés privées des certificats TLS pour tous les domaines.

```bash
# Permissions obligatoires
chmod 600 traefik/acme.json

# Ne jamais committer (vérifié dans .gitignore)
```

En cas d'échec ACME (rate limit, NXDOMAIN), supprimer l'entrée défaillante avant de relancer :

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

---

## Routing natif VM

Pour les services qui tournent hors Docker (Plex) ou en `network_mode: host` (Home Assistant), l'upstream doit utiliser l'IP gateway du réseau `proxy` :

```yaml
# Ne fonctionne pas depuis un container
url: "http://127.0.0.1:32400"

# Correct — vérifier avec : docker network inspect proxy | grep Gateway
url: "http://172.18.0.1:32400"
```
