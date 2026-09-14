#!/usr/bin/env python3
"""
BeamMP Control Panel
Ein schlankes, login-geschütztes Web-Panel zum Starten, Stoppen, Aktualisieren
und Konfigurieren eines BeamMP-Dedicated-Servers (BeamNG.drive), der als
systemd-Service läuft.

Hinweis: BeamMP besitzt KEIN RCON. Konsolen-Befehle werden über eine FIFO an die
Standard-Eingabe des Servers gesendet; die Spielerliste wird – so gut es geht –
aus dem Server-Log geschätzt.
"""
import datetime
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import urllib.request
import zipfile
from functools import wraps

from flask import (Flask, redirect, render_template, request,
                   session, url_for, flash, jsonify)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from i18n import translate, LANGS, DEFAULT_LANG

# ---------------------------------------------------------------------------
# Konfiguration laden
# ---------------------------------------------------------------------------
CONFIG_PATH = os.environ.get("PANEL_CONFIG", "/opt/beammp-panel/panel.json")

with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
    CONF = json.load(fh)

SERVER_DIR = CONF["server_dir"]                       # z. B. /home/beammp/beammp-server
SERVICE = CONF.get("service", "beammp.service")
UPDATE_SERVICE = CONF.get("update_service", "beammp-update.service")
SERVER_BINARY = CONF.get("server_binary", "BeamMP-Server")
CONFIG_FILE = os.path.join(SERVER_DIR, "ServerConfig.toml")
RESOURCES_DIR = os.path.join(SERVER_DIR, CONF.get("resource_folder", "Resources"))
CLIENT_DIR = os.path.join(RESOURCES_DIR, "Client")
PLUGIN_DIR = os.path.join(RESOURCES_DIR, "Server")
PLUGIN_DISABLED_DIR = os.path.join(RESOURCES_DIR, "Server-disabled")
VERSION_FILE = os.path.join(SERVER_DIR, ".installed_version")
GITHUB_RELEASES = "https://api.github.com/repos/BeamMP/BeamMP-Server/releases/latest"

# Panel-Verzeichnis (für Nebendateien wie maps.json)
PANEL_DIR = os.path.dirname(os.path.abspath(CONFIG_PATH))
MAPS_PATH = CONF.get("maps_path", os.path.join(PANEL_DIR, "maps.json"))

app = Flask(__name__)
app.secret_key = CONF["secret_key"]
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024 * 1024  # 2 GiB Upload-Limit für Mods

PANEL_VERSION = "1.0.0"

# Der Port wird beim Installieren festgelegt und ist im Panel gesperrt.
# ResourceFolder ebenfalls, weil das Panel darauf zeigt.
LOCKED_OPTIONS = {"Port", "ResourceFolder"}

# Standardwerte für die Feldliste, solange noch keine ServerConfig.toml existiert.
DEFAULT_SETTINGS = [
    ("AuthKey", "", "str"),
    ("Name", "BeamMP Server", "str"),
    ("Description", "BeamMP Server – powered by BeamMP Control Panel", "str"),
    ("Tags", "Freeroam", "str"),
    ("Map", "/levels/gridmap_v2/info.json", "str"),
    ("MaxPlayers", "10", "int"),
    ("MaxCars", "1", "int"),
    ("Port", "30814", "int"),
    ("Private", "true", "bool"),
    ("AllowGuests", "false", "bool"),
    ("LogChat", "true", "bool"),
    ("Debug", "false", "bool"),
    ("ResourceFolder", "Resources", "str"),
]

# In BeamNG.drive enthaltene Standard-Karten (Pfad, Anzeigename) fuer das Dropdown.
# Eigene Karten werden als .zip in Resources/Client hochgeladen und per Pfad
# /levels/<ordnername>/info.json eingetragen ("Eigene Karte ..." im Menue).
STOCK_MAPS = [
    ("/levels/gridmap_v2/info.json", "Grid Map V2"),
    ("/levels/automation_test_track/info.json", "Automation Test Track"),
    ("/levels/east_coast_usa/info.json", "East Coast USA"),
    ("/levels/west_coast_usa/info.json", "West Coast USA"),
    ("/levels/italy/info.json", "Italy"),
    ("/levels/utah/info.json", "Utah"),
    ("/levels/johnson_valley/info.json", "Johnson Valley"),
    ("/levels/jungle_rock_island/info.json", "Jungle Rock Island"),
    ("/levels/small_island/info.json", "Small Island"),
    ("/levels/hirochi_raceway/info.json", "Hirochi Raceway"),
    ("/levels/industrial/info.json", "Industrial"),
    ("/levels/driver_training/info.json", "Driver Training"),
    ("/levels/derby/info.json", "Derby"),
    ("/levels/cliff/info.json", "Cliff"),
    ("/levels/smallgrid/info.json", "Small Grid"),
]
STOCK_MAP_PATHS = [p for p, _ in STOCK_MAPS]

# ---------------------------------------------------------------------------
# Benutzer-Store (users.json) – alle Konten sind gleichberechtigt
# ---------------------------------------------------------------------------
USERS_PATH = CONF.get("users_path",
                      os.path.join(os.path.dirname(CONFIG_PATH), "users.json"))
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{2,32}$")
MIN_PW = 6
_users_lock = threading.Lock()
_maps_lock = threading.Lock()


