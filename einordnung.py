"""Einordnung: every Vorgang 2026 as a flowchart model for the citizen page.

Input: data/stadt/vorgaenge_2026.json (collect_2026.py), data/verfahren.json,
data/meetings_2026.jsonl, data/organizations.jsonl,
data/zusammenfassung.json (zusammenfassung.py) and the cover pages (Deckblatt)
of the documents from cache/get_file_text.

Steps
  deckblatt  the "Beratungsfolge" table on the cover page of each document
             (planned bodies, dates, roles) -> beratungsfolge_plan
  kalender   next concrete meeting per body from meetings_2026.jsonl
  verfahren  procedure id from data/verfahren.json (or einordnung_extra)
  knoten     eingang, documents, consultations, current step, expected steps
  mitwirken  rules from verfahren.json "einfluss_regeln"
  worum      1–2 sentences from type, submitters and deciding body (einordnung_extra.worum);
             worum_ki: content sentence by zusammenfassung.py, where the text is cached

Writes web/daten/vorgaenge-index.json, web/daten/vorgang/<stammnummer>.json
(only when changed; stale files are deleted) and data/stadt/einordnung_bericht.md.

Options
  --abruf         fetch missing cover pages from the server (get_file_text);
                  files without extracted text are noted in
                  cache/get_file_text_ohne_text.json and retried on the next --abruf
  --aktualisieren refetch future meetings (use_cache=False); agendas appear
                  about 14 days ahead
Without options the run uses only local data and the cache (no network).
"""
import hashlib
import json
import random
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

import mcp_client as m
import vorgang
from recht import rechtsgrundlagen
from daten import load_jsonl, write_if_changed

ROOT = Path(__file__).parent
SRC = ROOT / "data/stadt/vorgaenge_2026.json"
VERFAHREN = ROOT / "data/verfahren.json"
ZUSAMMENFASSUNG = ROOT / "data/zusammenfassung.json"  # zusammenfassung.py merge: {stammnummer: {satz, reference}}
WEB_DATA = ROOT / "web/daten"
INDEX_OUT = WEB_DATA / "vorgaenge-index.json"
DETAIL_DIR = WEB_DATA / "vorgang"
REPORT = ROOT / "data/stadt/einordnung_bericht.md"
NO_TEXT = m.CACHE / "get_file_text_ohne_text.json"
COVER_CHARS = 6000  # the cover page with the Beratungsfolge is at the start


# --- Server cache ------------------------------------------------------------------

def cache_path(tool, **args):
    key = hashlib.sha1(json.dumps([tool, args], sort_keys=True).encode()).hexdigest()
    return m.CACHE / tool / f"{key}.json"


def cached(tool, **args):
    """A cached server answer or None; never touches the network."""
    p = cache_path(tool, **args)
    return json.loads(p.read_text()) if p.exists() else None


def paper_id(doc):
    url = doc.get("web_url") or ""
    return url.rsplit("/", 1)[-1] if "/papers/" in url else None


def main_file(doc):
    pid = paper_id(doc)
    d = cached("get_paper", paper_id=pid) if pid else None
    return (d or {}).get("main_file") or {}


def cover_text(file_id):
    res = cached("get_file_text", file_id=file_id, max_chars=COVER_CHARS)
    return (res or {}).get("text")


def haupttext(v):
    """(reference, text) of the main document whose text is cached: the original paper, else the
    current main paper, else the first paper with text; (None, None) without any cached text."""
    st = v["stammnummer"]
    head = next((d for d in v["dokumente"] if d["reference"] == st), v["dokumente"][0])
    cur = vorgang.current_main(v["dokumente"], v["beratungen"])
    for d in [head, cur, *v["dokumente"]]:
        f = main_file(d)
        text = cover_text(f["id"]) if f.get("id") else None
        if text:
            return d["reference"], text
    return None, None


def wants_cover(v):
    """Documents whose planned Beratungsfolge matters: open or adjourned Vorgänge,
    and any document with a consultation not yet assigned to a meeting."""
    unassigned = {b["reference"] for b in v["beratungen"] if not b["datum"]}
    return [d for d in v["dokumente"]
            if v["status"] in ("offen", "vertagt") or d["reference"] in unassigned]


def fetch_covers(vorgaenge):
    """Fetch cover texts for all wanted documents; misses go to NO_TEXT."""
    try:
        missing = json.loads(NO_TEXT.read_text())
    except (OSError, ValueError):
        missing = {}
    todo = []
    for v in vorgaenge:
        for d in wants_cover(v):
            f = main_file(d)
            if f.get("id") and not cover_text(f["id"]):
                todo.append(f["id"])
    todo = sorted(set(todo))
    t0, got, failed = time.monotonic(), 0, 0
    for i, fid in enumerate(todo, 1):
        try:
            m.call("get_file_text", file_id=fid, max_chars=COVER_CHARS)
            got += 1
            missing.pop(fid, None)
        except RuntimeError as err:
            if "No extracted text" in str(err):
                missing[fid] = date.today().isoformat()
            else:
                failed += 1
        except Exception:  # network trouble: retried next time
            failed += 1
        if i % 25 == 0 or i == len(todo):
            print(f"\rget_file_text {i}/{len(todo)} ({time.monotonic() - t0:.0f} s, "
                  f"{got} mit Text, {len(missing)} ohne Text, {failed} Fehler)",
                  end="", file=sys.stderr, flush=True)
    print(file=sys.stderr)
    NO_TEXT.parent.mkdir(parents=True, exist_ok=True)
    NO_TEXT.write_text(json.dumps(dict(sorted(missing.items())), indent=0) + "\n")




# --- Deckblatt: planned Beratungsfolge ------------------------------------------------

ROLES = r"Entscheidung|Empfehlung|Anhörung|Kenntnisnahme|Vorberatung|Anregung|Genehmigung"
ROW_RE = re.compile(rf"^(?P<g>.*?)\s*(?P<d>\d{{2}}\.\d{{2}}\.\d{{4}})?\s*(?P<r>{ROLES})$")


def norm(name):
    return re.sub(r"[\s\-–]+", " ", (name or "").replace("­", "")).strip().lower()


class Orgs:
    """Body names (organizations.jsonl) -> id, name, classification."""

    def __init__(self):
        self.rows = load_jsonl("organizations.jsonl")
        self.by_id = {o["id"]: o for o in self.rows}
        self.by_norm = {norm(o["name"]): o for o in self.rows}

    def find(self, name):
        n = norm(name)
        if not n:
            return None
        if n in self.by_norm:
            return self.by_norm[n]
        hits = [o for k, o in self.by_norm.items() if k.startswith(n) or n.startswith(k)]
        return hits[0] if len(hits) == 1 else None

    def from_meeting_name(self, name):
        """'Sitzung des Ausschusses für Kinder-, Jugend und Familie' -> organization."""
        n = norm(re.sub(r"^(Gemeinsame )?Sitzung (des|der) ", "", name or ""))
        n = re.sub(r"\bausschusses\b", "ausschuss", n).replace("beirates", "beirat")
        n = n.replace("kinder , jugend", "kinder, jugend")
        hits = [o for k, o in self.by_norm.items() if k == n or (len(k) > 8 and n.startswith(k))]
        return max(hits, key=lambda o: len(o["name"])) if hits else None


def parse_beratungsfolge(text, orgs):
    """Rows of the cover table: [{gremium, gremium_id, gremienart, datum, rolle}].

    The table follows the word "Beratungsfolge"; body names may wrap over
    several lines, date and role close a row. Reading stops at the first block
    of lines that does not end in a role."""
    if not text or "Beratungsfolge" not in text:
        return []
    lines = [ln.strip() for ln in text.split("Beratungsfolge", 1)[1].splitlines()]
    rows, buf = [], []
    for ln in lines:
        if not ln:
            continue
        buf.append(ln)
        mt = ROW_RE.match(" ".join(buf))
        if mt and (mt["d"] or orgs.find(mt["g"])) and mt["g"]:
            o = orgs.find(mt["g"])
            d = mt["d"]
            rows.append({"gremium": o["name"] if o else re.sub(r"\s+", " ", mt["g"]),
                         "gremium_id": o["id"] if o else None,
                         "gremienart": o.get("classification") if o else None,
                         "datum": f"{d[6:]}-{d[3:5]}-{d[:2]}" if d else None,
                         "rolle": mt["r"]})
            buf = []
        elif len(buf) > 4:
            break
    return rows


