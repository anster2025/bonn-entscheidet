"""Incremental fetch for the citizen page: only what is new or changed since the last run.

The MCP cache (cache/) keeps every answer forever, so a plain rerun sees nothing new. This step asks the
server live (use_cache=False) for exactly the parts that can have changed and overwrites their cache
entries, so the following offline steps (collect_2026.py, einordnung.py) pick them up:

  papers     search_papers (list) published since the last run (2 days overlap) -> data/papers_2026.jsonl
  meetings   search_meetings from 28 days before the last run to 14 days ahead; get_meeting for each
             (with agenda) -> data/meetings_2026.jsonl (rows replaced by meeting id). The mirror links
             agenda items to papers only some days after a meeting, so recent meetings are fetched again
             until the link is there; meanwhile an agenda item is matched to a paper by its exact title.
  papers     get_paper + get_paper_meetings, live, for every new paper, every paper on those agendas and
             every known paper of the same Stammnummer (the cache keys collect_2026.py reads)
  offene     on Sundays (or with --offene) also every paper of all open, postponed or unclear Vorgänge
             (data/stadt/vorgaenge_2026.json): a weekly safety net for anything the window missed

There is no "modified since" filter: changes to existing Vorgänge (results, postponements, new dates)
are found through the meetings in the window. Untouched Vorgänge are not fetched again.
State: data/stadt/abruf_stand.json {"letzter_lauf": "YYYY-MM-DD"}; without it, the newest
published_date in papers_2026.jsonl. Options: --seit YYYY-MM-DD (override the start date), --offene.
"""
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import mcp_client as m
from daten import load_jsonl
from vorgang import stamm

ROOT = Path(__file__).parent
DATA = ROOT / "data"
STAND = DATA / "stadt/abruf_stand.json"
JAHR_ENDE = "2026-12-31"     # the page covers 2026 (papers_2026.jsonl, meetings_2026.jsonl)
UEBERLAPP = 2                # days of papers fetched again before the last run
ZURUECK = 28                 # days of meetings fetched again (agenda ↔ paper links arrive late)
VORAUS = 14                  # days ahead for new agendas


def live_pages(tool, items_key, **args):
    """All pages of a list tool, live (bypassing and refreshing the cache)."""
    offset = 0
    while offset is not None:
        page = m.call(tool, use_cache=False, limit=100, offset=offset, **args)
        yield from page.get(items_key, [])
        offset = page.get("next_offset")


def write_jsonl(path, rows):
    tmp = path.with_suffix(".tmp")
    tmp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    tmp.replace(path)


def startdatum():
    if "--seit" in sys.argv:
        return sys.argv[sys.argv.index("--seit") + 1]
    if STAND.exists():
        return json.loads(STAND.read_text())["letzter_lauf"]
    return max(p["published_date"][:10] for p in load_jsonl("papers_2026.jsonl") if p.get("published_date"))


def main():
    heute = date.today()
    start = date.fromisoformat(startdatum())
    seit = (start - timedelta(days=UEBERLAPP)).isoformat()
    sitzungen_ab = (start - timedelta(days=ZURUECK)).isoformat()
    bis = min((heute + timedelta(days=VORAUS)).isoformat(), JAHR_ENDE)
    offene = "--offene" in sys.argv or heute.weekday() == 6
    print(f"Vorlagen seit {seit}, Sitzungen {sitzungen_ab} bis {bis}{', alle offenen Vorgänge' if offene else ''}",
          file=sys.stderr)

    # 1. neue Vorlagen
    papers = load_jsonl("papers_2026.jsonl")
    bekannt = {p["id"] for p in papers}
    neu = [p for p in live_pages("search_papers", "papers", search_mode="list", published_after=seit,
                                 published_before=JAHR_ENDE, sort="oldest") if p["id"] not in bekannt]
    if neu:
        write_jsonl(DATA / "papers_2026.jsonl", papers + neu)

    # 2. Sitzungen im Fenster, mit Tagesordnung (dieselbe Variante, die build_index und Kalender lesen)
    meetings = {r["meeting"]["id"]: r for r in load_jsonl("meetings_2026.jsonl")}
    fenster = list(live_pages("search_meetings", "meetings", when="any", include_cancelled=True,
                              **{"from": sitzungen_ab, "to": bis}))
    titel = {}  # exakter Titel -> Stammnummer, für Tagesordnungspunkte ohne Verknüpfung
    for p in papers + neu:
        titel.setdefault(" ".join((p.get("name") or "").split()).casefold(), stamm(p["reference"]))
    auf_tagesordnung, per_titel = set(), set()
    for mt in fenster:
        try:
            row = m.call("get_meeting", use_cache=False, meeting_id=mt["id"], include_non_public=True)
        except RuntimeError as err:
            print(f"get_meeting {mt['id']}: {err}", file=sys.stderr)
            continue
        meetings[mt["id"]] = row
        for ai in row.get("agenda_items") or []:
            if ai.get("paper"):
                auf_tagesordnung.add(ai["paper"]["reference"])
            elif (st := titel.get(" ".join((ai.get("name") or "").split()).casefold())):
                per_titel.add(st)
    write_jsonl(DATA / "meetings_2026.jsonl",
                sorted(meetings.values(), key=lambda r: r["meeting"]["start_date"]))

    # 3. betroffene Vorlagen live: neue, auf den Tagesordnungen, und alle bekannten derselben Stammnummer
    staemme = {stamm(p["reference"]) for p in neu} | {stamm(ref) for ref in auf_tagesordnung} | per_titel
    if offene:
        staemme |= {v["stammnummer"] for v in json.loads((DATA / "stadt/vorgaenge_2026.json").read_text())
                    if v["status"] != "abgeschlossen"}
    staemme.discard(None)
    ids = {p["id"] for p in papers + neu if stamm(p["reference"]) in staemme}
    for row in meetings.values():
        for ai in row.get("agenda_items") or []:
            p = ai.get("paper") or {}
            if p.get("id") and stamm(p.get("reference")) in staemme:
                ids.add(p["id"])
    fehler = 0
    for pid in sorted(ids):
        for tool in ("get_paper", "get_paper_meetings"):
            try:
                m.call(tool, use_cache=False, paper_id=pid)
            except RuntimeError as err:
                fehler += 1
                print(f"{tool} {pid}: {err}", file=sys.stderr)

    STAND.parent.mkdir(parents=True, exist_ok=True)
    STAND.write_text(json.dumps({"letzter_lauf": heute.isoformat()}) + "\n")
    print(f"neue Vorlagen {len(neu)}, Sitzungen im Fenster {len(fenster)}, "
          f"davon per Titel zugeordnet {len(per_titel)}, Vorgänge neu abgerufen {len(staemme)} ({len(ids)} Dokumente), "
          f"Fehler {fehler}", file=sys.stderr)


if __name__ == "__main__":
    main()