def load_users():
    if os.path.exists(USERS_PATH):
        with open(USERS_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh).get("users", {})
    if "username" in CONF and "password_hash" in CONF:
        return {CONF["username"]: {"password_hash": CONF["password_hash"]}}
    return {}


def save_users(users):
    tmp = USERS_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"users": users}, fh, indent=2)
    os.chmod(tmp, 0o600)
    os.replace(tmp, USERS_PATH)


def current_user():
    name = session.get("user")
    if not name or name not in load_users():
        return None
    return {"name": name}


# ---------------------------------------------------------------------------
# Auth / CSRF / i18n
# ---------------------------------------------------------------------------
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_user() is None:
            session.clear()
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def csrf_token():
    tok = session.get("csrf")
    if not tok:
        tok = secrets.token_hex(16)
        session["csrf"] = tok
    return tok


def check_csrf():
    return request.form.get("csrf") and request.form.get("csrf") == session.get("csrf")


app.jinja_env.globals["csrf_token"] = csrf_token


def current_lang():
    lang = request.cookies.get("lang", DEFAULT_LANG)
    return lang if lang in LANGS else DEFAULT_LANG


def t(key, **kw):
    return translate(current_lang(), key, **kw)


app.jinja_env.globals["t"] = t
app.jinja_env.globals["current_lang"] = current_lang
app.jinja_env.globals["LANGS"] = LANGS


@app.context_processor
def inject_me():
    return {"me": current_user(), "panel_version": PANEL_VERSION}


@app.route("/lang/<code>")
def set_lang(code):
    resp = redirect(request.referrer or url_for("dashboard"))
    if code in LANGS:
        resp.set_cookie("lang", code, max_age=31536000, samesite="Lax")
    return resp


# ---------------------------------------------------------------------------
# systemd-Steuerung
# ---------------------------------------------------------------------------
def run(cmd, timeout=30):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout + p.stderr).strip()
    except subprocess.TimeoutExpired:
        return 1, "Zeitüberschreitung beim Ausführen des Befehls."


def service_active(name):
    _rc, out = run(["systemctl", "is-active", name])
    return out


def service_enabled(name):
    _rc, out = run(["systemctl", "is-enabled", name])
    return out


def svc(*args):
    """systemctl mit Root-Rechten (nur die in der sudoers-Regel erlaubten Aufrufe)."""
    return run(["sudo", "-n", "systemctl", *args])


def recent_logs(name, lines=80):
    rc, out = run(["journalctl", "-u", name, "-n", str(lines),
                   "--no-pager", "-o", "short-iso"])
    return out if rc == 0 else "Keine Logs verfügbar (Rechte prüfen)."


# ---------------------------------------------------------------------------
# Server-Adresse (öffentliche IP ermitteln, gecacht)
# ---------------------------------------------------------------------------
def local_ipv4():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


_PUBIP_SERVICES = [
    "https://api.ipify.org",
    "https://checkip.amazonaws.com",
    "https://ifconfig.me/ip",
]
_PUBIP_TTL = 600
_PUBIP_FAIL_TTL = 120
_IPV4_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")
_pubip_cache = {"ip": None, "ts": 0.0, "ok": False}


def detect_public_ip(timeout=2.0):
    now = time.time()
    ttl = _PUBIP_TTL if _pubip_cache["ok"] else _PUBIP_FAIL_TTL
    if now - _pubip_cache["ts"] < ttl:
        return _pubip_cache["ip"]
    ip = None
    for url in _PUBIP_SERVICES:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "beammp-panel"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                candidate = resp.read().decode("utf-8", "ignore").strip()
            if _IPV4_RE.match(candidate):
                ip = candidate
                break
        except Exception:
            continue
    _pubip_cache.update(ip=ip, ts=now, ok=bool(ip))
    return ip


def connect_info():
    """(adresse, port, art) für die Verbinden-Box. Port ist fest (beim Installieren gesetzt)."""
    port = game_port()
    manual = (CONF.get("public_ip") or "").strip()
    if manual:
        return manual, port, "manual"
    pub = detect_public_ip()
    if pub:
        return pub, port, "auto"
    return local_ipv4(), port, "local"


# ---------------------------------------------------------------------------
# Ressourcen (CPU / RAM / Disk) – containerbewusst über lxcfs
# ---------------------------------------------------------------------------
_cpu_prev = {"idle": None, "total": None}


def read_cpu_percent():
    try:
        with open("/proc/stat") as f:
            parts = f.readline().split()
        vals = [int(x) for x in parts[1:]]
        idle = vals[3] + (vals[4] if len(vals) > 4 else 0)
        total = sum(vals)
        prev_idle, prev_total = _cpu_prev["idle"], _cpu_prev["total"]
        _cpu_prev["idle"], _cpu_prev["total"] = idle, total
        if prev_total is None:
            return None
        d_total = total - prev_total
        if d_total <= 0:
            return None
        return round(100.0 * (1.0 - (idle - prev_idle) / d_total), 1)
    except Exception:
        return None


