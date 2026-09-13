#!/usr/bin/env bash
###############################################################################
#  BeamMP Control Panel – Installer
#
#  Installiert in einem Ubuntu-/Debian-LXC-Container:
#    * BeamMP-Dedicated-Server (BeamNG.drive) als systemd-Service
#      – Binary direkt aus den GitHub-Releases (KEIN SteamCMD nötig)
#    * Ein login-geschütztes Web-Panel (Start/Stop/Neustart, Update, Config, Mods)
#    * Update-Service (lädt die neueste passende Server-Binary)
#
#  Ausführen IM Container als root:   bash install.sh
###############################################################################
set -euo pipefail

# ------------------------- Einstellungen (anpassbar) ------------------------
BMP_USER="beammp"
BMP_HOME="/home/beammp"
INSTALL_DIR="/home/beammp/beammp-server"
PANEL_DIR="/opt/beammp-panel"
BINARY_NAME="BeamMP-Server"
PANEL_PORT="${PANEL_PORT:-80}"          # Port des Web-Panels
GAME_PORT="${GAME_PORT:-30814}"         # BeamMP-Port (TCP+UDP) – beim Installieren festgelegt
CONSOLE_FIFO="$INSTALL_DIR/console.in"

# Panel-Zugangsdaten + AuthKey: aus Umgebungsvariablen oder interaktiv abfragen
PANEL_USER="${PANEL_USER:-}"
PANEL_PASS="${PANEL_PASS:-}"
AUTH_KEY="${AUTH_KEY:-}"                 # optional; kann später im Panel gesetzt werden

