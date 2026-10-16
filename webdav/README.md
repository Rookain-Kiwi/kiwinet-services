# webdav

Serveur WebDAV minimal (rclone `serve webdav`) exposant
`/mnt/Data/Backups/Technique/grapheneos-backups` via `webdav.kiwinet.me`.
Destination des sauvegardes des terminaux mobiles :

- **Seedvault** (GrapheneOS, Pixel 10a) : trois profils, un sous-dossier chacun
  (`public`, `private`, `professional`) ;
- **Round Sync** : envoi quotidien du dossier de sauvegardes du téléphone, dans
  un sous-dossier distinct de ceux de Seedvault ;
- **Joplin** : synchronisation des notes (chiffrées de bout en bout), dans un
  sous-dossier dédié.

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
| Round Sync | sous-dossier dédié, distinct de ceux de Seedvault |
| Joplin    | sous-dossier dédié                              |

Identifiants : ceux du fichier `.htpasswd` (compte unique partagé).

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
- **Compte unique** partagé par tous les clients : un compte compromis voit
  toute l'arborescence servie. Seul le chiffrement de bout en bout (Seedvault,
  Joplin) protège le contenu ; à roter en cas de doute sur une fuite.
- Le volume Data est **répliqué vers Proton Drive** (ajouts et modifications,
  sans répercuter les suppressions) : tout fichier déposé sur ce partage y est
  aussi envoyé.
- Le niveau de journalisation par défaut de rclone ne trace pas les requêtes :
  pas de diagnostic possible en cas de suppression inexpliquée.
