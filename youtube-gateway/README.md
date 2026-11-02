# youtube-gateway

Passerelle qui sert des lives YouTube (radios lofi) en AAC, **à la demande**, à Music Assistant.
Une radio qui n'est pas écoutée ne consomme rien : ni bande passante, ni processeur.

## Principe

```text
Music Assistant ── ouvre /nom ──►  youtube-gateway ──► yt-dlp : retrouve l'adresse du flux
       ▲                                  │            ffmpeg : recopie l'AAC (sans réencodage)
       └────────── audio AAC ─────────────┘                          │
                                                               live YouTube
```

- Music Assistant (en réseau hôte) lit `http://127.0.0.1:8100/<nom>` comme une radio par URL.
- À l'ouverture seulement, la passerelle lance yt-dlp puis ffmpeg ; elle les arrête à la déconnexion du lecteur.
- L'audio est recopié tel quel : il est identique à celui du live d'origine.
- Aucun secret, aucune base de données. Un seul conteneur.

## Utilisation courante

La liste des radios est le fichier `config/radios.txt` (une ligne : `nom adresse-du-live`).
Il est relu automatiquement dès qu'il change : après un `git pull`, il n'y a rien à redémarrer.
La procédure complète d'ajout et de retrait, avec la commande de vérification d'un live, est écrite
dans les commentaires de ce fichier.

| Action | Commande ou geste |
|---|---|
| Voir les radios servies | `curl http://127.0.0.1:8100/` |
| Tester une radio (12 s) | `curl -m 12 -o /tmp/test.aac http://127.0.0.1:8100/<nom>` |
| Ajouter dans Music Assistant | menu Radio, saisir `http://127.0.0.1:8100/<nom>` |
| Voir ce qui se passe | `sudo docker logs youtube-gateway` |

Un lecteur qui interroge simplement la radio (requête HEAD) ne déclenche aucune écoute.

## Fichiers

