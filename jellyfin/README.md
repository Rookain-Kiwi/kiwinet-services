# jellyfin — Serveur média

Serveur média open source de la famille (films, séries, musique, photos,
livres). Il remplace Plex, Komga et Komf, retirés en septembre 2026. Accès
public via Traefik, et direct sur le réseau local.

> Contexte global : [kiwinet-docs](https://github.com/Rookain-Kiwi/kiwinet-docs)

---

## Stack

| Container  | Image                                         | Port interne |
|------------|-----------------------------------------------|--------------|
| `jellyfin` | `jellyfin/jellyfin` (officielle, épinglée par empreinte) | 8096 |

---

## Configuration

| Paramètre       | Valeur |
|-----------------|--------|
| Architecture    | x86-64 (Debian 13) |
| Image           | Officielle `jellyfin/jellyfin`, épinglée par empreinte, mise à jour manuelle |
| Données         | Volume nommé `jellyfin-config` (configuration, métadonnées, base SQLite, cache) |
| Chemins         | Variables `JELLYFIN_*` forcées pour reproduire la structure du volume restauré : ne pas les retirer |
| Base de données | SQLite (défaut Jellyfin). L'instance PostgreSQL du serveur n'est pas utilisée |
| Bibliothèques   | `/mnt/Libraries/{TV Shows,Movies,Music,Photos,Books}` → `/data/*`, disque USB local, un montage par répertoire, `:ro` |
| Accès           | `jellyfin.kiwinet.me` (HTTPS via Traefik, public) + réseau local sur `8096/tcp` et `7359/udp` |
| Durcissement    | `no-new-privileges`, ports liés à l'adresse du serveur, `secure-headers` et `rate-limit` côté Traefik |

---

## Structure

```
jellyfin/
├── docker-compose.yml
├── env.example
└── README.md
```

---

## Déploiement

Prérequis : Traefik déployé (réseau `proxy`), disque `Libraries` monté.

```bash
cd /opt/kiwinet-services/jellyfin

# Variables locales (le .env n'est jamais versionné)
cp env.example .env
chmod 600 .env
nano .env        # renseigner HOST_BIND_IP
```

> ⚠️ **Restaurer la configuration AVANT le premier démarrage.** Dès `up -d`, la
> route est servie sur Internet. Un premier démarrage sur un volume vide
> expose l'assistant de configuration initiale : n'importe qui pourrait créer
> le compte administrateur. La configuration de l'ancienne instance doit donc
> être extraite dans le volume `jellyfin-config` (en conservant les
> propriétaires d'origine) avant tout `docker compose up -d`.

```bash
docker compose config --quiet
docker compose pull
docker compose up -d
docker compose ps        # état (healthy) attendu
```

### Mise à jour

L'image est épinglée par empreinte : modifier l'empreinte dans
`docker-compose.yml` (commit, push, `git pull --ff-only` sur le serveur), puis :

```bash
docker compose pull && docker compose up -d
```

Jellyfin n'a pas de mécanisme de retour en arrière : après une migration de
base, la seule issue est de restaurer une sauvegarde. Sauvegarder le volume
avant toute mise à jour de version majeure ou mineure.

---

## Contraintes matérielles

Le GPU intégré du serveur n'accélère en matériel que le H.264 8 bits (ni HEVC
ni 10 bits), et aucune accélération n'est configurée. La lecture directe
(direct play) reste la norme. Un transcodage, notamment des vidéos H.264
10 bits, serait logiciel et très limité sur ce processeur.

---

## Accès distant

Route publique `jellyfin.kiwinet.me` via Traefik : certificat Let's Encrypt
(challenge HTTP), en-têtes de sécurité et limitation de débit. Choix assumé
(décision du 06/09/2026) : simplicité d'accès pour les enfants en
déplacement, au prix d'une exposition publique du service.

Pré-requis : enregistrement DNS `jellyfin.kiwinet.me` pointant vers la même
cible que les autres services Traefik. Les ports 80 et 443 sont déjà
redirigés pour Traefik, rien de plus à ouvrir.

Les ports `8096/tcp` et `7359/udp` sont publiés sur la seule adresse du
réseau local (`HOST_BIND_IP`) : ils servent aux télévisions, au Cast et à la
découverte automatique, pas à l'accès depuis Internet.

---

## Points d'attention

| Sujet | Point à connaître |
|---|---|
| Cast Chromecast | Le récepteur Cast de Jellyfin a été signalé instable derrière un reverse proxy HTTPS (rapports Jellyfin 10.8.x) : à tester en conditions réelles |
| Application Samsung Tizen | Déploiement officiel (24/05/2026) inégal selon le modèle, le firmware et la région : vérifier la disponibilité sur le modèle réel |
| Home Assistant | Intégration native Jellyfin. Le cast lancé depuis le panneau Media de Home Assistant vers un récepteur Cast générique ne fonctionne pas : le cast se fait depuis les applications Jellyfin |
