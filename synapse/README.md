# ============================================================================
# Synapse (Matrix Homeserver) — Étape 1
# ============================================================================
# Configuration: Server name: kiwinet
# Architecture: Synapse sur VPS + PostgreSQL mutualisé (réseau Docker db)
# Fédération: Désactivée en Étape 1 (firewall VPS, port 8448 fermé)
# ============================================================================

## Architecture

- **Server name:** kiwinet (identité du serveur Matrix)
- **Database:** PostgreSQL 16 (mutualisée, réseau Docker `db`)
- **Reverse proxy:** Traefik (`matrix.kiwinet.me`)
- **Port client:** 8008 (via Traefik)
- **Port fédération:** 8448 (désactivé en Étape 1, fermé au firewall)
- **Registration:** Libre, sans token requis
- **Fédération:** Désactivée (firewall VPS)

## ────────────────────────────────────────────────────────────────────────
## Déploiement sur VPS
## ────────────────────────────────────────────────────────────────────────

### Pull du repo
```bash
cd /opt/kiwinet-services
git pull origin main
cd synapse
```

### Créer `.env` avec secrets réels
```bash
cp .env.example .env
nano .env
```
Remplir les 3 secrets:
- `SYNAPSE_DB_PASSWORD` (de PostgreSQL)
- `SYNAPSE_MACAROON_SECRET` (clé secrète Synapse)
- `SYNAPSE_REGISTRATION_SECRET` (token registration)

### Éditer homeserver.yaml
```bash
nano homeserver.yaml
```
Vérifier la section `[database]`:
- `host: postgres` (hostname Docker)
- `user: synapse`
- `password: ${SYNAPSE_DB_PASSWORD}`

### Démarrer
```bash
docker compose up -d
docker compose ps
```
Status doit être: `Up X minutes (healthy)`

### Tester
```bash
curl http://localhost:8008/_matrix/client/versions
```
Doit retourner JSON avec les versions supportées

## ────────────────────────────────────────────────────────────────────────
## Secrets
## ────────────────────────────────────────────────────────────────────────

**Ne jamais committer:**
- `.env` — credentials PostgreSQL + secrets Synapse
- `homeserver.yaml` — config générée avec valeurs sensibles
- `kiwinet.signing.key` — clé privée de signature
- `data/` — contenu utilisateur (media, états de rooms, etc.)

Tous exclus via `.gitignore` à la racine du repo.

## ────────────────────────────────────────────────────────────────────────
## Prochaines étapes
## ────────────────────────────────────────────────────────────────────────

### Étape 4: Déployer sur VM Freebox
- Utiliser Ansible pour déployer la même config sur la VM
- PostgreSQL reste sur VPS, Synapse sur VM + VPS

### Étape 5: Configurer `.well-known`
- Ajouter `.well-known/matrix/client` et `.well-known/matrix/server` sur kiwinet.me
- Déléguer la fédération vers matrix.kiwinet.me

### Étape 6: Activer fédération
- Ouvrir port 8448 au firewall VPS
- Activer fédération dans homeserver.yaml