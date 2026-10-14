# music-assistant — Music Assistant

Serveur de musique multi-pièces. Accessible via `ma.kiwinet.me`.

> Contexte global : [kiwinet-docs](https://github.com/Rookain-Kiwi/kiwinet-docs)

---

## Stack

| Conteneur         | Réseau | Rôle                                         |
|-------------------|--------|----------------------------------------------|
| `music-assistant` | `host` | Serveur de musique, pilote les récepteurs Cast |

Music Assistant lit la musique de Jellyfin (fournisseur Jellyfin) et les radios
SomaFM (flux Internet, sans compte). Il est intégré à Home Assistant, qui le
pilote.

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

- Aucun disque de médias n'est monté dans le conteneur : la musique arrive
  uniquement par le fournisseur Jellyfin (aucun fournisseur de fichiers locaux).
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

**Exposition publique** — la route est publique (jaquettes de l'application
Android, bloquées en contenu mixte sinon). La protection repose sur
l'authentification native de Music Assistant : vérifier après toute
restauration que l'auto-inscription est désactivée.

**Données** — `auth.db` (comptes), `library.db` (bibliothèque), `settings.json`
(réglages et jetons). Les adresses héritées de l'ancienne instance (fournisseur
Jellyfin, adresse annoncée aux récepteurs, URL de base) sont à contrôler après
restauration.

**Journaux** — rotation par le pilote `json-file` (10 Mo, 3 fichiers).

---

## Intégrations

- **Jellyfin** : fournisseur de musique (compte en lecture seule).
- **SomaFM** : radios en ligne, sans compte.
- **Home Assistant** : intégration Music Assistant, à repointer vers
  l'instance après un changement d'adresse.
