#!/usr/bin/env bash
# Bürgerseite "Bonn entscheidet" (ganz Bonn 2026): collect → einordnung → seite → lint.
# Stops at the first error.
#   ./stadt.sh                  only local data and cache/ (no network for einordnung)
#   ./stadt.sh --aktualisieren  einordnung refetches future meetings (new agendas, ~14 days ahead)
#   ./stadt.sh --abruf          einordnung fetches missing cover pages (Deckblätter)
#   ./stadt.sh --zusammenfassung  also ask claude -p (subscription) for content sentences of Vorgänge
#                               with cached document text (zusammenfassung.py run) before einordnung
# Options can be combined.
set -euo pipefail
cd "$(dirname "$0")"

einordnung_args=()
zusammenfassung=0
for arg in "$@"; do
  case "$arg" in
    --aktualisieren|--abruf) einordnung_args+=("$arg") ;;
    --zusammenfassung) zusammenfassung=1 ;;
    *) echo "unbekannte Option: $arg (erlaubt: --aktualisieren, --abruf, --zusammenfassung)" >&2; exit 2 ;;
  esac
done

python3 collect_2026.py
if [ "$zusammenfassung" = 1 ]; then
  python3 zusammenfassung.py run
fi
python3 einordnung.py "${einordnung_args[@]}"
python3 seite.py
python3 lint.py
