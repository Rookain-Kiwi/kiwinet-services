# komga — Serveur de BD, Mangas & Comics

Serveur de bibliothèque image dockerisé. Accessible via `komga.kiwinet.me`.

> Contexte global : [kiwinet-docs](https://github.com/Rookain-Kiwi/kiwinet-docs)

---

## Stack

| Container | Image           | Port interne |
|-----------|-----------------|--------------|
| `komga`   | `gotson/komga`  | 8080         |

---

## Configuration

| Paramètre      | Valeur                                        |
|----------------|-----------------------------------------------|
| Architecture   | ARM AArch64                                   |
| Base de données| H2 embarquée (volume `komga-config`)          |
| Données config | Volume nommé `komga-config`                   |
| Collection     | `/mnt/Kodi/Lecture` (bind mount CIFS, `:ro`)  |

---

## Structure

```
komga/
├── docker-compose.yml
└── .env                # Credentials admin (gitignored)
```

---

## Fichier `.env` à créer

```bash
cat > .env << 'EOF'
KOMGA_ADMIN_EMAIL=admin@kiwinet.me
KOMGA_ADMIN_PASSWORD=<mot_de_passe_fort>
EOF
```

Ces variables ne s'appliquent qu'au **premier démarrage**. Modifier le `.env` après initialisation n'a aucun effet — changer le mot de passe via l'interface web.

---

## Déploiement

```bash
cd /opt/kiwinet-infra/komga

docker compose up -d
docker compose logs -f

# Mise à jour
docker compose pull && docker compose up -d --force-recreate
```

---

## Collection

La bibliothèque est montée depuis le NAS Freebox via CIFS (`/etc/fstab`), en **lecture seule**. Komga ne modifie jamais les fichiers source.

| Volume conteneur | Droits | Contenu                      |
|------------------|--------|------------------------------|
| `/data`          | `:ro`  | Bandes Dessinées + Mangas    |

### Formats supportés

| Format | Extension |
|--------|-----------|
| Comic Book ZIP | CBZ |
| Comic Book RAR | CBR |
| PDF            | PDF |
| Comic Book 7-Zip | CB7 |

---

## Bibliothèques

Deux bibliothèques à créer dans l'interface admin après le premier démarrage :

| Nom               | Chemin conteneur          |
|-------------------|---------------------------|
| Bandes Dessinées  | `/data/Bandes Dessinées`  |
| Mangas            | `/data/Mangas`            |

---

## Clients

| Client              | Plateforme     | Connexion              |
|---------------------|----------------|------------------------|
| Interface web       | Tous           | `https://komga.kiwinet.me` |
| Mihon (ex-Tachiyomi)| Android        | Extension Komga native |
| Panels              | iOS / iPadOS   | OPDS                   |
| Paperback           | iOS / iPadOS   | OPDS                   |

URL du catalogue OPDS :

```
https://komga.kiwinet.me/opds/v1.2/catalog
```

---

## Réseau

Komga n'expose aucun port directement. Tout le trafic transite par Traefik (`proxy` network, external).
