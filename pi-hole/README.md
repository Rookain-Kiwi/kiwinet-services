# pihole

Résolveur DNS filtrant (image officielle `pihole/pihole`, v6) pour le réseau
local. Objectif : réduire le bruit réseau et gagner en visibilité sur ce qui
sort (trackers, télémétrie, IoT bavard) — **pas** bloquer la publicité vidéo
des services de streaming (YouTube, Prime Video), structurellement hors de
portée d'un filtrage DNS (la pub est servie depuis les mêmes domaines que le
contenu).

---

## Pourquoi réseau hôte plutôt que macvlan

- Même pattern que Home Assistant et Music Assistant sur ce serveur : un
  service DNS doit être joignable par toute adresse qui l'interroge, pas
  seulement depuis l'hôte — le réseau hôte évite la complexité d'un réseau
  macvlan dédié pour un seul service supplémentaire.
- Conséquence : pas de `ports:` dans le compose (ignorés en réseau hôte), et
  **pas de chaîne DOCKER-USER** applicable ici — l'exposition est filtrée par
  `ufw` directement sur l'hôte, comme pour les autres services en réseau hôte.

---

## Prérequis avant premier démarrage

- IP fixe du serveur sur le LAN (réservation DHCP côté Freebox) — condition
  nécessaire avant de pousser cette adresse comme DNS à tout le réseau,
  sous peine de casser la résolution DNS du LAN au moindre changement d'IP.
- Fichier `.env` rempli à partir de `.env.example` (mot de passe admin, IP LAN
  du serveur, résolveurs DNS amont), **ignoré par Git, jamais commité**.
- Image épinglée par tag **et** par empreinte : relever le digest réel après
  le premier `docker compose pull` (`docker inspect --format='{{index
  .RepoDigests 0}}' pihole/pihole:<tag>`) et le figer dans le compose.
- Version minimale : Core ≥ 6.4.2 / FTL ≥ 6.6.1 (CVE-2026-35517 et
  CVE-2026-41489 corrigés à partir de ces versions) — ne jamais redescendre
  en dessous lors d'une mise à jour future.

---

## Démarrage

```bash
docker compose up -d
```

Aucun port publié par Docker (réseau hôte). Port web admin déplacé sur 8080
(évite le conflit avec Traefik, qui occupe 80/443 sur ce même serveur), lié à
la seule adresse LAN du serveur — jamais à toutes les interfaces.

---

## Configuration du réseau

- **DNS poussé à tout le LAN par le DHCP de la Freebox**, une fois la bascule
  validée (voir Décisions du socle) : chaque appareil qui obtient une IP par
  DHCP utilise automatiquement Pi-hole, sans configuration manuelle poste par
  poste.
- Résolveur de la box en amont primaire (conserve la résolution des noms
  locaux), résolveur public en secours — cohérent avec la convention DNS déjà
  en place sur ce serveur.
- Interface d'admin accessible uniquement en LAN
  (`http://<ip-serveur>:8080/admin`) — **jamais exposée via Traefik**, ni
  publiquement.

---

## Sécurité

- **Jamais exposé publiquement** : ni le port DNS (53) ni l'interface
  d'admin ne doivent sortir du LAN.
- Conteneur durci : `no-new-privileges`, toutes les capacités retirées par
  défaut (`NET_ADMIN` à n'ajouter que si une fonctionnalité réseau avancée
  l'exige réellement, après test), rotation des journaux.
- **Limite assumée** : tout appareil utilisant son propre client VPN (usage
  personnel, hors tunnel Gluetun de la seedbox) échappe entièrement au
  filtrage — comportement inhérent à tout tunnel VPN complet, pas une faille
  de Pi-hole.
- **Point de défaillance unique pour la résolution DNS du LAN** une fois la
  bascule DHCP faite : surveiller la disponibilité du service (Uptime Kuma),
  prévoir un DNS de secours côté DHCP Freebox.
- Mises à jour de sécurité à suivre activement : projet avec un historique de
  CVE critiques en 2026 (RCE, élévation de privilèges) — ne pas laisser
  l'image stagner.
