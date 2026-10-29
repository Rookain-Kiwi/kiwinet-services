# gerbera — Serveur UPnP (iPad)

Publie les films et les séries en lecture seule pour **VLC** sur un iPad 4 (iOS 10), dans « Réseau local ». Rien n'est copié, rien n'est exposé à Internet, Jellyfin n'est pas touché.

## Stack

| Élément | Valeur |
|---|---|
| Image | `gerbera/gerbera`, épinglée par empreinte (voir le compose) |
| Réseau | `network_mode: host` (découverte SSDP multicast, impossible en bridge) |
| Écoute | une seule adresse (`HOST_BIND_IP`), port fixe 49494/tcp, découverte 1900/udp |
| Médias | `/mnt/Libraries/Movies` et `/mnt/Libraries/TV Shows`, lecture seule |
| Interface web | désactivée (elle contient un navigateur de fichiers du serveur) |
| Transcodage | désactivé |

## Sécurité

Hors de la chaîne `DOCKER-USER` : **ufw est la seule barrière réseau** (même cas que Home Assistant et Music Assistant). UPnP n'authentifie pas : tout appareil que ufw laisse passer lit les dossiers publiés. Le client est donc limité à l'iPad, par son adresse IP (réservation DHCP obligatoire).

L'image donne à son utilisateur un `sudo` sans mot de passe et un script d'entrée qui démarre en root : il est contourné (`entrypoint` du compose), Gerbera tourne en `1000:1000` avec `no-new-privileges` et sans capacité.

## Déploiement

Dans cet ordre, une étape à la fois.

1. Réservation DHCP de l'iPad dans la box.
2. Règle ufw **avant** le premier démarrage (le service écoute dès le lancement) :
   ```bash
   sudo ufw allow proto tcp from <IP_IPAD> to <IP_SERVEUR> port 49494 comment 'Gerbera UPnP depuis iPad'
   ```
   Pas de règle UDP : `/etc/ufw/before.rules` accepte déjà le multicast SSDP (UDP vers l'adresse de découverte, port 1900) pour tous les appareils, donc la découverte passe sans règle ; en ajouter une seulement si le test VLC échoue. Le port 1900 est aussi occupé par Home Assistant (réseau hôte) : surveiller les journaux de Gerbera au premier démarrage.
3. Fichier d'environnement :
   ```bash
   cp env.example .env && chmod 600 .env   # renseigner HOST_BIND_IP
   ```
4. Créer le volume sans démarrer, puis lui donner le bon propriétaire :
   ```bash
   sudo docker compose up --no-start
   sudo chown 1000:1000 "$(sudo docker volume inspect gerbera_gerbera-config -f '{{ .Mountpoint }}')"
   ```
5. Démarrer : `sudo docker compose up -d`.

## Contrôles au premier démarrage

1. Journaux : aucune erreur d'écriture (signet, base) ni de liaison d'adresse.
2. Processus en utilisateur `1000`, pas root : `sudo docker top gerbera -o user,pid,args`.
3. `ss -tulpn` : écoute sur la seule adresse du serveur, en IPv4 **et** en IPv6 (la doc ne précise pas le comportement IPv6).
4. Depuis un appareil non autorisé : contenu inaccessible ; noter ce que la découverte y montre.
5. VLC sur l'iPad : le serveur apparaît, le film de test se lit ; tester le DTS 5.1 et les sous-titres SRT et ASS.

En cas d'échec au démarrage : retirer d'abord `read_only`, puis `cap_drop`.

## Mise à jour

Manuelle. Vérifier l'étiquette et l'empreinte dans le registre (version de plus de 14 jours), modifier le compose, commit, puis sur le serveur :

```bash
git pull
cd gerbera && sudo docker compose up -d --force-recreate
```

## Points d'attention

- Le multicast SSDP est accepté par ufw pour tous les appareils (`before.rules`), et Gerbera annonce sa présence à intervalles réguliers (par défaut 1800 s) : d'autres appareils du réseau, dont Home Assistant, peuvent voir que le service existe sans pouvoir lire les dossiers (le TCP est refusé hors iPad).
- La base SQLite est reconstruite par rescan toutes les heures (mode `timed`) : aucune sauvegarde nécessaire.
- L'iPad tourne sous un iOS sans correctifs de sécurité, jailbreaké : c'est le risque principal du réseau local pour ce service.
- Si le client change d'adresse (réservation modifiée), mettre à jour les règles ufw.