def read_mem():
    try:
        info = {}
        with open("/proc/meminfo") as f:
            for line in f:
                k, _, v = line.partition(":")
                if v:
                    info[k.strip()] = int(v.strip().split()[0])  # kB
        total = info.get("MemTotal", 0)
        avail = info.get("MemAvailable", info.get("MemFree", 0))
        used = total - avail
        return {"used_gb": round(used / 1048576, 1),
                "total_gb": round(total / 1048576, 1),
                "pct": round(100.0 * used / total, 1) if total else None}
    except Exception:
        return None


def read_disk():
    try:
        base = SERVER_DIR if os.path.exists(SERVER_DIR) else "/"
        st = os.statvfs(base)
        total = st.f_blocks * st.f_frsize
        free = st.f_bavail * st.f_frsize
        used = total - free
        return {"used_gb": round(used / 1073741824, 1),
                "total_gb": round(total / 1073741824, 1),
                "pct": round(100.0 * used / total, 1) if total else None}
    except Exception:
        return None


def resources():
    return {"cpu": read_cpu_percent(), "mem": read_mem(), "disk": read_disk()}


# ---------------------------------------------------------------------------
# Version / Update-Check (GitHub-Releases von BeamMP/BeamMP-Server)
# ---------------------------------------------------------------------------
def _read_text(path):
    """Liest eine Datei tolerant gegenüber BOM/UTF-16/Latin-1."""
    with open(path, "rb") as fh:
        data = fh.read()
    for enc in ("utf-8-sig", "utf-8", "utf-16", "latin-1"):
        try:
            return data.decode(enc)
        except (UnicodeDecodeError, UnicodeError):
            continue
    return data.decode("utf-8", errors="replace")


def installed_version():
    """Bevorzugt die vom Update-Skript geschriebene Versionsdatei, sonst aus dem Log."""
    if os.path.exists(VERSION_FILE):
        try:
            v = _read_text(VERSION_FILE).strip().lstrip("vV")
            if v:
                return v
        except Exception:
            pass
    rc, out = run(["journalctl", "-u", SERVICE, "--no-pager", "-o", "cat",
                   "-g", "BeamMP", "-n", "40"])
    if rc == 0 and out:
        found = re.findall(r"BeamMP[- ]Server\s+v?([\d.]+)", out)
        if found:
            return found[-1]
    return None


_latest_cache = {"tag": None, "ts": 0.0}


def latest_version(timeout=4.0):
    now = time.time()
    if _latest_cache["tag"] and now - _latest_cache["ts"] < 1800:
        return _latest_cache["tag"]
    try:
        req = urllib.request.Request(GITHUB_RELEASES,
                                     headers={"User-Agent": "beammp-panel",
                                              "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", "ignore"))
        tag = (data.get("tag_name") or "").lstrip("vV")
        if tag:
            _latest_cache.update(tag=tag, ts=now)
    except Exception:
        pass
    return _latest_cache["tag"]


# ---------------------------------------------------------------------------
# ServerConfig.toml – zeilenbasiert lesen/schreiben (erhält Kommentare)
# ---------------------------------------------------------------------------
_KV_RE = re.compile(r"^(\s*)([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$")


def _split_comment(rest):
    """Trennt einen Zeilenkommentar (# …) ab, ohne solche innerhalb von Strings zu treffen."""
    in_q = esc = False
    for i, ch in enumerate(rest):
        if esc:
            esc = False
            continue
        if ch == "\\" and in_q:
            esc = True
            continue
        if ch == '"':
            in_q = not in_q
            continue
        if ch == "#" and not in_q:
            return rest[:i].rstrip(), rest[i:]
    return rest.rstrip(), ""


def _typed(rawval):
    v = rawval.strip()
    if len(v) >= 2 and v[0] == '"' and v[-1] == '"':
        inner = v[1:-1].replace('\\"', '"').replace("\\\\", "\\")
        return inner, "str"
    low = v.lower()
    if low in ("true", "false"):
        return low, "bool"
    if re.fullmatch(r"-?\d+", v):
        return v, "int"
    if re.fullmatch(r"-?\d+\.\d+", v):
        return v, "float"
    return v, "bare"


def _emit(kind, newval):
    newval = (newval or "").strip()
    if kind == "str":
        return '"' + newval.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if kind == "bool":
        return "true" if newval.lower() in ("true", "1", "on", "yes") else "false"
    if kind == "int":
        return newval if re.fullmatch(r"-?\d+", newval) else '"' + newval.replace('"', "") + '"'
    if kind == "float":
        return newval if re.fullmatch(r"-?\d+(\.\d+)?", newval) else '"' + newval.replace('"', "") + '"'
    # bare / neu -> heuristisch
    if newval.lower() in ("true", "false"):
        return newval.lower()
    if re.fullmatch(r"-?\d+", newval):
        return newval
    return '"' + newval.replace("\\", "\\\\").replace('"', '\\"') + '"'


