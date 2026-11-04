# youtube-gateway

Passerelle qui sert des lives YouTube (radios lofi) et des playlists (lues en boucle, dans un ordre aléatoire)
en AAC, **à la demande**, à Music Assistant.
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

La liste des radios est le fichier `config/radios.txt` (une ligne : `nom adresse`). L'adresse est celle
d'un live (`https://www.youtube.com/watch?v=…`) ou d'une playlist (`https://www.youtube.com/playlist?list=…`).
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

## Playlists

Une ligne de `config/radios.txt` avec une adresse `https://www.youtube.com/playlist?list=…` définit une radio
« playlist » : la passerelle la lit **en boucle et dans un ordre aléatoire**, piste après piste.

- La playlist doit être **publique ou non répertoriée** (une playlist privée demanderait un compte Google).
  Une adresse `watch?v=…&list=…` est refusée : prendre l'adresse de la page de la playlist elle-même.
- Ajouter ou retirer un morceau se fait dans YouTube, sans commit ni redémarrage : la liste est relue au
  début d'une écoute et gardée environ une heure (`PLAYLIST_TTL`).
- Ordre : nouveau mélange à chaque écoute et à chaque tour ; aucune piste n'est rejouée dans un même tour,
  ni deux fois de suite d'un tour à l'autre.
- Audio : AAC recopié sans réencodage quand la piste est en AAC-LC 44,1 kHz stéréo ; sinon cette piste seule
  est réencodée en AAC 128 kbit/s, 44,1 kHz stéréo, pour que le flux garde les mêmes paramètres d'un bout à l'autre.
- Une piste indisponible (supprimée, privée) est sautée, signalée dans les journaux et pas réessayée avant 10 minutes.
- La piste suivante est préparée pendant la courante : les infos d'extraction sont obtenues d'avance, et son
  téléchargement démarre dès qu'il reste `PRESTART_SECONDS` d'audio à envoyer.
- Le lecteur voit une radio infinie : pas de titre, pas de « suivant ». Si les éléments de la playlist sont des
  albums d'une heure, le mélange se fait album par album ; pour un mélange morceau par morceau, une vidéo par morceau.
- **Démarrage** : à froid (liste, extraction et ouverture de la première piste, chacune de l'ordre de 2 à 5 s),
  environ 9 s avant le premier octet, mesuré hors Music Assistant ; avec les caches chauds (infos gardées 4 h,
  liste 1 h), environ 1 s. Depuis Music Assistant, le démarrage a été jugé rapide (1 à 3 s une fois l'enceinte
  réveillée, mesure du 04/11/2026, caches chauds). Si le lecteur n'attend pas un démarrage à froid, mettre
  `INTRO_SILENCE` (par exemple `10`) : la passerelle envoie aussitôt autant de secondes de silence.
- **Débit** : Music Assistant lit d'abord une réserve en rafale (de l'ordre de 15 Mo, soit environ un quart
  d'heure d'audio, à 1 ou 2 Mo/s pendant quelques secondes), puis cesse de lire jusqu'à en avoir besoin.
  Arrêter la lecture ferme le flux et tous les processus (vérifié le 04/11/2026).

## Fichiers

| Fichier | Rôle |
|---|---|
| `Dockerfile` | Image en deux étapes : télécharge yt-dlp et Deno aux versions épinglées (sommes de contrôle vérifiées), puis assemble Debian, ffmpeg, Python et `server.py` |
| `server.py` | Serveur HTTP en bibliothèque standard de Python (aucune dépendance) : lives et playlists |
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
| `PLAYLIST_TTL` | `3600` | Secondes pendant lesquelles la liste des pistes d'une playlist est gardée |
| `INFO_TTL` | `14400` | Secondes pendant lesquelles les infos d'extraction d'une piste sont gardées (4 h, sous la validité des adresses) |
| `DEAD_TTL` | `600` | Une piste en échec n'est pas réessayée avant ce délai, en secondes |
| `TRACK_FAILURES` | `5` | Pistes de suite en échec tolérées en cours d'écoute avant abandon (au démarrage : 1) |
| `PRESTART_SECONDS` | `12` | On prépare la piste suivante quand il reste cette durée d'audio à envoyer |
| `INTRO_SILENCE` | `0` | Secondes de silence envoyées dès l'ouverture d'une playlist (0 : aucune) |
| `TMP_DIR` | `/tmp` | Dossier des fichiers temporaires d'extraction (en mémoire, supprimés après usage) |

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
| Erreur 502 « playlist indisponible » | Playlist privée ou supprimée, adresse erronée, ou toutes les pistes en échec | Ouvrir la playlist sans compte dans un navigateur ; vérifier l'adresse ; lire les journaux |
| `piste XXXXXXXXXXX indisponible` | Vidéo supprimée, privée ou bloquée | La retirer de la playlist (elle est sautée, réessayée après `DEAD_TTL`) |
| Silence ou attente de plusieurs secondes au début d'une playlist | Démarrage à froid | Normal ; régler `INTRO_SILENCE` si le lecteur abandonne |
| Moniteur Kuma en panne alors que la passerelle répond | Minuteur arrêté ou adresse de push erronée | `systemctl status youtube-gateway-uptime-push.timer`, puis relancer la sonde à la main (`bash monitoring/uptime-kuma-push.sh`) |

Pour tester sur ce serveur, **toujours donner un réseau Docker explicite** (`--network youtube-gateway_default`).
Le réseau Docker par défaut a un DNS très lent ici : l'extraction y devient plusieurs fois plus longue.

## Sécurité

- Port publié sur la boucle locale du serveur seulement, jamais exposé par Traefik ni par la box. Il n'a
  pas d'authentification : tout processus local peut demander un flux (et donc consommer de la bande passante).
- Seules les adresses de `config/radios.txt` sont lancées ; leur format est strict
  (`https://www.youtube.com/watch?v=` suivi de 11 caractères, ou `https://www.youtube.com/playlist?list=` suivi
  de l'identifiant), les noms aussi. Aucune adresse n'est lue dans une requête, aucun shell n'est utilisé.
  Les identifiants de pistes lus dans une playlist sont revérifiés (11 caractères) avant tout lancement.
- Pour une piste, les infos d'extraction (qui contiennent des adresses de flux signées, donc l'adresse IP publique)
  sont écrites dans un fichier temporaire de l'espace en mémoire du conteneur (`TMP_DIR`, accès réservé,
  supprimé dès la piste terminée). Elles ne sont jamais écrites dans les journaux.
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
- **Playlists** : pas de titre ni de « suivant » côté lecteur ; une piste n'est lue sans réencodage que si elle
  est en AAC-LC 44,1 kHz stéréo ; entre deux pistes, un petit trou est possible si le lecteur n'a presque rien
  en réserve ; le démarrage à froid, mesuré hors Music Assistant, prend une dizaine de secondes (mesures du
  03/11/2026 : liste 2 s, extraction 4 à 5 s, ouverture du téléchargement 4 s la première fois, 1 s ensuite).
- **Supervision limitée au service** (voir plus haut) : aucune alerte quand un live meurt.

## Historique

Cette passerelle remplace une première version (un relais permanent par radio vers un serveur Icecast),
retirée le 02/11/2026. Son code est conservé dans les branches `archive/icecast-retired-20261102` et
`archive/youtube-relay-retired-20261102`. Ses mots de passe et ses images ont été supprimés : un retour
arrière demanderait de les régénérer et de reconstruire.
