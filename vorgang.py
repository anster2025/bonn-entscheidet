"""Shared helpers for council proceedings (Vorgänge): server access with retries,
the local index over 2026 agendas, paper groups by Stammnummer, consultations,
submitters and status rules.

Used by collect_2026.py (all of Bonn) and abruf_neu.py.
"""
import re
import time
from collections import defaultdict
from datetime import date, timedelta

import mcp_client as m
from daten import load_jsonl

REFRESH_DAYS_AHEAD = 14  # refetch meetings without agenda up to this many days ahead

REF_RE = re.compile(r"^(\d{6})(?:-(\d{2}))?")


# --- Server access ---------------------------------------------------------------

def call(tool, **args):
    """mcp_client.call with retries on transient server errors (DATABASE_ERROR)."""
    for attempt in range(4):
        try:
            return m.call(tool, **args)
        except RuntimeError as err:
            if attempt == 3 or "fetch failed" not in str(err):
                raise
            time.sleep(5 * (attempt + 1))


def paginate(tool, items_key, limit=100, **args):
    offset = 0
    while offset is not None:
        page = call(tool, limit=limit, offset=offset, **args)
        yield from page.get(items_key, [])
        offset = page.get("next_offset")


# --- Local indexes -------------------------------------------------------------

def stamm(ref):
    mt = REF_RE.match(ref or "")
    return mt.group(1) if mt else None


def org_of(meeting):
    orgs = meeting.get("organizations") or []
    return (orgs[0]["id"], orgs[0]["name"]) if orgs else (None, None)


def build_index():
    """Papers, scope, file->paper map and agenda-derived consultations, all local."""
    papers = {p["reference"]: p for p in load_jsonl("papers_2026.jsonl")}
    meetings = {}
    files = {}           # file id -> paper reference
    meeting_files = {}   # file id -> meeting id (invitation, minutes, TOP packages)
    agenda = defaultdict(list)  # paper reference -> [(meeting, agenda item)]
    horizon = (date.today() + timedelta(days=REFRESH_DAYS_AHEAD)).isoformat()
    for row in load_jsonl("meetings_2026.jsonl"):
        mt = row["meeting"]
        if not row["agenda_items"] and mt["start_date"][:10] <= horizon:
            # snapshot from step 1 predates the agenda; the explicit default
            # argument gives a separate cache entry, so this is fetched once
            row = call("get_meeting", meeting_id=mt["id"], include_non_public=True)
            mt = row["meeting"]
        meetings[mt["id"]] = row
        for key in ("invitation", "verbatim_protocol", "results_protocol"):
            doc = row["documents"].get(key)
            if doc:
                meeting_files[doc["id"]] = mt["id"]
        for doc in row["documents"].get("attachments") or []:
            meeting_files[doc["id"]] = mt["id"]
        for ai in row["agenda_items"]:
            rf = ai.get("resolution_file")
            p = ai.get("paper")
            if rf:
                meeting_files[rf["id"]] = mt["id"]
            if p:
                papers.setdefault(p["reference"], p)
                agenda[p["reference"]].append((mt, ai))
                if rf:
                    files[rf["id"]] = p["reference"]
    scope = {stamm(r) for r in papers} - {None}
    orgs = {o["name"]: o["id"] for o in load_jsonl("organizations.jsonl")}
    return {"papers": papers, "meetings": meetings, "files": files,
            "meeting_files": meeting_files, "agenda": agenda, "scope": scope,
            "orgs": orgs}


# --- Groups, consultations, status ------------------------------------------------

ORIGINATOR_TOKENS = [
    (r"\bCDU\b", "CDU"), (r"\bSPD\b", "SPD"), (r"\bFDP\b", "FDP"), (r"\bBBB\b", "BBB"),
    (r"\bVolt\b", "Volt"), (r"\bGR[ÜU]NE?\w*|\bGrün\w*", "Grüne"),
    (r"\bLinke\b|\bLINKE\b", "Linke"), (r"\bAfD\b", "AfD"), (r"\bBSW\b", "BSW"),
    (r"\bSBI\b", "SBI"), (r"\bKooperation\w*", "Kooperation"),
]
ADMIN_TYPES = ("Beschlussvorlage", "Mitteilungsvorlage", "Stellungnahme der Verwaltung",
               "Informationsbrief", "Dringlichkeitsentscheidung")