def read_settings():
    """(settings, raw, aktiver_pfad, using_default).
    settings: Liste (key, display, kind) in Dateireihenfolge."""
    if os.path.exists(CONFIG_FILE):
        raw = _read_text(CONFIG_FILE)
        settings = []
        seen = set()
        for line in raw.splitlines():
            s = line.strip()
            if not s or s.startswith("#") or s.startswith("["):
                continue
            m = _KV_RE.match(line)
            if not m:
                continue
            key = m.group(2)
            valpart, _cmt = _split_comment(m.group(3))
            display, kind = _typed(valpart)
            if key in seen:
                continue
            seen.add(key)
            settings.append((key, display, kind))
        if settings:
            return settings, raw, CONFIG_FILE, False
        return [(k, v, kd) for k, v, kd in DEFAULT_SETTINGS], raw, CONFIG_FILE, True
    return [(k, v, kd) for k, v, kd in DEFAULT_SETTINGS], "", CONFIG_FILE, True


def settings_lookup():
    settings, _raw, _active, _ud = read_settings()
    return {k: v for k, v, _kd in settings}


def write_settings(new_values):
    """Aktualisiert Werte in der ServerConfig.toml, ohne den Rest zu verändern.
    Fehlende Keys werden unter [General] ergänzt."""
    raw = _read_text(CONFIG_FILE) if os.path.exists(CONFIG_FILE) else ""
    lines = raw.splitlines()
    seen = set()
    out = []
    kinds = {k: kd for k, _v, kd in (read_settings()[0])}
    for line in lines:
        m = _KV_RE.match(line)
        if m and (m.group(2) in new_values):
            key = m.group(2)
            indent = m.group(1)
            _valpart, comment = _split_comment(m.group(3))
            kind = kinds.get(key)
            if kind is None:
                _disp, kind = _typed(_valpart)
            emitted = _emit(kind, new_values[key])
            tail = (" " + comment) if comment else ""
            out.append(f"{indent}{key} = {emitted}{tail}")
            seen.add(key)
        else:
            out.append(line)

    missing = [(k, v) for k, v in new_values.items() if k not in seen]
    if missing:
        # unter [General] einsortieren, sonst am Ende
        gi = next((i for i, l in enumerate(out) if l.strip().lower() == "[general]"), None)
        block = [f"{k} = {_emit(None, v)}" for k, v in missing]
        if gi is None:
            if out and out[-1].strip():
                out.append("")
            out.append("[General]")
            out.extend(block)
        else:
            insert_at = gi + 1
            # hinter die bestehenden [General]-Zeilen setzen
            j = gi + 1
            while j < len(out) and not out[j].strip().startswith("["):
                j += 1
            insert_at = j
            out[insert_at:insert_at] = block

    text = "\n".join(out)
    if not text.endswith("\n"):
        text += "\n"
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as fh:
        fh.write(text)


def write_raw(text):
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as fh:
        fh.write(text)


def game_port():
    p = CONF.get("game_port")
    if p:
        return str(p)
    v = settings_lookup().get("Port")
    return str(v) if v else "30814"


def enforce_locked():
    """Feste Werte (Port, ResourceFolder) zurückschreiben."""
    write_settings({"Port": game_port(),
                    "ResourceFolder": CONF.get("resource_folder", "Resources")})


def authkey_value():
    return (settings_lookup().get("AuthKey") or "").strip()


# ---------------------------------------------------------------------------
# Server-Konsole (BeamMP hat kein RCON – Befehle gehen an stdin via FIFO)
# ---------------------------------------------------------------------------
class ConsoleError(Exception):
    pass


def console_send(cmd):
    fifo = CONF.get("console_fifo") or os.path.join(SERVER_DIR, "console.in")
    if not os.path.exists(fifo):
        raise ConsoleError(t("console_no_fifo"))
    try:
        # O_NONBLOCK: kein Reader (Server aus) -> ENXIO statt Blockieren
        fd = os.open(fifo, os.O_WRONLY | os.O_NONBLOCK)
    except OSError:
        raise ConsoleError(t("console_not_running"))
    try:
        os.write(fd, (cmd.rstrip("\n") + "\n").encode("utf-8", "replace"))
    finally:
        os.close(fd)


# ---------------------------------------------------------------------------
# Spielerliste aus dem Server-Log schätzen (best effort, kein RCON)
# ---------------------------------------------------------------------------
_JOIN_RES = [
    re.compile(r'Identification confirmed for ["\']?(.+?)["\']?[,!]', re.I),
    re.compile(r'"([^"]+)"\s*\(\d+\)\s*(?:joined|connected)', re.I),
    re.compile(r'player\s+"?([^"\n]+?)"?\s+connected', re.I),
]
_LEAVE_RES = [
    re.compile(r'"([^"]+)"\s*\(\d+\)\s*disconnected', re.I),
    re.compile(r'player\s+"?([^"\n]+?)"?\s+disconnected', re.I),
    re.compile(r'Closing socket.*?["\']([^"\']+)["\']', re.I),
]


def log_players():
    """Bestmögliche Schätzung der aktuell verbundenen Spieler aus dem Log.
    Gibt eine Liste von Namen zurück oder None, wenn nichts erkennbar war."""
    if service_active(SERVICE) != "active":
        return []
    logs = recent_logs(SERVICE, 400)
    if not logs or logs.startswith("Keine Logs"):
        return None
    present = []
    matched_any = False
    for line in logs.splitlines():
        for rx in _JOIN_RES:
            m = rx.search(line)
            if m:
                name = m.group(1).strip()
                matched_any = True
                if name and name not in present:
                    present.append(name)
                break
        for rx in _LEAVE_RES:
            m = rx.search(line)
            if m:
                name = m.group(1).strip()
                matched_any = True
                if name in present:
                    present.remove(name)
                break
    return present if matched_any else None