# --- Calendar ----------------------------------------------------------------------

class Kalender:
    """Meetings of 2026 by body; cached refreshed agendas show where a paper is listed."""

    def __init__(self, orgs, today, refresh=False):
        self.today = today
        self.by_org = defaultdict(list)
        self.on_agenda = defaultdict(list)  # paper reference -> [meeting]
        for row in load_jsonl("meetings_2026.jsonl"):
            mt = row["meeting"]
            datum = mt["start_date"][:10]
            o = (mt.get("organizations") or [None])[0] or orgs.from_meeting_name(mt["name"])
            if datum >= today:
                if refresh:
                    try:
                        m.call("get_meeting", use_cache=False, meeting_id=mt["id"],
                               include_non_public=True)
                    except Exception as err:  # keep the cached state
                        print(f"get_meeting {mt['id']}: {err}", file=sys.stderr)
                fresh = cached("get_meeting", meeting_id=mt["id"], include_non_public=True)
                if fresh:
                    row = fresh
            entry = {"id": mt["id"], "datum": datum, "gremium": o["name"] if o else mt["name"],
                     "gremium_id": o["id"] if o else None, "sitzung_url": mt.get("web_url"),
                     "einladung_pdf": ((row.get("documents") or {}).get("invitation") or {}).get("access_url"),
                     "abgesagt": "abgesagt" in (mt.get("meeting_state") or "").lower()}
            if entry["gremium_id"]:
                self.by_org[entry["gremium_id"]].append(entry)
            for ai in row.get("agenda_items") or []:
                ref = (ai.get("paper") or {}).get("reference")
                if ref and datum >= today:
                    self.on_agenda[ref].append(dict(entry, top=ai.get("number")))
        for v in self.by_org.values():
            v.sort(key=lambda e: e["datum"])

    def meeting(self, gremium_id, datum):
        return next((e for e in self.by_org.get(gremium_id, []) if e["datum"] == datum), None)

    def next(self, gremium_id, after=None):
        after = max(after or "", self.today)
        return next((e for e in self.by_org.get(gremium_id, [])
                     if e["datum"] >= after and not e["abgesagt"]), None)


# --- Procedures ----------------------------------------------------------------------

SIDE_ST, SIDE_AA = "Stellungnahme der Verwaltung", "Änderungsantrag"
BAULEIT_RE = re.compile(r"Bebauungsplan|Satzungsbeschluss|Aufstellungsbeschluss|Offenlage|"
                        r"Flächennutzungsplan|frühzeitige[nr]? (Öffentlichkeits)?[Bb]eteiligung", re.I)
BAULEIT_SICHER = re.compile(r"Bebauungsplan|Flächennutzungsplan(änderung)?\b.*(Aufstellung|"
                            r"Offenlage|Satzung|Beteiligung|Änderung)", re.I)

# step ids per procedure: where a node of the Vorgang sits in the template
STEPS = {
    "antrag-rat": {"eingang": "a1", "st": "a4", "aa": "a5", "Entscheidung|Rat": "a6",
                   "ende": "a7", "ziel": ["a6"]},
    "antrag-bv": {"eingang": "v1", "st": "v4", "Entscheidung|Bezirksvertretungen": "v5",
                  "Anregung|Bezirksvertretungen": "v6", "Entscheidung|Rat": "v7",
                  "Entscheidung|Ratsgremien": "v7", "ende": "umsetzung", "ziel": ["v5"]},
    "dringlichkeitsantrag": {"eingang": "d1", "ende": "umsetzung", "ziel": ["d4"]},
    "beschlussvorlage": {"eingang": "b1", "aa": "b4", "Anhörung|Bezirksvertretungen": "b3",
                         "Empfehlung|Ratsgremien": "b5", "Entscheidung|Rat": "b6",
                         "ende": "b7", "ziel": ["b6"]},
    "ausschuss-entscheidung": {"eingang": "eingang-verwaltung", "Entscheidung|Ratsgremien": "e3",
                               "ende": "e6", "ziel": ["e3"]},
    "bauleitplanung": {"eingang": "p2", "Anhörung|Bezirksvertretungen": "p6",
                       "Empfehlung|Bezirksvertretungen": "p8", "Empfehlung|Ratsgremien": "p9",
                       "Entscheidung|Rat": "p10", "ende": "p11", "ziel": ["p10"]},
    "buergerantrag": {"eingang": "u1", "st": "u3", "Entscheidung|Bezirksvertretungen": "u5",
                      "Entscheidung|Ratsgremien": "u6", "Entscheidung|Rat": "u7",
                      "ende": "u8", "ziel": ["u5"]},
    "einwohnerfrage": {"eingang": "f1", "st": "f2", "Kenntnisnahme|Bezirksvertretungen": "f3",
                       "ziel": ["f2", "f3"]},
    "grosse-anfrage": {"eingang": "g1", "st": "g3", "Kenntnisnahme|*": "g4", "ende": "g5",
                       "ziel": ["g3", "g4"]},
    "kleine-anfrage": {"eingang": "k1", "st": "k3", "ziel": ["k3"]},
    "dringlichkeitsentscheidung": {"eingang": "x2", "Genehmigung|Rat": "x4",
                                   "Genehmigung|Bezirksvertretungen": "x5", "ziel": ["x4"]},
    "mitteilung": {"eingang": "m1", "Kenntnisnahme|*": "m2", "ziel": []},
    "nichtoeffentlich": {"eingang": "n1", "*|*": "n2", "ziel": []},
}


class Wissen:
    """Procedures, steps and roles from data/verfahren.json."""

    def __init__(self):
        self.src = json.loads(VERFAHREN.read_text())
        extra = self.src["einordnung_extra"]
        self.verfahren = {v["id"]: v for v in self.src["verfahren"] + extra["verfahren"]}
        self.steps = {}
        for v in self.verfahren.values():
            for s in v["schritte"]:
                self.steps[(v["id"], s["id"])] = s
        self.generic = extra["schritte"]
        self.rollen = extra["rollen"]
        self.worum = extra["worum"]
        self.regeln = self.src["einfluss_regeln"]

    def step(self, vid, sid):
        if not sid:
            return None
        s = self.steps.get((vid, sid)) or self.generic.get(sid)
        return dict(s, id=sid) if s else None

    def rolle(self, rolle, art):
        for r in self.rollen:
            if r["rolle"] in (rolle, "*") and r["gremienart"] in (art, "*"):
                if r["rolle"] == "*" and rolle in {x["rolle"] for x in self.rollen}:
                    continue
                return r
        return self.rollen[-1]

    def recht(self, beleg):
        return {"rechtsgrundlagen": rechtsgrundlagen(beleg), "beleg": beleg or None}


