#!/bin/bash
# Vérifie que Gerbera répond (description UPnP, la première page que lit VLC),
# puis pousse le résultat au moniteur push d'Uptime Kuma. Le jeton de push est
# un secret : il vit dans push-url.conf, à côté de ce script, ignoré par Git
# (comme .env). L'adresse du serveur vient de ../.env (HOST_BIND_IP), jamais
# écrite dans le dépôt.
# Aucun appel à docker : le compte de service n'est pas dans le groupe docker.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PUSH_URL_FILE="${SCRIPT_DIR}/push-url.conf"
ENV_FILE="${SCRIPT_DIR}/../.env"
GERBERA_PORT="49494"   # même valeur que --port dans ../docker-compose.yml

if [[ ! -f "$PUSH_URL_FILE" ]]; then
  echo "Fichier ${PUSH_URL_FILE} introuvable — voir push-url.conf.example" >&2
  exit 1
fi
if [[ ! -f "$ENV_FILE" ]]; then
  echo "Fichier ${ENV_FILE} introuvable — voir ../env.example" >&2
  exit 1
fi

HOST_BIND_IP="$({ grep -E '^HOST_BIND_IP=' "$ENV_FILE" || true; } | head -n1 | cut -d= -f2- | tr -d '"'"'"' ')"
if [[ ! "$HOST_BIND_IP" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "HOST_BIND_IP absent ou invalide dans ${ENV_FILE}" >&2
  exit 1
fi

PUSH_BASE_URL="$(cat "$PUSH_URL_FILE")"

# Réponse HTTP 200 et appareil annoncé comme serveur de médias UPnP. Le temps de
# réponse (ms) alimente le graphique de latence d'Uptime Kuma.
if OUT="$(curl -fsS --max-time 5 -w '\n%{time_total}' \
        "http://${HOST_BIND_IP}:${GERBERA_PORT}/description.xml" 2>/dev/null)" \
   && grep -q 'urn:schemas-upnp-org:device:MediaServer' <<<"$OUT"; then
  MS="$(tail -n1 <<<"$OUT" | awk '{printf "%d", $1 * 1000}')"
  curl -fsS --max-time 5 "${PUSH_BASE_URL}?status=up&msg=OK&ping=${MS}" >/dev/null
fi
# Volontairement rien en cas d'échec : un push explicite "status=down"
# contourne le système de tentatives d'Uptime Kuma pour les moniteurs push
# (comportement documenté du projet, déjà constaté pour Pi-hole). Ne rien
# envoyer laisse le moniteur passer en "Pending" puis "Down" selon ses propres
# réglages (tentatives, intervalle), qui absorbent les ratés ponctuels.
