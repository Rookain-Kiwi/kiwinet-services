#!/usr/bin/env python3
"""youtube-gateway : sert des lives et des playlists YouTube en AAC (ADTS), a la demande.

Music Assistant (ou tout lecteur) ouvre http://<hote>:<port>/<nom>. A cet instant
seulement, le serveur lance yt-dlp et ffmpeg, qui recopient l'audio AAC sans le
reencoder. Quand le lecteur se deconnecte, tout est arrete : une radio qui n'est pas
ecoutee ne consomme rien.

Deux sortes de radios, dans un fichier texte (RADIOS_FILE), relu des qu'il change :
  - un live      : https://www.youtube.com/watch?v=<11 caracteres>
  - une playlist : https://www.youtube.com/playlist?list=<identifiant>
    lue en boucle et dans un ordre aleatoire (nouveau melange a chaque ecoute et a
    chaque tour), piste apres piste. A froid, la preparation de la premiere piste depasse
    ce que le lecteur attend : du silence lui est envoye pendant ce temps.
Aucune adresse n'est jamais lue dans la requete : on ne lance que celles du fichier.
Sans bibliotheque externe : bibliotheque standard de Python seulement.
"""
import http.server
import json
import logging
import os
import random
import re
import select
import signal
import socket
import socketserver
import subprocess
import sys
import tempfile
import threading
import time

BIND = os.environ.get("BIND", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8100"))
RADIOS_FILE = os.environ.get("RADIOS_FILE", "/config/radios.txt")
MAX_STREAMS = int(os.environ.get("MAX_STREAMS", "3"))      # ecoutes simultanees
URL_TTL = int(os.environ.get("URL_TTL", "14400"))          # 4 h, sous les ~6 h de validite (lives)
MAX_FAILURES = int(os.environ.get("MAX_FAILURES", "5"))    # echecs de suite avant abandon (lives)
EXTRACT_TIMEOUT = int(os.environ.get("EXTRACT_TIMEOUT", "60"))
FIRST_BYTE_TIMEOUT = int(os.environ.get("FIRST_BYTE_TIMEOUT", "40"))
PLAYLIST_TTL = int(os.environ.get("PLAYLIST_TTL", "3600"))   # liste des pistes gardee 1 h
INFO_TTL = int(os.environ.get("INFO_TTL", "14400"))          # infos d'une piste gardees 4 h
DEAD_TTL = int(os.environ.get("DEAD_TTL", "600"))            # une piste en echec n'est pas reessayee avant 10 min
TRACK_FAILURES = int(os.environ.get("TRACK_FAILURES", "5"))  # pistes de suite en echec avant abandon
PRESTART_SECONDS = int(os.environ.get("PRESTART_SECONDS", "12"))  # on prepare la piste suivante quand il reste cette duree d'audio a envoyer
SILENCE_KEEPALIVE = os.environ.get("SILENCE_KEEPALIVE", "1") not in ("0", "", "no", "non")  # silence pendant un demarrage lent (playlists)
SILENCE_GRACE = float(os.environ.get("SILENCE_GRACE", "1.5"))  # attente (s) avant d'envoyer le premier silence
GOOD_BYTES = 256 * 1024     # au moins ca recu : la tentative compte comme reussie
CHUNK = 65536
TMP_DIR = os.environ.get("TMP_DIR", "/tmp")
FMT = "bestaudio[ext=m4a]/bestaudio"

NAME_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,39}")
LIVE_RE = re.compile(r"https://www\.youtube\.com/watch\?v=[A-Za-z0-9_-]{11}")
LIST_RE = re.compile(r"https://www\.youtube\.com/playlist\?list=[A-Za-z0-9_-]{10,64}")
VID_RE = re.compile(r"[A-Za-z0-9_-]{11}")
URL_RE = re.compile(r"https?://\S+")
YTDLP = ["yt-dlp", "--ignore-config", "--no-update", "--no-cache-dir"]

