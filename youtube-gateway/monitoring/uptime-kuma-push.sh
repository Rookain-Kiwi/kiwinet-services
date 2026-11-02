#!/bin/bash
# Sondes de youtube-gateway pour Uptime Kuma (moniteurs push).
# Usage : uptime-kuma-push.sh service | flux
#   service : /healthz repond (processus et port vivants).
#   flux    : vraie ecoute d'une radio temoin : extraction par yt-dlp, Deno, ffmpeg et
#             live vivant. Reussie si au moins MIN_BYTES d'audio arrivent a temps ; le
#             temps mis a les recevoir alimente le graphique de latence de Kuma.
# Les adresses de push sont des secrets : elles vivent dans push-url.conf, a cote de ce
# script, ignore par Git (comme .env). Aucun appel a docker, aucun root.
set -euo pipefail

MODE="${1:-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PUSH_URL_FILE="${SCRIPT_DIR}/push-url.conf"
GATEWAY_URL="${GATEWAY_URL:-http://127.0.0.1:8100}"   # meme port que ../docker-compose.yml
WITNESS_RADIO="${WITNESS_RADIO:-lofi}"                # radio temoin : doit etre dans ../config/radios.txt
MIN_BYTES=100000   # environ 6 s d'audio AAC : un vrai flux, pas une page d'erreur

case "$MODE" in
  service) KEY="SERVICE_URL" ;;
  flux)    KEY="FLUX_URL" ;;
  *) echo "Usage : $0 service|flux" >&2; exit 2 ;;
esac

if [[ ! -f "$PUSH_URL_FILE" ]]; then
  echo "Fichier ${PUSH_URL_FILE} introuvable - voir push-url.conf.example" >&2
  exit 1
fi

# Adresse de push du moniteur, sans les parametres qu'un copier-coller depuis Kuma ajoute.
PUSH_BASE_URL="$({ grep -E "^${KEY}=" "$PUSH_URL_FILE" || true; } | head -n1 | cut -d= -f2- | tr -d "\"' ")"
PUSH_BASE_URL="${PUSH_BASE_URL%%\?*}"
if [[ ! "$PUSH_BASE_URL" =~ ^https://[^/]+/api/push/[A-Za-z0-9_-]+$ ]]; then
  echo "${KEY} absent ou invalide dans ${PUSH_URL_FILE}" >&2
  exit 1
fi

now_ms() { date +%s%3N; }
push_up() { curl -fsS --max-time 5 "${PUSH_BASE_URL}?status=up&msg=OK&ping=${1}" >/dev/null; }

case "$MODE" in
  service)
    T0="$(now_ms)"
    if curl -fsS --max-time 5 "${GATEWAY_URL}/healthz" 2>/dev/null | grep -q '^ok$'; then
      push_up "$(( $(now_ms) - T0 ))"
    fi
    ;;
  flux)
    # Ecoute reelle : le serveur extrait l'adresse du flux et lance ffmpeg. On s'arrete
    # des que MIN_BYTES sont recus (head ferme le tube, curl se deconnecte, la passerelle
    # arrete ffmpeg), sans attendre la fin du delai.
    T0="$(now_ms)"
    BYTES="$(curl -sS --max-time 25 "${GATEWAY_URL}/${WITNESS_RADIO}" 2>/dev/null | head -c "$MIN_BYTES" | wc -c || true)"
    if (( ${BYTES:-0} >= MIN_BYTES )); then
      push_up "$(( $(now_ms) - T0 ))"
    fi
    ;;
esac
# Volontairement rien en cas d'echec : un push explicite "status=down" contourne le
# systeme de tentatives d'Uptime Kuma pour les moniteurs push (comportement documente du
# projet, deja constate pour Pi-hole). Ne rien envoyer laisse le moniteur passer en
# "Pending" puis "Down" selon ses propres reglages (tentatives, intervalle).