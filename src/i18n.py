#!/usr/bin/env python3
"""Leichtgewichtige DE/EN-Übersetzungen für das BeamMP Control Panel."""

LANGS = ("de", "en")
DEFAULT_LANG = "de"

TRANSLATIONS = {
    # -- Navigation / allgemein --
    "nav_overview": {"de": "Übersicht", "en": "Overview"},
    "nav_config": {"de": "Konfiguration", "en": "Configuration"},
    "nav_mods": {"de": "Mods", "en": "Mods"},
    "nav_users": {"de": "Benutzer", "en": "Users"},
    "nav_account": {"de": "Konto", "en": "Account"},
    "nav_logout": {"de": "Abmelden", "en": "Log out"},
    "save": {"de": "Speichern", "en": "Save"},

    # -- Login --
    "login_title": {"de": "Anmelden", "en": "Sign in"},
    "login_subtitle": {"de": "Melde dich an, um den Server zu verwalten.",
                       "en": "Sign in to manage the server."},
    "username": {"de": "Benutzername", "en": "Username"},
    "password": {"de": "Passwort", "en": "Password"},
    "login_btn": {"de": "Anmelden", "en": "Sign in"},
    "login_bad": {"de": "Benutzername oder Passwort ist falsch.",
                  "en": "Wrong username or password."},

    # -- Dashboard --
    "server_status": {"de": "Serverstatus", "en": "Server status"},
    "boot_on": {"de": "↻ startet nach einem Reboot automatisch",
                "en": "↻ starts automatically after a reboot"},
    "boot_off": {"de": "○ bleibt nach einem Reboot aus",
                 "en": "○ stays off after a reboot"},
    "connect_title": {"de": "Verbinden", "en": "Connect"},
    "connect_label": {"de": "Serveradresse", "en": "Server address"},
    "connect_hint": {"de": "Direktverbindung per IP:Port (TCP+UDP) – "
                           "öffentlich sichtbar nur mit gültigem AuthKey",
                     "en": "Direct connect by IP:port (TCP+UDP) – "
                           "publicly listed only with a valid AuthKey"},
    "connect_copy": {"de": "Kopieren", "en": "Copy"},
    "connect_kind_auto": {"de": "öffentliche IP · automatisch", "en": "public IP · auto-detected"},
    "connect_kind_manual": {"de": "manuelle Adresse", "en": "manual address"},
    "connect_kind_local": {"de": "lokale Adresse", "en": "local address"},
    "connect_local_note": {
        "de": "Öffentliche IP nicht ermittelbar (kein Internet-Egress?) – lokale Adresse "
              "angezeigt. Port {port} als TCP UND UDP in OPNsense/Firewall weiterleiten.",
        "en": "Public IP could not be detected (no internet egress?) – showing the local "
              "address. Forward port {port} as both TCP and UDP in your firewall."},
    "authkey_missing": {
        "de": "Kein AuthKey gesetzt – der Server erscheint nicht in der öffentlichen "
              "Serverliste. AuthKey unter „Konfiguration“ eintragen "
              "(kostenlos von keymaster.beammp.com).",
        "en": "No AuthKey set – the server will not appear in the public server list. "
              "Add your AuthKey under “Configuration” (free from keymaster.beammp.com)."},
    "btn_start": {"de": "Starten", "en": "Start"},
    "btn_restart": {"de": "Neu starten", "en": "Restart"},
    "btn_stop": {"de": "Stoppen", "en": "Stop"},
    "btn_update": {"de": "Aktualisieren", "en": "Update"},
    "confirm_update": {"de": "Update starten? Der Server wird dafür gestoppt.",
                       "en": "Start update? The server will be stopped for it."},
    "server_log": {"de": "Server-Log", "en": "Server log"},
    "auto_refresh": {"de": "aktualisiert automatisch", "en": "auto-refreshing"},
    "update_running": {"de": "Update läuft", "en": "Update running"},
    "loading": {"de": "Lade …", "en": "Loading …"},
    "resources": {"de": "Ressourcen", "en": "Resources"},
    "res_disk": {"de": "Disk", "en": "Disk"},
    "version_installed": {"de": "Installierte Version", "en": "Installed version"},

    # -- Server-Aktionen (Rückmeldungen) --
    "srv_started": {"de": "Server gestartet.", "en": "Server started."},
    "srv_stopped": {"de": "Server gestoppt.", "en": "Server stopped."},
    "srv_restarted": {"de": "Server neu gestartet.", "en": "Server restarted."},
    "update_started": {"de": "Update gestartet – siehe Log unten.",
                       "en": "Update started – see the log below."},
    "update_failed": {"de": "Update fehlgeschlagen: {out}", "en": "Update failed: {out}"},
    "unknown_action": {"de": "Unbekannte Aktion.", "en": "Unknown action."},
    "csrf_invalid": {"de": "Sitzung abgelaufen – bitte erneut versuchen.",
                     "en": "Session expired – please try again."},

    # -- Update-Prüfung --
    "update_check_btn": {"de": "Auf Updates prüfen", "en": "Check for updates"},
    "update_checking": {"de": "Prüfe …", "en": "Checking …"},
    "update_current": {"de": "Server ist aktuell.", "en": "Server is up to date."},
    "update_available": {"de": "Update verfügbar", "en": "Update available"},
    "update_unknown": {"de": "Version nicht ermittelbar.", "en": "Version could not be determined."},

    # -- Konsole (BeamMP hat kein RCON – Befehle gehen über die Server-Konsole) --
    "console_title": {"de": "Server-Konsole", "en": "Server console"},
    "console_hint": {
        "de": "BeamMP hat kein RCON. Befehle werden direkt an die Server-Konsole gesendet "
              "(nur bei laufendem Server). Verfügbare Befehle hängen vom Server und geladenen "
              "Lua-Plugins ab – z. B. „help“, „say <text>“, „list“, „kick <name>“.",
        "en": "BeamMP has no RCON. Commands are sent straight to the server console "
              "(only while running). Available commands depend on the server and any loaded "
              "Lua plugins – e.g. “help”, “say <text>”, “list”, “kick <name>”."},
    "console_ph": {"de": "Befehl, z. B. say Server startet gleich neu",
                   "en": "command, e.g. say server restarting soon"},
    "console_send": {"de": "Senden", "en": "Send"},
    "console_sent": {"de": "Befehl gesendet.", "en": "Command sent."},
    "console_empty": {"de": "Kein Befehl eingegeben.", "en": "No command entered."},
    "console_not_running": {"de": "Server läuft nicht – Konsole nicht erreichbar.",
                            "en": "Server is not running – console unavailable."},
    "console_no_fifo": {
        "de": "Konsolen-Eingabe nicht eingerichtet (FIFO fehlt). Neu installieren oder "
              "„console_fifo“ in panel.json prüfen.",
        "en": "Console input is not set up (FIFO missing). Reinstall or check "
              "“console_fifo” in panel.json."},
    "console_failed": {"de": "Befehl konnte nicht gesendet werden: {err}",
                       "en": "Could not send command: {err}"},

    # -- Spieler (aus dem Log geschätzt) --
    "players_online": {"de": "Spieler online", "en": "Players online"},
    "players_log_note": {"de": "aus dem Server-Log geschätzt", "en": "estimated from the server log"},
    "nobody_online": {"de": "Aktuell niemand erkannt.", "en": "Nobody detected right now."},

    # -- Konfiguration --
    "cfg_notice": {"de": "ServerConfig.toml wurde noch nicht erzeugt – Standardwerte werden "
                         "angezeigt. Datei: {path}",
                   "en": "ServerConfig.toml has not been generated yet – default values are "
                         "shown. File: {path}"},
    "ports_locked": {"de": "Der Port ist fest auf {port} (TCP+UDP) gesetzt und im Panel gesperrt.",
                     "en": "The port is fixed to {port} (TCP+UDP) and locked in the panel."},
    "authkey_help": {
        "de": "AuthKey ist Pflicht für die öffentliche Serverliste – kostenlos unter "
              "keymaster.beammp.com. Ohne Key ist nur Direktverbindung per IP möglich.",
        "en": "AuthKey is required for the public server list – free at keymaster.beammp.com. "
              "Without a key, only direct IP connections work."},
    "tab_settings": {"de": "Einstellungen", "en": "Settings"},
    "tab_raw": {"de": "Rohdatei", "en": "Raw file"},
    "cfg_save_hint": {"de": "Änderungen wirken nach einem Server-Neustart.",
                      "en": "Changes take effect after a server restart."},
    "cfg_save_raw_btn": {"de": "Rohdatei speichern", "en": "Save raw file"},
    "cfg_raw_warn": {"de": "Achtung: Die komplette ServerConfig.toml wird überschrieben.",
                     "en": "Warning: the entire ServerConfig.toml is overwritten."},
    "config_saved": {"de": "Konfiguration gespeichert.", "en": "Configuration saved."},
    "raw_saved": {"de": "Rohdatei gespeichert.", "en": "Raw file saved."},

    # -- Mods (Resources/Client = Client-Mods, Resources/Server = Lua-Plugins) --
    "mods_title": {"de": "Mods", "en": "Mods"},
    "client_head": {"de": "Client-Mods (Resources/Client)", "en": "Client mods (Resources/Client)"},
    "client_what_q": {"de": "Was ist das?", "en": "What is this?"},
    "client_what_a": {
        "de": "ZIP-Mods (Fahrzeuge, Maps, Konfigurationen), die der Server automatisch an "
              "alle Spieler verteilt. Werden in Resources/Client abgelegt.",
        "en": "ZIP mods (vehicles, maps, configs) that the server distributes to every player "
              "automatically. They live in Resources/Client."},
    "server_head": {"de": "Server-Plugins (Resources/Server)", "en": "Server plugins (Resources/Server)"},
    "server_what_q": {"de": "Was ist das?", "en": "What is this?"},
    "server_what_a": {
        "de": "Server-seitige Lua-Plugins (Ordner mit einer .lua-Datei). Laufen nur auf dem "
              "Server, nicht beim Client. Als ZIP hochladen – der Ordner wird entpackt.",
        "en": "Server-side Lua plugins (a folder with a .lua file). They run only on the "
              "server, not on clients. Upload as ZIP – the folder is extracted."},
    "mods_warn": {"de": "Nach Änderungen den Server neu starten, damit sie greifen.",
                  "en": "Restart the server after changes for them to take effect."},
    "mods_upload_label": {"de": "Mod hochladen", "en": "Upload mod"},
    "mods_upload_btn": {"de": "Hochladen", "en": "Upload"},
    "mods_restart_hint": {"de": "Ablageort:", "en": "Location:"},
    "mods_active": {"de": "aktiv", "en": "active"},
    "mods_inactive": {"de": "inaktiv", "en": "inactive"},
    "mods_none": {"de": "Noch keine Mods vorhanden.", "en": "No mods yet."},
    "mod_enable": {"de": "Aktivieren", "en": "Enable"},
    "mod_disable": {"de": "Deaktivieren", "en": "Disable"},
    "mod_delete": {"de": "Löschen", "en": "Delete"},
    "mod_confirm_delete": {"de": "„{name}“ wirklich löschen?", "en": "Really delete “{name}”?"},
    "mod_enabled": {"de": "„{name}“ aktiviert.", "en": "“{name}” enabled."},
    "mod_disabled": {"de": "„{name}“ deaktiviert.", "en": "“{name}” disabled."},
    "mod_deleted": {"de": "„{name}“ gelöscht.", "en": "“{name}” deleted."},
    "mod_not_found": {"de": "Mod nicht gefunden.", "en": "Mod not found."},
    "mod_uploaded": {"de": "{n} Datei(en) hochgeladen.", "en": "Uploaded {n} file(s)."},
    "mod_rejected": {"de": "{n} Datei(en) abgelehnt (nur .zip erlaubt).",
                     "en": "{n} file(s) rejected (only .zip allowed)."},
    "mod_none_selected": {"de": "Keine passende Datei ausgewählt.", "en": "No suitable file selected."},
    "plugin_bad_zip": {"de": "Ungültiges ZIP – kein Plugin-Ordner mit .lua gefunden.",
                       "en": "Invalid ZIP – no plugin folder with a .lua file found."},
    "plugin_uploaded": {"de": "Plugin(s) hochgeladen: {names}", "en": "Plugin(s) uploaded: {names}"},

    # -- Konto --
    "change_password": {"de": "Passwort ändern", "en": "Change password"},
    "logged_in_as": {"de": "Angemeldet als", "en": "Logged in as"},
    "current_password": {"de": "Aktuelles Passwort", "en": "Current password"},
    "new_password": {"de": "Neues Passwort", "en": "New password"},
    "repeat_new_password": {"de": "Neues Passwort wiederholen", "en": "Repeat new password"},
    "pw_wrong_current": {"de": "Aktuelles Passwort ist falsch.", "en": "Current password is wrong."},
    "pw_too_short": {"de": "Neues Passwort muss mindestens {n} Zeichen haben.",
                     "en": "New password must be at least {n} characters."},
    "pw_mismatch": {"de": "Die neuen Passwörter stimmen nicht überein.",
                    "en": "The new passwords do not match."},
    "pw_changed": {"de": "Passwort geändert.", "en": "Password changed."},

    # -- Benutzerverwaltung --
    "users_add_title": {"de": "Benutzer hinzufügen", "en": "Add user"},
    "users_add_pw_ph": {"de": "Passwort", "en": "Password"},
    "users_add_btn": {"de": "Hinzufügen", "en": "Add"},
    "users_equal_note": {"de": "Alle Benutzer sind gleichberechtigt.",
                         "en": "All users have equal rights."},
    "users_you": {"de": "du", "en": "you"},
    "users_new_pw_ph": {"de": "Neues Passwort", "en": "New password"},
    "users_reset_btn": {"de": "Zurücksetzen", "en": "Reset"},
    "users_delete_btn": {"de": "Löschen", "en": "Delete"},
    "users_delete_confirm": {"de": "Benutzer „{name}“ wirklich löschen?",
                             "en": "Really delete user “{name}”?"},
    "user_invalid_name": {"de": "Ungültiger Benutzername (2–32 Zeichen: A–Z, 0–9, _ . -).",
                          "en": "Invalid username (2–32 chars: A–Z, 0–9, _ . -)."},
    "user_exists": {"de": "Benutzer existiert bereits.", "en": "User already exists."},
    "user_pw_short": {"de": "Passwort muss mindestens {n} Zeichen haben.",
                      "en": "Password must be at least {n} characters."},
    "user_created": {"de": "Benutzer „{name}“ angelegt.", "en": "User “{name}” created."},
    "user_not_found": {"de": "Benutzer nicht gefunden.", "en": "User not found."},
    "user_pw_reset": {"de": "Passwort von „{name}“ zurückgesetzt.",
                      "en": "Password for “{name}” has been reset."},
    "user_delete_self": {"de": "Du kannst dich nicht selbst löschen.",
                         "en": "You cannot delete yourself."},
    "user_delete_last": {"de": "Der letzte Benutzer kann nicht gelöscht werden.",
                         "en": "The last user cannot be deleted."},
    "user_deleted": {"de": "Benutzer „{name}“ gelöscht.", "en": "User “{name}” deleted."},

    # -- Sprachnamen --
    "de": {"de": "Deutsch", "en": "German"},
    "en": {"de": "Englisch", "en": "English"},
}


def translate(lang, key, **kw):
    entry = TRANSLATIONS.get(key)
    if not entry:
        return key
    text = entry.get(lang) or entry.get(DEFAULT_LANG) or key
    if kw:
        try:
            return text.format(**kw)
        except (KeyError, IndexError, ValueError):
            return text
    return text
