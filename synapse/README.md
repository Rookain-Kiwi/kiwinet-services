# 🚀 Synapse (Matrix Server) — Déploiement Étape 1

**Version** : Étape 1 (Mode privé fermé, pas de fédération)  
**Server name** : `kiwinet`  
**Hostname** : `matrix.kiwinet.me`  
**Architecture** : Utilisateurs `@user:kiwinet`, PostgreSQL persistent  
**Status** : Production-ready pour mode privé  

---

## 📋 Fichiers du service

```
kiwinet-services/synapse/
├── docker-compose.yml          # Stack Synapse + PostgreSQL
├── homeserver.yaml             # Configuration Synapse
├── logging.yaml                # Logging JSON
├── init-synapse-db.sql         # Script SQL init PostgreSQL
├── .env.example                # Template secrets
├── .gitignore                  # Ignore .env + data/
└── README.md                   # Ce fichier
```

---

## 🔐 Prérequis — ÉTAPES 1 & 2

✅ **PostgreSQL 16 Alpine** opérationnel sur VPS  
✅ **User `synapse`** avec password : `_fj_GWsvSBwv6rhZD-5450gvg7SmuchWBaqaY_rDjcKyqeFaUBfXjIYkoJJm8j1f`  
✅ **Base `synapse`** créée et prête  
✅ **Block storage 50 GB** monté sur `/var/lib/postgresql`  
✅ **Traefik reverse proxy** configuré (réseaux `proxy` + `db`)  
✅ **Firewall VPS** ports 80/443 ouverts  
✅ **DNS** : `matrix.kiwinet.me` → 163.172.134.30 (Bluehost)  

---

## 🎯 Déploiement — Étape par étape

### 1️⃣ Préparation du répertoire (sur VPS)

```bash
# SSH sur VPS Scaleway
ssh -p 2222 rookain@163.172.134.30

# Naviguer vers kiwinet-services
cd /home/rookain/kiwinet-services

# Créer le répertoire synapse
mkdir -p synapse
cd synapse
```

### 2️⃣ Copie des fichiers

Option A — **Via git (recommandé)**
```bash
# Dans ta machine locale
cd kiwinet-services/synapse
# Ajouter les 5 fichiers en commit
git add docker-compose.yml homeserver.yaml logging.yaml .env.example init-synapse-db.sql README.md
git commit -m "feat(synapse): add Étape 1 deployment files"
git push origin develop

# Sur VPS
cd /home/rookain/kiwinet-services/synapse
git pull origin develop
```

Option B — **Via SCP (rapide)**
```bash
# Depuis ta machine locale
scp -P 2222 docker-compose.yml rookain@163.172.134.30:/home/rookain/kiwinet-services/synapse/
scp -P 2222 homeserver.yaml rookain@163.172.134.30:/home/rookain/kiwinet-services/synapse/
scp -P 2222 logging.yaml rookain@163.172.134.30:/home/rookain/kiwinet-services/synapse/
scp -P 2222 .env.example rookain@163.172.134.30:/home/rookain/kiwinet-services/synapse/
scp -P 2222 init-synapse-db.sql rookain@163.172.134.30:/home/rookain/kiwinet-services/synapse/
scp -P 2222 README.md rookain@163.172.134.30:/home/rookain/kiwinet-services/synapse/
```

### 3️⃣ Génération des secrets (sur ta machine locale)

```bash
# Macaroon secret (hex 32 = 64 caractères)
python3 -c "import secrets; print(secrets.token_hex(32))"
# Copie le résultat → SYNAPSE_MACAROON_SECRET dans .env

# Registration secret (urlsafe 32 = ~43 caractères)
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
# Copie le résultat → SYNAPSE_REGISTRATION_SECRET dans .env
```

### 4️⃣ Configuration .env (sur VPS)

```bash
cd /home/rookain/kiwinet-services/synapse

# Copier le template
cp .env.example .env

# Éditer et compléter avec les secrets générés
nano .env
```