# ---------------------------------------------------------------------------
# Mods: Client-Mods (Resources/Client, .zip) & Server-Plugins (Resources/Server)
# ---------------------------------------------------------------------------
def ensure_client_dir():
    os.makedirs(CLIENT_DIR, exist_ok=True)
    return CLIENT_DIR


def list_client_mods():
    out = []
    if os.path.isdir(CLIENT_DIR):
        for fn in sorted(os.listdir(CLIENT_DIR)):
            full = os.path.join(CLIENT_DIR, fn)
            if not os.path.isfile(full):
                continue
            if fn.lower().endswith(".zip"):
                enabled, stem = True, fn[:-4]
            elif fn.lower().endswith(".zip.disabled"):
                enabled, stem = False, fn[:-len(".zip.disabled")]
            else:
                continue
            out.append({"name": stem, "enabled": enabled,
                        "size_mb": round(os.path.getsize(full) / 1048576, 1)})
    return out


def _client_path(stem, enabled):
    return os.path.join(CLIENT_DIR, stem + (".zip" if enabled else ".zip.disabled"))


def toggle_client_mod(stem, enable):
    src = _client_path(stem, not enable)
    dst = _client_path(stem, enable)
    if os.path.isfile(src):
        try:
            os.rename(src, dst)
            return True
        except OSError:
            return False
    return False


def delete_client_mod(stem):
    removed = False
    for enabled in (True, False):
        p = _client_path(stem, enabled)
        if os.path.isfile(p):
            try:
                os.remove(p)
                removed = True
            except OSError:
                pass
    return removed


def _is_plugin_dir(full):
    if not os.path.isdir(full):
        return False
    for _root, _dirs, files in os.walk(full):
        if any(f.lower().endswith(".lua") for f in files):
            return True
    return False


def list_plugins():
    out = []
    for base, enabled in ((PLUGIN_DIR, True), (PLUGIN_DISABLED_DIR, False)):
        if os.path.isdir(base):
            for name in sorted(os.listdir(base)):
                if os.path.isdir(os.path.join(base, name)):
                    out.append({"name": name, "enabled": enabled})
    return sorted(out, key=lambda m: m["name"])


def toggle_plugin(name, enable):
    src = os.path.join(PLUGIN_DISABLED_DIR if enable else PLUGIN_DIR, name)
    dst = os.path.join(PLUGIN_DIR if enable else PLUGIN_DISABLED_DIR, name)
    if not os.path.isdir(src):
        return False
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst):
        shutil.rmtree(dst, ignore_errors=True)
    try:
        shutil.move(src, dst)
        return True
    except OSError:
        return False


def delete_plugin(name):
    ok = False
    for base in (PLUGIN_DIR, PLUGIN_DISABLED_DIR):
        p = os.path.join(base, name)
        if os.path.isdir(p):
            shutil.rmtree(p, ignore_errors=True)
            ok = True
    return ok


# ---------------------------------------------------------------------------
# Routen
# ---------------------------------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = request.form.get("username", "")
        pw = request.form.get("password", "")
        info = load_users().get(user)
        if info and check_password_hash(info["password_hash"], pw):
            session["user"] = user
            session.permanent = False
            nxt = request.args.get("next") or url_for("dashboard")
            if not nxt.startswith("/"):
                nxt = url_for("dashboard")
            return redirect(nxt)
        flash(t("login_bad"))
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def dashboard():
    state = service_active(SERVICE)
    c_ip, c_port, c_kind = connect_info()
    fifo = CONF.get("console_fifo") or os.path.join(SERVER_DIR, "console.in")
    return render_template(
        "dashboard.html",
        state=state,
        update_state=service_active(UPDATE_SERVICE),
        enabled=service_enabled(SERVICE),
        logs=recent_logs(SERVICE),
        service=SERVICE,
        connect_ip=c_ip,
        connect_port=c_port,
        connect_kind=c_kind,
        version=installed_version(),
        authkey_ok=bool(authkey_value()),
        console_ready=os.path.exists(fifo),
    )


@app.route("/status")
@login_required
def status():
    return jsonify(
        server=service_active(SERVICE),
        update=service_active(UPDATE_SERVICE),
        enabled=service_enabled(SERVICE),
        logs=recent_logs(SERVICE, 80),
        res=resources(),
    )


@app.route("/update-check", methods=["POST"])
@login_required
def update_check():
    if not check_csrf():
        return jsonify(ok=False, msg=t("csrf_invalid"))
    inst = installed_version()
    latest = latest_version()
    if inst and latest:
        status_key = "current" if inst == latest else "available"
    else:
        status_key = "unknown"
    return jsonify(ok=True, installed=inst, latest=latest, status=status_key)


@app.route("/update-logs")
@login_required
def update_logs():
    return jsonify(state=service_active(UPDATE_SERVICE),
                   logs=recent_logs(UPDATE_SERVICE, 120))


