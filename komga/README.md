# komga — Serveur de BD, Mangas & Comics

Serveur de bibliothèque image dockerisé. Accessible via `komga.kiwinet.me`.

> Contexte global : [kiwinet-docs](https://github.com/Rookain-Kiwi/kiwinet-docs)

---

## Stack

| Container | Image           | Port interne |
|-----------|-----------------|--------------|
| `komga`   | `gotson/komga`  | 25600        |

---

## Configuration

| Paramètre      | Valeur                                        |
|----------------|-----------------------------------------------|
| Architecture   | ARM AArch64                                   |
| Base de données| H2 embarquée (volume `komga-config`)          |
| Données config | Volume nommé `komga-config`                   |
| Collection     | `/mnt/Kodi/Lecture` → `/data` (bind mount CIFS, `:ro`) |

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
KOMGA_ADMIN_EMAIL=loic.kergoat@kiwinet.me
KOMGA_ADMIN_PASSWORD=<mot_de_passe_fort>
EOF
```

Ces variables ne s'appliquent qu'au **premier démarrage**. Modifier le `.env` après initialisation n'a aucun effet — changer le mot de passe via l'interface web.

Un second compte utilisateur (`arthur.kergoat@kiwinet.me`) est créé via l'interface admin après initialisation.

---

## Déploiement

```bash
cd /opt/kiwinet-services/komga

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

### Formats par collection

| Collection | Format actuel | Format cible |
|---|---|---|
| Mangas | CBZ (convertis depuis PDF à 150 DPI) | — |
| Bandes Dessinées | PDF | CBZ à 200 DPI (format album plus grand) |

La conversion PDF→CBZ est réalisée via le script `convert_pdf_to_cbz.sh` (`pdftoppm` + `zip`). Le gain de réactivité à distance est significatif (validé sur BLAME!).

---

## Bibliothèques

| Nom | Chemin conteneur | ID Komga |
|---|---|---|
| Bandes Dessinées | `/data/Bandes Dessinées` | `0Q7PKFTK2FT23` |
| Mangas | `/data/Mangas` | `0Q7PT6ZFTFX05` |

---

## Métadonnées

### Mangas — Komf (automatique)

Komf enrichit automatiquement les métadonnées manga via MangaUpdates, AniList et MangaDex. Le traitement se déclenche **après la fin complète du scan**, pas en temps réel.

Séries à **verrouiller** (cadenas dans Komga) pour empêcher Komf d'écraser les métadonnées corrigées manuellement :

| Série | Motif |
|---|---|
| Sillage | Faux match AniList "Collage" (hentai) |
| G de Keiichi Koike | Faux match Yamada Hitotsuki |
| Heaven's Door de Keiichi Koike | Faux match Watanabe Naomi |
| Portal 2 Lab Rat | Non référencé sur aucune source |

### BD franco-belge — BedethequeKomga (ponctuel)

Script Python à lancer manuellement après ajout de nouvelles BD. Chemin sur la VM : `/opt/kiwinet-services/bedetheque-komga/`. Ne pas lancer sur toute la bibliothèque d'un coup — respecter la bande passante de Bédéthèque.

---

## Clients

| Client | Plateforme | Connexion |
|---|---|---|
| Interface web | Tous | `https://komga.kiwinet.me` |
| Komelia (client officiel) | Android (F-Droid) | `https://komga.kiwinet.me` |

URL du catalogue OPDS :

```
https://komga.kiwinet.me/opds/v1.2/catalog
```

---

## API Komga

L'authentification se fait en **Basic Auth**. En cas de caractères spéciaux dans le mot de passe (ex. `!`), `curl` échoue en 401 à cause de l'interprétation bash. Utiliser Python à la place :

```python
import urllib.request, base64

url = "https://komga.kiwinet.me/api/v1/..."
req = urllib.request.Request(url)
credentials = base64.b64encode(b"loic.kergoat@kiwinet.me:<mot_de_passe>").decode()
req.add_header("Authorization", f"Basic {credentials}")
response = urllib.request.urlopen(req)
```

---

## Réseau

Komga n'expose aucun port directement. Tout le trafic transite par Traefik (`proxy` network, external).
