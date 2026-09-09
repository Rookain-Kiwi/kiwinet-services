# wireguard

Hub WireGuard central du mesh **kiwinet** — image [wg-easy](https://github.com/wg-easy/wg-easy)
(serveur WireGuard + interface web de gestion des pairs), déployé sur `kiwinet-scaleway`.

---

## Pourquoi le hub est sur kiwinet-scaleway et pas kiwinet-freebox

Décision architecturale (voir la page Notion *"Nœud WireGuard Pixel 10a — Garde-fous
d'accès de secours"*, projet `Stack [Kiwinet]`) : le VPS a une disponibilité de type
datacenter, une IP publique fixe native, et n'est pas sujet aux aléas d'une connexion
résidentielle (coupure ISP, reboot Freebox). `kiwinet-freebox` garde son rôle de
serveur applicatif (Traefik, Jellyfin, HA, WebDAV) mais devient un simple pair du
mesh, au même titre que le téléphone ou le laptop.

Objectif long terme : tous les accès admin (laptop `debian-pavilion`, VM Debian du
Pixel 10a) passent par ce tunnel, avec fermeture progressive de l'exposition SSH
publique sur `kiwinet-freebox` et `kiwinet-scaleway` une fois le mesh éprouvé en usage
réel.

---

## Pourquoi wg-easy plutôt que `wireguard-tools` natif ou `linuxserver/wireguard`

- Interface web de gestion des pairs — pertinent ici car le mesh est appelé à
  grandir dans le temps (VM 10a, laptop, freebox), pas pour un seul pair statique.
- Image officielle activement maintenue, multi-architecture
  (`linux/amd64`, `linux/arm64`, `linux/arm/v7`).
- Empreinte ressources négligeable : WireGuard reste un module noyau léger quel
  que soit le frontend utilisé au-dessus (confirmé lors du diagnostic ressources
  du VPS avant déploiement — non le facteur limitant).

---

## Points d'attention techniques

- **Tag épinglé sur la majeure `:15`, jamais `:latest`** — la doc officielle
  wg-easy indique explicitement que `:latest` pointe vers la v14 côté upstream.
- **Le port UDP 51820 est publié directement sur l'hôte**, hors Traefik : WireGuard
  est un protocole L3/UDP, un reverse proxy HTTP ne peut pas le relayer.
- **L'interface web (port 51821) n'est PAS publiée sur l'hôte.** Elle n'est
  accessible que via Traefik en HTTPS (`wg.kiwinet.me`), conformément à
  l'avertissement de sécurité de la doc officielle wg-easy : sans reverse proxy
  TLS devant elle, l'interface web transite en clair (session/identifiants
  exposés sur le réseau).
- **`traefik.docker.network=proxy` est obligatoire** : le conteneur est présent
  sur deux réseaux Docker (`wg` pour l'adressage WireGuard interne, `proxy` pour
  Traefik) — sans ce label, Traefik ne sait pas lequel utiliser pour joindre
  le conteneur.
- **IPv6 volontairement omis** de la configuration réseau par défaut proposée par
  wg-easy (l'image le supporte nativement) — non utilisé ailleurs dans
  `kiwinet-services`, à ajouter seulement si un besoin réel apparaît.

---

## Prérequis avant premier démarrage

**Sur la console Scaleway** (Security Group de l'instance `kiwinet-scaleway`) :
ouvrir le port **UDP 51820** en entrée. Le port 443 est déjà ouvert (Traefik)
pour l'accès à l'interface web via `wg.kiwinet.me`.

**DNS** : créer un enregistrement A `wg.kiwinet.me` → IP publique de
`kiwinet-scaleway`.

Aucune variable d'environnement à définir avant le premier lancement — la
configuration du endpoint public et la création du compte admin se font via
l'assistant web au tout premier accès.

---

## Démarrage

```bash
cd wireguard && docker compose up -d
```

Puis se rendre sur `https://wg.kiwinet.me` pour l'assistant de première
configuration (création du compte admin, saisie de l'IP/domaine public du
serveur).

---

## Restriction d'accès par pair — Per-Client Firewall

**Le champ "Allowed IPs" standard de l'interface web n'est PAS une restriction de
sécurité** : c'est une simple indication de routage côté client, qu'un pair peut
ignorer ou modifier localement. La doc officielle wg-easy est explicite sur ce
point (FAQ : *"How do I restrict client access to specific networks or
servers?"*).

La vraie restriction, appliquée côté serveur et non contournable par le client,
s'appelle **Per-Client Firewall** (nécessite `iptables`/`ip6tables` sur l'hôte,
déjà présents sur `kiwinet-scaleway` via `ufw`) :

1. **Admin Panel → Interface** → activer *"Per-Client Firewall"*
2. Éditer chaque pair → remplir *"Firewall Allowed IPs"* avec les destinations
   précises autorisées (ex. IP interne + port SSH de `kiwinet-freebox` et
   `kiwinet-scaleway` uniquement — pas d'accès LAN complet par défaut, cf.
   décision Notion).

À faire avant de créer le premier pair (VM Debian du Pixel 10a).

---

## Sécurité

- Interface d'administration exposée uniquement en HTTPS via Traefik
  (`secure-headers`, `rate-limit` — mêmes middlewares que les autres services
  publics de la stack, ex. `webdav`).
- `NET_ADMIN` + `SYS_MODULE` sont des capacités élevées, nécessaires pour que
  le conteneur gère les interfaces réseau et charge le module noyau WireGuard —
  limitées à ce seul conteneur (pas de `privileged: true`).
- Accès de chaque pair (VM 10a, futurs pairs) volontairement restreint dès sa
  création — pas d'accès LAN complet par défaut (voir décision Notion), à
  élargir explicitement seulement si un besoin réel apparaît.
- Le volume `etc_wireguard` contient la clé privée du serveur et les clés de
  tous les pairs — sa perte invalide tous les pairs existants. Sauvegarde à
  mettre en place (action en attente sur Notion : procédure de reconstruction
  du serveur).