@app.route("/players")
@login_required
def players():
    if service_active(SERVICE) != "active":
        return jsonify(running=False, players=[], note=t("console_not_running"))
    p = log_players()
    if p is None:
        return jsonify(running=True, players=[], note=t("players_log_note"), parsed=False)
    return jsonify(running=True, players=p, parsed=True)


@app.route("/action", methods=["POST"])
@login_required
def action():
    if not check_csrf():
        flash(t("csrf_invalid"))
        return redirect(url_for("dashboard"))
    act = request.form.get("act")
    if act == "start":
        rc, out = svc("enable", "--now", SERVICE)
        flash(t("srv_started") if rc == 0 else out)
    elif act == "stop":
        rc, out = svc("disable", "--now", SERVICE)
        flash(t("srv_stopped") if rc == 0 else out)
    elif act == "restart":
        svc("enable", SERVICE)
        rc, out = svc("restart", SERVICE)
        flash(t("srv_restarted") if rc == 0 else out)
    elif act == "update":
        rc, out = svc("start", UPDATE_SERVICE)
        flash(t("update_started") if rc == 0 else t("update_failed", out=out))
    else:
        flash(t("unknown_action"))
    return redirect(url_for("dashboard"))


@app.route("/console", methods=["POST"])
@login_required
def console():
    if not check_csrf():
        return jsonify(ok=False, msg=t("csrf_invalid"))
    cmd = (request.form.get("cmd") or "").strip()
    if not cmd:
        return jsonify(ok=False, msg=t("console_empty"))
    if service_active(SERVICE) != "active":
        return jsonify(ok=False, msg=t("console_not_running"))
    try:
        console_send(cmd)
        return jsonify(ok=True, msg=t("console_sent"))
    except ConsoleError as e:
        return jsonify(ok=False, msg=str(e))
    except OSError as e:
        return jsonify(ok=False, msg=t("console_failed", err=str(e)))


# ---------------------------------------------------------------------------
# Karten (Maps) – eigene Seite, aktive Karte = Map-Wert in der ServerConfig.toml
# ---------------------------------------------------------------------------
_MAP_PATH_RE = re.compile(r"^/levels/[A-Za-z0-9_\-]+/info\.json$")
MAP_MAXLEN = 100  # Backend-Limit von BeamMP für den Map-Wert


def _load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (json.JSONDecodeError, OSError):
            return json.loads(json.dumps(default))
    return json.loads(json.dumps(default))


def _save_json(path, data, mode=0o600):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    os.chmod(tmp, mode)
    os.replace(tmp, path)


def load_custom_maps():
    """Eigene Karten als Liste aus {name, path}."""
    data = _load_json(MAPS_PATH, {"maps": []})
    out = []
    for m in data.get("maps", []):
        p = (m.get("path") or "").strip()
        if p:
            out.append({"name": (m.get("name") or p).strip(), "path": p})
    return out


def save_custom_maps(maps):
    _save_json(MAPS_PATH, {"maps": maps})


def build_map_path(text):
    """Ordnername -> /levels/<ordner>/info.json ; vollständigen Pfad unverändert lassen."""
    text = text.strip()
    if text.startswith("/levels/"):
        return text
    return "/levels/%s/info.json" % text


def all_map_paths():
    return STOCK_MAP_PATHS + [m["path"] for m in load_custom_maps()]


def map_name_for(path):
    for p, label in STOCK_MAPS:
        if p == path:
            return label
    for m in load_custom_maps():
        if m["path"] == path:
            return m["name"]
    return path


def active_map():
    return (settings_lookup().get("Map") or "").strip()


@app.route("/maps")
@login_required
def maps_page():
    active = active_map()
    return render_template(
        "maps.html",
        official=[{"name": n, "path": p} for p, n in STOCK_MAPS],
        custom=load_custom_maps(),
        active=active,
        active_name=map_name_for(active) if active else "",
    )


@app.route("/maps/select", methods=["POST"])
@login_required
def maps_select():
    if not check_csrf():
        flash(t("csrf_invalid"))
        return redirect(url_for("maps_page"))
    path = request.form.get("path", "").strip()
    if path not in all_map_paths():
        flash(t("map_not_found"))
    elif len(path) > MAP_MAXLEN:
        flash(t("map_too_long", n=MAP_MAXLEN))
    else:
        write_settings({"Map": path})
        flash(t("map_selected", name=map_name_for(path)))
    return redirect(url_for("maps_page"))


@app.route("/maps/add", methods=["POST"])
@login_required
def maps_add():
    if not check_csrf():
        flash(t("csrf_invalid"))
        return redirect(url_for("maps_page"))
    raw_code = request.form.get("code", "").strip()
    name = request.form.get("name", "").strip()
    path = build_map_path(raw_code) if raw_code else ""
    if not raw_code or not _MAP_PATH_RE.match(path):
        flash(t("map_code_invalid"))
    elif len(path) > MAP_MAXLEN:
        flash(t("map_too_long", n=MAP_MAXLEN))
    elif path in all_map_paths():
        flash(t("map_exists"))
    else:
        with _maps_lock:
            maps = load_custom_maps()
            maps.append({"name": name or raw_code, "path": path})
            save_custom_maps(maps)
        flash(t("map_added", name=name or raw_code))
    return redirect(url_for("maps_page"))


