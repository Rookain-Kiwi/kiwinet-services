# webdav

Serveur WebDAV minimal (rclone `serve webdav`) exposant
`/mnt/Data/Backups/Technique/grapheneos-backups` via `webdav.kiwinet.me`. Destination des sauvegardes Seedvault du Pixel 10a
(GrapheneOS) pour les trois profils : Rookain, Public, Professionnel.

Remplace le transfert manuel via Freebox Files (peu fiable en connexion mobile,
et Freebox OS n'a pas de WebDAV natif).

---

## Pourquoi rclone plutôt que bytemark/webdav ou Nextcloud

- **Maintenu activement** (bytemark/webdav n'a pas été mis à jour depuis 7 ans)
- **Léger** — pas besoin de la stack complète Nextcloud pour ce seul usage
- Supporte l'auth **bcrypt** via `--htpasswd`, cohérent avec le mécanisme déjà
  utilisé pour le dashboard Traefik

Limite connue : support **partiel** du verrouillage WebDAV (LOCK/UNLOCK), contre
un support complet chez `go-webdav`. Sans impact ici : un seul client (Seedvault)
écrit ses sauvegardes de façon séquentielle, jamais en concurrence.

---

## Prérequis avant premier démarrage

Arm64 confirmé disponible dans le manifeste `rclone/rclone:1.71.2` (vérifié le 21/08).

Le dossier hôte `/mnt/Data/Backups/Technique/grapheneos-backups` existe déjà,
peuplé par les transferts manuels précédents (`public/`, `private/`,
`professional/`, `terminal/`). Le conteneur tourne avec `user: "1002:1002"`
pour matcher la propriété existante (`rookain:rookain`) — pas de chown requis.

```bash
# Générer les identifiants (bcrypt recommandé)
htpasswd -nB <utilisateur> >> webdav/.htpasswd
```

Le fichier `.htpasswd` est gitignored — ne jamais le committer.

---

## Démarrage

```bash
cd webdav && docker compose up -d
```

---

## Configuration Seedvault (par profil)

Dans Seedvault > choisir la destination > WebDAV :

| Champ         | Valeur                                    |
|---------------|--------------------------------------------|
| Serveur       | `webdav.kiwinet.me`                       |
| Port          | `443`                                      |
| HTTPS         | Oui                                         |
| Chemin        | `public`, `private`, ou `professional` selon le profil |
| Utilisateur   | celui généré dans `.htpasswd`              |
| Mot de passe  | celui généré dans `.htpasswd`              |

---

## Sécurité

- Exposé publiquement via Traefik (HTTPS + Let's Encrypt) pour permettre les
  sauvegardes en déplacement, pas seulement à domicile.
- Authentification bcrypt dédiée à ce service, indépendante de celle du
  dashboard Traefik.
- Middlewares `secure-headers` et `rate-limit` appliqués (voir `traefik/dynamic/dynamic.yml`).
- Le conteneur tourne en UID/GID non-root (`1000:1000`).
- Point d'attention : ce service reçoit les sauvegardes chiffrées des 3 profils
  du Pixel 10a. Le chiffrement Seedvault protège le contenu en cas de fuite du
  fichier, mais la disponibilité/l'intégrité du service repose sur la sécurité
  du compte `.htpasswd` — à roter en cas de doute sur une fuite.