def originators(paper, detail):
    """Submitters from the title (parties, citizens) or the paper type (administration)."""
    name, ptype = paper["name"], paper.get("paper_type") or ""
    if ptype.startswith(ADMIN_TYPES):
        found = ["Verwaltung"]
    elif ptype in ("Anregungen und Beschwerden", "Einwohnerfrage") or "Bürgerantrag" in name[:40]:
        found = ["Bürger:innen"]
    else:
        head = re.split(r":| - | – ", name)[0]
        found = []
        for rx, label in ORIGINATOR_TOKENS:
            if re.search(rx, head) and label not in found:
                found.append(label)
        if "Kooperation" in found:  # CDU/SPD/FDP coalition in the 2025-2030 council
            found = [x for x in found if x != "Kooperation"] or ["CDU", "SPD", "FDP"]
        if not found and "nterfraktionell" in head:
            found = ["interfraktionell"]
    orig = (detail or {}).get("originators") or {}
    for o in (orig.get("organizations") or []) + (orig.get("persons") or []):
        if o.get("name") and o["name"] not in found:
            found.append(o["name"])
    return found


def group_papers(st, idx):
    """All papers of a Drucksachengruppe: reference search + local + get_paper links."""
    group, other = {}, {}
    for p in paginate("search_papers", "papers", limit=100, query=st,
                        search_fields=["REFERENCE"], search_mode="name"):
        if stamm(p["reference"]) == st:
            group[p["id"]] = p
    for ref, p in idx["papers"].items():
        if stamm(ref) == st:
            group.setdefault(p.get("id") or f"datei:{ref}", p)
    details, queue = {}, [k for k in group if not k.startswith("datei:")]
    while queue:
        pid = queue.pop()
        d = call("get_paper", paper_id=pid)
        details[pid] = d
        for key in ("superordinated_papers", "subordinated_papers", "related_papers"):
            for q in d.get(key) or []:
                if stamm(q["reference"]) == st and q["id"] not in group:
                    group[q["id"]] = q
                    queue.append(q["id"])
                elif stamm(q["reference"]) != st:
                    other[q["reference"]] = q["name"]
    return group, details, other


def beratungen(paper, idx):
    """Consultations from get_paper_meetings, completed from local 2026 agendas."""
    out, seen = [], set()
    if not paper.get("id"):  # file-only paper: planned Beratungsfolge from the cover page
        return [{"role": b["role"], "authoritative": b["role"] == "Entscheidung",
                 "meeting_id": None, "datum": b["datum"], "gremium_id": b["gremium_id"],
                 "gremium": b["gremium"], "top": None, "top_name": None, "ergebnis": None}
                for b in paper.get("beratungsfolge") or []]
    res = call("get_paper_meetings", paper_id=paper["id"])
    for c in res.get("consultations") or []:
        mt = c.get("meeting") or {}
        ai = c.get("agenda_item") or {}
        oid, oname = org_of(mt)
        out.append({"role": c.get("role"), "authoritative": c.get("authoritative"),
                    "meeting_id": mt.get("id"), "datum": (mt.get("start_date") or "")[:10] or None,
                    "gremium_id": oid, "gremium": oname, "top": ai.get("number"),
                    "top_name": ai.get("name"), "ergebnis": ai.get("result")})
        seen.add(mt.get("id"))
    extra = [(mt, ai) for mt, ai in idx["agenda"].get(paper["reference"], [])
             if mt["id"] not in seen]
    blank = [b for b in out if not b["meeting_id"]]
    for mt, ai in extra:
        oid, oname = org_of(mt)
        local = {"meeting_id": mt["id"], "datum": mt["start_date"][:10], "gremium_id": oid,
                 "gremium": oname, "top": ai.get("number"), "top_name": ai.get("name"),
                 "ergebnis": ai.get("result") or None}
        if len(blank) == 1 and len(extra) == 1:  # the one consultation without meeting
            blank[0].update({k: v for k, v in local.items() if v or not blank[0].get(k)})
        else:
            out.append(dict(local, role=None, authoritative=None))
    out.sort(key=lambda b: b["datum"] or "9999")
    return out


DECIDED = re.compile(r"beschlossen|abgelehnt|zugestimmt", re.I)
SETTLED = re.compile(r"Kenntnis|zurückgezogen|beantwortet|erledigt", re.I)


SIDE_TYPES = ("Stellungnahme der Verwaltung", "Änderungsantrag")


def status(vorlagen):
    """State of the latest main paper; statements and amendments only accompany it."""
    main = [v for v in vorlagen if v["paper_type"] not in SIDE_TYPES] or vorlagen
    latest = ([v for v in main if v["beratungen"]] or main)[-1]
    berat = latest["beratungen"]
    if any(b["authoritative"] and DECIDED.search(b["ergebnis"] or "") for b in berat):
        return "entschieden"
    types = [v["paper_type"] or "" for v in main]
    if any("Mitteilungsvorlage" in t or "Informationsbrief" in t for t in types):
        return "erledigt"
    if any(SETTLED.search(b["ergebnis"] or "") for b in berat):
        return "erledigt"
    if any("Anfrage" in t for t in types) and any(
            v["paper_type"] == "Stellungnahme der Verwaltung" for v in vorlagen):
        return "erledigt"
    return "offen"