def assign(v, plan_arts):
    """(verfahren id, sicherheit, grund) from type, submitters and kinds of bodies."""
    typ = v["typ"] or ""
    arts = {b["gremienart"] for b in v["beratungen"] if b["gremienart"]} | plan_arts
    entsch = {b["gremienart"] for b in v["beratungen"]
              if b["rolle"] == "Entscheidung" and b["gremienart"]}
    titel = v["titel"] or ""
    if typ in ("Anregungen und Beschwerden",) or typ.startswith("Bürgerantrag"):
        return "buergerantrag", "hoch", f"Dokumenttyp „{typ}“ (Bürgerantrag nach § 24 GO NRW)."
    if typ == "Einwohnerfrage":
        return "einwohnerfrage", "hoch", "Dokumenttyp „Einwohnerfrage“."
    if typ == "Große Anfrage":
        return "grosse-anfrage", "hoch", "Dokumenttyp „Große Anfrage“."
    if typ == "Kleine Anfrage":
        return "kleine-anfrage", "hoch", "Dokumenttyp „Kleine Anfrage“."
    if typ.startswith("Dringlichkeitsentscheidung") or typ.startswith("Eilentscheidung"):
        return "dringlichkeitsentscheidung", "hoch", f"Dokumenttyp „{typ}“."
    if typ in ("Mitteilungsvorlage", "Informationsbrief"):
        return "mitteilung", "hoch", f"Dokumenttyp „{typ}“: nur zur Kenntnis."
    if typ.startswith("Tagesordnungspunkte in nichtöffentlicher"):
        return "nichtoeffentlich", "hoch", "Platzhalter für nichtöffentliche Tagesordnungspunkte."
    if typ == "Dringlichkeitsantrag":
        return "dringlichkeitsantrag", "hoch", "Dokumenttyp „Dringlichkeitsantrag“."
    if typ in ("Antrag", SIDE_AA):
        sure = "hoch" if typ == "Antrag" else "mittel"
        if arts and arts <= {"Bezirksvertretungen"}:
            return "antrag-bv", sure, "Antrag, beraten nur in Bezirksvertretungen."
        if arts & {"Rat", "Ratsgremien"}:
            return "antrag-rat", sure, "Antrag mit Beratung in Rat oder Ausschuss."
        if re.search(r"Bezirks(fraktion|verordnete|vertretung)|\bBV\b", titel):
            return "antrag-bv", "mittel", "Antrag ohne bekanntes Gremium; der Titel nennt die Bezirksebene."
        return "antrag-rat", "mittel", "Antrag ohne bekanntes Gremium; angenommen: Rat oder Ausschuss."
    if typ.startswith("Beschlussvorlage"):
        if BAULEIT_RE.search(titel):
            sure = "hoch" if BAULEIT_SICHER.search(titel) else "mittel"
            return "bauleitplanung", sure, "Beschlussvorlage zur Bauleitplanung (Titel)."
        if entsch and entsch <= {"Ratsgremien"}:
            return ("ausschuss-entscheidung", "hoch",
                    "Beschlussvorlage, verbindlich entscheidet ein Ausschuss.")
        if "Rat" in entsch:
            return "beschlussvorlage", "hoch", "Beschlussvorlage, verbindlich entscheidet der Rat."
        if entsch and entsch <= {"Bezirksvertretungen"}:
            return ("beschlussvorlage", "mittel",
                    "Beschlussvorlage, die Bezirksvertretung entscheidet selbst (Sache bleibt im Bezirk).")
        return "beschlussvorlage", "mittel", "Beschlussvorlage; das entscheidende Gremium ist noch nicht bekannt."
    return "beschlussvorlage", "mittel", f"Kein eigenes Verfahren für Dokumenttyp „{typ}“."


# --- Nodes ---------------------------------------------------------------------------

ANSWER_STEPS = {"g3", "k3", "f2"}  # the administration answers a question
QUESTION_PROCS = {"grosse-anfrage", "kleine-anfrage", "einwohnerfrage"}
ROLE_RANK = {"Kenntnisnahme": 0, "Anhörung": 1, "Vorberatung": 2, "Empfehlung": 2, "Anregung": 3,
             "Entscheidung": 4, "Genehmigung": 5}
ARTICLE = [(r"^Rat$", "der", "im"), (r"^Bezirksvertretung", "die", "in der"),
           (r"[Aa]usschuss", "der", "im"), (r"[Bb]eirat", "der", "im"), (r"[Kk]ommission", "die", "in der")]


def nom(g):
    for rx, art, _ in ARTICLE:
        if re.search(rx, g or ""):
            return f"{art} {g}"
    return g or "ein Gremium"


def de(iso):
    return f"{iso[8:10]}.{iso[5:7]}.{iso[:4]}" if iso else None


def gruppe(ergebnis, future=False):
    e = ergebnis or ""
    if re.search(r"vertagt|nicht aufgenommen|nicht behandelt", e, re.I):
        return "vertagt"
    if re.search(r"abgelehnt", e, re.I):
        return "abgelehnt"
    if re.search(r"beschlossen|zugestimmt", e, re.I):
        return "beschlossen"
    if re.search(r"Kenntnis", e, re.I):
        return "zur Kenntnis"
    if re.search(r"erledigt|zurückgezogen|beantwortet", e, re.I):
        return "erledigt"
    return "offen"


def doc_kind(d, head_ref):
    if d["reference"] == head_ref:
        return "eingang"
    if d["paper_type"] == SIDE_ST:
        return "stellungnahme"
    if d["paper_type"] == SIDE_AA:
        return "aenderungsantrag"
    return "folgevorlage"


KIND_TITLE = {"stellungnahme": "Stellungnahme der Verwaltung", "aenderungsantrag": "Änderungsantrag",
              "folgevorlage": "Weitere Vorlage"}


def doc_entry(d, kind, plan):
    return {"reference": d["reference"], "name": d["name"], "typ": d["paper_type"],
            "datum": d["datum"], "art": kind, "pdf": d["pdf"], "ratsinfo": d["web_url"],
            "beratungsfolge_plan": plan}


DATIV = {"Grüne": "den Grünen", "Linke": "der Linken", "BBB": "dem BBB", "BSW": "dem BSW", "Volt": "Volt"}  # "von …"


