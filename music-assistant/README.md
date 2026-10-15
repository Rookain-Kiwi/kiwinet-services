# music-assistant — Music Assistant

Serveur de musique multi-pièces. Accessible via `ma.kiwinet.me`.

> Contexte global : [kiwinet-docs](https://github.com/Rookain-Kiwi/kiwinet-docs)

---

## Stack

| Conteneur         | Réseau | Rôle                                         |
|-------------------|--------|----------------------------------------------|
| `music-assistant` | `host` | Serveur de musique, pilote les récepteurs Cast |

Music Assistant lit la musique directement sur le disque local, par son
fournisseur « Filesystem (local disk) » (dossier `/media/music`, en lecture
seule), et les radios SomaFM (flux Internet, sans compte). Il n'utilise plus
Jellyfin. Il est intégré à Home Assistant, qui le pilote.

---

## Structure

```
music-assistant/
├── docker-compose.yml
└── README.md
```

Aucun fichier d'environnement : en réseau hôte, aucun port n'est publié.
Les données vivent dans le volume nommé `music-assistant_music-assistant-data`
(nom du projet Compose + nom du volume : ne pas renommer le dossier).

---

## Prérequis

- Le disque Libraries doit être monté : seul `/mnt/Libraries/Music` est monté
  dans le conteneur (`/media/music`), en lecture seule. S'il est absent, le
  conteneur refuse de démarrer.
- Les données sont restaurées dans le volume **avant** le premier
  `docker compose up -d`. Un démarrage sur un volume vide repart d'une
  installation neuve (création de compte) par la route publique.

Restauration depuis une archive de volume (dossier racine `_data/`) :

```bash
docker compose create        # crée le volume, le conteneur reste à l'état Created
# vérifier que le volume est vide, puis extraire dans un conteneur jetable
# (réseau coupé, archive en lecture seule, -p --numeric-owner, --strip-components=1)
```

L'archive contient des secrets (jetons des fournisseurs, clés privées) : ne
jamais afficher `settings.json` sans filtre, ne rien en copier dans Git.

---

## Déploiement

```bash
docker compose config --quiet
docker compose up -d
docker compose logs -f music-assistant
```

Le port du flux audio est indiqué dans les journaux au démarrage.

---

## Mise à jour

L'image est épinglée par empreinte : `docker compose pull` ne change rien.

1. Lire les notes de version sur
   `https://github.com/music-assistant/server/releases` et choisir le tag
   (tags de version stable `X.Y.Z` ; `latest` désigne la dernière stable).
2. Relever l'empreinte de l'**index** du tag (registre GHCR).
   ```bash
   TOK=$(curl -s "https://ghcr.io/token?scope=repository:music-assistant/server:pull" | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')
   curl -sI -H "Authorization: Bearer $TOK" \
     -H "Accept: application/vnd.oci.image.index.v1+json" \
     "https://ghcr.io/v2/music-assistant/server/manifests/<tag>" | grep -i docker-content-digest
   ```
3. Modifier le tag et l'empreinte dans `docker-compose.yml`, commit, push, puis
   `git pull --ff-only` sur le serveur et `docker compose up -d`.

---

## Points critiques

**`network_mode: host`** — requis par la documentation officielle : la
découverte et la diffusion vers les lecteurs exigent un accès réseau direct.
Music Assistant écoute sur toutes les interfaces du serveur et **ne passe pas
par `DOCKER-USER`** : seul ufw le protège.

**Règles ufw** — autoriser uniquement le réseau local et la plage du réseau
`proxy` vers le port de l'interface web, et le réseau local vers le port du
flux audio. Sans elles, la route Traefik renvoie une erreur 504 et les
récepteurs ne peuvent pas lire le flux.

**Route Traefik** — déclarée manuellement dans `../traefik/dynamic/dynamic.yml`
(interface web et API uniquement). Le flux audio ne passe pas par Traefik : il
est servi en HTTP, directement aux récepteurs du réseau local.

**Exposition publique** — la route est publique, avec limitation de débit et
en-têtes de sécurité, sans authentification de base Traefik : la protection
repose sur l'authentification native de Music Assistant. La route sert
aussi les jaquettes des fichiers à Home Assistant et à l'application mobile,
voir « URL de base ». Sans connexion sur cette route : informations du serveur
(`/info`), page de connexion, documentation de l'API et images
(`/imageproxy/<empreinte>`), dont l'identifiant est une empreinte de 64
caractères. La documentation de l'API n'est pas restreinte (gain jugé marginal).
L'option d'auto-inscription ne concerne que la
connexion par OAuth Home Assistant : elle est masquée tant que ce fournisseur
n'est pas chargé, et activée par défaut. La désactiver avant d'ajouter ce
fournisseur.

**Serveur de flux** — il sert l'audio et les images aux lecteurs, en HTTP, sans
authentification, et n'est prévu que pour le réseau local (les mainteneurs
refusent qu'il passe derrière un proxy inverse). Ne jamais lui donner de route
Traefik ni l'ouvrir hors du réseau local.

**Données** — `auth.db` (comptes), `library.db` (bibliothèque), `settings.json`
(réglages, valeurs chiffrées avec une clé stockée dans le même fichier). Les
adresses héritées de l'ancienne instance (adresse annoncée aux récepteurs, URL
de base) sont à contrôler après restauration. Traiter ces fichiers, leurs copies
et leurs sauvegardes comme sensibles, et supprimer les copies de sécurité une
fois l'opération validée.