**Exemple .env complété :**
```env
POSTGRES_ROOT_PASSWORD=<ton_root_password_postgresql>
SYNAPSE_DB_PASSWORD=_fj_GWsvSBwv6rhZD-5450gvg7SmuchWBaqaY_rDjcKyqeFaUBfXjIYkoJJm8j1f
SYNAPSE_MACAROON_SECRET=a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a7b8c9d0e1f2
SYNAPSE_REGISTRATION_SECRET=abc123DEF456ghi789JKL012mno345pqrSTU678vwxYZ901
```

**Vérifier que .env est bien créé :**
```bash
ls -la .env
cat .env  # Vérifier les valeurs
```

### 5️⃣ Création des répertoires de données (sur VPS)

```bash
cd /home/rookain/kiwinet-services/synapse

# Répertoire data (pour homeserver files)
mkdir -p data

# Répertoire logs
mkdir -p data/logs

# Répertoire media store
mkdir -p data/media_store

# Permissions
chmod 755 data
```

### 6️⃣ Démarrage du stack Synapse (sur VPS)

```bash
cd /home/rookain/kiwinet-services/synapse

# Démarrer les containers
docker compose up -d

# Vérifier le statut
docker compose ps
docker compose logs -f synapse

# Attendre ~30 secondes que Synapse initialise
# (Voir healthcheck: "database system is ready")
```

**Sortie attendue :**
```
synapse          Running (healthy)
postgres-synapse Running (healthy)
```

### 7️⃣ Vérification santé (sur VPS)

```bash
# Test client API
curl -s http://localhost:8008/_matrix/client/versions | jq .

# Résultat attendu
{
  "versions": ["r0.0.1", "r0.0.2", "r0.1.0", "r0.2.0", "r0.3.0", "r0.4.0", "r0.5.0", "r0.6.0", "r0.6.1"]
}

# Test via Traefik (HTTPS)
curl -s https://matrix.kiwinet.me/_matrix/client/versions | jq .
```

### 8️⃣ Création du compte admin (sur VPS)

```bash
cd /home/rookain/kiwinet-services/synapse

# Générer un utilisateur admin
docker compose exec synapse synapse_register_new_matrix_user \
  -u admin \
  -p <TON_PASSWORD_ADMIN> \
  -a \
  http://localhost:8008

# Exemple
docker compose exec synapse synapse_register_new_matrix_user \
  -u admin \
  -p MySecureAdminPassword123! \
  -a \
  http://localhost:8008

# Résultat attendu
# User successfully registered
```

---

## 🌐 Configuration `.well-known` — Préparation Fédération (Étape 2)

Synapse fonctionne en mode privé (Étape 1), mais préparons la fédération pour plus tard.

### Structure `.well-known`

Sur le domaine `kiwinet.me` (site Astro), ajouter deux fichiers :

```
/.well-known/matrix/client
/.well-known/matrix/server
```

### Client Discovery (`/.well-known/matrix/client`)

**Path** : `kiwinet-web/public/.well-known/matrix/client`

```json
{
  "m.homeserver": {
    "base_url": "https://matrix.kiwinet.me"
  }
}
```

**Vérification :**
```bash
curl -s https://kiwinet.me/.well-known/matrix/client | jq .
```

### Server Discovery (`/.well-known/matrix/server`)

**Path** : `kiwinet-web/public/.well-known/matrix/server`

```json
{
  "m.server": "kiwinet.me:8448"
}
```

**Note** : Port 8448 n'existe pas encore en Étape 1 — sera activé en Étape 2 avec fédération.

---

## 🧪 Test avec un client Matrix (Element X / Element Desktop)

### Configuration client

1. **URL du serveur** : `https://matrix.kiwinet.me`
2. **Username** : `admin` (ou un autre utilisateur créé)
3. **Password** : Le password défini lors de la création
4. **Display name** : Ton nom d'affichage

### Flux d'inscription (Étape 1)

En Étape 1, l'enregistrement est **libre** (pas de token).

