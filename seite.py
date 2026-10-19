"""Citizen page "Bonn entscheidet": web/index.html, web/assets/, web/daten/verfahren.json.

web/index.html comes from templates/index.html (banner, menu, start page; hash router in
templates/assets/app.js): "Politische Prozesse verstehen" shows one procedure from
data/verfahren.json as a swimlane (lanes.js), "Politische Vorgänge in Bonn" lists the Vorgänge
from web/daten/ (einordnung.py) with filters and one Vorgang beside it (vorgaenge.js).
seite.py fills the placeholders {{RATSINFO}}, {{OPARL}}, {{ORTSRECHT}}, {{GO_NRW}}, {{STAND}},
{{STAND_ISO}} of the start page ("Wo kommen die Daten her?"). verfahren.json also carries
"anzahl_2026" per procedure (from web/daten/vorgaenge-index.json). Independent of the Obsidian vault:
the "note" fields of data/verfahren.json are dropped from the page data.

Layout of the procedure timelines comes from verfahren.py. Legal references become public links via recht.py.
The block "fahrplan" (five stops, branches, mapping of steps/roles to stops)
fed the Fahrplan diagram of the old page and is still checked.
Sources: templates/index.html and templates/assets/*; web/ stays generated. Files in web/assets/
without a source in templates/assets/ are deleted.
Idempotent: files are only written when their content changes.
"""
import json
import re
from pathlib import Path

import verfahren as vf
from daten import write_if_changed
from recht import URL_GO_NRW, rechtsgrundlagen

ROOT = Path(__file__).parent
TEMPLATE = ROOT / "templates/index.html"
ASSETS_SRC = ROOT / "templates/assets"
WEB = ROOT / "web"
PAGE = WEB / "index.html"
DATA_OUT = WEB / "daten/verfahren.json"
INDEX = WEB / "daten/vorgaenge-index.json"  # written by einordnung.py; read for counts only

# "Wo kommen die Daten her?" on the start page (checked 18.10.2026, HTTP 200)
QUELLEN = {
    "RATSINFO": "https://www.bonn.sitzung-online.de/",
    "OPARL": "https://oparl.bonn.machdenstaat.de/",
    "ORTSRECHT": "https://www.bonn.de/service-bieten/stadtpolitik-ortsrecht/ortsrecht.php",
    "GO_NRW": URL_GO_NRW,
}

ZIELE = {"anstossen", "fragen", "mitreden", "verstehen"}
STATION_IDS = ["einbringen", "stellungnahme", "vorberatung", "entscheidung", "umsetzung"]
ABZWEIG_ARTEN = {"umweg", "schleife", "zurueck", "ende"}
EBENEN = {"stadt", "bezirk", "beides"}


def check(src):
    """Errors in the citizen-page fields of verfahren.json (organe, buerger, glossar)."""
    errs = []
    organ_ids = {o["id"] for o in src.get("organe", [])}
    lanes = {b["id"] for b in src["bahnen"]} | {"beirat"}
    for o in src.get("organe", []):
        for k in ("name", "kurz", "macht", "wer", "entscheidet", "erreichen", "beleg"):
            if not o.get(k):
                errs.append(f"organ {o['id']}: feld fehlt: {k}")
        if not 2 <= len(o.get("macht", [])) <= 4:
            errs.append(f"organ {o['id']}: macht braucht 2–4 Punkte")
        if o.get("farbe") not in lanes:
            errs.append(f"organ {o['id']}: unbekannte farbe {o.get('farbe')}")
        for b in o.get("beziehungen", []):
            if b["zu"] not in organ_ids:
                errs.append(f"organ {o['id']}: beziehung zu unbekanntem organ {b['zu']}")
    akteure = {a["id"] for a in src["akteure"]}
    verfahren = {v["id"] for v in src["verfahren"]}
    buerger = src.get("buerger", {})
    for vid in verfahren - buerger.keys():
        errs.append(f"buerger: verfahren ohne filter-tags: {vid}")
    for vid, b in buerger.items():
        if vid not in verfahren:
            errs.append(f"buerger: unbekanntes verfahren {vid}")
        for a in b.get("wer", []):
            if a not in akteure:
                errs.append(f"buerger {vid}: unbekannter akteur {a}")
        if b.get("ziel") not in ZIELE:
            errs.append(f"buerger {vid}: ziel {b.get('ziel')} nicht in {sorted(ZIELE)}")
        if b.get("ebene") not in EBENEN:
            errs.append(f"buerger {vid}: ebene {b.get('ebene')} nicht in {sorted(EBENEN)}")
        if not 1 <= len(b.get("mitwirken", [])) <= 3:
            errs.append(f"buerger {vid}: mitwirken braucht 1–3 Hinweise")
        for m in b.get("mitwirken", []):
            if not (m.get("was") and m.get("frist") and m.get("beleg")):
                errs.append(f"buerger {vid}: mitwirken ohne was/frist/beleg")
    return errs + check_fahrplan(src)


