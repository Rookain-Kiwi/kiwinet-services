# plex — Plex Media Server

Serveur multimédia auto-hébergé, dockerisé avec l'image officielle `plexinc/pms-docker`.  
Accessible via `plex.kiwinet.me` (HTTPS via Traefik → port interne 32400, non exposé publiquement).

---

## Stack

| Container | Image                    | Rôle                       |
|-----------|--------------------------|----------------------------|
| `plex`    | `plexinc/pms-docker`     | Serveur Plex Media Server  |

---

## Configuration

| Paramètre         | Valeur                                          |
|-------------------|-------------------------------------------------|
| Architecture      | ARM AArch64 (Freebox Delta)                     |
| Timezone          | Europe/Paris                                    |
| PUID / PGID       | 994 / 991 (utilisateur `plex` natif de la VM)  |
| Port interne      | 32400 (non exposé directement)                  |
| Transcodage       | `/tmp/plex-transcode` (RAM)                     |
| Données config    | `/var/lib/plexmediaserver` (bind mount)         |

---

## Structure

```
plex/
├── docker-compose.yml
└── .env                ← PLEX_CLAIM (gitignored)
```

Les données Plex (base de données, métadonnées, config) sont conservées depuis l'installation native dans `/var/lib/plexmediaserver` — elles persistent entre les recreations du container.

---

## Médias

Les bibliothèques sont montées en lecture seule depuis le NAS Freebox (montages CIFS persistants via `/etc/fstab`) :

| Point de montage       | Contenu      |
|------------------------|--------------|
| `/mnt/Kodi/Films`      | Films        |
| `/mnt/Kodi/Séries TV`  | Séries TV    |
| `/mnt/Kodi/Musique`    | Musique      |

---

## Déploiement

```bash
cd /opt/kiwinet-infra/plex

# Premier démarrage (PLEX_CLAIM requis)
docker compose up -d

# Logs en temps réel
docker compose logs -f

# Mise à jour image
docker compose pull && docker compose up -d --force-recreate
```

---

## Premier démarrage

1. Générer un token sur `https://plex.tv/claim` (valable 4 minutes)
2. Renseigner le token dans `.env` :

```bash
cat > .env << 'EOF'
PLEX_CLAIM=claim-XXXXXXXXXXXXXXXX
EOF
```

3. Lancer le container — Plex se lie automatiquement au compte Plex.tv via le token
4. Une fois lié, le token n'est plus nécessaire — le container peut être relancé sans `PLEX_CLAIM`

---

## Routing réseau

Plex utilise les labels Docker pour s'exposer via Traefik :

```
Client → plex.kiwinet.me:443 → Traefik HTTPS → container plex:32400
```

Le port 32400 n'est pas exposé directement sur la VM — tout passe par Traefik avec certificat Let's Encrypt et middleware `secure-headers`.

---

## Variables d'environnement

| Variable      | Description                                                      |
|---------------|------------------------------------------------------------------|
| `PLEX_CLAIM`  | Token de claim Plex.tv — requis uniquement au premier démarrage |

---

## Intégration Home Assistant

Plex est intégré à Home Assistant via `hub.kiwinet.me`.  
L'intégration remonte l'état de lecture en temps réel (film en cours, utilisateur actif, etc.).
