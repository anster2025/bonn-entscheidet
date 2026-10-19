"""The hand-curated procedures in data/verfahren.json: loading, column layout of the steps, edges, checks.

Used by seite.py (timelines of "Verstehen") and einordnung.py. Steps sit on a time axis ("tage", "wochen",
"datum", "phasen"); layout() turns their times into columns, so same-day steps share a column and stack
inside their lane.
"""
import json
from collections import defaultdict
from pathlib import Path

SOURCE = Path(__file__).parent / "data/verfahren.json"

# Time units per layout column and the widest gap between two columns.
SCALE = {"tage": (7, 2), "wochen": (4, 3), "datum": (21, 3), "phasen": (1, 1)}


def load():
    return json.loads(SOURCE.read_text())


def tick_label(achse, t):
    if achse == "tage":
        return "T" if t == 0 else f"T {'−' if t < 0 else '+'} {abs(t)}"
    if achse == "wochen":
        return "Eingang" if t == 0 else f"Woche {t}"
    return ""


def layout(steps, achse, lane_order):
    """Add col/stack to each step; return ticks and the lanes in use.

    Columns grow with the time gap (SCALE) but at least by 1, so same-day
    steps share a column and stack inside their lane."""
    unit, max_gap = SCALE[achse]
    ts = sorted({s["t"] for s in steps})
    col, prev = {}, None
    for t in ts:
        col[t] = 0 if prev is None else col[prev] + min(max(1, (t - prev) / unit), max_gap)
        prev = t
    stacks = defaultdict(int)
    for s in steps:
        s["col"] = round(col[s["t"]], 2)
        s["stack"] = stacks[(s["t"], s["bahn"])]
        stacks[(s["t"], s["bahn"])] += 1
    ticks, prev = [], None
    for t in ts:
        named = next((s["zeit"] for s in steps if s["t"] == t and s.get("zeit")), None)
        sub = ""
        if achse == "wochen" and named:
            sub = tick_label(achse, t)
        elif achse == "datum" and prev is not None:
            sub = f"+{t - prev} Tage"
        ticks.append({"col": round(col[t], 2), "label": named or tick_label(achse, t), "sub": sub,
                      "luecke": prev is not None and (t - prev) / unit > max_gap, "frist": achse == "tage"})
        prev = t
    lanes = [b for b in lane_order if any(s["bahn"] == b for s in steps)]
    depth = {b: max([s["stack"] for s in steps if s["bahn"] == b], default=0) + 1 for b in lanes}
    return {"ticks": ticks, "bahnen": lanes, "tiefe": depth, "breite": round(col[ts[-1]], 2) if ts else 0}


def edges(v):
    if "kanten" in v:
        return v["kanten"]
    ids = [s["id"] for s in v["schritte"]]
    return [[a, b] for a, b in zip(ids, ids[1:])]


def check(src):
    """Errors in verfahren.json: unknown lanes, steps without source, broken edges, unknown procedures."""
    lanes = {b["id"] for b in src["bahnen"]}
    errs = []
    for i in src["instrumente"]:
        if i["verfahren"] not in {v["id"] for v in src["verfahren"]}:
            errs.append(f"instrument {i['name']}: verfahren fehlt: {i['verfahren']}")
    for v in src["verfahren"]:
        ids = {s["id"] for s in v["schritte"]}
        for s in v["schritte"]:
            if s["bahn"] not in lanes:
                errs.append(f"{v['id']}/{s['id']}: unbekannte bahn {s['bahn']}")
            if not (s.get("beleg") or s.get("note")):
                errs.append(f"{v['id']}/{s['id']}: weder beleg noch note")
            lab = (s.get("label") or "").strip()
            if not lab:
                errs.append(f"{v['id']}/{s['id']}: label fehlt")
            elif len(lab.split()) > 3:
                errs.append(f"{v['id']}/{s['id']}: label hat mehr als 3 Wörter: {lab}")
        for a, b in edges(v):
            if a not in ids or b not in ids:
                errs.append(f"{v['id']}: kante {a}->{b} zeigt ins Leere")
    return errs
