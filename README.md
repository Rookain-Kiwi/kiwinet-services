# kiwinet-infra

Configuration de l'infrastructure centrale de `kiwinet.me`  
Reverse proxy Traefik, gestion SSL, routing HTTP/HTTPS, middlewares de sécurité et services.

---

## Rôle de ce repo

Ce repo contient l'intégralité de la configuration Traefik : le point d'entrée unique de la VM pour tout le trafic HTTP/HTTPS entrant. Aucun service n'est exposé publiquement sans passer par ici.

Il fait partie d'un ensemble de quatre repos qui constituent l'infrastructure de `kiwinet.me` :

| Repo                   | Rôle                                    | URL déployée            
|------------------------|-----------------------------------------|-------------------------
| `kiwinet-infra`    | Traefik, routing, SSL, middlewares      | `none`
| `kiwinet-web`          | Site principal Astro + Nginx            | `kiwinet.me`            
| `kiwinet-status`       | Page de statut Uptime Kuma              | `status.kiwinet.me`     
| `kiwinet-monitoring`   | Stack Prometheus / Loki / Grafana       | `grafana.kiwinet.me`    

---

## Architecture générale

```
Internet
    │
    ▼
IP fixe
    │
    ├── :80   → Freebox → VM → Traefik  (HTTP Challenge Let's Encrypt + redirection HTTPS)
    ├── :443  → Freebox → VM → Traefik
    │               │
    │               ├── kiwinet.me / www.kiwinet.me  → container kiwinet-web (Nginx:80)
    │               ├── traefik.kiwinet.me           → dashboard Traefik (auth-basic)
    │               ├── plex.kiwinet.me              → VM:32400 (Plex natif, via 172.17.0.1)
    │               ├── status.kiwinet.me            → container uptime-kuma (:3001)
    │               └── grafana.kiwinet.me           → container grafana (:3000)
    │
    ├── :22    → SSH (hors Docker)
    └── :25565 → Minecraft (hors Docker, TCP brut - ne passe pas par Traefik)
```

**Réseau Docker :**
- `proxy` (bridge, externe) - partagé par tous les services exposés publiquement
- `monitoring` (bridge, interne) - isolé entre Prometheus, Loki, Grafana, exporters

---

## Structure du repo

```
kiwinet-infra/
├── docker-compose.yml          ← démarrage du container Traefik
├── .gitignore                  ← exclut traefik/acme.json
└── traefik/
    ├── traefik.yml             ← config statique (redémarrage requis si modifié)
    ├── dynamic.yml             ← config dynamique (routers, services, middlewares)
    └── acme.json               ← certificats Let's Encrypt (chmod 600, non commité)
```

`acme.json` n'est **jamais commité**. Il contient les clés privées des certificats TLS.  
Permissions requises : `chmod 600 traefik/acme.json`

---

## Gestion SSL

### Stratégie : HTTP Challenge (Let's Encrypt)

Traefik obtient et renouvelle automatiquement un certificat par domaine via le HTTP Challenge :

```
1. Traefik contacte Let's Encrypt pour un domaine donné
2. Let's Encrypt envoie une requête HTTP sur :80 vers ce domaine
3. Traefik répond avec un token de validation
4. Let's Encrypt vérifie → émet le certificat
5. Traefik stocke le certificat dans acme.json
6. Renouvellement automatique 30 jours avant expiration
```

