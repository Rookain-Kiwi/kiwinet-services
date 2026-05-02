# calibre-web — Serveur de bibliothèque Ebooks

Serveur de bibliothèque numérique dockerisé. Accessible via `calibre.kiwinet.me`.

> Contexte global : [kiwinet-docs](https://github.com/Rookain-Kiwi/kiwinet-docs)

---

## Stack

| Container      | Image                                      | Port interne |
|----------------|--------------------------------------------|--------------|
| `calibre-web`  | `lscr.io/linuxserver/calibre-web`          | 8083         |

---

## Configuration

| Paramètre        | Valeur                                                        |
|------------------|---------------------------------------------------------------|
| Architecture     | ARM AArch64                                                   |
| Base de données  | SQLite (`app.db`) — bind mount local `./config`               |
| Bibliothèque     | `./books` → `/books` (bind mount local VM)                    |
| Conversion       | Mod `universal-calibre` (EPUB, MOBI, PDF)                     |

---

## Structure

```
calibre/
├── docker-compose.yml
├── config/               # Base SQLite + configuration (gitignored)
└── books/                # Bibliothèque ebooks (gitignored)
```

---

## Pourquoi le stockage est local (hors NAS)

Le NAS Freebox est monté via CIFS (SMB). Ce protocole présente deux incompatibilités bloquantes avec Calibre-Web :

1. **Locking SQLite** — le `metadata.db` Calibre nécessite un locking exclusif incompatible avec SMB
2. **`rename()` atomique** — l'import via l'interface tente un rename cross-device qui échoue sur CIFS, générant des doublons de dossiers non récupérables proprement

**Architecture retenue : stockage intégralement local sur la VM.**

Les ebooks ne représentent que quelques Go — le stockage local est parfaitement adapté. L'alimentation se fait exclusivement via l'interface web Calibre-Web.

---

## Initialisation (premier déploiement)

Calibre-Web ne crée pas le `metadata.db` automatiquement. Le mod `universal-calibre` étant nécessaire pour `calibredb`, l'initialisation se fait via `docker compose run` :

```bash
cd /opt/kiwinet-services/calibre

# 1. Créer le répertoire books avec les bonnes permissions
mkdir -p books
sudo chown -R 1000:1000 books

# 2. Initialiser le metadata.db via le conteneur
docker compose run --rm calibre-web sh -c "calibredb add --empty --library-path /books"

# 3. Démarrer le service
docker compose up -d
```

> ⚠️ Le `docker compose run` télécharge le mod `universal-calibre` (~200 MB) à chaque exécution — prévoir 3-5 minutes.

Puis dans l'interface admin au premier login (`admin` / `admin123`) :

1. **Location of Calibre Database** : `/books`
2. **Separate Book Files from Library** : décoché
3. Changer le mot de passe admin immédiatement
4. Activer **Allow Upload** : *Admin* → *Basic Configuration* → **Allow Uploading**
5. Activer **OPDS** : *Admin* → *Basic Configuration* → **Enable OPDS catalog**

---

## Déploiement

```bash
cd /opt/kiwinet-services/calibre

docker compose up -d
docker compose logs -f

# Mise à jour
docker compose pull && docker compose up -d --force-recreate
```

> ⚠️ Ne jamais supprimer `./config/` ni `./books/` — contiennent la base SQLite, les comptes utilisateurs et tous les ebooks.

---

## Import de livres

L'upload se fait via **l'interface web** uniquement — Calibre-Web organise automatiquement l'arborescence `Auteur/Titre/` dans `./books`.

Aucune manipulation manuelle de fichiers n'est nécessaire ni recommandée.

---

## Collection

| Volume conteneur | Droits           | Contenu               |
|------------------|------------------|-----------------------|
| `/books`         | Lecture/écriture | EPUB, PDF, MOBI       |

---

## OPDS

URL du catalogue OPDS :

```
https://calibre.kiwinet.me/opds
```

---

## Clients

| Client        | Plateforme | Connexion                                        |
|---------------|------------|--------------------------------------------------|
| Interface web | Tous       | `https://calibre.kiwinet.me`                     |
| KOReader      | Android    | OPDS : `https://calibre.kiwinet.me/opds`         |
| Kobo          | Liseuse    | Plugin natif Calibre-Web (sync WiFi)             |

### Configuration KOReader (Android)

1. File Browser → menu haut → **loupe 🔍** → **OPDS Catalog**
2. **+** → renseigner nom, URL, login, mot de passe
3. Au **premier téléchargement**, KOReader demande le répertoire de destination — choisir `/emulated/0/Books`

> ⚠️ Le répertoire de téléchargement est fixé au premier téléchargement et difficile à modifier ensuite sur Android. Bien choisir dès le départ. En cas de mauvais répertoire, vider les données de l'app (Paramètres Android → Applications → KOReader → Vider les données) puis reconfigurer.

---

## Réseau

Calibre-Web n'expose aucun port directement. Tout le trafic transite par Traefik (`proxy` network, external).