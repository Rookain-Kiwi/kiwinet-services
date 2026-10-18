# kiwix

Serveur Kiwix (`kiwix-serve`) exposant une copie locale de Wikipédia, française
et anglaise avec images, et de ressources utiles en cas de coupure durable
d'Internet (médecine, survie, réparation, lecture, dictionnaires), via
`kiwix.kiwinet.me`. Les contenus sont lus dans des fichiers ZIM montés en
lecture seule depuis le disque Data.

**Statut** : déployé sur le serveur x86. Lecture des articles et recherche
dans un livre validées le 18/10/2026 (voir « Constats au déploiement »).

---

## Pourquoi Kiwix plutôt qu'une autre copie locale de Wikipédia

- **Lisible directement** : un ZIM contient articles, images et index de
  recherche, lus tels quels par `kiwix-serve` — contrairement aux dumps XML
  natifs de Wikipédia.
- **Léger** — un seul processus, sans base de données, en lecture seule.
- **Open source**, maintenu par le projet Kiwix (format défini par openZIM).

Limites connues :

- Le ZIM est un **instantané** : pas de mise à jour incrémentale, une nouvelle
  version remplace le fichier en entier (les deux Wikipédias seules pèsent
  environ 171 Gio).
- Pas de rythme de publication garanti : au moment du déploiement, la dernière
  version française date de mai 2026 et l'anglaise d'août 2026.
- La recherche plein texte sur ces volumes est coûteuse en CPU et en disque.
- **Pas de recherche globale entre langues différentes** : `kiwix-serve` refuse
  une recherche portant sur des ZIM de langues différentes (limite documentée,
  réponse 400 immédiate). La recherche se fait dans un livre à la fois, ou sur
  l'ensemble des livres d'une même langue après filtrage de la langue.
- Les collections `zimgit-*` sont des PDF : navigables, mais leur texte n'est
  pas indexé, donc absent de la recherche.
- **Première recherche lente sur un terme jamais lu** : quelques secondes, car
  le disque Data est un disque dur mécanique en USB ; les recherches suivantes
  répondent en une fraction de seconde (cache du système). Un SSD supprimerait
  cet écart.

---

## Prérequis avant premier démarrage

- Le disque Data est monté et le dossier `/mnt/Data/Sites` existe (le montage
  évite de le créer sur le SSD système : `create_host_path: false`).
- Les 26 ZIM sont présents dans ce dossier et vérifiés (somme SHA-256 publiée
  par Kiwix). Les deux Wikipédias :

| Fichier | Taille (octets) | SHA-256 (publié par Kiwix) |
|---|---|---|
| `wikipedia_fr_all_maxi_2026-05.zim` | 55 438 794 004 | `61401b1b3618afe736450a868c7205f572f590db310e044a9c72b51fbfcfb431` |
| `wikipedia_en_all_maxi_2026-08.zim` | 127 418 087 648 | `34162d18b9f96f494eac48a73a309c72e0bc95d85f76be405d0f5de795854aa6` |

  Les 24 autres, téléchargés le 18/10/2026 (environ 43 Gio au total), par thème :

| Thème | Fichiers (liste complète dans le compose) |
|---|---|
| Médecine, survie, technologies appropriées | `mdwiki` (variante maxi), `wikem`, `zimgit-medicine`, `zimgit-water`, `zimgit-food-preparation`, `zimgit-knots`, `zimgit-post-disaster`, `irp.fas.org` (médecine militaire), `appropedia` |
| Réparer et bricoler | `ifixit` (fr et en), Stack Exchange : cooking, diy, gardening, mechanics, outdoors, sustainability, electronics |
| Lecture et enfants | `wikibooks` fr, `vikidia` fr et en, `gutenberg` fr |
| Dictionnaires (sans images) | `wiktionary` fr et en |

  Les sommes SHA-256 de ces 24 fichiers ne sont pas recopiées ici : elles se
  lisent à côté de chaque fichier dans le catalogue (extension `.sha256`).
- Le conteneur tourne avec `user: "1000:1000"` ; les ZIM sont en `644`
  (lisibles par tous) et le dossier en `755`.
- Image `ghcr.io/kiwix/kiwix-serve` épinglée par tag et empreinte (index
  multi-architecture, amd64 inclus). Pour la mettre à jour : choisir le tag,
  relever l'empreinte avec
  `docker buildx imagetools inspect ghcr.io/kiwix/kiwix-serve:<tag>`, puis
  modifier le compose.