def check_fahrplan(src):
    """Errors in the block "fahrplan": five known stops, branches between stops, every procedure step mapped."""
    fp, errs = src.get("fahrplan"), []
    if not fp:
        return ["fahrplan: block fehlt"]
    ids = [s.get("id") for s in fp.get("stationen", [])]
    if ids != STATION_IDS:
        errs.append(f"fahrplan: stationen müssen {STATION_IDS} sein, nicht {ids}")
    known = set(STATION_IDS)
    organ_ids = {o["id"] for o in src.get("organe", [])}

    def note_ok(where, x):
        if not (x.get("beleg") or x.get("note")):
            errs.append(f"fahrplan {where}: beleg oder note fehlt")

    for s in fp.get("stationen", []):
        for k in ("label", "wer", "frist", "frist_text", "was"):
            if not s.get(k):
                errs.append(f"fahrplan station {s.get('id')}: feld fehlt: {k}")
        note_ok(f"station {s.get('id')}", s)
        for o in s.get("organe", []):
            if o not in organ_ids:
                errs.append(f"fahrplan station {s.get('id')}: unbekanntes organ {o}")
        for m in s.get("mitwirken", []):
            if not (m.get("id") and m.get("label") and m.get("text")):
                errs.append(f"fahrplan station {s.get('id')}: mitwirken ohne id/label/text")
            note_ok(f"station {s.get('id')} mitwirken {m.get('id')}", m)
    abz_ids = set()
    for a in fp.get("abzweige", []):
        abz_ids.add(a.get("id"))
        if a.get("art") not in ABZWEIG_ARTEN:
            errs.append(f"fahrplan abzweig {a.get('id')}: art {a.get('art')} nicht in {sorted(ABZWEIG_ARTEN)}")
        for st in [a.get("von"), *([a["nach"]] if a.get("nach") else []), *a.get("auch", [])]:
            if st not in known:
                errs.append(f"fahrplan abzweig {a.get('id')}: unbekannte station {st}")
        if not (a.get("label") and a.get("text")):
            errs.append(f"fahrplan abzweig {a.get('id')}: label oder text fehlt")
        note_ok(f"abzweig {a.get('id')}", a)
    steps = {v["id"]: {s["id"] for s in v["schritte"]} for v in src["verfahren"]}
    for v in src.get("einordnung_extra", {}).get("verfahren", []):
        steps[v["id"]] = {s["id"] for s in v["schritte"]}
    zu = fp.get("zuordnung", {})
    for vid in steps.keys() - zu.keys():
        errs.append(f"fahrplan zuordnung: verfahren fehlt: {vid}")
    for vid, z in zu.items():
        if vid not in steps:
            errs.append(f"fahrplan zuordnung: unbekanntes verfahren {vid}")
            continue
        for sid in steps[vid] - z.get("schritte", {}).keys():
            errs.append(f"fahrplan zuordnung {vid}: schritt ohne station: {sid}")
        for sid, st in z.get("schritte", {}).items():
            if sid not in steps[vid]:
                errs.append(f"fahrplan zuordnung {vid}: unbekannter schritt {sid}")
            if st not in known:
                errs.append(f"fahrplan zuordnung {vid}.{sid}: unbekannte station {st}")
        for a in z.get("abzweige", []):
            if a not in abz_ids:
                errs.append(f"fahrplan zuordnung {vid}: unbekannter abzweig {a}")
    extra = src.get("einordnung_extra", {}).get("schritte", {})
    for sid, st in fp.get("extra_schritte", {}).items():
        if sid not in extra:
            errs.append(f"fahrplan extra_schritte: unbekannter schritt {sid}")
        if st not in known:
            errs.append(f"fahrplan extra_schritte {sid}: unbekannte station {st}")
    rollen = {r["rolle"] for r in src.get("einordnung_extra", {}).get("rollen", [])}
    for r, st in fp.get("rollen", {}).items():
        if r not in rollen:
            errs.append(f"fahrplan rollen: unbekannte rolle {r}")
        if st not in known:
            errs.append(f"fahrplan rollen {r}: unbekannte station {st}")
    for a, st in fp.get("arten", {}).items():
        if st not in known:
            errs.append(f"fahrplan arten {a}: unbekannte station {st}")
    return errs


def stand():
    """Date of the data: latest activity in web/daten/vorgaenge-index.json (ISO), or None."""
    if not INDEX.exists():
        return None
    return max((v.get("zuletzt") or "" for v in json.loads(INDEX.read_text())["vorgaenge"]), default="") or None


