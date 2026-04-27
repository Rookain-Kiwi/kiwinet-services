# traefik — Reverse proxy

Point d'entrée unique de la VM. Aucun service n'est exposé publiquement sans passer par ici.

> Contexte global : [kiwinet-docs](https://github.com/Rookain-Kiwi/kiwinet-docs)

---

## Rôle

- Reverse proxy HTTP/HTTPS avec routing par domaine
- Gestion SSL automatique via Let's Encrypt (HTTP Challenge)
- TCP passthrough pour Minecraft (port 25565)
- Création du réseau Docker `proxy`

---

## Structure

Ce répertoire contient deux configurations Traefik indépendantes, une par hôte cible.

```
traefik/
├── docker-compose.yml      # Freebox Delta (VM ARM64)
├── traefik.yml             # Config statique Freebox
├── dynamic.yml             # Config dynamique Freebox
├── acme.json               # Certificats TLS Freebox (chmod 600, gitignored)
├── .htpasswd               # Auth basic dashboard Freebox (gitignored)
│
├── docker-compose.vps.yml  # VPS Scaleway (AMD64)
├── traefik.vps.yml         # Config statique VPS
├── dynamic.vps.yml         # Config dynamique VPS
└── acme.vps.json           # Certificats TLS VPS (chmod 600, gitignored)
```

---

## Déploiement

### Freebox Delta (VM ARM64)

```bash
cd /opt/kiwinet-services/traefik

# Permissions obligatoires avant premier démarrage
chmod 600 acme.json

# Démarrage
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

## Fichiers secrets à créer avant premier démarrage

### Freebox

`acme.json` — fichier vide avec permissions strictes :
```bash
touch acme.json && chmod 600 acme.json
```

`.htpasswd` — identifiants dashboard (bcrypt) :
```bash
htpasswd -nB <utilisateur> >> traefik/.htpasswd
chmod 600 traefik/.htpasswd
```

### VPS Scaleway

`acme.vps.json` — fichier vide avec permissions strictes :
```bash
touch acme.vps.json && chmod 600 acme.vps.json
```

Le dashboard Traefik n'est pas exposé sur le VPS — pas de `.htpasswd` requis.

---

## Middlewares disponibles

Définis dans `dynamic.yml` (Freebox) et `dynamic.vps.yml` (VPS), référencés via `@file` depuis les labels Docker.

### Freebox (`dynamic.yml`)

| Middleware             | Usage                              |
|------------------------|------------------------------------|
| `auth-basic@file`      | Dashboard Traefik                  |
| `secure-headers@file`  | Services publics                   |
| `rate-limit@file`      | Endpoints publics                  |
| `ha-forwardproto@file` | Home Assistant (X-Forwarded-Proto) |

### VPS Scaleway (`dynamic.vps.yml`)

| Middleware            | Usage             |
|-----------------------|-------------------|
| `secure-headers@file` | Services publics  |
| `rate-limit@file`     | Endpoints publics |

---

## Points critiques

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
