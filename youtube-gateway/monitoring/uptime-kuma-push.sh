#!/bin/bash
# Sonde de youtube-gateway pour Uptime Kuma (moniteur push) : /healthz repond, donc le
# processus et le port sont vivants. Le temps de reponse (ms) alimente le graphique de
# latence de Kuma.
# L'adresse de push est un secret : elle vit dans push-url.conf, a cote de ce script,
# ignore par Git (comme .env). Aucun appel a docker, aucun root.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PUSH_URL_FILE="${SCRIPT_DIR}/push-url.conf"
GATEWAY_URL="${GATEWAY_URL:-http://127.0.0.1:8100}"   # meme port que ../docker-compose.yml

if [[ ! -f "$PUSH_URL_FILE" ]]; then
  echo "Fichier ${PUSH_URL_FILE} introuvable - voir push-url.conf.example" >&2
  exit 1
fi

# Adresse de push du moniteur, sans les parametres qu'un copier-coller depuis Kuma ajoute.
PUSH_BASE_URL="$({ grep -E '^SERVICE_URL=' "$PUSH_URL_FILE" || true; } | head -n1 | cut -d= -f2- | tr -d "\"' ")"
PUSH_BASE_URL="${PUSH_BASE_URL%%\?*}"
if [[ ! "$PUSH_BASE_URL" =~ ^https://[^/]+/api/push/[A-Za-z0-9_-]+$ ]]; then
  echo "SERVICE_URL absent ou invalide dans ${PUSH_URL_FILE}" >&2
  exit 1
fi

now_ms() { date +%s%3N; }
T0="$(now_ms)"
if curl -fsS --max-time 5 "${GATEWAY_URL}/healthz" 2>/dev/null | grep -q '^ok$'; then
  curl -fsS --max-time 5 "${PUSH_BASE_URL}?status=up&msg=OK&ping=$(( $(now_ms) - T0 ))" >/dev/null
fi
# Volontairement rien en cas d'echec : un push explicite "status=down" contourne le
# systeme de tentatives d'Uptime Kuma pour les moniteurs push (comportement documente du
# projet, deja constate pour Pi-hole). Ne rien envoyer laisse le moniteur passer en
# "Pending" puis "Down" selon ses propres reglages (tentatives, intervalle).