log = logging.getLogger("gateway")
lock = threading.Lock()
active = 0
cache = {}              # live : nom -> (adresse du flux, heure d'extraction)
playlist_cache = {}     # playlist : adresse -> (identifiants des pistes, heure)
info_cache = {}         # piste : identifiant -> (infos d'extraction, heure)
dead_cache = {}         # piste : identifiant -> heure du dernier echec
inflight = {}           # piste : identifiant -> evenement signale quand son extraction en cours se termine
children = set()        # processus en cours, pour l'arret propre
stopping = threading.Event()


def clean(text):
    """Derniere ligne d'un message d'erreur, sans adresse (elles contiennent l'IP publique)."""
    lines = [l.strip() for l in (text or "").splitlines() if l.strip()]
    return URL_RE.sub("<adresse>", lines[-1])[:200] if lines else ""


_radios_cache = {"sig": None, "radios": {}}


def load_radios():
    """Liste des radios. Le fichier est relu des qu'il change (git pull, edition),
    jamais besoin de redemarrer. Les lignes invalides ne sont signalees qu'une fois."""
    try:
        st = os.stat(RADIOS_FILE)
        sig = (st.st_mtime_ns, st.st_size, st.st_ino)
    except OSError as e:
        sig = None
        if _radios_cache["sig"] is not None or not _radios_cache.get("warned"):
            log.error("liste des radios illisible : %s", e.strerror)
            _radios_cache["warned"] = True
    if sig is not None and sig == _radios_cache["sig"]:
        return _radios_cache["radios"]
    radios = parse_radios() if sig is not None else {}
    _radios_cache["sig"], _radios_cache["radios"] = sig, radios
    return radios


