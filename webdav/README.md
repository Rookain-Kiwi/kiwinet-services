# webdav

Serveur WebDAV minimal (rclone `serve webdav`) exposant
`/mnt/Data/Backups/Technique/grapheneos-backups` et, en sous-dossier `photos`,
`/mnt/Libraries/Photos` via `webdav.kiwinet.me`.
Destination des sauvegardes des terminaux mobiles :

- **Seedvault** (GrapheneOS, Pixel 10a) : trois profils, un sous-dossier chacun
  (`public`, `private`, `professional`) ;
- **Round Sync** : envoi quotidien du dossier de sauvegardes du téléphone, dans
  un sous-dossier distinct de ceux de Seedvault ;
- **Joplin** : synchronisation des notes (chiffrées de bout en bout), dans un
  sous-dossier dédié ;
- **Photos du Pixel** : Round Sync copie chaque nuit le dossier de l'appareil
  photo vers `photos`, qui est le dossier `Photos` de Libraries monté en
  lecture-écriture ; un minuteur systemd le range par mois (voir
  [Photos du Pixel](#photos-du-pixel)).

---

## Pourquoi rclone plutôt que bytemark/webdav ou Nextcloud

- **Maintenu activement** : versions de sécurité régulières (la dernière
  consultée date du 09/10/2026).
- **Léger** — pas besoin de la stack complète Nextcloud pour ce seul usage.
- Supporte l'auth **bcrypt** via `--htpasswd`.

Limite connue : support **partiel** du verrouillage WebDAV (LOCK/UNLOCK). Les
clients écrivent dans des sous-dossiers distincts, mais partagent un compte
unique : pas de cloisonnement entre eux (voir Sécurité).

---

## Prérequis avant premier démarrage

- Le disque Data est monté et le dossier
  `/mnt/Data/Backups/Technique/grapheneos-backups` existe (le montage évite de
  le créer sur le SSD système : `create_host_path: false`).
- Le conteneur tourne avec `user: "1000:1000"`, identifiant du propriétaire du
  dossier servi sur le serveur. **Pas de `chown`** : le volume Data est
  répliqué vers Proton Drive.
- Pour les photos : le point de montage `photos` existe, **vide**, dans le
  dossier servi (créé à la main par le compte d'administration, sinon Docker le
  crée en root sous Data), et la racine de `/mnt/Libraries/Photos` appartient à
  l'UID 1000 (changement de propriétaire de la seule racine, sans récursion).
- Image `rclone/rclone` épinglée par tag et empreinte (index multi-architecture,
  amd64 inclus). Pour la mettre à jour : choisir le tag, relever le champ
  `digest` sur Docker Hub, puis modifier le compose.
- Fichier d'identifiants bcrypt, **ignoré par Git, jamais commité** :

```bash
htpasswd -nB <utilisateur> >> webdav/.htpasswd
```

rclone relit ce fichier à chaud : l'ajout ou le changement d'un mot de passe ne
demande pas de redémarrage.

---

## Démarrage

```bash
cd webdav && docker compose up -d
```

Aucun port n'est publié : le service n'est joignable que par Traefik (réseau
Docker `proxy`). Le certificat est géré par Traefik (Let's Encrypt).

---

## Configuration des clients

Le serveur sert sous le préfixe `--baseurl /webdav` : l'adresse d'un client est
de la forme `https://webdav.kiwinet.me/webdav/<sous-dossier>`.

| Client    | Sous-dossier                                   |
|-----------|------------------------------------------------|
| Seedvault | `public`, `private` ou `professional` (selon le profil) |
| Round Sync (sauvegardes) | sous-dossier dédié, distinct de ceux de Seedvault |
| Round Sync (photos) | `photos` (= `Photos` de Libraries) : `vendor = rclone`, mode copie |
| Joplin    | sous-dossier dédié                              |

Identifiants : ceux du fichier `.htpasswd` (compte unique partagé).

Round Sync : toujours en mode **copie**, jamais en synchronisation (elle
supprimerait à la destination, donc dans `Photos`).

---

## Photos du Pixel

```
Pixel (DCIM/Camera) ──Round Sync, copie, 03:00──▶ /webdav/photos (= Photos, à plat)
   ──photos-sort, 04:00──▶ Photos/AAAA/AAAA-MM/ ──Proton Drive, 04:30──▶ cloud
```

Round Sync n'a pas de mode déplacement : il renvoie chaque nuit tout ce qui reste
sur le téléphone ; le vidage du Pixel se fait à la main. Le script
`photos-sort/photos-sort.sh` (minuteur systemd, compte d'administration, jamais
root) reste dans le dépôt, **jamais dans `Photos`**, que ce service peut écrire.
Il range :

- les fichiers `PXL_AAAAMMJJ_…` de la racine, vieux de plus de 10 minutes, par
  le mois lu dans le nom (UTC : une photo prise juste après minuit peut être
  rangée dans le mois précédent) ;
- sans jamais écraser : la copie à la racine n'est supprimée que si elle est
  identique octet par octet à celle déjà rangée (sinon elle partirait à plat
  chez Proton) ;
- contenu différent ou nom inconnu : laissé à la racine, sans signalement, à
  traiter à la main (en local et chez Proton) ; aucun moniteur ;
- l'unité ne sort en erreur que pour un problème technique (disque non monté,
  dossier non inscriptible).

Installation des unités (copies appartenant à root) :

```bash
sudo install -m 644 -o root -g root webdav/photos-sort/photos-sort.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now photos-sort.timer
```

À savoir : les mois d'années anciennes encore à l'ancien identifiant (4242) sont
bloqués (changement de propriétaire ciblé du dossier concerné, sans récursion) ;
le service garde la liste des dossiers en cache quelques minutes (un renvoi juste
après un tri peut être ignoré, sans effet sur le flux réel) ; les envois de
vidéos longues demandent le délai de lecture relevé dans Traefik (voir
`traefik/README.md`).

---

## Sécurité

- Exposé publiquement via Traefik (HTTPS + Let's Encrypt) pour permettre les
  sauvegardes en déplacement, pas seulement à domicile.
- Authentification bcrypt dédiée à ce service, indépendante de celle du
  dashboard Traefik.
- Middlewares `secure-headers` et `rate-limit` appliqués (voir
  `traefik/dynamic/dynamic.yml`).
- Conteneur durci : UID/GID non-root (`1000:1000`), `no-new-privileges`,
  toutes les capacités retirées, système de fichiers en lecture seule,
  rotation des journaux.
- `Photos` est monté en **lecture-écriture** : seule exception au principe
  « médias en lecture seule » (décision du 03/11/2026). Seul ce dossier de
  Libraries est monté, jamais le disque entier.
- **Compte unique** partagé par tous les clients : un compte compromis voit
  toute l'arborescence servie, **y compris Photos (lecture, écriture,
  suppression, écrasement)**. Seul le chiffrement de bout en bout (Seedvault,
  Joplin) protège le contenu ; les photos ne sont pas chiffrées. À roter en cas
  de doute sur une fuite.
- Les volumes Data et Photos sont **répliqués vers Proton Drive** (ajouts et
  modifications, sans répercuter les suppressions) : tout fichier déposé sur ce
  partage y est aussi envoyé.
- Le niveau de journalisation par défaut de rclone ne trace pas les requêtes :
  pas de diagnostic possible en cas de suppression inexpliquée. Plus gênant
  depuis que Photos est monté en écriture.