Un certificat wildcard (`*.kiwinet.me`) aurait nécessité un DNS Challenge - non disponible chez Bluehost (absence d'API DNS publique). Le HTTP Challenge implique un certificat par domaine : c'est le compromis retenu.

### Certificats gérés

| Domaine                | Gestionnaire | Renouvellement                   
|------------------------|--------------|----------------------------------
| `kiwinet.me` + `www`   | Traefik      | Automatique                      
| `traefik.kiwinet.me`   | Traefik      | Automatique                      
| `plex.kiwinet.me`      | Traefik      | Automatique                      
| `status.kiwinet.me`    | Traefik      | Automatique                      
| `grafana.kiwinet.me`   | Traefik      | Automatique                      
| `freebox.kiwinet.me`   | Certbot      | Manuel - échéance 15/06/2026 

`freebox.kiwinet.me` est un cas particulier : la Freebox bloque les connexions depuis le réseau local vers ses ports d'administration. Traefik ne peut pas lui faire de proxy. Le certificat est généré avec Certbot standalone (port 80 libéré temporairement) et importé manuellement dans l'interface Freebox.

---

## Middlewares disponibles

Définis dans `traefik/dynamic.yml` et référencés via `@file` depuis les labels Docker ou les routers statiques.

| Middleware              | Usage                                                
|-------------------------|------------------------------------------------------
| `auth-basic@file`       | Dashboard Traefik, Prometheus, Grafana               
| `secure-headers@file`   | Site principal, Plex, Uptime Kuma (services publics) 
| `rate-limit@file`       | Endpoints publics                                    

---

## Routing des services natifs (hors Docker)

Pour les services qui tournent directement sur la VM (Plex, Minecraft), Traefik ne peut pas utiliser `127.0.0.1` depuis l'intérieur du container — ce loopback pointe vers le container lui-même, pas vers l'hôte.

```yaml
# ❌ Ne fonctionne pas
url: "http://127.0.0.1:32400"

# ✅ Correct — IP de l'interface docker0 (gateway hôte)
url: "http://172.17.0.1:32400"
```

L'IP `172.17.0.1` est l'interface `docker0`, stable au redémarrage.

---

## Points critiques

**`dynamic.yml` - une seule section `http:`**  
Toutes les définitions (routers, services, middlewares) doivent être imbriquées sous une unique section `http:`. Plusieurs sections `http:` dans le même fichier provoquent des erreurs de parsing silencieuses.

**Rechargement de `dynamic.yml` non fiable**  
Bien que `watch: true` soit configuré, le rechargement à chaud ne fonctionne pas de manière fiable sur cette infrastructure. Toute modification de `dynamic.yml` nécessite un redémarrage explicite :

```bash
docker restart traefik
# Vérifier la prise en compte :
docker exec traefik cat /etc/traefik/dynamic.yml | tail -20
```

**Nettoyage de `acme.json` après échec de certificat**  
En cas d'échec (NXDOMAIN, rate limit), Traefik enregistre l'échec dans `acme.json` et applique un backoff. Un simple `restart` ne suffit pas :

```bash
cd /opt/traefik && docker compose down

python3 -c "
import json
with open('traefik/acme.json', 'r') as f:
    data = json.load(f)
for resolver in data:
    data[resolver]['Certificates'] = [
        c for c in data[resolver].get('Certificates', [])
        if c.get('domain', {}).get('main') not in ['domaine-a-supprimer.kiwinet.me']
    ]
with open('traefik/acme.json', 'w') as f:
    json.dump(data, f, indent=2)
print('OK')
"

chmod 600 traefik/acme.json
docker compose up -d
```

**Rate limit Let's Encrypt**  
Let's Encrypt applique un rate limit de **5 tentatives échouées par heure** par domaine. En cas de boucles d'erreurs (restarts répétés avant propagation DNS), attendre l'expiration avant de relancer. Le timestamp de reprise est indiqué dans le message d'erreur.

---

## Déploiement

Ce repo est cloné sur la VM dans `/opt/traefik/`. Le workflow est entièrement manuel pour l'infra (pas de CI/CD pour l'instant sur ce repo) :

```bash
# Sur la machine locale
git push origin main

# Sur la VM
cd /opt/traefik
git pull
docker compose up -d --force-recreate
```

**Prérequis sur la VM :**
- Docker + Docker Compose installés
- Ports `80` et `443` ouverts (UFW + redirections Freebox)
- DNS A de chaque domaine pointant vers l'IP fixe
- `traefik/acme.json` existant avec `chmod 600`

---

## Ports UFW ouverts

| Port  | Protocole | Usage                                        
|-------|-----------|----------------------------------------------
| 22    | TCP       | SSH                                          
| 80    | TCP       | Traefik - HTTP Challenge + redirection HTTPS 
| 443   | TCP       | Traefik - HTTPS                              
| 25565 | TCP       | Minecraft (hors Docker)                      
| 32400 | TCP       | Plex (hors Docker)                           

---

## Infrastructure cible

| Composant      | Détail                                
|----------------|---------------------------------------
| OS             | Debian GNU/Linux 13.3 (Trixie)        
| Architecture   | ARM Cortex-A72 - AArch64 (2 cœurs)    
| RAM            | 12 Go                                 
| Virtualisation | QEMU / VirtIO (Freebox Delta)         
| Domaine        | `kiwinet.me` - DNS géré chez Bluehost 
| IP publique    | `**.**.***.***`                       