class Builder:
    def __init__(self, wissen, orgs, kalender, today, zusammenfassung=None):
        self.w, self.orgs, self.kal, self.today = wissen, orgs, kalender, today
        self.zf = zusammenfassung or {}

    # step + legal basis of a node
    def place(self, vid, key_kind, rolle=None, art=None):
        table = STEPS.get(vid, {})
        if key_kind == "beratung":
            sid = (table.get(f"{rolle}|{art}") or table.get(f"{rolle}|*") or table.get("*|*"))
        else:
            sid = table.get(key_kind) or {"st": "stellungnahme", "aa": "aenderungsantrag",
                                           "folge": "folgevorlage"}.get(key_kind)
        s = self.w.step(vid, sid)
        r = self.w.rolle(rolle, art) if key_kind == "beratung" else None
        beleg = (s or {}).get("beleg") or (r or {}).get("beleg")
        out = {"schritt": {"id": sid, "was": s["was"]} if s else None}
        out.update(self.w.recht(beleg))
        if r:
            out["rolle_text"] = r["text"]
        return out

    def plans(self, v):
        out = {}
        for d in v["dokumente"]:
            f = main_file(d)
            text = cover_text(f["id"]) if f.get("id") else None
            rows = parse_beratungsfolge(text, self.orgs) if text else None
            out[d["reference"]] = rows  # None: cover not available, []: no table found
        return out

    def build(self, v):
        st = v["stammnummer"]
        plans = self.plans(v)
        plan_arts = {r["gremienart"] for rows in plans.values() for r in rows or [] if r["gremienart"]}
        vid, sicher, grund = assign(v, plan_arts)
        head = next((d for d in v["dokumente"] if d["reference"] == st), v["dokumente"][0])
        nodes = []

        # eingang
        n = {"art": "eingang", "titel": "Eingang: " + (head["paper_type"] or "Vorlage"),
             "datum": head["datum"], "einreicher": v["einreicher"], "reference": head["reference"],
             "pdf": head["pdf"], "ratsinfo": head["web_url"], "status": "erledigt"}
        n.update(self.place(vid, "eingang"))
        nodes.append(n)

        # consultations grouped by meeting (date + body)
        dated = defaultdict(list)
        for b in v["beratungen"]:
            if b["datum"]:
                dated[(b["datum"], b["gremium"] or "")].append(b)
        docs = {d["reference"]: d for d in v["dokumente"]}
        # the current main paper, as in vorgang.status_2026: latest non-side paper with consultations
        current_main = vorgang.current_main(v["dokumente"], v["beratungen"])["reference"]
        attached = set()
        for (datum, gremium), bs in sorted(dated.items()):
            bs.sort(key=lambda b: (b["reference"] != current_main, b["reference"] != st, b["reference"]))
            lead = next((b for b in bs if docs.get(b["reference"], {}).get("paper_type")
                         not in (SIDE_ST, SIDE_AA)), bs[0])
            future = not lead["ergebnis"] and datum >= self.today
            n = {"art": "beratung", "titel": f"{lead['rolle'] or 'Beratung'}: {gremium or 'Gremium unbekannt'}",
                 "datum": datum, "gremium": gremium or None, "gremienart": lead["gremienart"],
                 "rolle": lead["rolle"], "ergebnis": lead["ergebnis"],
                 "ergebnis_gruppe": gruppe(lead["ergebnis"]), "top": lead["top"],
                 "sitzung_url": lead["sitzung_url"], "einladung_pdf": lead["einladung_pdf"],
                 "beschluss_pdf": lead["beschluss_pdf"],
                 "status": "geplant" if future else "erledigt",
                 "punkte": [{"reference": b["reference"], "art": doc_kind(docs[b["reference"]], st)
                             if b["reference"] in docs else None, "rolle": b["rolle"],
                             "ergebnis": b["ergebnis"], "ergebnis_gruppe": gruppe(b["ergebnis"]),
                             "top": b["top"], "beschluss_pdf": b["beschluss_pdf"],
                             "pdf": docs.get(b["reference"], {}).get("pdf"),
                             "ratsinfo": docs.get(b["reference"], {}).get("web_url")} for b in bs]}
            n.update(self.place(vid, "beratung", lead["rolle"], lead["gremienart"]))
            if future:
                n["erwartet"] = True
                n["quelle"] = "sitzung"
            nodes.append(n)
            attached |= {b["reference"] for b in bs}

        erwartet = self.expected(v, vid, plans, nodes, docs)
        planned = {p["reference"] for n in erwartet for p in n.get("punkte", [])}

        # accompanying documents and follow-up papers: own node if no consultation carries
        # them, or if a follow-up paper of another type starts a new round
        for d in v["dokumente"]:
            kind = doc_kind(d, st)
            if kind == "eingang":
                continue
            if kind == "folgevorlage" and d["paper_type"] == head["paper_type"] and \
                    d["reference"] in attached | planned:
                continue  # same kind of paper (new version, further submission): shown in its consultation
            if kind != "folgevorlage" and d["reference"] in attached:
                continue
            n = {"art": "dokument", "dokument_art": kind, "titel": KIND_TITLE[kind],
                 "name": d["name"], "typ": d["paper_type"], "datum": d["datum"],
                 "reference": d["reference"], "pdf": d["pdf"], "ratsinfo": d["web_url"],
                 "status": "erledigt"}
            n.update(self.place(vid, {"stellungnahme": "st", "aenderungsantrag": "aa"}.get(kind, "folge")))
            nodes.append(n)

        # the submission comes first even if its publication date is after the first meeting
        nodes.sort(key=lambda n: (n["art"] != "eingang", n["datum"] or "9999",
                                  1 if n["art"] == "dokument" else 2, n.get("gremium") or ""))
        nodes += erwartet
        for i, n in enumerate(nodes):
            n["id"] = f"k{i + 1:02d}"
        for i, n in enumerate(nodes):
            n["vor"] = [nodes[i - 1]["id"]] if i else []
            n["nach"] = [nodes[i + 1]["id"]] if i + 1 < len(nodes) else []
            n.setdefault("erwartet", False)
            n["aktuell"] = False
        cur, abschluss = self.current(v, vid, nodes)
        if abschluss in ("zur Kenntnis", "erledigt") and any(
                not n["erwartet"] and n["art"] == "beratung" and n["rolle"] == "Entscheidung"
                and n["ergebnis_gruppe"] == "beschlossen" for n in nodes):
            abschluss = "beschlossen"  # e.g. a council decision, later a report taken note of
        cur["aktuell"] = True
        termin = next((n for n in nodes if n["erwartet"] and n.get("datum")
                       and n["datum"] >= self.today), None)
        naechster = ({"datum": termin["datum"], "gremium": termin.get("gremium"),
                      "gremienart": termin.get("gremienart"), "rolle": termin.get("rolle"),
                      "sitzung_url": termin.get("sitzung_url"), "quelle": termin.get("quelle")}
                     if termin else None)
        ctx = {"status": v["status"], "verfahren": vid, "ebene": v["ebene"], "bezirk": v["bezirk"],
               "termin": naechster, "abschluss": abschluss}
        dokumente = [doc_entry(d, doc_kind(d, st), plans.get(d["reference"])) for d in v["dokumente"]]
        proc = self.w.verfahren[vid]
        return {
            "stammnummer": st, "titel": v["titel"], "typ": v["typ"], "einreicher": v["einreicher"],
            "status": v["status"], "status_grund": v["status_grund"], "ebene": v["ebene"],
            "bezirk": v["bezirk"], "gremien": v["gremien"],
            "zuletzt": v["zuletzt"],
            "verfahren": {"id": vid, "titel": proc["titel"], "kurz": proc["kurz"],
                          "sicherheit": sicher, "grund": grund},
            "worum": self.worum(v, vid, nodes),
            "worum_ki": (self.zf.get(st) or {}).get("satz"),
            "knoten": nodes, "naechster_termin": naechster,
            "mitwirken": self.mitwirken(ctx),
            "dokumente": dokumente,
            "verwandte": v.get("verwandte") or [],
        }

    # expected steps -----------------------------------------------------------------
    def expected(self, v, vid, plans, nodes, docs):
        st = v["stammnummer"]
        active = v["status"] in ("offen", "vertagt")
        have = {(n["datum"], n.get("gremium")) for n in nodes if n["art"] == "beratung"}
        concrete = {}  # (datum, gremium) -> node
        open_roles = Counter()
        for b in v["beratungen"]:
            if not b["datum"] and not b["ergebnis"]:
                open_roles[(b["reference"], b["rolle"])] += 1

        def add(datum, gremium, gid, art, rolle, ref, quelle, hinweis=None):
            key = (datum, gremium)
            if key in have:
                return
            n = concrete.get(key)
            if not n:
                mt = self.kal.meeting(gid, datum) if gid and datum else None
                agenda = [e for e in self.kal.on_agenda.get(ref, []) if e["id"] == (mt or {}).get("id")]
                n = {"art": "beratung", "titel": f"{rolle or 'Beratung'}: {gremium}", "datum": datum,
                     "gremium": gremium, "gremienart": art, "rolle": rolle, "ergebnis": None,
                     "ergebnis_gruppe": "offen", "top": agenda[0]["top"] if agenda else None,
                     "sitzung_url": (mt or {}).get("sitzung_url"),
                     "einladung_pdf": (mt or {}).get("einladung_pdf"), "beschluss_pdf": None,
                     "status": "geplant", "erwartet": True,
                     "quelle": "tagesordnung" if agenda else quelle, "punkte": []}
                if hinweis:
                    n["hinweis"] = hinweis
                n.update(self.place(vid, "beratung", rolle, art))
                concrete[key] = n
            if ref not in [p["reference"] for p in n["punkte"]]:
                n["punkte"].append({"reference": ref, "art": doc_kind(docs[ref], st) if ref in docs else None,
                                    "rolle": rolle, "ergebnis": None, "ergebnis_gruppe": "offen",
                                    "pdf": docs.get(ref, {}).get("pdf"),
                                    "ratsinfo": docs.get(ref, {}).get("web_url")})

        # 1. future rows of the cover tables; agenda listings of refreshed meetings
        for ref, rows in plans.items():
            for r in rows or []:
                if r["datum"] and r["datum"] >= self.today:
                    add(r["datum"], r["gremium"], r["gremium_id"], r["gremienart"], r["rolle"], ref,
                        "deckblatt")
                    open_roles[(ref, r["rolle"])] -= 1
            for e in self.kal.on_agenda.get(ref, []):
                o = self.orgs.by_id.get(e["gremium_id"]) or {}
                add(e["datum"], e["gremium"], e["gremium_id"], o.get("classification"), None, ref,
                    "tagesordnung")
        if not active:  # stale plans of finished Vorgänge: only concrete dates
            out = sorted(concrete.values(), key=lambda n: n["datum"])
            return out + self.ending(v, vid, nodes)

        # 2. adjourned: the next meeting of the same body
        last = [n for n in nodes if n["art"] == "beratung" and n["ergebnis_gruppe"] == "vertagt"]
        if v["status"] == "vertagt" and last:
            for n in [x for x in last if x["datum"] == last[-1]["datum"]]:
                o = self.orgs.find(n["gremium"])
                if not o or any(c["gremium"] == o["name"] for c in concrete.values()):
                    continue
                mt = self.kal.next(o["id"], after=(n["datum"] or "") + "~")
                if mt:
                    for p in n["punkte"]:
                        add(mt["datum"], o["name"], o["id"], o.get("classification"),
                            n["rolle"], p["reference"], "kalender",
                            "Nächste Sitzung dieses Gremiums; ob der Punkt dort wieder auf der "
                            "Tagesordnung steht, zeigt erst die Einladung.")
                        open_roles[(p["reference"], n["rolle"])] -= 1

        # 3. cover rows with a past date that never reached a meeting -> next meeting of that body
        for ref, rows in plans.items():
            for r in rows or []:
                if (r["datum"] and r["datum"] < self.today and r["gremium_id"]
                        and (r["datum"], r["gremium"]) not in have
                        and open_roles[(ref, r["rolle"])] > 0
                        and not any(c["gremium"] == r["gremium"] for c in concrete.values())):
                    mt = self.kal.next(r["gremium_id"])
                    if mt:
                        add(mt["datum"], r["gremium"], r["gremium_id"], r["gremienart"], r["rolle"],
                            ref, "kalender", f"Laut Deckblatt für den {de(r['datum'])} geplant; dort "
                            "nicht beraten. Angenommen: die nächste Sitzung dieses Gremiums.")
                        open_roles[(ref, r["rolle"])] -= 1
        # 3b. still unassigned, but exactly one body had this role before in the Vorgang
        for (ref, r), k in sorted(open_roles.items(), key=lambda kv: (kv[0][0], kv[0][1] or "")):
            if k <= 0 or not r or any(c["rolle"] == r for c in concrete.values()):
                continue
            bodies = {n["gremium"] for n in nodes if n["art"] == "beratung" and n.get("gremium")
                      and (n["rolle"] == r or any(p["rolle"] == r for p in n["punkte"]))}
            o = self.orgs.find(bodies.pop()) if len(bodies) == 1 else None
            mt = self.kal.next(o["id"]) if o else None
            if mt:
                add(mt["datum"], o["name"], o["id"], o.get("classification"), r, ref, "kalender",
                    "Noch keiner Sitzung zugeordnet. Angenommen: dasselbe Gremium wie bei der "
                    "bisherigen Beratung, in seiner nächsten Sitzung.")
                open_roles[(ref, r)] = 0
        out = sorted(concrete.values(), key=lambda n: n["datum"])

        # 4. consultations without meeting and without plan -> abstract, one per role
        roles = sorted({r for (ref, r), k in open_roles.items() if k > 0 and r},
                       key=lambda r: ROLE_RANK.get(r, 9))
        for r in roles:
            if any(c["rolle"] == r for c in out):
                continue
            n = {"art": "beratung", "titel": f"{r}: Gremium und Termin noch offen", "datum": None,
                 "gremium": None, "gremienart": None, "rolle": r, "ergebnis": None,
                 "ergebnis_gruppe": "offen", "status": "geplant", "erwartet": True,
                 "quelle": "ratsinfo", "punkte": [],
                 "hinweis": "Im Ratsinformationssystem geplant, aber noch keiner Sitzung zugeordnet."}
            n.update(self.place(vid, "beratung", r, None))
            out.append(n)

        # 5. template steps: the answer of the administration if none is there yet (before the
        #    consultations), and the goal step if nothing decisive is expected or decided
        decided = any(n.get("ergebnis_gruppe") in ("beschlossen", "abgelehnt", "erledigt")
                      and n.get("rolle") in ("Entscheidung", "Genehmigung") for n in nodes)
        decisive = any(n.get("rolle") in ("Entscheidung", "Genehmigung") for n in out)
        has_st = any(d["paper_type"] == SIDE_ST for d in v["dokumente"])
        present = {(n.get("schritt") or {}).get("id") for n in out}
        ziel = STEPS.get(vid, {}).get("ziel", [])
        if vid == "buergerantrag" and v["ebene"] != "bezirk":
            ziel = ["u5", "u6"] if v["ebene"] is None else ["u6"]
        pre, post = [], []
        for sid in ziel:
            if sid in present:
                continue
            if sid in ANSWER_STEPS:
                if has_st:
                    continue
                target = pre
            elif decisive or decided or (vid in QUESTION_PROCS and out):
                continue
            else:
                target = post
            s = self.w.step(vid, sid)
            n = {"art": "vorlage", "titel": s["was"], "datum": None, "status": "geplant",
                 "erwartet": True, "quelle": "verfahren", "schritt": {"id": sid, "was": s["was"]},
                 "hinweis": "Voraussichtlicher Schritt nach dem üblichen Ablauf."}
            n.update(self.w.recht(s.get("beleg")))
            target.append(n)
        out = pre + out + post
        return out + self.ending(v, vid, nodes)

    def ending(self, v, vid, nodes):
        """Final template step (implementation, notice, minutes) as expected node."""
        sid = STEPS.get(vid, {}).get("ende")
        if not sid or v["status"] == "unklar":
            return []
        if v["status"] == "abgeschlossen":
            final = [n for n in nodes if n["art"] == "beratung" and n["rolle"] in ("Entscheidung", None)
                     and n["ergebnis_gruppe"] == "beschlossen"]
            if not final and vid not in ("buergerantrag", "grosse-anfrage"):
                return []
            if vid == "buergerantrag" and not any(n["art"] == "beratung" and
                                                  n["ergebnis_gruppe"] != "offen" for n in nodes):
                return []
        s = self.w.step(vid, sid)
        n = {"art": "vorlage", "titel": s["was"], "datum": None, "status": "geplant", "erwartet": True,
             "quelle": "verfahren", "schritt": {"id": sid, "was": s["was"]},
             "hinweis": "Voraussichtlicher Schritt nach dem üblichen Ablauf."}
        n.update(self.w.recht(s.get("beleg")))
        return [n]

    # current node -----------------------------------------------------------------
    def current(self, v, vid, nodes):
        """(node marked aktuell, kind of closing: beschlossen/abgelehnt/zur Kenntnis/erledigt/None)."""
        status = v["status"]
        actual = [n for n in nodes if not n["erwartet"]]
        if status == "vertagt":
            last = [n for n in actual if n["art"] == "beratung" and n["ergebnis_gruppe"] == "vertagt"]
            if last:
                n = last[-1]
                n["hinweis"] = "Vertagt: wird erneut beraten."
                return n, None
        if status in ("offen", "vertagt"):
            nxt = next((n for n in nodes if n["erwartet"] and n["art"] == "beratung"), None) or \
                next((n for n in nodes if n["erwartet"]), None)
            if nxt:
                return nxt, None
            return actual[-1], None
        mt = re.search(r"in (.+?) am (\d\d)\.(\d\d)\.(\d{4})", v["status_grund"])
        if mt:
            g, datum = mt.group(1), f"{mt.group(4)}-{mt.group(3)}-{mt.group(2)}"
            hit = [n for n in actual if n["art"] == "beratung" and n["datum"] == datum
                   and (n.get("gremium") or "unbekanntem Gremium") == g]
            if hit:
                n = hit[-1]
                ergebnis = re.search(r"„(.+?)“", v["status_grund"])
                grp = gruppe(ergebnis.group(1)) if ergebnis else n["ergebnis_gruppe"]
                return n, grp
        if v["status_grund"].startswith("Mitteilung der Verwaltung"):
            mitt = [d["reference"] for d in v["dokumente"]
                    if (d["paper_type"] or "").startswith(("Mitteilungsvorlage", "Informationsbrief"))]
            hit = [n for n in actual if n.get("reference") in mitt or
                   set(mitt) & {p["reference"] for p in n.get("punkte", [])}]
            return (hit[-1] if hit else actual[0] if vid == "mitteilung" else actual[-1]), "zur Kenntnis"
        ref = re.search(r"Stellungnahme (\S+ ST)", v["status_grund"])
        if ref:
            r = ref.group(1).rstrip(".")
            hit = [n for n in actual if n.get("reference") == r or
                   r in [p["reference"] for p in n.get("punkte", [])]]
            if hit:
                hit[0]["hinweis"] = f"Die Antwort der Verwaltung liegt vor: Stellungnahme {r}."
                return hit[0], "erledigt"
        return actual[0] if vid == "mitteilung" else actual[-1], "zur Kenntnis" if vid == "mitteilung" else None

    # words -------------------------------------------------------------------------
    def worum(self, v, vid, nodes):
        """1–2 short sentences: what kind of matter this is, who brought it, who decides.
        No dates and no status (they stand in the meta line of the page). The second sentence (who decides)
        is left out when that body already stands in the meta line (current body or next documented meeting)."""
        einr = [DATIV.get(x, f"der {x}") for x in v["einreicher"] if x not in ("Verwaltung", "Bürger:innen")]
        von = ("" if not einr else " mehrerer Fraktionen" if einr == ["der interfraktionell"] else
               " von " + (", ".join(einr[:-1]) + " und " + einr[-1] if len(einr) > 1 else einr[0]))
        von = von.replace("von dem ", "vom ")
        g = next((n["gremium"] for n in nodes if n.get("rolle") == "Entscheidung" and n.get("gremium")), None)
        done = [n["gremium"] for n in nodes if n["art"] == "beratung" and n.get("gremium") and not n["erwartet"]]
        kommend = [n for n in nodes if n["erwartet"] and n.get("datum") and n["datum"] >= self.today]
        stand = done[-1] if done else next((n.get("gremium") for n in kommend), None)  # = stand_gremium()
        belegt = next((n.get("gremium") for n in kommend if n.get("quelle") in ("sitzung", "deckblatt", "tagesordnung")), None)
        entscheider = nom(g) if g else None
        s1, s2 = self.w.worum.get(vid, ["", ""])
        if g and g in (stand, belegt) and vid != "dringlichkeitsentscheidung":  # dort sagt s2 mehr als wer
            s2 = ""
        out = [s1.format(von=von)]
        if s2 and (entscheider or "{" not in s2):
            out.append(s2.format(entscheider=entscheider, Entscheider=(entscheider or "")[:1].upper() + (entscheider or "")[1:]))
        return " ".join(x for x in out if x)

    # influence ---------------------------------------------------------------------
    def buergerantrag_ziel(self, ctx, tage):
        """Body for an own Bürgerantrag and its next meeting whose deadline is still ahead."""
        if ctx["bezirk"] and ctx["ebene"] == "bezirk":
            o = self.orgs.find(f"Bezirksvertretung {ctx['bezirk']}")
        else:
            o = self.orgs.find("Ausschuss für Beteiligung der Bürgerinnen und Bürger")
        after = (date.fromisoformat(self.today) - timedelta(days=tage)).isoformat()
        return o, (self.kal.next(o["id"], after=after) if o else None)

    def mitwirken(self, ctx):
        """Evaluate einfluss_regeln; frist_datum is absolute, the page compares it with today."""
        out, t = [], ctx["termin"]
        for r in self.w.regeln:
            w = r["wenn"]
            if ("status" in w and ctx["status"] not in w["status"]
                    or "verfahren" in w and ctx["verfahren"] not in w["verfahren"]
                    or ctx["verfahren"] in w.get("nicht_verfahren", [])
                    or "ebene" in w and ctx["ebene"] not in w["ebene"]
                    or ctx["ebene"] in w.get("nicht_ebene", [])
                    or "termin" in w and bool(t) != w["termin"]
                    or "termin_gremienart" in w and (not t or t["gremienart"] not in w["termin_gremienart"])
                    or "abschluss" in w and ctx["abschluss"] not in w["abschluss"]):
                continue
            vals, bezug = {}, None
            if t:
                vals.update(gremium=t["gremium"], datum=de(t["datum"]))
            if r.get("bezug") == "termin" and t:
                bezug = t["datum"]
            elif r.get("bezug") == "buergerantrag_ziel":
                o, mt = self.buergerantrag_ziel(ctx, r.get("tage", 0))
                if not (o and mt):
                    continue
                vals.update(ziel=nom(o["name"]), ziel_datum=de(mt["datum"]))
                bezug = mt["datum"]
            try:
                was = r["was"].format(**vals)
            except KeyError:
                continue
            frist, frist_datum = r["frist"], None
            if bezug:
                frist_datum = (date.fromisoformat(bezug) + timedelta(days=r.get("tage", 0))).isoformat()
                frist += f" ({de(frist_datum)})" if not r.get("tage") else f", also bis {de(frist_datum)}"
            item = {"id": r["id"], "was": was, "frist": frist, "frist_datum": frist_datum}
            item.update(self.w.recht(r.get("beleg")))
            out.append(item)
        return out