def beratungen_2026(paper, idx):
    """Like beratungen, but consultations without meeting are joined to local 2026
    TOPs by agenda item id (the server often omits the meeting, not the TOP)."""
    res = call("get_paper_meetings", paper_id=paper["id"])
    local = {ai["id"]: (mt, ai) for mt, ai in idx["agenda"].get(paper["reference"], [])}
    out, used = [], set()
    for c in res.get("consultations") or []:
        mt = c.get("meeting") or {}
        ai = c.get("agenda_item") or {}
        # TOP ids recur when an item is carried over to a later meeting, so a local
        # TOP counts as this consultation only if the meeting is missing or the same
        hit = local.get(ai.get("id"))
        if hit and not mt.get("id"):
            mt = hit[0]
        if hit and hit[0]["id"] == mt.get("id"):
            used.add(ai["id"])
        oid, oname = org_of(mt)
        out.append({"role": c.get("role"), "authoritative": c.get("authoritative"),
                    "meeting_id": mt.get("id"), "datum": (mt.get("start_date") or "")[:10] or None,
                    "gremium_id": oid, "gremium": oname, "top": ai.get("number"),
                    "top_name": ai.get("name"), "ergebnis": ai.get("result") or None,
                    "agenda_item_id": ai.get("id")})
    seen = {b["meeting_id"] for b in out}
    for aid, (mt, ai) in local.items():
        if aid in used or mt["id"] in seen:
            continue
        oid, oname = org_of(mt)
        out.append({"role": None, "authoritative": None, "meeting_id": mt["id"],
                    "datum": mt["start_date"][:10], "gremium_id": oid, "gremium": oname,
                    "top": ai.get("number"), "top_name": ai.get("name"),
                    "ergebnis": ai.get("result") or None, "agenda_item_id": aid})
    out.sort(key=lambda b: b["datum"] or "9999")
    return out


# --- Status for the city-wide view (collect_2026.py) -----------------------------------

VERTAGT = re.compile(r"vertagt|nicht aufgenommen|nicht behandelt", re.I)
KENNTNIS_TYPES = ("Mitteilungsvorlage", "Informationsbrief")
QUESTION_TYPES = ("Anfrage", "Einwohnerfrage")


def de_date(iso):
    return f"{iso[8:10]}.{iso[5:7]}.{iso[:4]}" if iso else "ohne Datum"


def _at(b):
    return f"{b['gremium'] or 'unbekanntem Gremium'} am {de_date(b['datum'])}"


def is_followup(paper_type):
    """Reports and questions that follow a motion or proposal (e.g. a Mitteilungsvorlage
    on the implementation, a Große Anfrage on the state of an old motion)."""
    t = paper_type or ""
    return t.startswith(KENNTNIS_TYPES) or any(q in t for q in QUESTION_TYPES)


def current_main(dokumente, berat):
    """The current main paper: the latest non-side paper with consultations.

    A later report or question on a motion or proposal (e.g. a Mitteilungsvorlage on
    the implementation, a Große Anfrage on the state of an old motion) does not
    replace it, unless the question is still pending (a consultation marked
    `zukünftig`); reports count as settled anyway (see status_2026)."""
    consulted = {b["reference"] for b in berat}
    mains = [d for d in dokumente if d["paper_type"] not in SIDE_TYPES] or dokumente
    cands = [d for d in mains if d["reference"] in consulted] or mains
    last = cands[-1]
    head = next((d for d in dokumente if REF_RE.fullmatch(d["reference"] or "")), None)
    base = [d for d in cands if not is_followup(d["paper_type"])]
    if not base or not is_followup(last["paper_type"]) or (head and is_followup(head["paper_type"])):
        return last
    pending = any(b.get("zukünftig") for b in berat if b["reference"] == last["reference"])
    if pending and not (last["paper_type"] or "").startswith(KENNTNIS_TYPES):
        return last
    return base[-1]