**Fournisseur de musique** — retirer un fournisseur supprime aussi les éléments
fusionnés avec un autre fournisseur : lancer ensuite la synchronisation du
fournisseur restant. Un fichier MP3 corrompu apparaît à chaque balayage comme un
« succès partiel », sans autre effet.

**Jaquette manquante** — déposer `cover.jpg` (ou `folder.jpg`, `album.jpg`) dans
le dossier de l'album, de préférence carré et d'au moins 512 pixels, avec le
même propriétaire et les mêmes droits que les autres fichiers du dossier
(lecture pour tous). Le dossier de musique est monté en lecture seule dans le
conteneur : l'écriture se fait sur l'hôte. Puis lancer « Update Metadata » sur
l'album dans l'interface.

**Démarrage** — le conteneur refuse de démarrer si le disque de musique n'est
pas monté. Après un redémarrage de la machine, si Music Assistant est arrêté,
vérifier le montage puis relancer `docker compose up -d`. Le fournisseur de
fichiers n'ouvre aucune connexion réseau au démarrage, contrairement à l'ancien
fournisseur Jellyfin qui ne se reconnectait pas après un échec.

**URL de base** — réglée sur le domaine public en HTTPS (Paramètres, Système,
Serveur Web, champ « URL de base », valeur par défaut `auto`). Avec `auto`, les
jaquettes issues des fichiers sont annoncées en HTTP sur l'adresse du réseau
local : Home Assistant et l'application Android ne peuvent alors pas les
charger (contenu mixte, ou réseau local inaccessible). Conséquence : ces images
dépendent de Traefik, du DNS et du certificat. L'audio n'est pas concerné, il a
son propre serveur de flux, local. Retour arrière : remettre `auto`.

**Nom du serveur** — défini explicitement à un nom neutre dans le même écran :
vide, il retombe sur un nom par défaut qui contient le nom d'hôte, visible dans
l'information publique du serveur.

**Journaux** — rotation par le pilote `json-file` (10 Mo, 3 fichiers).

---

## Intégrations

- **Fichiers locaux** : fournisseur « Filesystem (local disk) » sur
  `/media/music`, étiquettes et pochettes lues dans les fichiers.
- **SomaFM** : radios en ligne, sans compte.
- **Home Assistant** : intégration Music Assistant, configurée sur le domaine
  public de Music Assistant (par Traefik), à repointer après un changement
  d'adresse.