@app.route("/maps/delete", methods=["POST"])
@login_required
def maps_delete():
    if not check_csrf():
        flash(t("csrf_invalid"))
        return redirect(url_for("maps_page"))
    path = request.form.get("path", "").strip()
    with _maps_lock:
        maps = load_custom_maps()
        if not any(m["path"] == path for m in maps):
            flash(t("map_not_found"))
        else:
            save_custom_maps([m for m in maps if m["path"] != path])
            flash(t("map_deleted"))
    return redirect(url_for("maps_page"))


@app.route("/config", methods=["GET"])
@login_required
def config():
    settings, raw, _active, using_default = read_settings()
    settings = [s for s in settings if s[0] not in LOCKED_OPTIONS and s[0] != "Map"]
    return render_template("config.html", settings=settings, raw=raw,
                           using_default=using_default, cfg_path=CONFIG_FILE,
                           game_port=game_port())


@app.route("/config/save", methods=["POST"])
@login_required
def config_save():
    if not check_csrf():
        flash(t("csrf_invalid"))
        return redirect(url_for("config"))
    settings, _raw, _active, _ud = read_settings()
    new_values = {}
    for k, _old, _kind in settings:
        if k in LOCKED_OPTIONS:
            continue
        if ("opt_" + k) in request.form:
            new_values[k] = request.form.get("opt_" + k, "")
    new_values["Port"] = game_port()
    new_values["ResourceFolder"] = CONF.get("resource_folder", "Resources")
    write_settings(new_values)
    flash(t("config_saved"))
    return redirect(url_for("config"))


@app.route("/config/save-raw", methods=["POST"])
@login_required
def config_save_raw():
    if not check_csrf():
        flash(t("csrf_invalid"))
        return redirect(url_for("config"))
    write_raw(request.form.get("raw", ""))
    enforce_locked()
    flash(t("raw_saved"))
    return redirect(url_for("config"))


@app.route("/mods")
@login_required
def mods_page():
    return render_template("mods.html",
                           client_mods=list_client_mods(), client_path=CLIENT_DIR,
                           plugins=list_plugins(), plugin_path=PLUGIN_DIR)


@app.route("/mods/client/upload", methods=["POST"])
@login_required
def client_upload():
    if not check_csrf():
        flash(t("csrf_invalid"))
        return redirect(url_for("mods_page"))
    d = ensure_client_dir()
    saved = rejected = 0
    for f in request.files.getlist("modfiles"):
        if not f or not f.filename:
            continue
        name = secure_filename(f.filename)
        if name.lower().endswith(".zip"):
            f.save(os.path.join(d, name))
            saved += 1
        else:
            rejected += 1
    if saved:
        flash(t("mod_uploaded", n=saved))
    if rejected:
        flash(t("mod_rejected", n=rejected))
    if not saved and not rejected:
        flash(t("mod_none_selected"))
    return redirect(url_for("mods_page"))


@app.route("/mods/client/toggle", methods=["POST"])
@login_required
def client_toggle():
    if not check_csrf():
        flash(t("csrf_invalid"))
        return redirect(url_for("mods_page"))
    stem = request.form.get("name", "")
    enable = request.form.get("enable") == "1"
    if stem in {m["name"] for m in list_client_mods()} and toggle_client_mod(stem, enable):
        flash(t("mod_enabled" if enable else "mod_disabled", name=stem))
    else:
        flash(t("mod_not_found"))
    return redirect(url_for("mods_page"))


@app.route("/mods/client/delete", methods=["POST"])
@login_required
def client_delete():
    if not check_csrf():
        flash(t("csrf_invalid"))
        return redirect(url_for("mods_page"))
    stem = request.form.get("name", "")
    if stem in {m["name"] for m in list_client_mods()} and delete_client_mod(stem):
        flash(t("mod_deleted", name=stem))
    else:
        flash(t("mod_not_found"))
    return redirect(url_for("mods_page"))


@app.route("/mods/plugin/upload", methods=["POST"])
@login_required
def plugin_upload():
    if not check_csrf():
        flash(t("csrf_invalid"))
        return redirect(url_for("mods_page"))
    f = request.files.get("modzip")
    if not f or not f.filename or not f.filename.lower().endswith(".zip"):
        flash(t("plugin_bad_zip"))
        return redirect(url_for("mods_page"))
    os.makedirs(PLUGIN_DIR, exist_ok=True)
    tmpdir = tempfile.mkdtemp()
    try:
        zpath = os.path.join(tmpdir, "m.zip")
        f.save(zpath)
        try:
            with zipfile.ZipFile(zpath) as z:
                for n in z.namelist():
                    if n.startswith("/") or ".." in n.replace("\\", "/").split("/"):
                        flash(t("plugin_bad_zip"))
                        return redirect(url_for("mods_page"))
                z.extractall(os.path.join(tmpdir, "x"))
        except zipfile.BadZipFile:
            flash(t("plugin_bad_zip"))
            return redirect(url_for("mods_page"))
        # Plugin-Ordner finden: oberste Ordner, die (rekursiv) eine .lua enthalten
        extracted = os.path.join(tmpdir, "x")
        found = []
        top = [d for d in os.listdir(extracted) if os.path.isdir(os.path.join(extracted, d))]
        if top:
            for d in top:
                full = os.path.join(extracted, d)
                if _is_plugin_dir(full):
                    found.append(full)
        # Falls die .lua direkt im ZIP-Wurzelverzeichnis liegt -> als Plugin nach Dateiname
        if not found and any(fn.lower().endswith(".lua") for fn in os.listdir(extracted)):
            name = secure_filename(os.path.splitext(f.filename)[0]) or "plugin"
            target = os.path.join(PLUGIN_DIR, name)
            if os.path.exists(target):
                shutil.rmtree(target, ignore_errors=True)
            shutil.copytree(extracted, target)
            flash(t("plugin_uploaded", names=name))
            return redirect(url_for("mods_page"))
        if not found:
            flash(t("plugin_bad_zip"))
            return redirect(url_for("mods_page"))
        for src in found:
            name = os.path.basename(src)
            target = os.path.join(PLUGIN_DIR, name)
            if os.path.exists(target):
                shutil.rmtree(target, ignore_errors=True)
            shutil.copytree(src, target)
        flash(t("plugin_uploaded", names=", ".join(os.path.basename(s) for s in found)))
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    return redirect(url_for("mods_page"))