def status_2026(dokumente, berat, today):
    """(status, reason) of a Vorgang: offen, vertagt, abgeschlossen or unklar.

    dokumente: [{reference, paper_type}] sorted by date; berat: consultations of
    all documents with reference, datum, gremium, authoritative, ergebnis.
    Decisions are read from the current main paper (the latest one with
    consultations); statements and amendments (SIDE_TYPES) only accompany it,
    their results count for `vertagt` and a statement answers a question.
    """
    key = lambda b: b["datum"] or ""
    # a later main paper (new version, follow-up Vorlage) supersedes earlier rounds,
    # but a later report or answered question does not (current_main)
    current = current_main(dokumente, berat)
    later = [d["reference"] for d in dokumente if d["datum"] and current["datum"]
             and d["datum"] > current["datum"] and is_followup(d["paper_type"])]
    main = sorted((b for b in berat if b["reference"] == current["reference"]), key=key)
    upcoming = [b for b in main if not b["ergebnis"] and b["datum"] and b["datum"] >= today]
    unassigned = [b for b in main if not b["ergebnis"] and not b["datum"]]
    nxt = upcoming[0] if upcoming else None

    def closed(b, text):
        if nxt and nxt["datum"] > key(b):
            return "offen", f"{text}; weitere Beratung in {_at(nxt)} geplant."
        if not b["authoritative"] and any(u["authoritative"] for u in unassigned):
            return "offen", f"{text}; die verbindliche Beratung ist noch keiner Sitzung zugeordnet."
        return "abgeschlossen", text + "."

    decided = [b for b in main if b["authoritative"] and DECIDED.search(b["ergebnis"] or "")]
    if decided:
        b = decided[-1]
        return closed(b, f"Verbindlich „{b['ergebnis']}“ in {_at(b)}")
    settled = [b for b in main if SETTLED.search(b["ergebnis"] or "")]
    if settled:
        b = settled[-1]
        return closed(b, f"„{b['ergebnis']}“ in {_at(b)}")
    if (current["paper_type"] or "").startswith(KENNTNIS_TYPES) and not nxt:
        return "abgeschlossen", "Mitteilung der Verwaltung zur Kenntnis, braucht keinen Beschluss."

    results = [b for b in sorted(berat, key=key) if b["ergebnis"] and b["datum"]]
    if results:
        last = [b for b in results if b["datum"] == results[-1]["datum"]]
        # a later past consultation without result (e.g. 240891: adjourned in the BV, then
        # on the agenda of a committee) means the matter moved on; then it is not `vertagt`
        moved_on = any(b["datum"] and last[0]["datum"] < b["datum"] < today and not b["ergebnis"]
                       for b in berat)
        if all(VERTAGT.search(b["ergebnis"]) for b in last) and not moved_on:
            b = last[-1]
            text = f"Zuletzt „{b['ergebnis']}“ in {_at(b)}, seitdem kein Ergebnis"
            return "vertagt", text + (f"; nächste Beratung in {_at(nxt)}." if nxt else ".")
    # checked after `vertagt`: an answer that was not dealt with (e.g. meeting aborted) is pending
    answers = [d["reference"] for d in dokumente if d["paper_type"] == "Stellungnahme der Verwaltung"]
    if any(q in (current["paper_type"] or "") for q in QUESTION_TYPES) and answers:
        return "abgeschlossen", f"Anfrage, beantwortet durch Stellungnahme {answers[-1]}."
    if nxt:
        return "offen", f"Nächste Beratung in {_at(nxt)}."
    after = f"; danach nur Bericht oder Nachfrage ({', '.join(later)})" if later else ""
    missing = [b for b in main if b["authoritative"] and b["datum"] and not b["ergebnis"]]
    if missing:
        # with later reports or questions the decision was probably taken, but is not in the data
        return ("unklar" if later else "offen"), \
            f"Verbindliche Beratung in {_at(missing[-1])} ohne eingetragenes Ergebnis{after}."
    if unassigned:
        return "offen", "Beratung geplant, aber noch keiner Sitzung zugeordnet."
    if results:
        own = [b for b in results if b["reference"] == current["reference"]]
        if later and own:
            b = own[-1]
            return "unklar", (f"Letztes Ergebnis zur Hauptvorlage „{b['ergebnis']}“ in {_at(b)}, "
                              f"keine verbindliche Entscheidung in den Daten{after}.")
        b = results[-1]
        later_open = [x for x in sorted(berat, key=key)
                      if x["datum"] and b["datum"] < x["datum"] < today and not x["ergebnis"]]
        if later_open:
            x = later_open[-1]
            return "offen", (f"Zuletzt „{b['ergebnis']}“ in {_at(b)}; danach beraten in {_at(x)}, "
                             "ohne eingetragenes Ergebnis.")
        return "offen", f"Letztes Ergebnis „{b['ergebnis']}“ in {_at(b)} schließt den Vorgang nicht ab."
    if main or berat:
        b = (main or berat)[-1]
        return "offen", f"Beratung in {_at(b)} ohne eingetragenes Ergebnis."
    return "unklar", "Keine Beratungsdaten, und keine Regel für den Dokumenttyp greift."