- Enregistrement DNS `kiwix.kiwinet.me` créé et résolu **avant** le premier
  démarrage (validation Let's Encrypt par HTTP).
- Middlewares `secure-headers-sameorigin`, `rate-limit` et `auth-basic`
  présents dans `traefik/dynamic/dynamic.yml`. `secure-headers-sameorigin` est
  une copie de `secure-headers` où seul l'en-tête anti-cadre change
  (`SAMEORIGIN` au lieu de `DENY`), indispensable au lecteur Kiwix (voir
  Sécurité). Il est réutilisable par tout service qui affiche ses propres
  pages dans un cadre ; les autres gardent `secure-headers`.
- **Synchronisation Proton Drive** : le volume Data y est répliqué, donc
  `/mnt/Data/Sites` aussi (décision du 18/10/2026 : l'exclusion d'abord
  envisagée est écartée, la capacité du cloud suffit). C'est une copie de
  secours de contenu public re-téléchargeable. Points à vérifier avant la
  première exécution de la synchronisation (pas encore redéployée sur le
  serveur) : les très gros fichiers (un ZIM dépasse 100 Gio) sont acceptés par
  Proton Drive et par l'outil de synchronisation, et le sort du sous-dossier
  `.partial/` (téléchargements en cours). Les suppressions n'étant pas
  répercutées vers le cloud, les anciennes versions de ZIM y restent après une
  mise à jour : ménage manuel.

### Obtenir les ZIM

Téléchargement en HTTPS avec reprise (`wget -c`) dans
`/mnt/Data/Sites/.partial/`, puis vérification SHA-256 avant de déplacer le
fichier : un ZIM incomplet ne se retrouve jamais à côté des ZIM servis. Les 24
ZIM supplémentaires ont été téléchargés par groupes avec un script local au
serveur (non versionné), sur ce même principe. Tous les miroirs n'ont pas tous
les fichiers : en cas de 404 ou de débit faible, essayer un autre miroir de la
liste publiée par le répartiteur de Kiwix.

Kiwix recommande BitTorrent pour ménager ses miroirs. Il n'a pas été retenu :
un téléchargement ponctuel ne justifie ni client BitTorrent ni connexions
entrantes sur le serveur. Le miroir choisi par défaut par le répartiteur de
charge plafonnait à environ 2 Mo/s ; un autre miroir de la liste officielle
(`mirrors.json` du répartiteur) a donné 60 à 80 Mo/s.

---

## Démarrage

```bash
cd kiwix
docker compose config --quiet && echo "compose valide"
docker compose pull
docker compose up -d
docker compose logs --tail 50 kiwix
```

Aucun port n'est publié : le service n'est joignable que par Traefik (réseau
Docker `proxy`). Le certificat est géré par Traefik (Let's Encrypt).

---

## Utilisation

Adresse : `https://kiwix.kiwinet.me`, avec les identifiants de
l'authentification de base. La page d'accueil liste les deux Wikipédias ; la
recherche plein texte s'applique à la bibliothèque ou à un ZIM choisi.

---

## Mise à jour d'un ZIM

1. Repérer la version la plus récente dans le catalogue :
   `curl -sL https://download.kiwix.org/zim/wikipedia/ | grep -E 'wikipedia_(fr|en)_all_maxi'`
2. Télécharger dans `.partial/` avec reprise possible (`wget -c`).
3. Vérifier l'empreinte avec la somme publiée à côté du fichier (extension
   `.sha256`) : `sha256sum -c` doit répondre « OK ».
4. Déplacer le fichier vers `/mnt/Data/Sites`, puis `chmod 644`.
5. Remplacer le nom du fichier dans la liste `command` du compose, mettre à
   jour le tableau ci-dessus, puis `docker compose up -d --force-recreate`.
6. Contrôler dans le navigateur. Ne supprimer l'ancien ZIM qu'ensuite : les
   deux versions coexistent un temps, prévoir l'espace disque. La suppression
   n'est pas répercutée vers Proton Drive : supprimer aussi l'ancienne version
   côté cloud.

---

## Sécurité

- Exposé publiquement via Traefik (HTTPS + Let's Encrypt), aucun port publié
  sur l'hôte.
- Authentification de base par le middleware `auth-basic`, appliqué après
  `rate-limit` : les essais de mot de passe sont eux aussi limités en débit.
  `kiwix-serve` n'a pas d'authentification propre.
- **`auth-basic` est le middleware qui protège aussi le dashboard Traefik** :
  quiconque a accès à Kiwix détient les identifiants du dashboard. Acceptable
  tant que l'administrateur est le seul utilisateur ; avant tout partage de
  l'accès, créer un middleware dédié avec son propre fichier d'utilisateurs.
- Middlewares `secure-headers-sameorigin` et `rate-limit` appliqués (voir
  `traefik/dynamic/dynamic.yml`). Avec `secure-headers`, le lecteur Kiwix
  s'affichait en erreur (« n'autorise pas la connexion ») : l'en-tête
  `X-Frame-Options: DENY` interdit le cadre dans lequel le lecteur charge les
  articles et les résultats de recherche. `secure-headers-sameorigin` autorise
  le cadre pour le même site uniquement (aucun autre site ne peut cadrer
  Kiwix). Cet assouplissement est à réserver aux services qui en ont besoin.
- ZIM montés en **lecture seule** : le conteneur ne peut rien modifier.
- Conteneur durci : `no-new-privileges`, toutes les capacités retirées, système
  de fichiers en lecture seule, rotation des journaux.
- Ne **jamais** utiliser la variable `DOWNLOAD` de l'image : elle fait
  télécharger un fichier au démarrage du conteneur.
- Le dossier des ZIM est répliqué vers Proton Drive avec le reste de Data (voir
  Prérequis) : contenu public, aucun secret n'y est stocké.

---

## Constats au déploiement

- Avec `secure-headers`, le lecteur s'affichait en erreur (« n'autorise pas la
  connexion ») à cause de `X-Frame-Options: DENY`. Corrigé par
  `secure-headers-sameorigin`. Après un changement d'en-têtes, le navigateur
  peut garder l'ancienne réponse en cache : vider le cache du navigateur
  (Ctrl+Maj+Suppr, « Images et fichiers en cache » seulement), ou tester en
  fenêtre privée.
- Le durcissement (`read_only`, `cap_drop`) n'empêche pas le démarrage.
- L'authentification de base ne gêne pas le lecteur.
- La recherche globale est refusée entre langues différentes ; la recherche
  dans un livre fonctionne (voir Limites connues).
