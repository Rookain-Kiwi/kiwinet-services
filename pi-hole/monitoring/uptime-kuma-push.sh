#!/bin/bash
# Teste une vraie résolution DNS via Pi-hole, puis pousse le résultat au
# moniteur push d'Uptime Kuma. Le jeton de push est un secret : il vit dans
# push-url.conf, à côté de ce script, ignoré par Git (comme .env).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PUSH_URL_FILE="${SCRIPT_DIR}/push-url.conf"
PIHOLE_IP="192.168.1.6"
TEST_DOMAIN="google.com"

if [[ ! -f "$PUSH_URL_FILE" ]]; then
  echo "Fichier ${PUSH_URL_FILE} introuvable — voir push-url.conf.example" >&2
  exit 1
fi

PUSH_BASE_URL="$(cat "$PUSH_URL_FILE")"

if ANSWER="$(dig "@${PIHOLE_IP}" "$TEST_DOMAIN" +short +time=2 +tries=2 A 2>/dev/null)" \
   && [[ "$ANSWER" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  curl -fsS --max-time 5 "${PUSH_BASE_URL}?status=up&msg=OK&ping=" >/dev/null
fi
# Volontairement rien en cas d'échec : un push explicite "status=down"
# contourne le système de tentatives d'Uptime Kuma pour les moniteurs push
# (comportement documenté du projet). Ne rien envoyer laisse le moniteur
# passer en "Pending" puis "Down" selon ses propres réglages (tentatives,
# intervalle), qui absorbent les ratés ponctuels au lieu de basculer au
# premier accroc.
