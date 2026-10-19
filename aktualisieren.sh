#!/usr/bin/env bash
# Tägliche Aktualisierung der Bürgerseite "Bonn entscheidet": nur Neues und Geändertes vom Server holen,
# Seite offline neu schreiben, Feed der Änderungen erzeugen. Bricht beim ersten Fehler ab.
#   abruf_neu.py      live: neue Vorlagen seit dem letzten Lauf, Sitzungen im Fenster, betroffene Vorgänge
#   collect_2026.py   offline aus cache/ (jetzt mit den frischen Einträgen)
#   einordnung.py     --aktualisieren: Tagesordnungen der nächsten 14 Tage
#   seite.py, feed.py, lint.py
# Läuft täglich über bonn-rat-update.timer; von Hand: ./aktualisieren.sh
set -euo pipefail
cd "$(dirname "$0")"

cp web/daten/vorgaenge-index.json data/stadt/index_vorher.json
python3 abruf_neu.py "$@"
python3 collect_2026.py
python3 einordnung.py --aktualisieren
python3 seite.py
python3 feed.py
python3 lint.py