def parse_radios():
    """Lit le fichier des radios : une ligne 'nom adresse', # pour les commentaires.
    Retourne {nom: (genre, adresse)}, genre valant 'live' ou 'playlist'."""
    radios = {}
    try:
        with open(RADIOS_FILE, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError as e:
        log.error("liste des radios illisible : %s", e.strerror)
        return radios
    log.info("liste des radios (re)lue")
    for n, raw in enumerate(lines, 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 2 or not NAME_RE.fullmatch(parts[0]):
            log.warning("ligne %d ignoree (format invalide)", n)
            continue
        if LIVE_RE.fullmatch(parts[1]):
            kind = "live"
        elif LIST_RE.fullmatch(parts[1]):
            kind = "playlist"
        else:
            log.warning("ligne %d ignoree (format invalide)", n)
            continue
        if parts[0] in radios:
            log.warning("ligne %d ignoree (nom deja utilise)", n)
            continue
        radios[parts[0]] = (kind, parts[1])
    return radios


# --------------------------------------------------------------------------- lives

def extract(name, page_url, fresh):
    """Adresse du flux audio d'un live. Gardee URL_TTL secondes, sauf si fresh."""
    if not fresh:
        with lock:
            hit = cache.get(name)
        if hit and time.time() - hit[1] < URL_TTL:
            return hit[0]
    cmd = YTDLP + ["--no-playlist", "-g", "-f", "bestaudio", "--", page_url]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=EXTRACT_TIMEOUT,
                           stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        log.error("%s : extraction trop longue", name)
        return None
    words = r.stdout.split()
    if r.returncode != 0 or not words or not words[0].startswith("https://"):
        log.error("%s : extraction echouee (code %s) : %s", name, r.returncode, clean(r.stderr))
        return None
    with lock:
        cache[name] = (words[0], time.time())
    return words[0]


def start_ffmpeg(stream_url, mid_stream):
    # live_start_index : par defaut ffmpeg demarre 3 segments (15 s) avant le direct,
    # ce qui donne une reserve a l'ouverture. En reprise de flux en cours de route,
    # on demarre au dernier segment pour ne pas rejouer 15 s deja entendues.
    cmd = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-rw_timeout", "15000000"]
    if mid_stream:
        cmd += ["-live_start_index", "-1"]
    cmd += ["-i", stream_url, "-vn", "-c:a", "copy", "-f", "adts", "pipe:1"]
    proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, bufsize=0)
    with lock:
        children.add(proc)
    return proc


def finish(proc, grace=1.0):
    """Arrete le processus s'il tourne encore (arret poli pendant grace secondes, puis force),
    retourne son dernier message d'erreur."""
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
    try:
        err = proc.stderr.read(65536).decode("utf-8", "replace")
    except (OSError, ValueError, AttributeError):
        err = ""
    for pipe in (proc.stdout, proc.stderr):
        try:
            if pipe is not None:
                pipe.close()
        except OSError:
            pass
    with lock:
        children.discard(proc)
    return clean(err)


# ----------------------------------------------------------------------- playlists

def playlist_ids(name, list_url):
    """Identifiants des pistes d'une playlist, gardes PLAYLIST_TTL secondes."""
    with lock:
        hit = playlist_cache.get(list_url)
    if hit and time.time() - hit[1] < PLAYLIST_TTL:
        return hit[0]
    cmd = YTDLP + ["--flat-playlist", "--print", "%(id)s", "--", list_url]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=EXTRACT_TIMEOUT,
                           stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        r = None
    ids = []
    if r is not None:
        for line in r.stdout.splitlines():
            line = line.strip()
            if VID_RE.fullmatch(line) and line not in ids:
                ids.append(line)
    if not ids:
        log.error("%s : playlist illisible ou vide : %s", name,
                  "delai depasse" if r is None else clean(r.stderr))
        return hit[0] if hit else None       # a defaut, la derniere liste connue
    with lock:
        playlist_cache[list_url] = (ids, time.time())
    return ids


def mark_dead(vid):
    with lock:
        if len(dead_cache) >= 256:
            dead_cache.clear()
        dead_cache[vid] = time.time()


def track_info(name, vid):
    """Infos d'extraction d'une piste (adresses du flux comprises), gardees INFO_TTL secondes.
    Retourne un dict, ou None si la piste est indisponible. Une seule extraction a la fois par
    piste : un second appel attend le resultat du premier au lieu de relancer yt-dlp."""
    with lock:
        hit = info_cache.get(vid)
        failed = dead_cache.get(vid)
        if hit and time.time() - hit[1] < INFO_TTL:
            return hit[0]
        if failed and time.time() - failed < DEAD_TTL:
            return None              # deja en echec il y a peu : on ne harcele pas YouTube
        waiting = inflight.get(vid)
        if waiting is None:
            inflight[vid] = threading.Event()
    if waiting is not None:
        waiting.wait(EXTRACT_TIMEOUT + 10)
        with lock:
            hit = info_cache.get(vid)
        return hit[0] if hit else None
    try:
        return extract_info(name, vid)
    finally:
        with lock:
            done = inflight.pop(vid, None)
        if done is not None:
            done.set()


def extract_info(name, vid):
    """Extraction proprement dite (yt-dlp), appelee par track_info."""
    cmd = YTDLP + ["--no-playlist", "-f", FMT, "-j", "--", "https://www.youtube.com/watch?v=" + vid]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=EXTRACT_TIMEOUT,
                           stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        log.error("%s : piste %s : extraction trop longue", name, vid)
        mark_dead(vid)
        return None
    lines = [l for l in r.stdout.splitlines() if l.strip()]
    if r.returncode != 0 or not lines:
        log.error("%s : piste %s indisponible (code %s) : %s", name, vid, r.returncode, clean(r.stderr))
        mark_dead(vid)
        return None
    try:
        meta = json.loads(lines[-1])
    except ValueError:
        log.error("%s : piste %s : reponse d'extraction illisible", name, vid)
        mark_dead(vid)
        return None
    info = {
        "json": lines[-1],
        "ext": meta.get("ext"),
        "acodec": str(meta.get("acodec") or ""),
        "asr": meta.get("asr"),
        "channels": meta.get("audio_channels"),
        "abr": meta.get("abr"),
        "duration": meta.get("duration"),
    }
    with lock:
        if len(info_cache) >= 16:                      # quelques entrees suffisent
            info_cache.pop(min(info_cache, key=lambda k: info_cache[k][1]), None)
        info_cache[vid] = (info, time.time())
    return info


_silence = {}


def silence_bytes(seconds):
    """Quelques secondes de silence en AAC-LC 44,1 kHz stereo (memes parametres que les pistes),
    envoyees pendant un demarrage lent pour que le lecteur ne renonce pas."""
    key = round(seconds, 1)
    with lock:
        data = _silence.get(key)
    if data is None:
        cmd = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
               "anullsrc=r=44100:cl=stereo", "-t", str(seconds), "-c:a", "aac", "-b:a", "128k",
               "-ar", "44100", "-ac", "2", "-f", "adts", "pipe:1"]
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=30, stdin=subprocess.DEVNULL)
            data = r.stdout if r.returncode == 0 else b""
        except (subprocess.TimeoutExpired, OSError):
            data = b""
        if not data:
            log.warning("silence d'attente impossible a produire")
        with lock:
            _silence[key] = data
    return data