msg()  { printf '\n\033[1;36m==>\033[0m \033[1m%s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m[!]\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[x] %s\033[0m\n' "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "Bitte als root ausführen (im LXC-Container)."
command -v apt-get >/dev/null || die "Dieser Installer ist für Debian/Ubuntu-LXC gedacht."

# Zugangsdaten abfragen, falls nicht gesetzt
if [ -z "$PANEL_USER" ]; then
    read -rp "Panel-Benutzername [admin]: " PANEL_USER
    PANEL_USER="${PANEL_USER:-admin}"
fi
if [ -z "$PANEL_PASS" ]; then
    while :; do
        read -rsp "Panel-Passwort: " PANEL_PASS; echo
        [ -n "$PANEL_PASS" ] || { warn "Passwort darf nicht leer sein."; continue; }
        read -rsp "Passwort wiederholen: " P2; echo
        [ "$PANEL_PASS" = "$P2" ] && break || warn "Passwörter stimmen nicht überein."
    done
fi
if [ -z "$AUTH_KEY" ]; then
    echo "BeamMP-AuthKey (kostenlos von https://keymaster.beammp.com)."
    read -rp "AuthKey [leer lassen, später im Panel setzen]: " AUTH_KEY
fi

# ------------------------- Pakete installieren ------------------------------
msg "Aktualisiere Paketquellen und installiere Abhängigkeiten ..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y --no-install-recommends \
    python3 python3-venv python3-pip \
    sudo curl ca-certificates tar xz-utils procps liblua5.3-0

# BeamMP-Laufzeitbibliotheken (Paketnamen unterscheiden sich je nach Release)
apt-get install -y --no-install-recommends zlib1g libssl3 2>/dev/null || true
apt-get install -y --no-install-recommends libcurl4t64 2>/dev/null \
  || apt-get install -y --no-install-recommends libcurl4 2>/dev/null || true

# ------------------------- Benutzer anlegen ---------------------------------
msg "Lege Benutzer '$BMP_USER' an ..."
if ! id "$BMP_USER" >/dev/null 2>&1; then
    useradd -m -d "$BMP_HOME" -s /bin/bash "$BMP_USER"
fi
usermod -aG systemd-journal "$BMP_USER" || true
mkdir -p "$INSTALL_DIR"
chown -R "$BMP_USER":"$BMP_USER" "$BMP_HOME"

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
[ -d "$REPO_DIR/src" ] || die "src/ nicht gefunden – bitte install.sh aus dem Repo-Wurzelverzeichnis ausführen."

# ------------------------- Server-Binary laden ------------------------------
msg "Lade die neueste passende BeamMP-Server-Binary aus GitHub ..."
install -m 0755 "$REPO_DIR/src/beammp-update.sh" "$BMP_HOME/beammp-update.sh"
chown "$BMP_USER":"$BMP_USER" "$BMP_HOME/beammp-update.sh"
sudo -u "$BMP_USER" -H INSTALL_DIR="$INSTALL_DIR" BINARY_NAME="$BINARY_NAME" \
    "$BMP_HOME/beammp-update.sh" || die "Download der Server-Binary fehlgeschlagen."

# ------------------------- ServerConfig.toml erzeugen -----------------------
msg "Erzeuge ServerConfig.toml (Server einmal starten lassen) ..."
sudo -u "$BMP_USER" -H bash -c "cd '$INSTALL_DIR' && timeout 15 './$BINARY_NAME' >/dev/null 2>&1 || true"

msg "Setze Port, AuthKey und Standardwerte ..."
sudo -u "$BMP_USER" -H INSTALL_DIR="$INSTALL_DIR" GAME_PORT="$GAME_PORT" AUTH_KEY="$AUTH_KEY" python3 - <<'PY'
import os, re
d = os.environ["INSTALL_DIR"]
cfg = os.path.join(d, "ServerConfig.toml")
port = os.environ["GAME_PORT"]
authkey = os.environ.get("AUTH_KEY", "").strip()

DEFAULT = f'''[General]
AuthKey = ""
Name = "BeamMP Server"
Description = "BeamMP Server – powered by BeamMP Control Panel"
Tags = "Freeroam"
Map = "/levels/gridmap_v2/info.json"
MaxPlayers = 10
MaxCars = 1
Port = {port}
Private = true
AllowGuests = false
LogChat = true
Debug = false
ResourceFolder = "Resources"
'''

raw = open(cfg, encoding="utf-8", errors="replace").read() if os.path.exists(cfg) else ""
if "[General]" not in raw:
    raw = DEFAULT

def set_key(text, key, value):
    pat = re.compile(r"(?mi)^(\s*%s\s*=\s*).*$" % re.escape(key))
    if pat.search(text):
        return pat.sub(lambda m: m.group(1) + value, text, count=1)
    # unter [General] ergänzen
    return re.sub(r"(?mi)^\[General\]\s*$", "[General]\n%s = %s" % (key, value), text, count=1)

raw = set_key(raw, "Port", port)
raw = set_key(raw, "ResourceFolder", '"Resources"')
if authkey:
    raw = set_key(raw, "AuthKey", '"%s"' % authkey.replace('"', ""))

open(cfg, "w", encoding="utf-8").write(raw)
os.makedirs(os.path.join(d, "Resources", "Client"), exist_ok=True)
os.makedirs(os.path.join(d, "Resources", "Server"), exist_ok=True)
PY
chown -R "$BMP_USER":"$BMP_USER" "$INSTALL_DIR"

# Konsolen-FIFO anlegen (für Server-Befehle aus dem Panel)
sudo -u "$BMP_USER" -H bash -c "[ -p '$CONSOLE_FIFO' ] || { rm -f '$CONSOLE_FIFO'; mkfifo '$CONSOLE_FIFO'; }"

# ------------------------- Panel-Dateien kopieren ---------------------------
msg "Kopiere Panel-Dateien nach $PANEL_DIR ..."
mkdir -p "$PANEL_DIR"
cp -r "$REPO_DIR/src/app.py" "$REPO_DIR/src/i18n.py" \
      "$REPO_DIR/src/templates" "$REPO_DIR/src/static" "$PANEL_DIR/"

# ------------------------- systemd-Units ------------------------------------
msg "Erstelle systemd-Services ..."

cat > /etc/systemd/system/beammp.service <<UNIT
[Unit]
Description=BeamMP Dedicated Server
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=beammp
Group=beammp
WorkingDirectory=$INSTALL_DIR
# Konsolen-FIFO sicherstellen; stdin des Servers an die FIFO hängen (O_RDWR -> kein EOF),
# damit das Panel Konsolen-Befehle senden kann. BeamMP hat kein RCON.
ExecStartPre=/bin/sh -c 'test -p "$CONSOLE_FIFO" || { rm -f "$CONSOLE_FIFO"; mkfifo "$CONSOLE_FIFO"; }'
ExecStart=/bin/sh -c 'exec 3<>"$CONSOLE_FIFO"; exec "$INSTALL_DIR/$BINARY_NAME" <&3'
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
UNIT

cat > /etc/systemd/system/beammp-update.service <<UNIT
[Unit]
Description=BeamMP Server Update (GitHub Release)
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=beammp
Group=beammp
WorkingDirectory=$INSTALL_DIR
Environment=INSTALL_DIR=$INSTALL_DIR
Environment=BINARY_NAME=$BINARY_NAME
# Server vor dem Update stoppen (mit Root-Rechten, daher '+')
ExecStartPre=+/usr/bin/systemctl stop beammp.service
ExecStart=$BMP_HOME/beammp-update.sh
TimeoutStartSec=1800
UNIT

cat > /etc/systemd/system/beammp-panel.service <<UNIT
[Unit]
Description=BeamMP Control Panel (Web UI)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=beammp
Group=beammp
# Erlaubt dem unprivilegierten Dienst, privilegierte Ports (<1024, z. B. 80) zu binden
AmbientCapabilities=CAP_NET_BIND_SERVICE
WorkingDirectory=$PANEL_DIR
Environment=PANEL_CONFIG=$PANEL_DIR/panel.json
ExecStart=$PANEL_DIR/venv/bin/waitress-serve --listen=0.0.0.0:__PANEL_PORT__ app:app
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT
sed -i "s/__PANEL_PORT__/${PANEL_PORT}/" /etc/systemd/system/beammp-panel.service

# ------------------------- Python-venv + Flask ------------------------------
msg "Richte Python-Umgebung für das Panel ein ..."
python3 -m venv "$PANEL_DIR/venv"
"$PANEL_DIR/venv/bin/pip" install --upgrade pip >/dev/null
"$PANEL_DIR/venv/bin/pip" install flask waitress >/dev/null

# ------------------------- panel.json + users.json --------------------------
msg "Erzeuge Panel-Konfiguration und ersten Benutzer ..."
PANEL_USER="$PANEL_USER" PANEL_PASS="$PANEL_PASS" GAME_PORT="$GAME_PORT" \
INSTALL_DIR="$INSTALL_DIR" PANEL_DIR="$PANEL_DIR" CONSOLE_FIFO="$CONSOLE_FIFO" \
"$PANEL_DIR/venv/bin/python" - <<'PY'
import json, os, secrets
from werkzeug.security import generate_password_hash

conf = {
    "secret_key": secrets.token_hex(32),
    "server_dir": os.environ["INSTALL_DIR"],
    "service": "beammp.service",
    "update_service": "beammp-update.service",
    "server_binary": "BeamMP-Server",
    "resource_folder": "Resources",
    "users_path": os.path.join(os.environ["PANEL_DIR"], "users.json"),
    "console_fifo": os.environ["CONSOLE_FIFO"],
    "game_port": int(os.environ["GAME_PORT"]),
}
with open(os.path.join(os.environ["PANEL_DIR"], "panel.json"), "w") as fh:
    json.dump(conf, fh, indent=2)

users = {"users": {
    os.environ["PANEL_USER"]: {"password_hash": generate_password_hash(os.environ["PANEL_PASS"])}
}}
with open(os.path.join(os.environ["PANEL_DIR"], "users.json"), "w") as fh:
    json.dump(users, fh, indent=2)
PY

# ------------------------- Rechte ------------------------------------------
chown -R "$BMP_USER":"$BMP_USER" "$PANEL_DIR"
chmod 600 "$PANEL_DIR/panel.json" "$PANEL_DIR/users.json"

# ------------------------- sudoers-Regel ------------------------------------
msg "Setze eingeschränkte sudo-Rechte für das Panel ..."
SUDO_FILE=/etc/sudoers.d/beammp-panel
cat > "$SUDO_FILE" <<'SUDO'
beammp ALL=(root) NOPASSWD: /usr/bin/systemctl enable --now beammp.service, /usr/bin/systemctl disable --now beammp.service, /usr/bin/systemctl enable beammp.service, /usr/bin/systemctl disable beammp.service, /usr/bin/systemctl restart beammp.service, /usr/bin/systemctl start beammp-update.service
SUDO
chmod 440 "$SUDO_FILE"
visudo -cf "$SUDO_FILE" >/dev/null || die "sudoers-Regel ungültig."

# ------------------------- Services aktivieren ------------------------------
msg "Aktiviere Services ..."
systemctl daemon-reload
# beammp.service wird bewusst NICHT fest aktiviert: ob es nach einem Reboot startet,
# richtet sich nach der letzten Aktion im Panel (Start = Autostart an, Stopp = aus).
systemctl disable beammp.service >/dev/null 2>&1 || true
systemctl enable --now beammp-panel.service

# ------------------------- Zusammenfassung ----------------------------------
IP=$(hostname -I 2>/dev/null | awk '{print $1}')
cat <<DONE

$(printf '\033[1;32m')============================================================$(printf '\033[0m')
  Fertig! Das BeamMP Control Panel ist eingerichtet.

  Web-Panel:   http://${IP:-<container-ip>}:${PANEL_PORT}
  Login:       Benutzer '${PANEL_USER}' + dein gewähltes Passwort

  Server-Port: ${GAME_PORT}  (als TCP UND UDP in Firewall/OPNsense freigeben)

  AuthKey:     $( [ -n "$AUTH_KEY" ] && echo "gesetzt." || echo "NOCH NICHT gesetzt – im Panel unter „Konfiguration“ eintragen (keymaster.beammp.com), sonst kein Eintrag in der öffentlichen Serverliste." )

  Konsole:     BeamMP hat kein RCON. Das Panel sendet Konsolen-Befehle über eine
               FIFO an den Server (nur bei laufendem Server).

  Autostart:   Der Server startet nach einem Reboot nur, wenn er zuletzt lief.
               Start im Panel = Autostart an, Stopp = Autostart aus.
               Der LXC selbst startet über Proxmox (Container-Option onboot=1).

  Der Spielserver ist noch NICHT gestartet – erst im Panel unter
  "Konfiguration" die Einstellungen (v. a. AuthKey) prüfen, dann "Starten".

  Nützliche Befehle:
    systemctl status beammp.service
    journalctl -u beammp.service -f
    systemctl status beammp-panel.service
$(printf '\033[1;32m')============================================================$(printf '\033[0m')
DONE
