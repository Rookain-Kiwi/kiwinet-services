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
| Sauvegardes     | Sauvegarde native de Jellyfin (manuelle), écrite dans un dossier dédié du disque `Data` monté sur `/config/data/data/backups` |
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

Prérequis : Traefik déployé (réseau `proxy`), disque `Libraries` monté, dossier
de sauvegarde créé sur le disque `Data` (voir « Sauvegardes »).

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

### Restauration de la configuration

```bash
# Valider le compose, puis créer le volume et le conteneur SANS le démarrer
docker compose config --quiet
docker compose create

# Extraire l'archive dans le volume (qui doit être vide), propriétaires conservés
IMG=$(docker inspect -f '{{.Config.Image}}' jellyfin)
docker run --rm --network none --user 0 --entrypoint tar \
  -v jellyfin_jellyfin-config:/config \
  -v "$HOME/migration-export":/archive:ro "$IMG" \
  -xzpf /archive/<archive>.tgz -C /config --strip-components=1 --numeric-owner

# Dossier racine du volume : propriétaire du compte du conteneur
docker run --rm --network none --user 0 --entrypoint sh \
  -v jellyfin_jellyfin-config:/config "$IMG" \
  -c 'chown 1000:1000 /config && chmod 755 /config'
```

L'archive est montée en lecture seule et n'est jamais modifiée : elle sert de
retour arrière.

À contrôler dans la configuration restaurée, avant le démarrage :

- `system.xml` : `IsStartupWizardCompleted` à `true` (sinon l'assistant de
  configuration initiale serait exposé) ;
- `network.xml` : `KnownProxies` doit inclure le sous-réseau du réseau Docker
  `proxy`, et l'adresse `internal` de `PublishedServerUriBySubnet` doit être
  celle du serveur (`HOST_BIND_IP`) ;
- `encoding.xml` et bibliothèques : aucun reste de l'ancien matériel, chemins
  `/data/*` conformes aux montages.

### Premier démarrage

```bash
docker compose up -d
docker compose ps        # état (healthy) attendu
```

La première ouverture applique les migrations de base éventuelles : ne pas
l'interrompre.

### Mise à jour

L'image est épinglée par empreinte : modifier l'empreinte dans
`docker-compose.yml` (commit, push, `git pull --ff-only` sur le serveur), puis :

```bash
docker compose pull && docker compose up -d
```

Jellyfin n'a pas de mécanisme de retour en arrière : après une migration de
base, la seule issue est de restaurer une sauvegarde. Créer une sauvegarde
native (Tableau de bord → Sauvegardes) avant toute mise à jour de version
majeure ou mineure.

---

## Sauvegardes

La sauvegarde native de Jellyfin (depuis la 10.11) se lance à la main, depuis le
Tableau de bord → Sauvegardes. Elle n'a pas de planification native : à créer
notamment avant chaque mise à jour. La restauration se fait depuis la même page
ou avec l'argument `--restore-archive` au démarrage.

Les sauvegardes sont écrites dans un dossier dédié du disque `Data`
(`/mnt/Data/Backups/Technique/jellyfin-backups`), monté en lecture-écriture sur
`/config/data/data/backups` et limité à ce seul dossier.

- Prérequis : le dossier existe, propriétaire `1000:1000`, droits `700`.
- Si le disque `Data` n'est pas monté, Jellyfin ne démarre pas
  (`create_host_path: false`, comportement testé). C'est voulu : sinon les
  sauvegardes seraient écrites sur le SSD système sans que personne le sache.
- Une sauvegarde contient la base de Jellyfin (comptes, hachages de mots de
  passe, clés d'API) : la traiter comme un secret.
- Pas de copie hors site tant que la synchronisation cloud du disque `Data`
  n'est pas en place et ne couvre pas ce dossier.

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
