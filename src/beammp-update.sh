#!/usr/bin/env bash
# Aktualisiert den BeamMP-Dedicated-Server auf die neueste GitHub-Release-Version.
# Wird vom Panel über beammp-update.service (oneshot) aufgerufen.
# Der Server wird durch die Service-Definition vorher gestoppt.
#
# BeamMP nutzt kein SteamCMD: die passende Binary wird direkt aus den Releases von
# github.com/BeamMP/BeamMP-Server geladen (nach Distribution + Architektur).
set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-$HOME/beammp-server}"
BINARY_NAME="${BINARY_NAME:-BeamMP-Server}"
BIN="$INSTALL_DIR/$BINARY_NAME"
VERSION_FILE="$INSTALL_DIR/.installed_version"
API="https://api.github.com/repos/BeamMP/BeamMP-Server/releases/latest"

echo "[$(date '+%F %T')] BeamMP-Server-Update gestartet."

# --- Distribution / Architektur bestimmen -----------------------------------
. /etc/os-release 2>/dev/null || true
DISTRO_ID="${ID:-ubuntu}"
DISTRO_VER="${VERSION_ID:-}"
ARCH_RAW="$(uname -m)"
case "$ARCH_RAW" in
    x86_64|amd64) ARCH="x86_64" ;;
    aarch64|arm64) ARCH="arm64" ;;
    *) ARCH="x86_64" ;;
esac
echo "System: ${DISTRO_ID} ${DISTRO_VER} (${ARCH})"

# --- Passendes Release-Asset ermitteln (robust gegen Namensänderungen) -------
SEL="$(DISTRO_ID="$DISTRO_ID" DISTRO_VER="$DISTRO_VER" ARCH="$ARCH" API="$API" python3 - <<'PY'
import json, os, re, sys, urllib.request

distro = os.environ["DISTRO_ID"].lower()
ver = os.environ.get("DISTRO_VER", "")
arch = os.environ["ARCH"].lower()

req = urllib.request.Request(os.environ["API"],
    headers={"User-Agent": "beammp-panel", "Accept": "application/vnd.github+json"})
data = json.load(urllib.request.urlopen(req, timeout=15))
tag = (data.get("tag_name") or "").strip()

def bad(name):
    n = name.lower()
    return (n.endswith(".exe") or n.endswith(".sig") or n.endswith(".sha256")
            or "debuginfo" in n or "source" in n or n.endswith(".zip") or n.endswith(".tar.gz"))

def ver_key(name):
    """Höhere Distro-Version als Tie-Breaker (z. B. 24.04 vor 22.04)."""
    cleaned = re.sub(r"x86[_-]?64|amd64|aarch64|arm64", "", name, flags=re.I)
    nums = re.findall(r"(\d+(?:\.\d+)?)", cleaned)
    best = 0.0
    for x in nums:
        try:
            best = max(best, float(x))
        except ValueError:
            pass
    return best

best, best_key = None, (-1, -1.0)
for a in data.get("assets", []):
    name = a["name"]
    if bad(name):
        continue
    n = name.lower()
    if "beammp-server" not in n:
        continue
    score = 0
    # Architektur zählt am meisten – eine falsche Arch läuft schlicht nicht.
    if arch in n:
        score += 4
    elif arch == "x86_64" and not re.search(r"arm64|aarch64", n):
        score += 1  # kein Arch-Suffix -> i. d. R. x86_64
    if distro in n:
        score += 3
    if ver and ver.lower() in n:
        score += 2
    elif ver and ver.split(".")[0] and ver.split(".")[0] in re.findall(r"\d+", n):
        score += 1
    key = (score, ver_key(name))
    if key > best_key:
        best, best_key = a, key

# Notnagel: irgendein passendes x86_64/ubuntu-Asset
if best is None or best_key[0] < 4:
    for a in data.get("assets", []):
        if bad(a["name"]):
            continue
        n = a["name"].lower()
        if "beammp-server" in n and ("ubuntu" in n or "debian" in n) and "arm" not in n:
            best = a
            break

if not best:
    sys.stderr.write("Kein passendes Release-Asset gefunden.\n")
    sys.exit(3)

print(best["browser_download_url"])
print(best["name"])
print(tag)
PY
)"

URL="$(printf '%s\n' "$SEL" | sed -n '1p')"
ASSET="$(printf '%s\n' "$SEL" | sed -n '2p')"
TAG="$(printf '%s\n' "$SEL" | sed -n '3p')"
[ -n "$URL" ] || { echo "Download-URL nicht ermittelbar." >&2; exit 3; }
echo "Neuestes Release: ${TAG:-?} · Asset: $ASSET"

# --- Herunterladen -----------------------------------------------------------
mkdir -p "$INSTALL_DIR"
TMP="$(mktemp "$INSTALL_DIR/.dl.XXXXXX")"
echo "Lade $ASSET ..."
if command -v curl >/dev/null; then
    curl -fSL --retry 3 -o "$TMP" "$URL"
else
    wget -q -O "$TMP" "$URL"
fi
chmod +x "$TMP"

# --- Atomar ersetzen (Backup der alten Binary) -------------------------------
if [ -f "$BIN" ]; then
    cp -a "$BIN" "$BIN.bak" 2>/dev/null || true
fi
mv -f "$TMP" "$BIN"
printf '%s\n' "${TAG#v}" > "$VERSION_FILE"

echo "[$(date '+%F %T')] Update abgeschlossen: $BINARY_NAME = ${TAG:-?}"
