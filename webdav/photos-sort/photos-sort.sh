#!/bin/bash
# photos-sort.sh : range par mois les photos et vidéos déposées à la racine de Photos
# par Round Sync (via le WebDAV), vers Photos/AAAA/AAAA-MM/.
#
# - Mois et année lus dans le NOM du fichier (PXL_AAAAMMJJ_...), en UTC. Toutes les
#   années sont acceptées (4 chiffres) ; seul le mois est contrôlé (01 à 12).
# - Prend tous les fichiers de la racine, quelle que soit leur date, à condition qu'ils
#   aient plus de MIN_AGE_MIN minutes (un envoi en cours n'est pas touché) et un nom Pixel
#   conforme (extensions autorisées). Les autres restent à la racine, en silence.
# - N'écrase JAMAIS. Si la cible existe :
#     identique octet par octet -> la copie à la racine est supprimée (elle est
#                                  redondante : Round Sync la renvoie tant que le fichier
#                                  est sur le téléphone) ;
#     différente                -> rien n'est touché, rien n'est signalé : le fichier reste
#                                  à la racine, à traiter à la main (local et cloud).
# - Aucun nom de fichier n'est passé à un shell. Pas de sudo, pas de chown.
# - Aucun moniteur. Code de sortie 1 seulement en cas de problème technique (disque non
#   monté, dossier non inscriptible, déplacement ou suppression impossible).
# DRY_RUN=1 : simule, ne déplace ni ne supprime rien.
set -uo pipefail

PHOTOS_DIR="${PHOTOS_DIR:-/mnt/Libraries/Photos}"
MOUNT_POINT="${MOUNT_POINT-/mnt/Libraries}"   # vide = pas de contrôle (essais)
MIN_AGE_MIN="${MIN_AGE_MIN:-10}"
DRY_RUN="${DRY_RUN:-0}"

[[ -d "$PHOTOS_DIR" ]] || { echo "photos-sort : $PHOTOS_DIR introuvable" >&2; exit 1; }
if [[ -n "$MOUNT_POINT" ]] && ! mountpoint -q "$MOUNT_POINT"; then
  echo "photos-sort : $MOUNT_POINT n'est pas monté" >&2; exit 1
fi

shopt -s nocasematch
NAME_RE='^PXL_([0-9]{4})([0-9]{2})([0-9]{2})_[0-9]{9}[A-Za-z0-9._-]*\.(jpg|jpeg|png|webp|heic|dng|gif|mp4|mov)$'
moved=0; removed=0; conflict=0; blocked=0; unknown=0

while IFS= read -r -d '' f; do
  name="${f##*/}"
  if [[ ! "$name" =~ $NAME_RE ]]; then
    unknown=$((unknown + 1)); continue
  fi
  y="${BASH_REMATCH[1]}"; m="${BASH_REMATCH[2]}"
  if (( 10#$m < 1 || 10#$m > 12 )); then
    unknown=$((unknown + 1)); continue
  fi
  dir="$PHOTOS_DIR/$y/$y-$m"; dst="$dir/$name"

  if [[ -e "$dst" || -L "$dst" ]]; then
    if [[ -f "$dst" && ! -L "$dst" ]] && cmp -s -- "$f" "$dst"; then
      if [[ "$DRY_RUN" == "1" ]]; then echo "SIMULATION  : doublon identique supprimé : $name"
      elif rm -- "$f"; then echo "DOUBLON     : copie à la racine supprimée (identique) : $name"
      else echo "ÉCHEC       : suppression impossible : $name"; blocked=$((blocked + 1)); continue; fi
      removed=$((removed + 1))
    else
      conflict=$((conflict + 1))
    fi
    continue
  fi

  if [[ "$DRY_RUN" == "1" ]]; then echo "SIMULATION  : $name -> $y/$y-$m/"; moved=$((moved + 1)); continue; fi

  if ! mkdir -p -- "$dir" 2>/dev/null || [[ ! -w "$dir" || ! -x "$dir" ]]; then
    echo "BLOQUÉ      : $name ($y/$y-$m non inscriptible ou non créable)"; blocked=$((blocked + 1)); continue
  fi
  if mv -n -- "$f" "$dst" 2>/dev/null && [[ ! -e "$f" && -f "$dst" ]]; then
    echo "RANGÉ       : $name -> $y/$y-$m/"; moved=$((moved + 1))
  else
    echo "ÉCHEC       : $name (déplacement non confirmé)"; blocked=$((blocked + 1))
  fi
done < <(find "$PHOTOS_DIR" -maxdepth 1 -type f -mmin +"$MIN_AGE_MIN" -print0)

waiting="$(find "$PHOTOS_DIR" -maxdepth 1 -type f -mmin -"$MIN_AGE_MIN" -printf '.' | wc -c)"
echo "RÉSUMÉ : rangés=$moved doublons_supprimés=$removed restes_laissés=$((conflict + unknown)) bloqués=$blocked en_attente=$waiting"
(( blocked == 0 ))