# --- Output --------------------------------------------------------------------------

def short(text, n):
    text = re.sub(r"\s+", " ", text or "").strip()
    return text if len(text) <= n else text[:n - 1].rstrip() + "…"


def status_kurz(grund):
    """'Verbindlich „abgelehnt“ in Bezirksvertretung Bonn am 21.04.2026.' -> short list text."""
    g = re.sub(r"^(Verbindlich|Zuletzt) ", "", grund.split(";")[0].rstrip("."))
    g = g.replace("Bezirksvertretung ", "BV ").replace(", seitdem kein Ergebnis", "")
    return short(g, 80)


def stand_gremium(d):
    """Body where the Vorgang stands, as the page draws it ("jetzt" in lanes.js): the last body that actually
    dealt with it, else the body of the next meeting; None without any body."""
    done = [n for n in d["knoten"] if n["art"] == "beratung" and n.get("gremium") and not n["erwartet"]]
    t = d["naechster_termin"]
    return done[-1]["gremium"] if done else (t or {}).get("gremium")


# Themen für die Statistik: zuerst nach dem ersten Fachausschuss, der den Vorgang berät (Teil des Namens),
# sonst nach Stichwörtern im Titel, sonst "Sonstiges". Stichwörter gelten auch mitten im Wort (Komposita:
# „Katzensteuer“, „Parkverbot“); nur kurze Wörter mit ^ müssen am Wortanfang stehen. Reihenfolge = Vorrang.
THEMEN = [
    ("Verkehr & Mobilität", ["Mobilität", "Verkehr"],
     "verkehr straße strasse radweg fahrrad radfahr parkpl parkraum parkverbot parkausweis parkhaus parken ^park "
     "^bus haltestelle ^bahn ampel tempo zebrastreifen fußgänger fussgänger gehweg bürgersteig bordstein brücke "
     "tunnel unterführung kreuzung stellpl scooter carsharing ladesäule einbahn schulweg brötchentaste"),
    ("Bauen & Stadtplanung", ["Planen", "Planung", "Bauen", "Denkmalschutz", "Stadthalle"],
     "bebauungsplan bauleit flächennutzung bauvorhaben neubau sanierung gebäude grundstück wohnungsbau wohnen "
     "denkmal baugebiet quartier stadtentwicklung veränderungssperre nutzungsänderung abriss bauarbeiten ^bau-"),
    ("Umwelt & Klima", ["Umwelt", "Naturschutz", "Baumkommission"],
     "baum bäume klima umwelt natur grünfläche grünanlage begrünung pflanz gewässer hochwasser abfall müll energie "
     "solar photovoltaik wärme lärm ^luft friedhof rheinufer ufer hitze kühle mehrweg"),
    ("Bildung, Kinder & Jugend", ["Schul", "Kinder", "Jugend"],
     "schul kita kindertages ^ogs kinder jugend spielplatz bildung ganztag"),
    ("Soziales & Gesundheit", ["Soziales", "Chancengerechtigkeit", "Integration", "Senioren", "SGB"],
     "sozial senior gesundheit migration integration geflüchtet flüchtl obdach wohnungslos pflege inklusion "
     "barrierefrei armut ehrenamt"),
    ("Kultur, Sport & Freizeit", ["Kultur", "Sport"],
     "kultur sport theater museum beethoven schwimm bäder ^bad\\b bibliothek musik festival veranstaltung freizeit "
     "boule fitness karneval marathon markt schauspiel ^oper feste ^fest\\b"),
    ("Finanzen, Wirtschaft & Verwaltung", ["Finanzen", "Wirtschaft", "Digitalisierung", "Rechnungsprüfung", "Wissenschaft", "Wahlprüfung"],
     "haushalt finanz steuer gebühr wirtschaft digital personal verwaltung vergabe beteiligung stadtwerke "
     "jahresabschluss wirtschaftsplan vorsitz schriftführ besetzung kommunikation social media medaille ehrung oberbürgermeister"),
    ("Sicherheit & Ordnung", ["Sicherheit"],
     "sicherheit ordnung polizei feuerwehr feuerwerk kriminal videoüberwach rettungs blackout katastroph gewalt"),
]
THEMEN_RE = [(name, teile, re.compile("|".join(
    r"(?<!\w)" + w[1:] if w.startswith("^") else w for w in muster.split()), re.I))
    for name, teile, muster in THEMEN]