def can_copy(info):
    """Recopie sans reencodage seulement pour de l'AAC-LC 44,1 kHz stereo : toutes les
    pistes enchainees gardent ainsi les memes parametres, que le lecteur lit sans accroc."""
    return (info["ext"] == "m4a" and info["acodec"].startswith("mp4a.40.2")
            and info["asr"] == 44100 and info["channels"] in (None, 2))


class Track:
    """Une piste : yt-dlp lit le fichier (a partir des infos deja extraites), ffmpeg sort de l'ADTS."""

    def __init__(self, vid, info):
        self.vid = vid
        self.copy = can_copy(info)
        # Mode de lecture, pour le journal : recopie sans reencodage, ou reencodage et pourquoi.
        detail = "%s %s %s Hz %s canaux" % (info["ext"] or "?", info["acodec"] or "?",
                                            info["asr"] or "?", info["channels"] or "?")
        self.mode = "recopiee (%s)" % detail if self.copy else "reencodee (%s)" % detail
        rate = info["abr"] if (self.copy and info["abr"]) else 128      # kbit/s
        # Octets envoyes a partir desquels la piste suivante est preparee : il reste alors
        # PRESTART_SECONDS d'audio a envoyer (estimation d'apres la duree et le debit).
        # Un lecteur qui lit en temps reel a donc le temps de la voir demarrer : pas de trou.
        self.prestart_at = (max(0, int((info["duration"] - PRESTART_SECONDS) * rate * 125))
                            if info["duration"] else None)
        fd, self.path = tempfile.mkstemp(prefix="gw-", suffix=".json", dir=TMP_DIR)
        with os.fdopen(fd, "w") as f:
            f.write(info["json"])
        codec = ["-c:a", "copy"] if self.copy else ["-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2"]
        self.y = subprocess.Popen(YTDLP + ["-q", "--no-warnings", "--load-info-json", self.path,
                                           "-f", FMT, "-o", "-"],
                                  stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.f = subprocess.Popen(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
                                   "-i", "pipe:0", "-vn"] + codec + ["-f", "adts", "pipe:1"],
                                  stdin=self.y.stdout, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, bufsize=0)
        self.y.stdout.close()
        with lock:
            children.update((self.y, self.f))

    def stop(self):
        """Arrete tout, supprime le fichier temporaire, retourne le dernier message d'erreur."""
        # La sortie est jetee : inutile d'attendre un arret poli (ffmpeg, bloque a ecrire dans
        # un tube que personne ne lit, ne reagit qu'apres plusieurs secondes).
        err = finish(self.f, 0)
        yerr = finish(self.y, 0)
        try:
            os.unlink(self.path)
        except OSError:
            pass
        return err or yerr


class Shuffler:
    """Ordre aleatoire, sans repetition dans un tour ; nouveau melange a chaque tour,
    sans jouer deux fois de suite la meme piste."""

    def __init__(self, ids):
        self.ids = list(ids)
        self.queue = []
        self.last = None
        self.prev_tail = None

    def _refill(self):
        if not self.queue:
            q = self.ids[:]
            random.shuffle(q)
            last = self.last if self.last is not None else self.prev_tail
            if len(q) > 1 and q[0] == last:
                q[0], q[-1] = q[-1], q[0]
            self.queue = q

    def next(self):
        self._refill()
        self.last = self.queue.pop(0)
        self.prev_tail = self.last
        return self.last

    def peek(self):
        """Prochaine piste, sans la retirer (prepare le tour suivant si besoin)."""
        self._refill()
        return self.queue[0]


