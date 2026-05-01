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

| Paramètre        | Valeur                                                                      |
|------------------|-----------------------------------------------------------------------------|
| Architecture     | ARM AArch64                                                                 |
| Base de données  | SQLite (`app.db`) — bind mount local `./config` (hors CIFS)                |
| Bibliothèque     | `/mnt/Kodi/Lecture/Livres` → `/books` (bind mount CIFS, lecture/écriture)  |
| Conversion       | Mod `universal-calibre` (EPUB, MOBI, PDF)                                  |

---

## Structure

```
calibre/
├── docker-compose.yml
└── config/               # Base SQLite + configuration (gitignored)
```

---

## Contrainte CIFS / SQLite

Le NAS Freebox est monté via CIFS (SMB). Ce protocole est **incompatible avec le locking exclusif SQLite** utilisé par Calibre pour son `metadata.db`. La base de données ne peut donc pas résider sur le NAS.

**Architecture retenue :**

| Donnée | Emplacement | Raison |
|---|---|---|
| `metadata.db` Calibre | `./config/` (local VM) | Hors CIFS — locking SQLite compatible |
| Fichiers ebooks (EPUB, PDF, MOBI) | `/mnt/Kodi/Lecture/Livres` (CIFS) | Source de vérité sur le NAS |

L'option **"Separate Book Files from Library"** doit être activée dans l'interface admin pour refléter cette séparation.

---

## Initialisation (premier déploiement)

Calibre-Web ne crée pas le `metadata.db` automatiquement. Il faut l'initialiser en local avant le premier démarrage :

```bash
# Créer le metadata.db dans un dossier temporaire local (conteneur arrêté)
calibredb add --empty --library-path /tmp/calibre-init
cp /tmp/calibre-init/metadata.db /opt/kiwinet-services/calibre/config/metadata.db
chown 1000:1000 /opt/kiwinet-services/calibre/config/metadata.db
docker compose up -d
```

Puis dans l'interface admin au premier login (`admin` / `admin123`) :
1. **Location of Calibre Database** : `/config`
2. Cocher **Separate Book Files from Library**
3. **Book files location** : `/books`
4. Changer le mot de passe admin immédiatement

---

## Déploiement

```bash
cd /opt/kiwinet-services/calibre

docker compose up -d
docker compose logs -f

# Mise à jour
docker compose pull && docker compose up -d --force-recreate
```

> ⚠️ Ne jamais supprimer `./config/` — contient la base SQLite et tous les comptes utilisateurs.

---

## Import de livres

L'upload via l'interface web crée automatiquement l'arborescence `Auteur/Titre/` sur le NAS.

**Limitation CIFS connue** : le `rename()` atomique final échoue sur SMB — des dossiers en double (avec suffixe numérique) peuvent apparaître après un import. Ils sont vides et peuvent être supprimés manuellement :

```bash
# Exemple de nettoyage post-import
cd "/mnt/Kodi/Lecture/Livres/Auteur"
rm -rf "Titre (2)" "Titre (3)"   # doublons — les dossiers sans numéro sont les bons
```

**Alternative sans doublon** : déposer les fichiers directement sur le NAS dans la bonne arborescence via SCP, puis déclencher un scan depuis l'interface (*Admin* → *Tasks* → *Scan Library*) :

```bash
scp fichier.epub kiwinet:"/mnt/Kodi/Lecture/Livres/Auteur/Titre/Titre.epub"
```

---

## Collection

| Volume conteneur | Droits           | Contenu               |
|------------------|------------------|-----------------------|
| `/books`         | Lecture/écriture | EPUB, PDF, MOBI       |

---

## OPDS

URL du catalogue OPDS (pour KOReader et autres clients) :

```
https://calibre.kiwinet.me/opds
```

À activer dans l'interface : *Admin* → *Basic Configuration* → **Enable OPDS catalog**.

---

## Clients

| Client        | Plateforme | Connexion                                        |
|---------------|------------|--------------------------------------------------|
| Interface web | Tous       | `https://calibre.kiwinet.me`                     |
| KOReader      | Android    | OPDS : `https://calibre.kiwinet.me/opds`         |
| Kobo          | Liseuse    | Plugin natif Calibre-Web (sync WiFi)             |

---

## Réseau

Calibre-Web n'expose aucun port directement. Tout le trafic transite par Traefik (`proxy` network, external).