def seite_html():
    """templates/index.html with the source links and the data date filled in."""
    iso = stand()
    werte = {**QUELLEN, "STAND_ISO": iso or "", "STAND": f"{iso[8:10]}.{iso[5:7]}.{iso[:4]}" if iso else "unbekannt"}
    html = re.sub(r"\{\{(\w+)\}\}", lambda m: werte[m.group(1)], TEMPLATE.read_text())
    if "{{" in html:
        raise SystemExit("templates/index.html: Platzhalter nicht ersetzt")
    return html


def counts_2026():
    """Vorgänge 2026 per procedure id ("anzahl_2026" in verfahren.json)."""
    if not INDEX.exists():
        return {}
    counts = {}
    for v in json.loads(INDEX.read_text())["vorgaenge"]:
        counts[v["verfahren"]] = counts.get(v["verfahren"], 0) + 1
    return counts


def page_data(src):
    lane_order = [b["id"] for b in src["bahnen"]]

    def enrich(x):
        x = dict(x)
        x.pop("note", None)  # vault note names: not part of the page
        if x.get("beleg"):
            x["recht"] = rechtsgrundlagen(x["beleg"])
        return x

    verfahren, anzahl = [], counts_2026()
    for v in src["verfahren"]:
        v = json.loads(json.dumps(v))  # copy; layout() writes into the steps
        v.pop("beispiele", None)  # real cases belong to the Vorgänge area
        v["layout"] = vf.layout(v["schritte"], v["achse"], lane_order)
        v["kanten"] = vf.edges(v)
        v.pop("note", None)
        v["schritte"] = [enrich(s) for s in v["schritte"]]
        v["ausgaenge"] = [enrich(a) for a in v["ausgaenge"]]
        b = src["buerger"][v["id"]]
        v.update(wer=b["wer"], ziel=b["ziel"], ebene=b["ebene"], mitwirken=[enrich(m) for m in b["mitwirken"]])
        if anzahl.get(v["id"]):
            v["anzahl_2026"] = anzahl[v["id"]]
        verfahren.append(v)
    fp = json.loads(json.dumps(src["fahrplan"]))
    fp.pop("hinweis", None)
    fp["stationen"] = [{**enrich(s), "mitwirken": [enrich(m) for m in s.get("mitwirken", [])],
                        **({"frist_recht": rechtsgrundlagen(s["frist_beleg"])} if s.get("frist_beleg") else {})}
                       for s in fp["stationen"]]
    fp["abzweige"] = [enrich(a) for a in fp["abzweige"]]
    organe = []
    for o in src["organe"]:
        o = enrich(o)
        o["beziehungen"] = [enrich(b) for b in o["beziehungen"]]
        organe.append(o)
    return {
        "bahnen": src["bahnen"], "akteure": src["akteure"],
        "fristen": [enrich(f) for f in src["fristen"]],
        "zustaendigkeit": [enrich(z) for z in src["zustaendigkeit"]],
        "organe": organe, "verfahren": verfahren, "fahrplan": fp,
        "glossar": [enrich(g) for g in src["glossar"]],
        "abkuerzungen": src["abkuerzungen"],
    }


def write_assets():
    """Copy templates/assets/ (with subfolders, e.g. fonts/) to web/assets/ and delete stale files there;
    returns the deleted names."""
    out = WEB / "assets"
    src = {p.relative_to(ASSETS_SRC) for p in ASSETS_SRC.rglob("*") if p.is_file()}
    for rel in sorted(src):
        ziel, data = out / rel, (ASSETS_SRC / rel).read_bytes()
        if not ziel.exists() or ziel.read_bytes() != data:
            ziel.parent.mkdir(parents=True, exist_ok=True)
            ziel.write_bytes(data)
    stale = sorted(p.relative_to(out) for p in out.rglob("*") if p.is_file() and p.relative_to(out) not in src)
    for rel in stale:
        (out / rel).unlink()
    return [str(r) for r in stale]


def main():
    src = vf.load()
    errs = vf.check(src) + check(src)
    for e in errs:
        print(f"ERROR verfahren.json: {e}")
    if errs:
        raise SystemExit(1)
    data = page_data(src)
    write_if_changed(DATA_OUT, json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n")
    stale = write_assets()
    write_if_changed(PAGE, seite_html())
    print(f"{len(data['organe'])} Organe, {len(data['verfahren'])} Verfahren → web/index.html, "
          f"web/daten/verfahren.json, web/assets/ (Stand {stand() or 'unbekannt'})"
          + (f"; veraltet gelöscht: {', '.join(stale)}" if stale else ""))


if __name__ == "__main__":
    main()