# ----------------------------------------------------------------------------- HTTP

class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"     # corps sans longueur, jusqu'a la fermeture
    server_version = "youtube-gateway"
    sys_version = ""

    def log_message(self, fmt, *args):
        pass                          # on journalise nous-memes, sans adresses

    def reply(self, code, text):
        body = (text + "\n").encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def lookup(self):
        """(nom, genre, adresse) si le chemin demande est une radio connue, sinon None."""
        name = self.path.split("?", 1)[0].lstrip("/")
        if not NAME_RE.fullmatch(name):
            return None
        radio = load_radios().get(name)
        return (name,) + radio if radio else None

    def do_HEAD(self):
        # Une simple verification (HEAD) ne declenche jamais d'extraction ni de flux.
        if self.path.split("?", 1)[0] == "/healthz":
            return self.reply(200, "ok")
        if self.lookup():
            self.send_response(200)
            self.send_header("Content-Type", "audio/aac")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
        else:
            self.reply(404, "radio inconnue")

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/healthz":
            return self.reply(200, "ok")
        if path == "/":
            return self.reply(200, "\n".join(sorted(load_radios())) or "(aucune radio)")
        found = self.lookup()
        if not found:
            return self.reply(404, "radio inconnue")
        global active
        with lock:
            if active >= MAX_STREAMS:
                busy = True
            else:
                busy = False
                active += 1
        if busy:
            log.warning("%s : refuse, %d ecoutes deja en cours", found[0], MAX_STREAMS)
            return self.reply(503, "trop d'ecoutes en cours")
        try:
            name, kind, url = found
            if kind == "playlist":
                self.stream_playlist(name, url)
            else:
                self.stream_live(name, url)
        finally:
            with lock:
                active -= 1

    def send_data(self, state, data):
        """Envoie des octets au lecteur (en-tetes au premier envoi). Retourne False s'il est parti."""
        try:
            if not state["sent"]:
                self.send_response(200)
                self.send_header("Content-Type", "audio/aac")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                state["sent"] = True
            self.wfile.write(data)
            self.wfile.flush()
        except OSError:
            return False
        return True

    def keepalive(self, state):
        """Pendant que la piste n'est pas prete, envoie du silence (une seconde par seconde, avec
        deux secondes d'avance) : le lecteur, qui abandonne apres quelques secondes sans octet,
        reste connecte. Rien n'est envoye avant SILENCE_GRACE secondes d'attente : un demarrage a
        chaud ne produit aucun silence. Retourne False si le lecteur est parti."""
        if not SILENCE_KEEPALIVE:
            return True
        block = silence_bytes(1.0)
        if not block:
            return True
        now = time.time()
        due = state.get("sil_next")
        if due is None:
            if now - state.get("wait_since", now) < SILENCE_GRACE:
                return True
            state["sil_next"] = now + 1.0
            state["sil_blocks"] = state.get("sil_blocks", 0) + 2
            return self.send_data(state, block * 2)
        if now >= due:
            state["sil_next"] = due + 1.0
            state["sil_blocks"] = state.get("sil_blocks", 0) + 1
            return self.send_data(state, block)
        return True

    def relay(self, proc, state, hook=None, keepalive=False):
        """Copie ffmpeg -> client. Retourne (raison, octets) : client, eof, timeout ou stop.
        hook(octets envoyes) est appele apres chaque envoi. Avec keepalive, du silence est envoye
        tant que le premier octet de la piste n'est pas la."""
        fd = proc.stdout.fileno()
        sock = self.connection
        total = 0
        t0 = time.time()
        while not stopping.is_set():
            ready, _, _ = select.select([fd, sock], [], [], 0.5 if keepalive else 1.0)
            if sock in ready:
                try:
                    if sock.recv(1, socket.MSG_PEEK) == b"":
                        return "client", total
                    sock.recv(4096)       # octets inattendus du client : on les ignore
                except OSError:
                    return "client", total
            if fd in ready:
                data = os.read(fd, CHUNK)
                if not data:
                    return "eof", total
                if not self.send_data(state, data):
                    return "client", total
                if not state.get("music"):
                    state["music"] = True
                    if state.get("sil_blocks"):
                        log.info("%s : %d s de silence envoyes pendant le demarrage",
                                 state.get("name", "?"), state["sil_blocks"])
                state["sil_next"] = None
                state["wait_since"] = time.time()
                total += len(data)
                if hook is not None:
                    hook(total)
            elif total == 0:
                if keepalive and not self.keepalive(state):
                    return "client", total
                if time.time() - t0 > FIRST_BYTE_TIMEOUT:
                    return "timeout", total
        return "stop", total

    def client_gone(self):
        """Vrai si le lecteur a ferme la connexion (sans bloquer)."""
        try:
            ready, _, _ = select.select([self.connection], [], [], 0)
            return bool(ready) and self.connection.recv(1, socket.MSG_PEEK) == b""
        except OSError:
            return True

    def stream_live(self, name, page_url):
        state = {"sent": False}
        failures = attempt = 0
        total = 0
        t_start = time.time()
        log.info("%s : ecoute demarree", name)
        reason = "stop"
        while not stopping.is_set():
            if self.client_gone():
                reason = "client"
                break
            url = extract(name, page_url, fresh=attempt > 0)
            if url is None:
                failures += 1
                reason = "extraction"
            else:
                proc = start_ffmpeg(url, mid_stream=state["sent"])
                t_try = time.time()
                reason, n = self.relay(proc, state)
                err = finish(proc)
                total += n
                if reason in ("client", "stop"):
                    break
                if n >= GOOD_BYTES or time.time() - t_try >= 60:
                    failures = 0
                else:
                    failures += 1
                log.warning("%s : flux interrompu (%s) %s", name, reason, err)
            # Au demarrage, on echoue vite (le lecteur attend une reponse) ; en cours de
            # route, on insiste davantage pour passer un renouvellement d'adresse.
            if failures > (MAX_FAILURES if state["sent"] else 1):
                log.error("%s : abandon apres %d echecs de suite", name, failures)
                break
            attempt += 1
            # Attente avant le nouvel essai, interrompue si le lecteur est parti.
            deadline = time.time() + (min(2 * failures, 10) if failures else 1)
            while time.time() < deadline and not stopping.is_set() and not self.client_gone():
                stopping.wait(0.5)
        if not state["sent"]:
            try:
                self.reply(502, "flux indisponible")
            except OSError:
                pass
        log.info("%s : ecoute terminee (%s) apres %.0f s, %.2f Mo", name, reason,
                 time.time() - t_start, total / 1e6)

    def stream_playlist(self, name, list_url):
        state = {"sent": False, "music": False, "name": name, "wait_since": time.time(), "sil_next": None}
        total = played = failures = reencoded = 0
        t_start = time.time()
        reason = "stop"
        log.info("%s : ecoute de playlist demarree", name)
        # La liste et la premiere piste sont preparees a part. A froid, cela prend une dizaine de
        # secondes, plus que ce que le lecteur attend : pendant ce temps on lui envoie du silence.
        prep = {"done": threading.Event(), "ids": None, "shuffler": None, "track": None, "abandoned": False}
        plock = threading.Lock()

        def prepare():
            track = None
            try:
                prep["ids"] = playlist_ids(name, list_url)
                if prep["ids"]:
                    prep["shuffler"] = Shuffler(prep["ids"])
                    log.info("%s : %d piste(s), ordre aleatoire", name, len(prep["ids"]))
                    track = self.open_track(name, prep["shuffler"])
            except Exception as e:           # le fil ne doit jamais mourir sans signaler sa fin
                log.error("%s : preparation impossible : %s", name, e)
            finally:
                with plock:
                    if prep["abandoned"] and track is not None:
                        track.stop()         # le lecteur est parti pendant ce temps
                        track = None
                    prep["track"] = track
                    prep["done"].set()

        threading.Thread(target=prepare, daemon=True).start()
        cur = nxt = None
        try:
            left = False
            while not prep["done"].wait(0.5):
                if stopping.is_set() or self.client_gone() or not self.keepalive(state):
                    left = True
                    break
            with plock:
                if left and not prep["done"].is_set():
                    prep["abandoned"] = True    # la preparation rangera elle-meme sa piste
                cur = prep["track"]
            if left:
                reason = "client"
            shuffler = prep["shuffler"]
            if not left and shuffler is not None:
                log.info("%s : preparation terminee apres %.0f s", name, time.time() - t_start)
                while not stopping.is_set():
                    if self.client_gone():
                        reason = "client"
                        break
                    if cur is None:
                        cur = self.open_track(name, shuffler)
                    if cur is None:
                        failures += 1
                        reason = "extraction"
                    else:
                        # le temps d'ecoute de cette piste sert a preparer l'extraction de la suivante
                        following = shuffler.peek()
                        if following:
                            threading.Thread(target=track_info, args=(name, following), daemon=True).start()
                        played += 1
                        reencoded += 0 if cur.copy else 1
                        log.info("%s : piste %s (%d) %s", name, cur.vid, played, cur.mode)
                        nxt = None

                        def hook(sent, cur_track=cur):
                            nonlocal nxt
                            if (nxt is None and cur_track.prestart_at is not None
                                    and sent >= cur_track.prestart_at):
                                nxt = self.open_track(name, shuffler)

                        reason, n = self.relay(cur.f, state, hook, keepalive=True)
                        total += n
                        ok = False
                        if reason == "eof":
                            try:
                                ok = cur.f.wait(timeout=10) == 0 and n > 0
                            except subprocess.TimeoutExpired:
                                ok = False
                        err = cur.stop()
                        if reason in ("client", "stop"):
                            cur = None
                            break
                        if ok:
                            failures = 0
                        else:
                            failures += 1
                            log.warning("%s : piste %s interrompue (%s) %s", name, cur.vid, reason, err)
                        cur, nxt = nxt, None
                    # Tant qu'aucune musique n'est partie, on echoue vite ; ensuite on saute les pistes en echec.
                    if failures > (TRACK_FAILURES if state["music"] else 1):
                        log.error("%s : abandon apres %d pistes de suite en echec", name, failures)
                        break
        finally:
            for track in (cur, nxt):
                if track is not None:
                    track.stop()
        if not state["sent"]:
            try:
                self.reply(502, "playlist indisponible")
            except OSError:
                pass
        log.info("%s : ecoute de playlist terminee (%s) apres %.0f s, %d piste(s) dont %d reencodee(s), %.2f Mo",
                 name, reason, time.time() - t_start, played, reencoded, total / 1e6)

    def open_track(self, name, shuffler):
        """Demarre la prochaine piste lisible (saute les indisponibles, trois essais au plus)."""
        for _ in range(3):
            vid = shuffler.next()
            info = track_info(name, vid)
            if info is not None:
                try:
                    return Track(vid, info)
                except OSError as e:
                    log.error("%s : piste %s : lancement impossible (%s)", name, vid, e.strerror)
        return None


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                        format="%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    server = Server((BIND, PORT), Handler)
    if SILENCE_KEEPALIVE:
        threading.Thread(target=silence_bytes, args=(1.0,), daemon=True).start()   # pret avant d'en avoir besoin

    def on_signal(signum, _frame):
        log.info("arret demande")
        stopping.set()
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)
    log.info("youtube-gateway pret : %d radio(s), %d ecoute(s) simultanee(s) au plus",
             len(load_radios()), MAX_STREAMS)
    server.serve_forever()
    with lock:
        left = list(children)
    for proc in left:
        finish(proc)
    log.info("arrete")


if __name__ == "__main__":
    main()