1. Ouvrir Element X → "Create account"
2. Cliquer "Create your own"
3. Server : `matrix.kiwinet.me`
4. Username : `@monuser:kiwinet`
5. Password : Créer un mot de passe sécurisé
6. Créer un compte

**Résultat attendu** : Compte créé, accès au client Matrix.

---

## 📊 Monitoring & Observabilité

### Logs Synapse (JSON format)

```bash
# Logs en direct
docker compose logs -f synapse

# Logs PostgreSQL
docker compose logs -f postgres-synapse

# Logs spécifiques (par niveau)
docker compose logs synapse | grep ERROR
docker compose logs synapse | grep WARNING
```

### Intégration Loki (via Promtail)

Les logs Synapse sont en JSON (champ `json` dans `logging.yaml`).  
À intégrer à Loki en Étape 3+ avec labellisation Promtail.

### Métriques Prometheus

Synapse expose les métriques sur `http://localhost:8008/_synapse/metrics` (à activer si nécessaire).

---

## 🔧 Troubleshooting

### ❌ `docker compose up -d` échoue

```bash
# Vérifier les logs complètement
docker compose logs

# Erreur commune: Port 8008 déjà utilisé
netstat -tlnp | grep 8008

# Arrêter les anciens containers
docker compose down
```

### ❌ Synapse ne se connecte pas à PostgreSQL

```bash
# Vérifier la connexion PostgreSQL
docker compose exec synapse psql \
  -h 127.0.0.1 -U synapse -d synapse -c "SELECT version();"

# Password: _fj_GWsvSBwv6rhZD-5450gvg7SmuchWBaqaY_rDjcKyqeFaUBfXjIYkoJJm8j1f
```

### ❌ Traefik ne route pas vers Synapse

```bash
# Vérifier que le label Traefik est correct
docker inspect synapse | grep -A 20 "Labels"

# Vérifier la configuration Traefik
docker exec traefik cat /etc/traefik/dynamic/kiwinet-services.yml | grep -A 20 matrix

# Redémarrer Traefik
docker compose -f ../traefik/docker-compose.yml restart traefik
```

### ❌ Account creation fails

```bash
# Vérifier que registration est activée
docker compose exec synapse cat /data/homeserver.yaml | grep enable_registration

# Doit montrer: enable_registration: true
```

---

## 🚀 Transition vers Étape 2 (Fédération)

Checklist pour passer en mode fédération :

- [ ] Port 8448 ouvert au firewall VPS (Scaleway + UFW)
- [ ] DNS `matrix.kiwinet.me` résout bien
- [ ] Certificate TLS valide pour `matrix.kiwinet.me`
- [ ] `/.well-known/matrix/server` configuré sur `kiwinet.me`
- [ ] Configuration Synapse : `federation_ip_range_whitelist` à ajuster
- [ ] Synapse redémarré avec nouvelle config fédération
- [ ] Test avec serveur Matrix tiers (ex: matrix.org)

---

## 📝 ADR & Documentation

Voir **ADR-007** (en cours) : Architecture Matrix Synapse sur Kiwinet  
Voir **stack-technique.md** : Vue d'ensemble infrastructure

---

## 🔒 Sécurité — Rappels

✅ **`.env` jamais en git** → `.gitignore` contient `.env`  
✅ **Secrets générés aléatoirement** → `secrets.token_hex()` / `secrets.token_urlsafe()`  
✅ **Fédération désactivée au firewall** en Étape 1 → Port 8448 fermé  
✅ **PostgreSQL localhost only** → Pas d'exposition publique  
✅ **Traefik HTTPS** → TLS via Let's Encrypt  

---

## 📞 Support & Questions

- **Logs** : `docker compose logs -f`
- **PostgreSQL** : Voir `ETAPES_1_2_COMPLETE.md`
- **Traefik** : Voir `../traefik/README.md`
- **Matrix** : https://matrix-org.github.io/synapse/latest/

---

**Status** : ✅ **Prêt pour déploiement Étape 1** 🚀
