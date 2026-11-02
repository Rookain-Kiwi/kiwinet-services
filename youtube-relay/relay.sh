#!/bin/sh
# Relais YouTube : live YouTube -> MP3 -> Icecast, avec reconnexion automatique.
set -u

: "${STREAM_URL:?STREAM_URL manquant}"
: "${MOUNT:?MOUNT manquant}"
ICECAST_HOST="${ICECAST_HOST:-icecast}"
ICECAST_PORT="${ICECAST_PORT:-8000}"
BITRATE="${BITRATE:-128k}"
PASS_FILE="${PASS_FILE:-/run/secrets/youtube_relay_source_password}"

[ -r "$PASS_FILE" ] || { echo "secret illisible : $PASS_FILE" >&2; exit 1; }
PASS=$(cat "$PASS_FILE")
[ -n "$PASS" ] || { echo "secret vide" >&2; exit 1; }

child=""
trap 'echo "arret demande"; [ -n "$child" ] && kill "$child" 2>/dev/null; exit 0' TERM INT

# Lance en arriere-plan pour que le signal d'arret soit traite tout de suite.
run() { "$@" & child=$!; wait "$child"; status=$?; child=""; return "$status"; }

delay=10
backoff() {
  echo "nouvel essai dans ${delay}s"
  run sleep "$delay"
  delay=$((delay * 2)); [ "$delay" -gt 300 ] && delay=300
}

while true; do
  echo "extraction de l'adresse du flux"
  AUDIO_URL=$(yt-dlp --ignore-config --no-update --no-cache-dir --no-playlist \
    -g -f bestaudio "$STREAM_URL" | head -n 1)
  if [ -z "$AUDIO_URL" ]; then
    echo "extraction echouee"
    backoff
    continue
  fi
  echo "diffusion vers /${MOUNT}"
  start=$(date +%s)
  run ffmpeg -nostdin -hide_banner -loglevel warning -rw_timeout 15000000 \
    -i "$AUDIO_URL" -vn -c:a libmp3lame -b:a "$BITRATE" \
    -content_type audio/mpeg -f mp3 -password "$PASS" \
    "icecast://source@${ICECAST_HOST}:${ICECAST_PORT}/${MOUNT}"
  [ $(( $(date +%s) - start )) -ge 60 ] && delay=10
  echo "flux interrompu"
  backoff
done