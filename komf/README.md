# komf — Komga Metadata Fetcher

Service de récupération automatique de métadonnées pour Komga. Interne uniquement — pas d'exposition publique.

> Contexte global : [kiwinet-docs](https://github.com/Rookain-Kiwi/kiwinet-docs)

---

## Stack

| Container | Image        | Port interne |
|-----------|--------------|--------------|
| `komf`    | `sndxr/komf` | 8085 (interne, non exposé) |

---

## Configuration

| Paramètre | Valeur |
|---|---|
| Architecture | ARM AArch64 |
| Connexion Komga | `http://komga:25600` (réseau Docker `proxy`) |
| Authentification | API key Komga |
| Périmètre | Bibliothèque Mangas uniquement |
| Mode mise à jour | API + ComicInfo.xml (CBZ) / API uniquement (PDF) |

---

## Structure

```
komf/
├── docker-compose.yml
└── .env                # API key Komga (gitignored)
```

---

## Fichier `.env` à créer

```bash
cat > .env << 'EOF'
KOMF_KOMGA_API_KEY=<clé_api_komga>
EOF
```

La clé API se génère dans Komga → **Mon Compte → Clés API**.

---

## Sources de métadonnées

| Source | Bibliothèque | Priorité | Statut |
|---|---|---|---|
| MangaUpdates | Mangas | 1 | ✅ Actif |
| AniList | Mangas | 2 | ✅ Actif |
| MangaDex | Mangas | 3 | ✅ Actif |
| ComicVine | BD | — | ⏸ Désactivé (clé API non configurée) |

### Activer ComicVine

1. Générer une clé API sur `https://comicvine.gamespot.com/api/`
2. Ajouter dans `.env` : `KOMF_METADATA_PROVIDERS_COMIC_VINE_API_KEY=<clé>`
3. Passer `KOMF_METADATA_PROVIDERS_DEFAULT_PROVIDERS_COMIC_VINE_ENABLED` à `"true"` dans le `docker-compose.yml`

---

## Bibliothèques Komga

| Bibliothèque | ID Komga | Couvert par Komf |
|---|---|---|
| Mangas | `0Q7MZKV1AFR66` | ✅ Oui (event listener actif) |
| Bandes Dessinées | `0Q7MZDD9YFTCG` | ❌ Non (BedethequeKomga ponctuel) |

---

## BD franco-belge : BedethequeKomga

Les métadonnées des BD franco-belges sont gérées séparément via le script **BedethequeKomga** :

```
https://github.com/Inervo/BedethequeKomga
```

Script Python à lancer ponctuellement après ajout de nouvelles BD. Ne pas lancer sur toute la bibliothèque d'un coup — respecter la bande passante de Bédéthèque.

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

Komf communique avec Komga uniquement via le réseau Docker interne `proxy`. Aucun port n'est exposé publiquement.
