"""Atom feed of what changed in Bonn since the last update: web/feed.xml.

Compares the list index before the update (data/stadt/index_vorher.json, copied by aktualisieren.sh)
with the new web/daten/vorgaenge-index.json and records one entry per change:
  neu      a Vorgang that was not there before
  schritt  new dates among its actual steps (termine), with the status if it changed
  termin   a new or moved next meeting (naechster)
Entries accumulate in data/stadt/feed.json (newest first, at most HISTORIE); the feed shows the newest
FEED. Links point at the page (BONN_RAT_URL, default http://127.0.0.1:8767/). Without a snapshot
(first run) only the feed file is written from the history. Python stdlib only.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).parent
VORHER = ROOT / "data/stadt/index_vorher.json"
INDEX = ROOT / "web/daten/vorgaenge-index.json"
HIST = ROOT / "data/stadt/feed.json"
OUT = ROOT / "web/feed.xml"
BASIS = os.environ.get("BONN_RAT_URL", "http://127.0.0.1:8767/")
HISTORIE, FEED = 300, 100
STATUS = {"offen": "offen", "vertagt": "vertagt", "abgeschlossen": "abgeschlossen", "unklar": "Stand unklar"}


def dmy(iso):
    return f"{iso[8:10]}.{iso[5:7]}.{iso[:4]}"


def lade(path):
    raw = json.loads(path.read_text())
    namen = raw["gremien"]
    out = {}
    for v in raw["vorgaenge"]:
        if v.get("verfahren") == "nichtoeffentlich":
            continue
        v = dict(v)
        v["gremium"] = namen[v["gremium"]] if v.get("gremium") is not None else None
        if v.get("naechster"):
            v["naechster"] = [v["naechster"][0], namen[v["naechster"][1]] if v["naechster"][1] is not None else None]
        out[v["stammnummer"]] = v
    return out


def aenderungen(alt, neu, jetzt):
    """Entries for every change between two loaded indexes."""
    eintraege = []
    def eintrag(v, art, schluessel, titel, text):
        eintraege.append({"id": f"{v['stammnummer']}:{art}:{schluessel}", "zeit": jetzt, "nr": v["stammnummer"],
                          "titel": titel, "text": text, "thema": v.get("thema"), "gremium": v.get("gremium")})
    for nr, v in neu.items():
        a = alt.get(nr)
        wo = f" · {v['gremium']}" if v.get("gremium") else ""
        if not a:
            eintrag(v, "neu", v.get("zuletzt") or "", f"Neu: {v['titel']}",
                    f"{v.get('typ') or 'Vorgang'}{wo} · {STATUS.get(v['status'], v['status'])}. {v.get('status_grund') or ''}".strip())
            continue
        neue_daten = sorted(set(v.get("termine") or []) - set(a.get("termine") or []))
        if neue_daten:
            stand = STATUS.get(v["status"], v["status"])
            wechsel = f" (vorher {STATUS.get(a['status'], a['status'])})" if a["status"] != v["status"] else ""
            eintrag(v, "schritt", neue_daten[-1], f"Neuer Schritt ({stand}): {v['titel']}",
                    f"Neu am {', '.join(dmy(d) for d in neue_daten)}{wo}. Stand: {stand}{wechsel}. {v.get('status_grund') or ''}".strip())
        if v.get("naechster") and v["naechster"] != a.get("naechster"):
            datum, gremium = v["naechster"]
            eintrag(v, "termin", datum, f"Termin {dmy(datum)}{' · ' + gremium if gremium else ''}: {v['titel']}",
                    f"Nächste Beratung am {dmy(datum)}{' im Gremium ' + gremium if gremium else ''}.")
    return eintraege


def atom(eintraege, jetzt):
    def e(x):
        link = f"{BASIS}index.html#vorgaenge/{x['nr']}"
        kat = "".join(f'<category term="{escape(t, {chr(34): "&quot;"})}"/>' for t in (x.get("thema"), x.get("gremium")) if t)
        return (f"<entry><id>urn:bonn-entscheidet:{escape(x['id'])}</id><title>{escape(x['titel'])}</title>"
                f'<link href="{escape(link)}"/><updated>{x["zeit"]}</updated>{kat}'
                f"<summary>{escape(x['text'])}</summary></entry>")
    aktuell = eintraege[0]["zeit"] if eintraege else jetzt
    return ('<?xml version="1.0" encoding="utf-8"?>\n<feed xmlns="http://www.w3.org/2005/Atom">'
            "<title>Bonn entscheidet: Neues aus Rat und Bezirken</title>"
            f'<id>urn:bonn-entscheidet:feed</id><updated>{aktuell}</updated>'
            f'<link rel="self" href="{escape(BASIS)}feed.xml"/><link href="{escape(BASIS)}index.html#vorgaenge"/>'
            "<author><name>Bonn entscheidet</name></author>"
            + "".join(e(x) for x in eintraege[:FEED]) + "</feed>\n")


def main():
    jetzt = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    hist = json.loads(HIST.read_text()) if HIST.exists() else []
    neu = []
    if VORHER.exists():
        neu = aenderungen(lade(VORHER), lade(INDEX), jetzt)
        alte_ids = {x["id"] for x in hist}
        neu = [x for x in neu if x["id"] not in alte_ids]
        hist = (neu + hist)[:HISTORIE]
        HIST.write_text(json.dumps(hist, ensure_ascii=False, indent=1) + "\n")
    OUT.write_text(atom(hist, jetzt))
    print(f"Feed: {len(neu)} neue Einträge, {min(len(hist), FEED)} im Feed → web/feed.xml")


if __name__ == "__main__":
    main()
