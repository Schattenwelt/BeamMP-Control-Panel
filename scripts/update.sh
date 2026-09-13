#!/usr/bin/env bash
# Aktualisiert nur den Panel-Code (app.py, i18n.py, Templates, CSS, beammp-update.sh)
# aus dem ausgecheckten Repo und startet das Panel neu. Nutzerdaten bleiben unangetastet.
set -euo pipefail
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PANEL_DIR="/opt/beammp-panel"; BMP_USER="beammp"; BMP_HOME="/home/beammp"
[ "$(id -u)" -eq 0 ] || { echo "Bitte als root ausführen." >&2; exit 1; }
[ -d "$PANEL_DIR" ] || { echo "$PANEL_DIR fehlt – zuerst install.sh ausführen." >&2; exit 1; }
cp -r "$REPO_DIR/src/app.py" "$REPO_DIR/src/i18n.py" \
      "$REPO_DIR/src/templates" "$REPO_DIR/src/static" "$PANEL_DIR/"
install -m 0755 "$REPO_DIR/src/beammp-update.sh" "$BMP_HOME/beammp-update.sh"
chown -R "$BMP_USER":"$BMP_USER" "$PANEL_DIR" "$BMP_HOME/beammp-update.sh"
chmod 600 "$PANEL_DIR/panel.json" "$PANEL_DIR/users.json" 2>/dev/null || true
systemctl restart beammp-panel.service
echo "Panel aktualisiert und neu gestartet."
