# minecraft — Serveur Minecraft Java Edition

Serveur privé dockerisé. Accessible via `minecraft.kiwinet.me:25565`.

> Contexte global : [kiwinet-docs](https://github.com/Rookain-Kiwi/kiwinet-docs)

---

## Stack

| Container   | Image                           |
|-------------|---------------------------------|
| `minecraft` | `itzg/minecraft-server` (ARM64) |

---

## Configuration

| Paramètre   | Valeur                             |
|-------------|------------------------------------|
| Type        | VANILLA (PaperMC dès support 26.1) |
| Version     | 26.1                               |
| RAM allouée | 4 Go                               |
| Joueurs max | 6                                  |
| Difficulté  | Normal / Survie                    |
| Whitelist   | Activée                            |
| RCON        | Activé (port 25575, interne)       |

---

## Structure

```
minecraft/
├── docker-compose.yml
└── .env                # RCON_PASSWORD (gitignored)
```

Le volume `minecraft-data` est déclaré `external: true` — il persiste entre les recreations.

---

## Fichier `.env` à créer

```bash
cat > .env << 'EOF'
RCON_PASSWORD=<mot_de_passe>
EOF
```

---

## Variante VPS : mot de passe RCON en secret

Le compose du VPS (`docker-compose.vps.yml`) ne lit plus `RCON_PASSWORD` dans le `.env` : le mot de passe vient d'un secret Docker, fichier créé à la main sur le VPS et absent du dépôt.

- Fichier : `/etc/kiwinet/secrets/minecraft_rcon_password`, propriétaire UID 1000, mode 400.
- Le propriétaire doit être l'UID 1000 : l'image démarre sous cet utilisateur, et un fichier réservé à root fait boucler le conteneur (`Permission denied` au démarrage).
- Raison : une variable d'environnement se lit avec `docker inspect`, donc par tout client du socket Docker.
- Le mot de passe reste écrit dans `server.properties` du volume de données (Minecraft en a besoin).

Console RCON sur le VPS, avec le secret passé le temps d'un appel :

```bash
docker exec minecraft sh -c 'RCON_PASSWORD="$(cat /run/secrets/minecraft_rcon_password)" rcon-cli list'
```

L'option `rcon-cli --config /data/.rcon-cli.yaml` échoue avec le mot de passe actuel (constaté). Cause probable, non vérifiée : le mot de passe contient un antislash, que le fichier YAML généré par l'image n'échappe pas.

---

## Déploiement

```bash
cd /opt/kiwinet-services/minecraft

docker compose up -d
docker compose logs -f

# Mise à jour
docker compose pull && docker compose up -d --force-recreate
```

---

## RCON — console à distance

```bash
docker exec -i minecraft rcon-cli --password <RCON_PASSWORD>

# Commandes utiles
> whitelist add <pseudo>
> whitelist remove <pseudo>
> whitelist list
> op <pseudo>
> say Message serveur
```

---

## Routing réseau

```
Client → minecraft.kiwinet.me:25565 → Traefik TCP passthrough → container:25565
```

Le port 25565 n'est pas exposé directement — tout passe par le TCP passthrough Traefik.
