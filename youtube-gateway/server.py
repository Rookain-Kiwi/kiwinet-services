#!/usr/bin/env python3
"""youtube-gateway : sert des lives YouTube en AAC (ADTS), a la demande.

Music Assistant (ou tout lecteur) ouvre http://<hote>:<port>/<nom>. A cet instant
seulement, le serveur retrouve l'adresse du flux (yt-dlp) et lance ffmpeg, qui
recopie l'audio AAC sans le reencoder. Quand le lecteur se deconnecte, ffmpeg est
arrete : une radio qui n'est pas ecoutee ne consomme rien.

Les radios viennent d'un fichier texte (RADIOS_FILE), relu des qu'il change.
Aucune adresse n'est jamais lue dans la requete : on ne lance que celles du fichier.
Sans bibliotheque externe : bibliotheque standard de Python seulement.
"""
import http.server
import logging
import os
import re
import select
import signal
import socket
import socketserver
import subprocess
import sys
import threading
import time

BIND = os.environ.get("BIND", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8100"))
RADIOS_FILE = os.environ.get("RADIOS_FILE", "/config/radios.txt")
MAX_STREAMS = int(os.environ.get("MAX_STREAMS", "3"))      # ecoutes simultanees
URL_TTL = int(os.environ.get("URL_TTL", "14400"))          # 4 h, sous les ~6 h de validite
MAX_FAILURES = int(os.environ.get("MAX_FAILURES", "5"))    # echecs de suite avant abandon
EXTRACT_TIMEOUT = int(os.environ.get("EXTRACT_TIMEOUT", "60"))
FIRST_BYTE_TIMEOUT = int(os.environ.get("FIRST_BYTE_TIMEOUT", "40"))
GOOD_BYTES = 256 * 1024     # au moins ca recu : la tentative compte comme reussie
CHUNK = 65536

NAME_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,39}")
LIVE_RE = re.compile(r"https://www\.youtube\.com/watch\?v=[A-Za-z0-9_-]{11}")
URL_RE = re.compile(r"https?://\S+")

log = logging.getLogger("gateway")
lock = threading.Lock()
active = 0
cache = {}              # nom -> (adresse du flux, heure d'extraction)
children = set()        # processus ffmpeg en cours, pour l'arret propre
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
    """Lit le fichier des radios : une ligne 'nom adresse', # pour les commentaires."""
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
        if len(parts) != 2 or not NAME_RE.fullmatch(parts[0]) or not LIVE_RE.fullmatch(parts[1]):
            log.warning("ligne %d ignoree (format invalide)", n)
            continue
        if parts[0] in radios:
            log.warning("ligne %d ignoree (nom deja utilise)", n)
            continue
        radios[parts[0]] = parts[1]
    return radios


def extract(name, page_url, fresh):
    """Adresse du flux audio d'un live. Gardee URL_TTL secondes, sauf si fresh."""
    if not fresh:
        with lock:
            hit = cache.get(name)
        if hit and time.time() - hit[1] < URL_TTL:
            return hit[0]
    cmd = ["yt-dlp", "--ignore-config", "--no-update", "--no-cache-dir", "--no-playlist",
           "-g", "-f", "bestaudio", "--", page_url]
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


def finish(proc):
    """Arrete ffmpeg s'il tourne encore, retourne son dernier message d'erreur."""
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
    try:
        err = proc.stderr.read(65536).decode("utf-8", "replace")
    except OSError:
        err = ""
    for pipe in (proc.stdout, proc.stderr):
        try:
            pipe.close()
        except OSError:
            pass
    with lock:
        children.discard(proc)
    return clean(err)


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
        """(nom, adresse du live) si le chemin demande est une radio connue, sinon None."""
        name = self.path.split("?", 1)[0].lstrip("/")
        if not NAME_RE.fullmatch(name):
            return None
        page_url = load_radios().get(name)
        return (name, page_url) if page_url else None

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
            self.stream(*found)
        finally:
            with lock:
                active -= 1

    def relay(self, proc, state):
        """Copie ffmpeg -> client. Retourne (raison, octets) : client, eof, timeout ou stop."""
        fd = proc.stdout.fileno()
        sock = self.connection
        total = 0
        t0 = time.time()
        while not stopping.is_set():
            ready, _, _ = select.select([fd, sock], [], [], 1.0)
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
                    return "client", total
                total += len(data)
            elif total == 0 and time.time() - t0 > FIRST_BYTE_TIMEOUT:
                return "timeout", total
        return "stop", total

    def client_gone(self):
        """Vrai si le lecteur a ferme la connexion (sans bloquer)."""
        try:
            ready, _, _ = select.select([self.connection], [], [], 0)
            return bool(ready) and self.connection.recv(1, socket.MSG_PEEK) == b""
        except OSError:
            return True

    def stream(self, name, page_url):
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


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                        format="%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    server = Server((BIND, PORT), Handler)

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