| Fichier | Rôle |
|---|---|
| `Dockerfile` | Image en deux étapes : télécharge yt-dlp et Deno aux versions épinglées (sommes de contrôle vérifiées), puis assemble Debian, ffmpeg, Python et `server.py` |
| `server.py` | Serveur HTTP en bibliothèque standard de Python (aucune dépendance) |
| `docker-compose.yml` | Service durci, port publié sur la boucle locale seulement |
| `config/radios.txt` | Liste des radios, montée en lecture seule **par dossier** (un `git pull` remplace le fichier : un montage de fichier unique garderait l'ancienne copie) |
| `monitoring/` | Sonde de supervision pour Uptime Kuma : script, unité et minuteur systemd, modèle du fichier d'adresse de push |

## Réglages (variables d'environnement)

| Variable | Défaut | Rôle |
|---|---|---|
| `BIND` | `127.0.0.1` | Adresse d'écoute. Le compose met `0.0.0.0` : valable dans le conteneur seulement, l'accès est limité par `ports` |
| `PORT` | `8100` | Port d'écoute |
| `RADIOS_FILE` | `/config/radios.txt` | Fichier des radios |
| `MAX_STREAMS` | `3` | Écoutes simultanées au plus (au-delà : erreur 503) |
| `URL_TTL` | `14400` | Secondes pendant lesquelles l'adresse d'un flux est gardée (4 h, sous sa validité d'environ 6 h) |
| `MAX_FAILURES` | `5` | Échecs de suite tolérés en cours d'écoute avant abandon |
| `EXTRACT_TIMEOUT` | `60` | Durée maximale d'une extraction par yt-dlp, en secondes |
| `FIRST_BYTE_TIMEOUT` | `40` | Attente maximale du premier octet de ffmpeg, en secondes |

## Déploiement et mise à jour

Premier déploiement, depuis ce dossier sur le serveur :

```bash
sudo docker compose config -q && sudo docker compose build && sudo docker compose up -d
```

Si `server.py` ou le `Dockerfile` changent : changer le tag de l'image dans `docker-compose.yml`, puis
`sudo docker compose build && sudo docker compose up -d`. Modifier `config/radios.txt` ne demande rien.

### Mettre à jour yt-dlp ou Deno

YouTube change régulièrement ses formats : si les journaux montrent des « extraction echouee » répétées,
yt-dlp est probablement à mettre à jour. Les versions sont épinglées dans le `Dockerfile`
(`YTDLP_VERSION`, `YTDLP_SHA256`, `DENO_VERSION`, `DENO_SHA256`), avec leur somme de contrôle.

1. Télécharger les fichiers de la version choisie depuis les pages de publication officielles
   (`yt-dlp` et `SHA2-256SUMS` pour yt-dlp ; l'archive `deno-x86_64-unknown-linux-gnu.zip` et son
   fichier `.sha256sum` pour Deno).
2. Comparer la somme de contrôle calculée (`sha256sum`) à celle publiée.
3. Reporter version et somme dans le `Dockerfile`, changer le tag de l'image, reconstruire, redémarrer.

L'image de base est épinglée par empreinte (`DEBIAN_IMAGE`). Les correctifs de Debian (dont ffmpeg)
n'arrivent qu'à la reconstruction de l'image : la refaire de temps en temps. Pour relever l'empreinte
de la base : `sudo docker pull debian:stable-slim`, puis
`sudo docker inspect --format '{{index .RepoDigests 0}}' debian:stable-slim`.

**À revoir avant octobre 2027 :** l'équipe de Deno a annoncé en octobre 2026 rejoindre Cloudflare, avec
un an de correctifs mensuels puis l'arrêt de son développement (le projet reste open source).
yt-dlp accepte d'autres moteurs JavaScript (Node, QuickJS, Bun).

## Supervision

Un moniteur push d'Uptime Kuma (sur le VPS) vérifie que la passerelle répond.

- `monitoring/uptime-kuma-push.sh` appelle la route `/healthz` depuis le serveur et pousse le résultat.
  En cas d'échec il n'envoie rien : jamais de « down » explicite, l'absence de signal laisse Kuma appliquer ses tentatives.
- `youtube-gateway-uptime-push.timer` le déclenche chaque minute, sur horloge fixe ;
  `youtube-gateway-uptime-push.service` le lance sous le compte d'administration, durci, sans root.
- L'adresse de push est un secret : `monitoring/push-url.conf` (modèle : `push-url.conf.example`), droits 600,
  ignoré par Git. **Avant de le créer, vérifier avec `git check-ignore -v monitoring/push-url.conf`** : les règles
  du `.gitignore` sont écrites dossier par dossier.
- Installation, en copies appartenant à root (pas de liens vers le dépôt, qui est modifiable par le compte d'administration) :

  ```bash
  cd monitoring
  sudo install -m 644 -o root -g root youtube-gateway-uptime-push.service youtube-gateway-uptime-push.timer /etc/systemd/system/
  sudo systemctl daemon-reload && sudo systemctl enable --now youtube-gateway-uptime-push.timer
  ```

  Après toute modification de ces fichiers versionnés, les recopier et recharger systemd.
- Vérifier : `systemctl list-timers youtube-gateway-uptime-push.timer`, puis `sudo journalctl -u youtube-gateway-uptime-push.service`
  (le compte d'administration ne lit pas le journal système sans sudo). L'état du moniteur se lit dans Kuma : le script est silencieux.
- Avant de commiter une modification du script : `bash -n monitoring/uptime-kuma-push.sh`.
- **Limite** : la sonde valide le service et le serveur, pas les lives. Un live mort n'est vu qu'à l'écoute (erreur 502).

## Diagnostic

| Constat | Cause probable | Que faire |
|---|---|---|
| Erreur 404 à l'ouverture | Nom absent de la liste, ou ligne invalide (ignorée et signalée une fois dans les journaux) | Vérifier `config/radios.txt` et `sudo docker logs youtube-gateway` |
| Erreur 502 « flux indisponible » | Live terminé (son identifiant est mort) ou extraction impossible | Vérifier le live avec la commande des commentaires de `radios.txt` ; remplacer la ligne ; sinon mettre à jour yt-dlp |
| Erreur 503 | `MAX_STREAMS` écoutes déjà en cours | Fermer une lecture, ou relever `MAX_STREAMS` |
| `extraction echouee` dans les journaux | Live mort, réseau coupé, ou yt-dlp dépassé | Idem 502 |
| `flux interrompu` puis la lecture continue | Reprise normale (adresse expirée, coupure réseau) | Rien |
| `abandon apres N echecs de suite` | La reprise n'a pas abouti | Relancer la lecture ; si ça se répète, vérifier le live et yt-dlp |
| Moniteur Kuma en panne alors que la passerelle répond | Minuteur arrêté ou adresse de push erronée | `systemctl status youtube-gateway-uptime-push.timer`, puis relancer la sonde à la main (`bash monitoring/uptime-kuma-push.sh`) |

Pour tester sur ce serveur, **toujours donner un réseau Docker explicite** (`--network youtube-gateway_default`).
Le réseau Docker par défaut a un DNS très lent ici : l'extraction y devient plusieurs fois plus longue.

## Sécurité

- Port publié sur la boucle locale du serveur seulement, jamais exposé par Traefik ni par la box. Il n'a
  pas d'authentification : tout processus local peut demander un flux (et donc consommer de la bande passante).
- Seules les adresses de `config/radios.txt` sont lancées ; leur format est strict
  (`https://www.youtube.com/watch?v=` suivi de 11 caractères), les noms aussi. Aucune adresse n'est lue
  dans une requête, aucun shell n'est utilisé.
- Conteneur durci : utilisateur non root, privilèges et capacités retirés, système de fichiers en lecture
  seule, espace temporaire limité sans exécution, mémoire et nombre de processus limités, rotation des journaux.
- Les journaux ne contiennent aucune adresse de flux (elles embarquent l'adresse IP publique).
- Risque résiduel : ffmpeg décode des données venues d'Internet, et le ffmpeg de Debian embarque beaucoup
  de code inutile ici (d'où une image lourde). Un ffmpeg statique à épingler est une piste, à étudier.

## Limites connues

- **Renouvellement de l'adresse en écoute très longue** : l'adresse d'un flux est valable environ 6 h.
  La reprise de ffmpeg en cours d'écoute est testée par simulation, pas encore observée en conditions réelles.
- **Bande passante** : chaque écoute télécharge environ 1,5 Mbit/s (mesure du 02/11/2026), dont l'essentiel
  est le rechargement de la liste de segments du live ; deux écoutes de la même radio font deux téléchargements.
- **Radio saisonnière** : quand un live se termine, son identifiant meurt ; la ligne est à remplacer.
- **Supervision limitée au service** (voir plus haut) : aucune alerte quand un live meurt.

## Historique

Cette passerelle remplace une première version (un relais permanent par radio vers un serveur Icecast),
retirée le 02/11/2026. Son code est conservé dans les branches `archive/icecast-retired-20261102` et
`archive/youtube-relay-retired-20261102`. Ses mots de passe et ses images ont été supprimés : un retour
arrière demanderait de les régénérer et de reconstruire.
