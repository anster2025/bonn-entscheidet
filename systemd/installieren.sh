#!/usr/bin/env bash
# Richtet die systemd-Benutzerdienste der Bürgerseite ein: bonn-rat-seite.service (liefert web/ auf
# http://127.0.0.1:8767/ aus) und bonn-rat-update.timer (täglich 06:30 ./aktualisieren.sh).
# Die Vorlagen hier enthalten den Platzhalter @PROJEKT@; das Skript setzt den Pfad dieses Projekts ein
# und schreibt die Units nach ~/.config/systemd/user/. Nach einem Umzug des Ordners erneut ausführen.
set -euo pipefail
cd "$(dirname "$0")"
projekt="$(cd .. && pwd)"
ziel="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
mkdir -p "$ziel"
for unit in bonn-rat-seite.service bonn-rat-update.service bonn-rat-update.timer; do
  rm -f "$ziel/$unit"   # ersetzt auch einen alten Symlink
  sed "s#@PROJEKT@#$projekt#g" "$unit" > "$ziel/$unit"
done
systemctl --user daemon-reload
systemctl --user enable --now bonn-rat-seite.service bonn-rat-update.timer
echo "eingerichtet für $projekt"
