#!/usr/bin/env bash
# Sauvegarde technique récurrente de PostgreSQL (conteneur Docker).
#
# Un jeu de sauvegarde = un dossier daté contenant :
#   - un fichier pg_dump au format personnalisé (-Fc) par base ;
#   - roles.sql : rôles de l'instance, sans mots de passe (--no-role-passwords).
#
# Variables obligatoires, définies par l'unité systemd et jamais dans ce fichier :
#   BACKUP_DIR   dossier de destination, il doit déjà exister (jamais créé ici)
#   MOUNT_POINT  point de montage qui doit être actif, et qui contient BACKUP_DIR
# Variables facultatives :
#   CONTAINER    nom du conteneur PostgreSQL (défaut : postgres)
#   KEEP         nombre de jeux conservés (défaut : 7)
#   WAIT_SECONDS attente maximale que le conteneur soit prêt (défaut : 300), utile
#                quand le timer rattrape une exécution manquée juste après un démarrage
#
# Le script s'exécute en root, lancé par bash (pas de droit d'exécution requis).
# Toute erreur arrête le script avec un code non nul : l'unité systemd passe en échec.
set -Eeuo pipefail
umask 077

: "${BACKUP_DIR:?BACKUP_DIR non défini}"
: "${MOUNT_POINT:?MOUNT_POINT non défini}"
CONTAINER="${CONTAINER:-postgres}"
KEEP="${KEEP:-7}"
WAIT_SECONDS="${WAIT_SECONDS:-300}"

log() { printf '%s\n' "$*"; }
die() { printf 'ERREUR : %s\n' "$*" >&2; exit 1; }

# Exécute un client PostgreSQL dans le conteneur, avec l'utilisateur de l'instance.
in_pg() {
  docker exec -i "$CONTAINER" sh -c \
    'cmd=$1; shift; exec "$cmd" -U "${POSTGRES_USER:-postgres}" "$@"' _ "$@"
}

# --- Contrôles préalables : rien n'est écrit si l'un d'eux échoue ---------------
[[ "$KEEP" =~ ^[1-9][0-9]*$ ]] || die "KEEP doit être un entier strictement positif"
[[ "$WAIT_SECONDS" =~ ^[0-9]+$ ]] || die "WAIT_SECONDS doit être un entier"
mountpoint -q "$MOUNT_POINT" || die "$MOUNT_POINT n'est pas monté"
[[ -d "$BACKUP_DIR" ]] || die "dossier de destination absent : $BACKUP_DIR"
case "$BACKUP_DIR/" in
  "$MOUNT_POINT"/*) ;;
  *) die "la destination n'est pas sous $MOUNT_POINT" ;;
esac

# Attend que le conteneur soit démarré et sain (healthcheck de l'image si défini).
wait_for_postgres() {
  local waited=0 status
  while :; do
    status="$(docker inspect -f \
      '{{if .State.Running}}{{if .State.Health}}{{.State.Health.Status}}{{else}}healthy{{end}}{{else}}stopped{{end}}' \
      "$CONTAINER" 2>/dev/null || echo absent)"
    [[ "$status" == "healthy" ]] && return 0
    ((waited >= WAIT_SECONDS)) && die "conteneur $CONTAINER non prêt après ${WAIT_SECONDS}s (état : $status)"
    sleep 5
    waited=$((waited + 5))
  done
}
wait_for_postgres

exec 9>/run/lock/pg-backup.lock
flock -n 9 || die "une sauvegarde est déjà en cours"

# --- Jeu de travail : invisible tant qu'il n'est pas complet et vérifié ----------
STAMP="$(date +%Y-%m-%d_%H%M%S)"
TMP="$BACKUP_DIR/.en-cours-$STAMP"
FINAL="$BACKUP_DIR/$STAMP"
mkdir -- "$TMP"

# En cas d'échec, seul ce dossier de travail partiel est supprimé, jamais un jeu existant.
cleanup() {
  local rc=$?
  if [[ $rc -ne 0 && -d "$TMP" ]]; then
    rm -rf -- "$TMP"
  fi
}
trap cleanup EXIT

# --- Bases : toutes celles qui acceptent les connexions, hors modèles ------------
mapfile -t DBS < <(in_pg psql -d postgres -Atc \
  "select datname from pg_database where datallowconn and not datistemplate order by 1")
((${#DBS[@]} > 0)) || die "aucune base trouvée"

for db in "${DBS[@]}"; do
  f="$TMP/$db.dump"
  log "dump : $db"
  in_pg pg_dump -Fc -d "$db" > "$f"
  [[ -s "$f" ]] || die "fichier vide pour la base $db"
  # Lecture complète de l'archive (sans base cible, pg_restore écrit le script SQL
  # sur la sortie standard) : détecte une archive tronquée ou corrompue.
  docker exec -i "$CONTAINER" pg_restore < "$f" > /dev/null \
    || die "archive illisible pour la base $db"
  n="$(docker exec -i "$CONTAINER" pg_restore --list < "$f" | grep -vc '^;' || true)"
  ((n > 0)) || die "sommaire de l'archive vide pour la base $db"
done

# --- Rôles, sans les hachages de mots de passe ----------------------------------
log "dump : rôles"
in_pg pg_dumpall --globals-only --no-role-passwords > "$TMP/roles.sql"
grep -q '^CREATE ROLE ' "$TMP/roles.sql" || die "aucun rôle dans roles.sql"

# --- Publication : propriétaire du dossier de destination, puis renommage --------
chown -R "$(stat -c '%u:%g' "$BACKUP_DIR")" "$TMP"
sync -f "$TMP"
mv -T -- "$TMP" "$FINAL"
log "jeu complet : $FINAL ($(du -sh "$FINAL" | cut -f1))"

# --- Purge : seulement après un jeu complet, seulement les plus anciens ----------
# Compte les jeux (pas les jours) : si les sauvegardes s'arrêtent, rien n'est supprimé.
mapfile -t SETS < <(find "$BACKUP_DIR" -mindepth 1 -maxdepth 1 -type d \
  -name '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]_[0-9][0-9][0-9][0-9][0-9][0-9]' | sort)
excess=$((${#SETS[@]} - KEEP))
if ((excess > 0)); then
  for old in "${SETS[@]:0:excess}"; do
    log "purge : $old"
    rm -rf -- "$old"
  done
fi

# Restes d'une exécution interrompue brutalement : signalés, jamais supprimés.
while IFS= read -r stale; do
  log "ATTENTION : reste d'une exécution interrompue : $stale"
done < <(find "$BACKUP_DIR" -mindepth 1 -maxdepth 1 -type d -name '.en-cours-*')

log "terminé"