def thema(d):
    """One topic per Vorgang for the statistics page (see THEMEN)."""
    for g in d["gremien"]:
        if g.startswith("Bezirksvertretung") or g in ("Rat", "Hauptausschuss"):
            continue
        for name, teile, _ in THEMEN_RE:
            if any(t in g for t in teile):
                return name
    for name, _, rx in THEMEN_RE:
        if rx.search(d["titel"] or ""):
            return name
    return "Sonstiges"


def termine(d):
    """Sorted dates of all actual steps and documents; the page filters by year and period on them."""
    return sorted({n["datum"] for n in d["knoten"] if n.get("datum") and not n["erwartet"]} |
                  {x["datum"] for x in d["dokumente"] if x.get("datum")})


def index_row(d, gremien):
    """One list entry; empty values (null, false, 0, []) are left out to keep the file small."""
    t = d["naechster_termin"]
    such = " ".join(d["einreicher"] + [x["reference"] for x in d["dokumente"]
                                       if x["reference"] != d["stammnummer"]])
    row = {"stammnummer": d["stammnummer"], "titel": d["titel"], "typ": d["typ"],
           "status": d["status"], "status_grund": status_kurz(d["status_grund"]),
           "verfahren": d["verfahren"]["id"], "ebene": d["ebene"], "bezirk": d["bezirk"],
           "gremien": [gremien.index(g) for g in d["gremien"]],
           "zuletzt": d["zuletzt"], "termine": termine(d), "einreicher": d["einreicher"], "thema": thema(d), "gremium": gremien.index(stand_gremium(d)) if stand_gremium(d) else None,
           "naechster": [t["datum"], gremien.index(t["gremium"]) if t["gremium"] in gremien else None]
           if t else None,
           "suchtext": short(such, 120)}
    return {k: v for k, v in row.items() if v not in (None, False, 0, [], "")}


