# RetroArch — émulation rétro via navigateur

Frontend d'émulation multi-systèmes accessible depuis n'importe quel navigateur,
sans installation côté client. Le rendu graphique et audio est entièrement géré
côté serveur via KasmVNC, puis streamé en HTTPS vers le navigateur.

> Contexte global du projet : [kiwinet-docs](https://github.com/Rookain-Kiwi/kiwinet-docs)

---

## Accès

| Interface | URL | Authentification |
|---|---|---|
| Web (KasmVNC) | `https://retroarch.kiwinet.me` | Mot de passe KasmVNC (voir `.env`) |

---

## Architecture

```
Navigateur
    │ HTTPS (Traefik + Let's Encrypt)
    ▼
Traefik (VM Freebox)
    │ HTTPS interne (certificat auto-signé, InsecureSkipVerify)
    ▼
RetroArch container (port 3000 — KasmVNC)
    │
    ├── Cores Libretro (embarqués dans l'image)
    ├── ROMs      → ./roms/{amstrad,oric,amiga}/
    ├── BIOS      → ./config/retroarch/system/
    └── Saves     → ./config/retroarch/saves/
```

Le container utilise LLVMPipe (rendu CPU logiciel) — suffisant pour les systèmes
8 et 16 bits ciblés. Aucun GPU requis.

---

## Prérequis

- Réseau Docker `proxy` existant
- Traefik opérationnel avec le resolver `letsencrypt`
- ROMs déposées dans `./roms/` (non versionnées — voir section ci-dessous)
- BIOS Amiga déposé dans `./config/retroarch/system/` (voir section BIOS)

---

## Structure des fichiers

```
retroarch/
├── docker-compose.yml
├── config/                     # Données persistantes RetroArch (gitignored)
│   └── retroarch/
│       ├── retroarch.cfg       # Configuration principale
│       ├── system/             # BIOS — déposer ici
│       └── saves/              # Sauvegardes
└── roms/                       # ROMs par plateforme (gitignored)
    ├── amstrad/                # Amstrad CPC — .dsk, .cdt, .cpr
    ├── oric/                   # Oric Atmos — .tap, .dsk
    └── amiga/                  # Amiga — .adf, .lha, .hdf
```

---

## Cores utilisés

| Système | Core Libretro | Formats supportés | BIOS requis |
|---|---|---|---|
| Amstrad CPC | `cap32` (Caprice32) | `.dsk`, `.cdt`, `.cpr`, `.m3u` | Non |
| Oric Atmos | *(voir note)* | `.tap`, `.dsk` | Non |
| Amiga 500 / 1200 | `puae` (UAE4ARM) | `.adf`, `.lha`, `.hdf`, `.m3u` | **Oui** |

### Note — Oric Atmos

Le support RetroArch de l'Oric Atmos est limité : aucun core Libretro dédié
n'est maintenu activement. L'image LinuxServer intègre le core `fuse`
(émulateur ZX Spectrum principalement) qui peut lancer certaines ROMs Oric,
mais avec des résultats variables.

**Alternative recommandée** : `oricutron` (émulateur natif Oric, open source).
Un déploiement dédié via container custom est envisageable en Phase suivante.
Pour l'instant, tenter via le core `fuse` — les résultats sur `.tap` sont corrects
pour la plupart des titres de la bibliothèque commerciale de l'époque.

---

## BIOS Amiga (obligatoire pour PUAE)

Le core PUAE nécessite un Kickstart ROM original. Sans lui, le core se lance
mais refuse de booter tout support.

Fichiers à déposer dans `./config/retroarch/system/` :

| Fichier | Système | MD5 de référence |
|---|---|---|
| `kick13.rom` | Amiga 500 (Kickstart 1.3) | `891e9a547772fe0c6c19b610baf8bc4e` |
| `kick20.rom` | Amiga 500+ (Kickstart 2.0) | `c3e114a89d7fd9e6e34de24ee9e7edf6` |
| `kick31.rom` | Amiga 1200 (Kickstart 3.1) | `6079d289e994f1addc72d1ecd23af48a` |

Vérifier l'intégrité après dépôt :
```bash
md5sum ./config/retroarch/system/kick*.rom
```

---

## Déploiement initial

```bash
# 1. Créer la structure de répertoires (les volumes doivent exister avant le démarrage)
mkdir -p config/retroarch/{system,saves,states}
mkdir -p roms/{amstrad,oric,amiga}

# 2. Déposer les BIOS Amiga dans config/retroarch/system/ (hors versioning)

# 3. Démarrer le container
docker compose up -d

# 4. Vérifier les logs
docker logs retroarch -f
```

---

## Alimenter les ROMs

Les ROMs sont montées depuis `./roms/` sur la VM — elles ne transitent pas par
le NAS Freebox (incompatibilité CIFS/LLVMPipe non testée, stockage local préféré).

```bash
# Depuis la machine locale, copier via SCP
scp ma_rom.dsk rookain@kiwinet-vm:/opt/kiwinet-services/retroarch/roms/amstrad/

# Ou via rsync pour un lot
rsync -av roms/ rookain@kiwinet-vm:/opt/kiwinet-services/retroarch/roms/
```

RetroArch détecte automatiquement les ROMs ajoutées via le scanner de la playlist.

---

## Authentification KasmVNC

L'interface web est protégée par un mot de passe KasmVNC. Il est défini via
les variables d'environnement de l'image LinuxServer.

Créer un fichier `.env` dans le répertoire `retroarch/` (non versionné) :

```env
# retroarch/.env
CUSTOM_USER=kiwi
PASSWORD=<mot_de_passe_fort>
```

Puis référencer dans `docker-compose.yml` :
```yaml
env_file:
  - .env
```

> Sans ces variables, le mot de passe par défaut de KasmVNC s'applique.
> À sécuriser impérativement avant exposition publique.

---

## Points critiques

**HTTPS obligatoire pour KasmVNC**
KasmVNC requiert HTTPS pour les fonctionnalités audio et vidéo (WebCodecs).
Traefik assure le TLS public. Le container expose en HTTPS interne avec un
certificat auto-signé — `InsecureSkipVerify: true` est défini dans les labels
Traefik pour contourner la vérification interne.

**`shm_size: 1gb`**
La mémoire partagée est nécessaire pour le rendu KasmVNC. Ne pas réduire
en dessous de 512 Mo sous peine d'instabilité graphique.

**Manette / Gamepad**
L'interface KasmVNC supporte les gamepads via l'API Web Gamepad (navigateurs
modernes). Brancher la manette avant d'ouvrir l'interface. RetroArch la
détecte automatiquement via l'auto-configuration Libretro.

---

## Estimation RAM

| Composant | RAM estimée |
|---|---|
| RetroArch (idle, LLVMPipe) | ~300 Mo |
| RetroArch (en jeu, Amiga) | ~500 Mo |

---

## Références

- [LinuxServer.io — docker-retroarch](https://docs.linuxserver.io/images/docker-retroarch/)
- [Libretro — core Caprice32 (cap32)](https://docs.libretro.com/library/caprice32/)
- [Libretro — core PUAE (Amiga)](https://docs.libretro.com/library/puae/)
- [GitHub — linuxserver/docker-retroarch](https://github.com/linuxserver/docker-retroarch)
