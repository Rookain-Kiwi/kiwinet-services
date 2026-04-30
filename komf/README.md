# komf — Komga Metadata Fetcher

Service de récupération automatique de métadonnées pour Komga. Interne uniquement — pas d'exposition publique.

> Contexte global : [kiwinet-docs](https://github.com/Rookain-Kiwi/kiwinet-docs)

---

## Stack

| Container | Image        | Port interne |
|-----------|--------------|--------------|
| `komf`    | `sndxr/komf:latest` | 8085 (interne, non exposé) |

---

## Configuration

| Paramètre | Valeur |
|---|---|
| Architecture | ARM AArch64 |
| Connexion Komga | `http://komga:25600` (réseau Docker `proxy`) |
| Authentification | Login/password Komga (l'API key ne fonctionne pas pour le SSE) |
| Périmètre | Toutes les bibliothèques (voir note libraryFilter) |
| Mode mise à jour | API + ComicInfo.xml (CBZ) / API uniquement (PDF) |

---

## Structure

```
komf/
├── docker-compose.yml
├── config/
│   ├── application.yml           # Configuration Komf (non versionné, contient credentials)
│   └── application.yml.template  # Template versionné avec placeholders
└── .env                          # Fichier vide requis — docker compose up échoue sans lui
```

---

## Credentials Komga

Les credentials sont renseignés directement dans `config/application.yml` sur la VM :

```yaml
komgaUser: "loic.kergoat@kiwinet.me"
komgaPassword: "<mot_de_passe>"
```

L'API key Komga **ne fonctionne pas** pour l'authentification SSE — utiliser login/password uniquement.

---

## Sources de métadonnées

| Source | Priorité | Statut |
|---|---|---|
| MangaUpdates | 10 | ✅ Actif |
| AniList | 20 | ✅ Actif |
| MangaDex | 30 | ✅ Actif (couvertures : fr, en, ja) |
| MAL | 40 | ❌ Désactivé |
| ComicVine | 15 | ⏸ Désactivé volontairement |

### ComicVine

Clé API configurée sous `metadataProviders.comicVineApiKey` (niveau racine — obligatoire) :

```yaml
metadataProviders:
  comicVineApiKey: "<clé>"   # niveau racine, PAS sous defaultProviders.comicVine
  defaultProviders:
    comicVine:
      priority: 15
      enabled: false  # désactivé : BedethequeKomga couvre mieux les BD franco-belges
```

---

## Bibliothèques Komga

| Bibliothèque | ID Komga | Couvert par Komf |
|---|---|---|
| Mangas | `0Q7PT6ZFTFX05` | ✅ Oui (event listener, toutes sources manga) |
| Bandes Dessinées | `0Q7PKFTK2FT23` | ❌ Non (BedethequeKomga ponctuel) |

### Note : libraryFilter

Le `libraryFilter` est intentionnellement commenté dans `application.yml`. Avec un filtre actif (même ID valide), Komf ne traite rien — cause inconnue, comportement observé et non documenté upstream. Sans filtre, les BD franco-belges ne matchent sur aucune source manga : pas de risque de pollution.

---

## Comportement event listener

Komf écoute le flux SSE Komga et traite les séries **après la fin complète du scan**, pas pendant. Les métadonnées n'apparaissent donc pas en temps réel.

### Déclenchement manuel

La seule méthode fiable pour forcer un retraitement est de supprimer puis recréer la bibliothèque dans Komga (nouveaux IDs générés = Komf considère tout comme nouveau).

---

## Bilan des matchs — collection manga Kiwinet

| Statut | Exemples |
|---|---|
| ✅ Identifiés correctement | Dragon Ball, Bleach, Naruto, Acony, Franken Fran, … |
| ❌ Correction manuelle requise | G de Keiichi Koike (faux match Yamada Hitotsuki), Heaven's Door de Keiichi Koike (faux match Watanabe Naomi), Portal 2 Lab Rat (non référencé) |

Les séries corrigées manuellement doivent être verrouillées dans Komga (cadenas) pour empêcher Komf d'écraser les métadonnées.

---

## BD franco-belge : BedethequeKomga

Les métadonnées des BD franco-belges sont gérées séparément via le script **BedethequeKomga** :

```
https://github.com/Inervo/BedethequeKomga
```

Script Python à lancer ponctuellement après ajout de nouvelles BD. Chemin sur la VM : `/opt/kiwinet-services/bedetheque-komga/`.

---

## Déploiement

```bash
cd /opt/kiwinet-services/komf

docker compose up -d
docker compose logs -f

# Mise à jour
docker compose pull && docker compose up -d --force-recreate
```

---

## Réseau

Komf communique avec Komga uniquement via le réseau Docker interne `proxy`. Aucun port n'est exposé publiquement. L'interface web est accessible depuis la VM uniquement (`http://172.18.0.x:8085` — vérifier l'IP avec `docker inspect komf | grep IPAddress`).

### Extension Firefox Komf

L'extension est installée sur la VM mais **non fonctionnelle** en raison d'une erreur CORS. Utiliser l'interface web directement.