def index_file(details):
    """{"gremien": [names], "vorgaenge": [rows]}; rows refer to bodies by position in "gremien"."""
    names = sorted({g for d in details for g in d["gremien"]} |
                   {d["naechster_termin"]["gremium"] for d in details
                    if d["naechster_termin"] and d["naechster_termin"]["gremium"]} |
                   {stand_gremium(d) for d in details if stand_gremium(d)})
    return {"hinweis": "gremien und naechster[1] sind Positionen in der Liste gremien; "
                       "naechster = [datum, gremium]. Leere Felder fehlen.",
            "gremien": names, "vorgaenge": [index_row(d, names) for d in details]}


def dump(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n"


def write_all(details):
    write_if_changed(INDEX_OUT, dump(index_file(details)))
    DETAIL_DIR.mkdir(parents=True, exist_ok=True)
    keep = set()
    for d in details:
        path = DETAIL_DIR / f"{d['stammnummer']}.json"
        keep.add(path.name)
        write_if_changed(path, dump(d))
    stale = [p for p in DETAIL_DIR.glob("*.json") if p.name not in keep]
    for p in stale:
        p.unlink()
    return len(stale)


def check(wissen=None):
    """Errors in the written Verfolgen data (used by lint.py)."""
    w = wissen or Wissen()
    errs = []
    for name in ("mitteilung", "nichtoeffentlich"):
        if name not in w.verfahren:
            errs.append(f"einordnung_extra: verfahren {name} fehlt")
    for vid, e in w.worum.items():
        if vid not in w.verfahren:
            errs.append(f"einordnung_extra.worum: unbekanntes verfahren {vid}")
        if not (isinstance(e, list) and len(e) == 2 and e[0]):
            errs.append(f"einordnung_extra.worum {vid}: braucht [satz, satz-mit-entscheider oder \"\"]")
    for r in w.regeln:
        for k in ("id", "wenn", "was", "frist", "beleg"):
            if not r.get(k):
                errs.append(f"einfluss_regeln {r.get('id')}: feld fehlt: {k}")
        for vid in r["wenn"].get("verfahren", []) + r["wenn"].get("nicht_verfahren", []):
            if vid not in w.verfahren:
                errs.append(f"einfluss_regeln {r['id']}: unbekanntes verfahren {vid}")
    for vid, table in STEPS.items():
        if vid not in w.verfahren:
            errs.append(f"einordnung.STEPS: unbekanntes verfahren {vid}")
        for key, sid in table.items():
            for s in (sid if isinstance(sid, list) else [sid]):
                if not w.step(vid, s):
                    errs.append(f"einordnung.STEPS {vid}: unbekannter schritt {s}")
    if not INDEX_OUT.exists():
        return errs + [f"{INDEX_OUT.relative_to(ROOT)} fehlt (python3 einordnung.py)"]
    index = json.loads(INDEX_OUT.read_text())
    files = {p.stem for p in DETAIL_DIR.glob("*.json")}
    ids = {r["stammnummer"] for r in index["vorgaenge"]}
    for r in index["vorgaenge"]:
        for g in r.get("gremien", []) + [(r.get("naechster") or [None, None])[1]]:
            if g is not None and not 0 <= g < len(index["gremien"]):
                errs.append(f"index {r['stammnummer']}: gremium-position {g} ungültig")
    for st in sorted(ids - files):
        errs.append(f"vorgang {st}: detaildatei fehlt")
    for st in sorted(files - ids):
        errs.append(f"vorgang {st}: detaildatei ohne indexeintrag")
    for st in sorted(ids & files):
        d = json.loads((DETAIL_DIR / f"{st}.json").read_text())
        nodes = d.get("knoten") or []
        known = {n["id"] for n in nodes}
        cur = [n["id"] for n in nodes if n.get("aktuell")]
        if len(cur) != 1:
            errs.append(f"vorgang {st}: {len(cur)} aktuelle knoten statt 1")
        if len(known) != len(nodes):
            errs.append(f"vorgang {st}: doppelte knoten-ids")
        if d["verfahren"]["id"] not in w.verfahren:
            errs.append(f"vorgang {st}: unbekanntes verfahren {d['verfahren']['id']}")
        if not d.get("worum"):
            errs.append(f"vorgang {st}: worum fehlt (einordnung_extra.worum für {d['verfahren']['id']})")
        for n in nodes:
            for k in n.get("vor", []) + n.get("nach", []):
                if k not in known:
                    errs.append(f"vorgang {st} knoten {n['id']}: unbekannte id {k}")
        for x in nodes + d.get("mitwirken", []):
            for r in x.get("rechtsgrundlagen", []):
                if not r.get("url"):
                    errs.append(f"vorgang {st}: rechtsgrundlage ohne url: {r.get('label')}")
    return errs


def report(details, vorgaenge, today):
    by = {d["stammnummer"]: d for d in details}
    lines = ["# Einordnung der Vorgänge 2026 – Bericht", "",
             f"Erzeugt von `einordnung.py` aus `data/stadt/vorgaenge_2026.json`; „künftig“ relativ zum Lauf am {today}.", ""]
    statuses = ["offen", "vertagt", "abgeschlossen", "unklar"]
    tab = defaultdict(Counter)
    for d in details:
        tab[d["verfahren"]["id"]][d["status"]] += 1
    lines += ["## Verfahren × Status", "", "| Verfahren | " + " | ".join(statuses) + " | gesamt |",
              "|---|" + "---:|" * (len(statuses) + 1)]
    for vid, c in sorted(tab.items(), key=lambda kv: -sum(kv[1].values())):
        lines.append(f"| {vid} | " + " | ".join(str(c[s]) for s in statuses) + f" | {sum(c.values())} |")
    sure = Counter((d["verfahren"]["sicherheit"]) for d in details)
    lines += ["", "## Sicherheit der Zuordnung", ""]
    lines += [f"- {k}: {n}" for k, n in sure.most_common()]
    lines += ["", "Gründe bei Sicherheit „mittel“:", ""]
    for g, n in Counter(d["verfahren"]["grund"] for d in details
                        if d["verfahren"]["sicherheit"] == "mittel").most_common():
        lines.append(f"- {n} × {g}")
    active = [d for d in details if d["status"] in ("offen", "vertagt")]
    with_t = [d for d in active if d["naechster_termin"]]
    q = Counter(d["naechster_termin"]["quelle"] for d in with_t)
    covers = [x for d in details for x in d["dokumente"]]
    wanted = {x["reference"] for v in vorgaenge for x in wants_cover(v)}
    lines += ["", "## Nächster Termin und Deckblätter", "",
              f"- Offene oder vertagte Vorgänge: {len(active)}, davon mit konkretem nächstem Termin: "
              f"{len(with_t)} ({100 * len(with_t) / max(1, len(active)):.0f} %)",
              "  - Quelle: " + ", ".join(f"{k} {n}" for k, n in q.most_common()),
              f"  - offen: {sum(1 for d in with_t if d['status'] == 'offen')} von "
              f"{sum(1 for d in active if d['status'] == 'offen')}, vertagt: "
              f"{sum(1 for d in with_t if d['status'] == 'vertagt')} von "
              f"{sum(1 for d in active if d['status'] == 'vertagt')}",
              f"- Abgeschlossene Vorgänge mit späterem Termin (z. B. Kenntnisnahme der Antwort): "
              f"{sum(1 for d in details if d['status'] == 'abgeschlossen' and d['naechster_termin'])}",
              f"- Dokumente, deren Deckblatt gebraucht wird: {len(wanted)}; Deckblatt-Text vorhanden: "
              f"{sum(1 for x in covers if x['reference'] in wanted and x['beratungsfolge_plan'] is not None)}, "
              f"davon mit erkannter Beratungsfolge: "
              f"{sum(1 for x in covers if x['reference'] in wanted and x['beratungsfolge_plan'])}",
              f"- Alle Dokumente mit Beratungsfolge-Plan: {sum(1 for x in covers if x['beratungsfolge_plan'])}",
              f"- Plan-Zeilen ohne zugeordnetes Gremium: "
              f"{sum(1 for x in covers for r in x['beratungsfolge_plan'] or [] if not r['gremium_id'])}",
              f"- Aktueller Knoten ist erwartet (nächster Schritt): "
              f"{sum(1 for d in details for n in d['knoten'] if n['aktuell'] and n['erwartet'])}"]
    lines += ["", "## Stichprobe (20 zufällige Vorgänge, Seed 2027)", ""]
    for st in random.Random(2027).sample(sorted(by), 20):
        d = by[st]
        cur = next(n for n in d["knoten"] if n["aktuell"])
        first = next((x for x in d["mitwirken"] if not x["frist_datum"] or x["frist_datum"] >= today),
                     None)
        cur_txt = (f"{cur['titel']}" + (f" ({de(cur['datum'])})" if cur.get("datum") else "")
                   + (" – erwartet" if cur["erwartet"] else ""))
        lines += [f"- **{st}** {short(d['titel'], 90)} ({d['typ']}, {d['status']})",
                  f"  - Verfahren: `{d['verfahren']['id']}` ({d['verfahren']['sicherheit']}): {d['verfahren']['grund']}",
                  f"  - Aktueller Knoten: {cur_txt}",
                  f"  - Worum: {d['worum']}" + (f" KI: {d['worum_ki']}" if d.get("worum_ki") else ""),
                  f"  - Erster Mitwirken-Hinweis: {first['was'] + ' – ' + first['frist'] if first else '–'}"]
    write_if_changed(REPORT, "\n".join(lines) + "\n" + PRUEFUNG)


PRUEFUNG = """
## Prüfung der Stichprobe gegen die Rohdaten

Alle 20 Vorgänge der Stichprobe am 17.10.2026 gegen `data/stadt/vorgaenge_2026.json` (Beratungen, Dokumente)
und die Deckblätter geprüft:

- **stimmt (15):** 253838, 260781, 253208, 261248, 260423, 260631, 261183, 261917 (Deckblatt: BV Bad Godesberg
  02.12.2026, Sitzung im Kalender verlinkt), 261605, 260491, 260065, 260336, 261320, 261573, 260310.
  Bei 261573 und 260310 ist „Rat entscheidet“ nur aus der Verfahrensvorlage abgeleitet (in den Daten steht
  nur eine Anhörung); der Knoten ist als voraussichtlich markiert, die Zuordnung hat Sicherheit „mittel“.
- **Grenzfall, behoben:** 260075 – das Veröffentlichungsdatum der Vorlage (06.02.) liegt nach der
  Ratsentscheidung (05.02.); der Eingangsknoten steht jetzt immer vorn.
- **Grenzfall, behoben:** 260067 – Rat hat den Antrag am 05.02. beschlossen, danach wurde eine
  Mitteilungsvorlage zur Kenntnis genommen. Der Status aus Schritt A nennt die Kenntnisnahme; der Abschluss
  zählt jetzt als „beschlossen“, damit der Mitwirken-Hinweis zur Umsetzung passt. Aktueller Knoten bleibt
  die Kenntnisnahme.
- **Grenzfall, behoben (18.10.):** 220577 – Antrag von 2022 (nur BV-Empfehlung), 2026 nur eine Große Anfrage
  mit Stellungnahme zur Kenntnis genommen. Eine spätere Anfrage oder Mitteilung ersetzt jetzt nicht mehr die
  Hauptvorlage (`vorgang.current_main`); Status `unklar`, weil eine Entscheidung in den Daten fehlt.
- **Grenzfall, behoben (18.10.):** 261109 – Große Anfrage mit Stellungnahme, die Sitzung am 02.09. wurde
  abgebrochen. Die Regel „Anfrage beantwortet“ greift erst nach der Vertagungsregel; Status `vertagt`, nächster
  Termin aus dem Kalender.
- **Annahme:** 260613 – zweimal vertagt (28.05. Mobilität, 15.07. AUKLA); der nächste Termin 25.11.2026
  ist die nächste AUKLA-Sitzung laut Kalender, nicht bestätigt (`quelle: kalender`).

Zweite Stichprobe am 18.10.2026 (15 Vorgänge, je eine Zelle Status × Verfahren, Seed 1815) gegen
`cache/get_paper_meetings` und `meetings_2026.jsonl`:

- **stimmt (13):** 261598, 261263 (Folgetermin aus dem Kalender angenommen), 260336, 252942 (`unklar`), 261804,
  260346, 260089, 261187 (Ratsberatung 11.06. ohne Ergebnis in den Rohdaten), 253195, 210685 (Große Anfrage zu
  einer Vorlage von 2021 noch offen, Termin vom Deckblatt), 260496, 260313, 261530.
- **behoben:** 240810 – die Erklärung schrieb die Tagesordnung vom 23.06.2026 (Mitteilung -02) dem Antrag zu;
  sie nennt jetzt das Dokument. 240891 – nach der Vertagung in der BV stand der Antrag am 15.09. im
  Mobilitätsausschuss (ohne Ergebnis); `vertagt` gilt jetzt nur, wenn danach keine Beratung mehr war → `offen`.

Allgemeine Grenzen:

- **Deckblätter:** Der Server hat bisher nur für 156 der 1.128 abgefragten Hauptdokumente Text
  (Extraktion läuft, etwa 1.000 PDFs pro Tag). Die übrigen stehen in
  `cache/get_file_text_ohne_text.json` und werden mit `python3 einordnung.py --abruf` erneut versucht.
- **Kalender-Termine** (`quelle: kalender`) sind Annahmen: nächste Sitzung desselben Gremiums nach einer
  Vertagung, nach einem verpassten Deckblatt-Termin oder wenn genau ein Gremium die Rolle schon hatte.
  Seite und Erklärung sagen „voraussichtlich“.
- **Tagesordnungen:** Bis 02.11.2026 steht keine Sitzung in `meetings_2026.jsonl`; künftige Sitzungen
  haben noch keine Tagesordnung (`quelle: tagesordnung` kommt erst nach `--aktualisieren` vor).
- **Rechtsgrundlagen je Rolle** sind allgemein: Empfehlung einer BV → BezS § 8, Anhörung → BezS § 9,
  Ausschuss → ZustO ohne Ziffer. Kenntnisnahmen haben meist keine eigene Rechtsgrundlage.
- **Einreicher** stammen aus dem Titel (Parteikürzel), daher „eingereicht von: Grüne“.
"""


def main():
    vorgaenge = json.loads(SRC.read_text())
    if "--abruf" in sys.argv:
        fetch_covers(vorgaenge)
    today = date.today().isoformat()
    orgs = Orgs()
    kal = Kalender(orgs, today, refresh="--aktualisieren" in sys.argv)
    zf = json.loads(ZUSAMMENFASSUNG.read_text()) if ZUSAMMENFASSUNG.exists() else {}
    b = Builder(Wissen(), orgs, kal, today, zf)
    details = [b.build(v) for v in vorgaenge]
    stale = write_all(details)
    report(details, vorgaenge, today)
    size = INDEX_OUT.stat().st_size
    active = [d for d in details if d["status"] in ("offen", "vertagt")]
    print(f"{len(details)} Vorgänge → {INDEX_OUT.relative_to(ROOT)} ({size / 1024:.0f} KB), "
          f"{DETAIL_DIR.relative_to(ROOT)}/ ({stale} veraltete gelöscht); offen/vertagt mit Termin: "
          f"{sum(1 for d in active if d['naechster_termin'])}/{len(active)}", file=sys.stderr)


if __name__ == "__main__":
    main()
