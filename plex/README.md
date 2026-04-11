# plex — Plex Media Server

Serveur multimédia dockerisé. Accessible via `plex.kiwinet.me`.

> Contexte global : [kiwinet-docs](https://github.com/Rookain-Kiwi/kiwinet-docs)

---

## Stack

| Container | Image                | Port interne |
|-----------|----------------------|--------------|
| `plex`    | `plexinc/pms-docker` | 32400        |

---

## Configuration

| Paramètre      | Valeur                                  |
|----------------|-----------------------------------------|
| Architecture   | ARM AArch64                             |
| Timezone       | Europe/Paris                            |
| PUID / PGID    | 994 / 991 (utilisateur `plex` VM)       |
| Transcodage    | `/tmp/plex-transcode` (RAM)             |
| Données config | `/var/lib/plexmediaserver` (bind mount) |

---

## Structure

```
plex/
├── docker-compose.yml
└── .env                # PLEX_CLAIM (gitignored)
```

---

## Fichier `.env` à créer

```bash
cat > .env << 'EOF'
PLEX_CLAIM=claim-XXXXXXXXXXXXXXXX
EOF
```

Le token se génère sur `https://plex.tv/claim` (valable 4 minutes). Requis uniquement au premier démarrage — le container peut ensuite être relancé sans `PLEX_CLAIM`.

---

## Déploiement

```bash
cd /opt/kiwinet-infra/plex

docker compose up -d
docker compose logs -f

# Mise à jour
docker compose pull && docker compose up -d --force-recreate
```

---

## Médias

Bibliothèques montées depuis le NAS Freebox via CIFS (`/etc/fstab`). Les points de montage sont définis dans le `docker-compose.yml`.

### Options fstab requises

```
guest,uid=rookain,gid=rookain,file_mode=0777,dir_mode=0777,vers=3.0,cache=strict,serverino,_netdev,x-systemd.automount,x-systemd.device-timeout=30
```

| Option                         | Raison                                                                                                                                                       |
|--------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `file_mode=0777,dir_mode=0777` | L'uid `plex` dans le conteneur (`1000`) diffère de l'uid `plex` sur la VM (`994`) — la gestion fine par propriétaire/groupe est inopérante depuis le conteneur. `0777` est le seul moyen de garantir l'accès en écriture. |
| `uid=rookain,gid=rookain`      | Propriétaire des fichiers côté VM pour les opérations manuelles                                                                                              |
| `vers=3.0,cache=strict`        | Stabilité CIFS sous Docker                                                                                                                                   |
| `serverino`                    | Inodes stables — requis pour Plex                                                                                                                            |
| `_netdev,x-systemd.automount`  | Montage différé au démarrage, après disponibilité réseau                                                                                                     |

### Droits par bibliothèque

| Volume conteneur  | Droits | Raison                                    |
|-------------------|--------|-------------------------------------------|
| `/media/films`    | `rw`   | Écriture des versions optimisées          |
| `/media/series`   | `rw`   | Écriture des versions optimisées          |
| `/media/musique`  | `:ro`  | Lecture seule — pas de cas d'optimisation |

---

## Versions optimisées

Plex peut générer des versions allégées des médias ("Optimize for TV") pour faciliter le streaming à distance.

Plex ne propose pas d'option de redirection du répertoire de stockage — les fichiers optimisés sont écrits directement dans l'arborescence des médias source, dans un sous-dossier dédié :

```
/media/series/<Titre série>/Plex Versions/Optimized for TV/<Titre série>/
/media/films/<Titre film>/Plex Versions/Optimized for TV/
```

Ces fichiers sont stockés sur le NAS Freebox (3 To) et non sur le disque VM (120 Go).

### Paramètres recommandés

**Paramètres → Transcodeur :**

| Paramètre                                     | Valeur      |
|-----------------------------------------------|-------------|
| Préréglage x264 en arrière-plan               | Très rapide |
| Transcodages vidéo en arrière-plan simultanés | 1           |

---

## Clients

Le transcodage serveur est le principal facteur de dégradation sur ARM64 — pas le codec ni le débit. Les clients modernes (smartphones, tablettes, TV) sont capables de décoder nativement le x264/x265 10-bit sans intervention du serveur.

**Configuration cible pour chaque client Plex :**

**Paramètres → Vidéo & Audio :**

| Paramètre         | Valeur   |
|-------------------|----------|
| Qualité locale    | Maximum  |
| Qualité Wi-Fi     | Maximum  |
| Qualité mobile    | Maximum  |
| Lecture directe   | Activée  |
| Diffusion directe | Activée  |

Sans cette configuration, Plex transcode à la volée côté serveur, provoquant des freezes et une charge CPU élevée sur ARM64 — même pour des fichiers que le client pourrait lire nativement.

Les versions optimisées ("Optimize for TV") restent utiles pour les clients vraiment limités incapables de Direct Play, mais ne sont pas nécessaires pour les appareils récents.

---

## Réseau

Le port `32400` est exposé directement sur le LAN pour permettre aux clients locaux (Android TV, etc.) de se connecter sans transiter par Traefik. Ce port ne doit pas être ouvert côté WAN sur la Freebox Delta.

### Configuration post-déploiement (manuelle, une seule fois)

Après le premier démarrage, configurer les URLs de connexion dans Plex Web :

**Paramètres → Réseau → "URL personnalisées pour accéder au serveur"**

```
https://plex.kiwinet.me,http://192.168.1.33:32400
```

Sans cette configuration, les clients Chromecast/Android TV transitent systématiquement par Traefik, provoquant des coupures audio erratiques.