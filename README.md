# BeamMP Control Panel

Ein selbstgehostetes, login-geschütztes Web-Panel zur Verwaltung eines
**BeamMP-Dedicated-Servers** (Multiplayer für BeamNG.drive) auf einem
Ubuntu-/Debian-LXC-Container. Start/Stopp/Neustart, Server-Update, Konfiguration
und Mod-Verwaltung im Browser – ohne SSH.

Portiert aus dem Palworld/ARK/ASA/Satisfactory-Control-Panel; gleiche Bedienung,
an die BeamMP-Besonderheiten angepasst.

---

## Funktionen

- **Serversteuerung** – Starten, Stoppen, Neustarten per Klick (via systemd).
- **Server-Update** – lädt die neueste passende Server-Binary direkt aus den
  [GitHub-Releases von BeamMP-Server](https://github.com/BeamMP/BeamMP-Server)
  (automatisch nach Distribution + Architektur ausgewählt). **Kein SteamCMD.**
- **Konfiguration** – `ServerConfig.toml` bequem über Formular bearbeiten
  (Name, Map, MaxPlayers, MaxCars, Private, AllowGuests …) oder im Rohtext.
  `Port` und `ResourceFolder` sind gesperrt, um die Installation nicht zu zerlegen.
- **Konsole** – BeamMP hat **kein RCON**. Das Panel schickt Konsolenbefehle über
  eine FIFO an die Server-Standardeingabe (nur bei laufendem Server).
- **Spielerliste** – best effort aus dem Server-Log ermittelt (kann je nach
  Log-Format unvollständig sein; entsprechend gekennzeichnet).
- **Mods** – Client-Mods (`.zip` in `Resources/Client`, werden automatisch an
  Spieler verteilt) und Server-Plugins (Ordner mit `.lua` in `Resources/Server`)
  hochladen, aktivieren/deaktivieren, löschen.
- **Mehrbenutzer** – mehrere Panel-Konten, Passwörter als Hash gespeichert.
- **Ressourcen** – CPU-, RAM- und Speicherauslastung auf dem Dashboard.
- **Zweisprachig** – Deutsch/Englisch per Klick umschaltbar.
- **Auto-Update des Panels** – optionaler täglicher Timer, der dein Repo pullt.

---

## Voraussetzungen

- Ein **LXC-Container** (Proxmox) oder eine VM mit **Ubuntu 22.04/24.04** oder
  **Debian 12/13** (x86_64 oder arm64).
- Root-Zugriff im Container.
- Ein **BeamMP-AuthKey** (kostenlos): https://keymaster.beammp.com – nötig, damit
  der Server in der öffentlichen Serverliste erscheint. Kann bei der Installation
  oder später im Panel eingetragen werden.
- Freigegebener **Server-Port `30814` als TCP *und* UDP** (Firewall/OPNsense).

---

## Installation

```bash
# im Container als root
git clone https://github.com/Schattenwelt/BeamMP-Control-Panel.git
cd BeamMP-Control-Panel
bash install.sh
```

Der Installer fragt Panel-Benutzer, -Passwort und (optional) den AuthKey ab.
Alternativ ohne Rückfragen:

```bash
PANEL_USER=admin PANEL_PASS='geheim' AUTH_KEY='dein-authkey' bash install.sh
```

Weitere optionale Variablen: `PANEL_PORT` (Standard `80`), `GAME_PORT`
(Standard `30814`).

Nach der Installation:

```
http://<container-ip>:80
```

Der **Spielserver ist zunächst nicht gestartet** – erst im Panel unter
„Konfiguration“ die Einstellungen (v. a. den AuthKey) prüfen, dann „Starten“.

---

## Was der Installer einrichtet

| Komponente | Pfad / Name |
|---|---|
| Server-Benutzer | `beammp` (Home `/home/beammp`) |
| Server-Installation | `/home/beammp/beammp-server` |
| Server-Binary | `/home/beammp/beammp-server/BeamMP-Server` |
| Konfiguration | `/home/beammp/beammp-server/ServerConfig.toml` |
| Ressourcen/Mods | `/home/beammp/beammp-server/Resources/{Client,Server}` |
| Konsolen-FIFO | `/home/beammp/beammp-server/console.in` |
| Panel-Code | `/opt/beammp-panel` |
| systemd-Services | `beammp.service`, `beammp-update.service`, `beammp-panel.service` |

Der Panel-Dienst läuft als unprivilegierter Benutzer `beammp` und darf per
eng gefasster `sudoers`-Regel nur die drei `beammp*`-Services steuern.

---

## Autostart-Verhalten

`beammp.service` wird bewusst **nicht** fest aktiviert. Ob der Server nach einem
Reboot startet, richtet sich nach der letzten Aktion im Panel:

- **Starten** → Autostart an (Server kommt nach Reboot von allein hoch)
- **Stoppen** → Autostart aus

Damit der Container selbst nach einem Proxmox-Neustart läuft, in Proxmox die
Container-Option **„Start at boot“ (`onboot=1`)** setzen.

---

## Panel aktualisieren

Nur den Panel-Code neu ausrollen (Nutzerdaten bleiben erhalten):

```bash
cd BeamMP-Control-Panel && git pull
sudo bash scripts/update.sh
```

Automatisch täglich per Timer:

```bash
sudo bash scripts/setup-autoupdate.sh
# sofort einmal ausführen:
sudo bash scripts/setup-autoupdate.sh --run-now
```

---

## BeamMP-spezifische Hinweise

- **Kein RCON.** Serverbefehle laufen über die Konsole (FIFO → Server-stdin).
  Deshalb funktionieren Konsolenbefehle nur, wenn der Server läuft.
- **Spielerliste** wird aus dem Log geschätzt und ist nicht garantiert vollständig.
- **AuthKey** ist Pflicht für den öffentlichen Serverlisten-Eintrag.
- **Port 30814** muss als **TCP und UDP** offen sein.
- **Updates** kommen aus GitHub-Releases, nicht über Steam.

---

## Lizenz

Siehe [LICENSE](LICENSE).
