# minecraft — Serveur Minecraft Java Edition

Serveur Minecraft privé, dockerisé avec `itzg/minecraft-server`.  
Accessible via `minecraft.kiwinet.me:25565` — TCP brut routé par Traefik en passthrough.

---

## Stack

| Container   | Image                      | Rôle                  |
|-------------|----------------------------|-----------------------|
| `minecraft` | `itzg/minecraft-server`    | Serveur Java Edition  |

---

## Configuration

| Paramètre         | Valeur                              |
|-------------------|-------------------------------------|
| Type              | VANILLA (PaperMC dès support 26.1)  |
| Version           | 26.1                                |
| RAM allouée       | 4 Go                                |
| Joueurs max       | 6                                   |
| Difficulté        | Normal / Survie                     |
| Whitelist         | Activée                             |
| RCON              | Activé (port 25575, interne)        |
| Map               | `kiwinet`                           |

---

## Structure

```
minecraft/
├── docker-compose.yml
└── .env                ← RCON_PASSWORD (gitignored)
```

Le volume `minecraft-data` (données serveur, map, whitelist) est géré en `external: true` — il persiste entre les recreations du container.

---

## Déploiement

```bash
cd /opt/kiwinet-infra/minecraft

# Démarrage
docker compose up -d

# Logs en temps réel
docker compose logs -f

# Mise à jour image (redémarre le serveur)
docker compose pull && docker compose up -d --force-recreate
```

---

## RCON — accès console

RCON permet d'envoyer des commandes au serveur sans entrer dans le container :

```bash
# Depuis la VM
docker exec -i minecraft rcon-cli --password <RCON_PASSWORD>

# Exemples de commandes
> whitelist add <pseudo>
> whitelist remove <pseudo>
> whitelist list
> op <pseudo>
> say Redémarrage dans 5 minutes
```

---

## Routing réseau

Traefik écoute sur le port `25565` (entrypoint `minecraft` défini dans `traefik/traefik.yml`) et forward le TCP brut vers le container via `traefik/dynamic.yml` :

```
Client Minecraft → minecraft.kiwinet.me:25565 → Traefik TCP passthrough → container minecraft:25565
```

Le container n'expose pas de port directement — tout passe par Traefik.

---

## Variables d'environnement

| Variable        | Description                              |
|-----------------|------------------------------------------|
| `RCON_PASSWORD` | Mot de passe RCON (défini dans `.env`)   |

Créer le `.env` à partir du template :

```bash
cat > .env << 'EOF'
RCON_PASSWORD=<mot_de_passe>
EOF
```