@app.route("/mods/plugin/toggle", methods=["POST"])
@login_required
def plugin_toggle():
    if not check_csrf():
        flash(t("csrf_invalid"))
        return redirect(url_for("mods_page"))
    name = request.form.get("name", "")
    enable = request.form.get("enable") == "1"
    if name in {m["name"] for m in list_plugins()} and toggle_plugin(name, enable):
        flash(t("mod_enabled" if enable else "mod_disabled", name=name))
    else:
        flash(t("mod_not_found"))
    return redirect(url_for("mods_page"))


@app.route("/mods/plugin/delete", methods=["POST"])
@login_required
def plugin_delete():
    if not check_csrf():
        flash(t("csrf_invalid"))
        return redirect(url_for("mods_page"))
    name = request.form.get("name", "")
    if name in {m["name"] for m in list_plugins()} and delete_plugin(name):
        flash(t("mod_deleted", name=name))
    else:
        flash(t("mod_not_found"))
    return redirect(url_for("mods_page"))


@app.route("/account", methods=["GET", "POST"])
@login_required
def account():
    if request.method == "POST":
        if not check_csrf():
            flash(t("csrf_invalid"))
            return redirect(url_for("account"))
        me = session["user"]
        cur = request.form.get("current", "")
        new = request.form.get("new", "")
        conf = request.form.get("confirm", "")
        users = load_users()
        if not check_password_hash(users[me]["password_hash"], cur):
            flash(t("pw_wrong_current"))
        elif len(new) < MIN_PW:
            flash(t("pw_too_short", n=MIN_PW))
        elif new != conf:
            flash(t("pw_mismatch"))
        else:
            with _users_lock:
                users = load_users()
                users[me]["password_hash"] = generate_password_hash(new)
                save_users(users)
            flash(t("pw_changed"))
        return redirect(url_for("account"))
    return render_template("account.html")


@app.route("/users")
@login_required
def users_page():
    return render_template("users.html", users=load_users(), me=session["user"])


@app.route("/users/add", methods=["POST"])
@login_required
def users_add():
    if not check_csrf():
        flash(t("csrf_invalid"))
        return redirect(url_for("users_page"))
    name = request.form.get("username", "").strip()
    pw = request.form.get("password", "")
    users = load_users()
    if not USERNAME_RE.match(name):
        flash(t("user_invalid_name"))
    elif name in users:
        flash(t("user_exists"))
    elif len(pw) < MIN_PW:
        flash(t("user_pw_short", n=MIN_PW))
    else:
        with _users_lock:
            users = load_users()
            users[name] = {"password_hash": generate_password_hash(pw)}
            save_users(users)
        flash(t("user_created", name=name))
    return redirect(url_for("users_page"))


@app.route("/users/reset", methods=["POST"])
@login_required
def users_reset():
    if not check_csrf():
        flash(t("csrf_invalid"))
        return redirect(url_for("users_page"))
    name = request.form.get("username", "")
    pw = request.form.get("password", "")
    users = load_users()
    if name not in users:
        flash(t("user_not_found"))
    elif len(pw) < MIN_PW:
        flash(t("user_pw_short", n=MIN_PW))
    else:
        with _users_lock:
            users = load_users()
            users[name]["password_hash"] = generate_password_hash(pw)
            save_users(users)
        flash(t("user_pw_reset", name=name))
    return redirect(url_for("users_page"))


@app.route("/users/delete", methods=["POST"])
@login_required
def users_delete():
    if not check_csrf():
        flash(t("csrf_invalid"))
        return redirect(url_for("users_page"))
    name = request.form.get("username", "")
    me = session["user"]
    users = load_users()
    if name not in users:
        flash(t("user_not_found"))
    elif name == me:
        flash(t("user_delete_self"))
    elif len(users) <= 1:
        flash(t("user_delete_last"))
    else:
        with _users_lock:
            users = load_users()
            users.pop(name, None)
            save_users(users)
        flash(t("user_deleted", name=name))
    return redirect(url_for("users_page"))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=True)
