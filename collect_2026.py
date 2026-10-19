"""All council proceedings (Vorgänge) of 2026 in the whole city of Bonn.

Flow:
  group      every paper of papers_2026.jsonl (plus 2026 agenda papers of the
             same Stammnummer) bundled by Stammnummer
  fetch      get_paper + get_paper_meetings per paper; older papers of the same
             Stammnummer (e.g. the 2025 main paper of a 2026 statement) are
             followed via super-/subordinated links; meetings outside
             meetings_2026.jsonl via get_meeting. All cached in cache/, so an
             interrupted run resumes and a second run needs no network.
  build      documents, consultations (with PDFs), status, level, next step

Writes data/stadt/vorgaenge_2026.json and data/stadt/bericht.md.
Options: --nur-abruf (fetch only).
"""
import json
import random
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

from daten import load_jsonl
from vorgang import (SIDE_TYPES, beratungen_2026, build_index, call, originators, stamm,
                     status_2026)

ROOT = Path(__file__).parent
OUT = ROOT / "data/stadt"
SAMPLE = OUT / "stichprobe.json"         # manual verdicts {stammnummer: {ok, notiz}}
LINKS = ("superordinated_papers", "subordinated_papers", "related_papers")


# --- Fetch ------------------------------------------------------------------------

class Progress:
    """One stderr line with count, rate and failures."""

    def __init__(self, label, total):
        self.label, self.total, self.done, self.t0 = label, total, 0, time.monotonic()

    def step(self, failed):
        self.done += 1
        if self.done % 20 and self.done != self.total:
            return
        dt = time.monotonic() - self.t0
        print(f"\r{self.label} {self.done}/{self.total} ({dt:.0f} s, {failed} Fehler)",
              end="", file=sys.stderr, flush=True)
        if self.done == self.total:
            print(file=sys.stderr)


def safe_call(tool, failures, **args):
    """vorgang.call, but a failing paper is logged and skipped (rerun retries it)."""
    try:
        return call(tool, **args)
    except Exception as err:  # network or server error; not cached
        failures.append({"tool": tool, "args": args, "fehler": str(err)[:200]})
        return None


def collect_groups(idx):
    """Stammnummer -> {paper id: list-view paper} for all 2026 papers and their agenda kin."""
    groups = defaultdict(dict)
    for p in load_jsonl("papers_2026.jsonl"):
        groups[stamm(p["reference"])][p["id"]] = p
    for ref, p in idx["papers"].items():
        st = stamm(ref)
        if st in groups and p.get("id"):
            groups[st].setdefault(p["id"], p)
    return groups


def fetch(groups, idx, failures):
    """get_paper for every paper (following same-Stammnummer links), then get_paper_meetings."""
    details, other = {}, defaultdict(dict)
    queue = [(st, pid) for st in sorted(groups) for pid in groups[st]]
    prog = Progress("get_paper", len(queue))
    while queue:
        st, pid = queue.pop(0)
        d = safe_call("get_paper", failures, paper_id=pid)
        if d:
            details[pid] = d
            for key in LINKS:
                for q in d.get(key) or []:
                    if stamm(q["reference"]) == st and q["id"] not in groups[st]:
                        groups[st][q["id"]] = q
                        queue.append((st, q["id"]))
                        prog.total += 1
                    elif stamm(q["reference"]) != st:
                        other[st][q["reference"]] = q["name"]
        prog.step(len(failures))

    pids = [pid for st in sorted(groups) for pid in groups[st]]
    prog = Progress("get_paper_meetings", len(pids))
    meeting_ids = set()
    for pid in pids:
        res = safe_call("get_paper_meetings", failures, paper_id=pid)
        for c in (res or {}).get("consultations") or []:
            if (c.get("meeting") or {}).get("id"):
                meeting_ids.add(c["meeting"]["id"])
        prog.step(len(failures))

    missing = sorted(meeting_ids - set(idx["meetings"]))
    prog = Progress("get_meeting", len(missing))
    for mid in missing:
        row = safe_call("get_meeting", failures, meeting_id=mid)
        if row:
            idx["meetings"][mid] = row
        prog.step(len(failures))
    return details, other


# --- Build ------------------------------------------------------------------------

def agenda_item(row, aid, ref, top):
    """The TOP of a meeting row: by id, else by paper reference, else by number."""
    items = (row or {}).get("agenda_items") or []
    hit = next((ai for ai in items if aid and ai.get("id") == aid), None) or next(
        (ai for ai in items if (ai.get("paper") or {}).get("reference") == ref), None)
    return hit or next((ai for ai in items if top and ai.get("number") == top), None)


def url(f):
    return (f or {}).get("access_url")


def consultations(paper, idx, gremienart, today):
    if paper.get("id") in idx["failed"]:  # get_paper_meetings failed in this run
        return []
    out = []
    for b in beratungen_2026(paper, idx):
        row = idx["meetings"].get(b["meeting_id"])
        ai = agenda_item(row, b["agenda_item_id"], paper["reference"], b["top"])
        ergebnis = b["ergebnis"] or (ai or {}).get("result") or None
        mt = (row or {}).get("meeting") or {}
        out.append({
            "reference": paper["reference"], "datum": b["datum"], "gremium": b["gremium"],
            "gremienart": gremienart.get(b["gremium_id"]), "rolle": b["role"],
            "authoritative": b["authoritative"], "ergebnis": ergebnis, "top": b["top"],
            "sitzung_url": mt.get("web_url"),
            "einladung_pdf": url(((row or {}).get("documents") or {}).get("invitation")),
            "beschluss_pdf": url((ai or {}).get("resolution_file")),
            "zukünftig": not ergebnis and (not b["datum"] or b["datum"] >= today)})
    return out


def level(berat, gremienart):
    """('stadt'|'bezirk'|None, district name or None) from the bodies involved."""
    arts = {b["gremium"]: b["gremienart"] for b in berat if b["gremium"]}
    bvs = sorted(g for g, a in arts.items() if a == "Bezirksvertretungen")
    bezirk = bvs[0].removeprefix("Bezirksvertretung ") if len(bvs) == 1 else None
    if not arts:
        return None, None
    return ("bezirk" if all(a == "Bezirksvertretungen" for a in arts.values()) else "stadt"), bezirk


def build_vorgang(st, group, details, other, idx, gremienart, today):
    docs, berat = [], []
    for pid, p in group.items():
        d = details.get(pid) or {}
        full = d.get("paper") or p
        docs.append({"reference": full["reference"], "name": full["name"],
                     "paper_type": full.get("paper_type"),
                     "datum": (full.get("published_date") or "")[:10] or None,
                     "web_url": full.get("web_url"), "pdf": url(d.get("main_file")),
                     "_full": full, "_detail": d})
        berat += consultations(full, idx, gremienart, today)
    docs.sort(key=lambda v: (v["datum"] or "", v["reference"]))
    berat.sort(key=lambda b: (b["datum"] or "9999", b["reference"], b["top"] or ""))
    main = [v for v in docs if v["paper_type"] not in SIDE_TYPES] or docs
    head = next((v for v in docs if v["reference"] == st), main[0])
    status, grund = status_2026(docs, berat, today)
    gremien = []
    for b in berat:
        if b["gremium"] and b["gremium"] not in gremien:
            gremien.append(b["gremium"])
    ebene, bezirk = level(berat, gremienart)
    upcoming = [b for b in berat if b["zukünftig"] and b["datum"]]
    pending = [b for b in berat if b["zukünftig"] and not b["datum"]]
    nxt = (upcoming or ([] if status == "abgeschlossen" else pending) or [None])[0]
    past = [b["datum"] for b in berat if b["datum"] and b["datum"] < today]
    zuletzt = max(past + [v["datum"] for v in docs if v["datum"]], default=None)
    return {"stammnummer": st, "titel": head["name"], "typ": head["paper_type"],
            "einreicher": originators(head["_full"], head["_detail"]),
            "status": status, "status_grund": grund, "ebene": ebene, "bezirk": bezirk,
            "gremien": gremien,
            "dokumente": [{k: v for k, v in d.items() if not k.startswith("_")} for d in docs],
            "beratungen": berat, "naechster_schritt": nxt, "zuletzt": zuletzt,
            "verwandte": [{"reference": r, "name": n} for r, n in sorted(other.items())]}


GRENZFAELLE = """
## Statusregeln und Grenzfälle

Regeln in `vorgang.status_2026`, in dieser Reihenfolge, gelesen an der *aktuellen Hauptvorlage*
(jüngste Vorlage ohne Stellungnahme/Änderungsantrag, die Beratungen hat; `vorgang.current_main`).
Ein späterer Bericht (Mitteilungsvorlage, Informationsbrief) oder eine spätere Anfrage zu einem Antrag
oder einer Beschlussvorlage ersetzt diese nicht als Hauptvorlage, außer die Anfrage ist noch nicht
behandelt (z. B. 261340: Ratsbeschluss, danach Mitteilung; 220577: Antrag 2022, Anfrage 2026).

1. **abgeschlossen**: verbindliche Beratung (`authoritative`) mit „beschlossen/abgelehnt/zugestimmt“,
   sonst ein Ergebnis „erledigt/zurückgezogen/zur Kenntnis genommen/beantwortet“, sonst Mitteilungsvorlage
   oder Informationsbrief ohne künftige Sitzung. Ausnahmen → **offen**: eine datierte Beratung nach dem
   Abschluss; ein nicht verbindliches „zur Kenntnis genommen“, während die verbindliche Beratung noch
   ohne Sitzung ist.
2. **vertagt**: alle Ergebnisse am jüngsten Ergebnis-Datum (aller Dokumente) lauten „vertagt“,
   „nicht aufgenommen“ oder „nicht behandelt“ (auch „wg. Sitzungsabbruch nicht behandelt“), und danach
   gab es keine vergangene Beratung ohne Ergebnis (sonst ist die Sache weitergewandert, z. B. 240891 → offen).
3. **abgeschlossen**: die Hauptvorlage ist eine (Große/Kleine) Anfrage oder Einwohnerfrage und eine
   Stellungnahme der Verwaltung liegt vor (erst nach Regel 2, damit eine Antwort aus einer abgebrochenen
   Sitzung als vertagt gilt, z. B. 261109).
4. **offen**: künftige oder nicht zugeordnete Beratung, verbindliche Beratung ohne Ergebnis, oder das
   letzte Ergebnis ist kein Abschluss (z. B. „verwiesen“, „ohne Votum“, Empfehlung ohne Entscheidung).
5. **unklar**: Die Hauptvorlage hat nur eine Empfehlung oder eine verbindliche Beratung ohne Ergebnis,
   danach kamen nur Berichte oder Nachfragen (z. B. 220577); oder es gibt keine Beratung und keine Regel greift.

Grenzfälle:

- **Keine datierten künftigen Beratungen.** Der Server ordnet eine Beratung erst einer Sitzung zu, wenn
  deren Tagesordnung steht. Alle künftigen Beratungen sind deshalb „nicht zugeordnet“ (ohne Datum und
  Gremium); `naechster_schritt` hat nie ein Datum, `vertagt` nie einen Folgetermin. Für Sitzungen der
  nächsten 14 Tage ohne Tagesordnung nutzt `build_index` einen einmal gecachten Abruf; neue
  Tagesordnungen erscheinen erst, wenn dieser Cache-Eintrag gelöscht wird.
- **Veraltete Planungen.** 180 abgeschlossene Vorgänge haben noch nicht zugeordnete Beratungen ohne
  Ergebnis (meist Kenntnisnahmen der Stellungnahme in weiteren Gremien). Sie ändern den Status nicht und
  werden nicht als `naechster_schritt` gezeigt.
- **Neue Runde.** Hat ein Vorgang mehrere Hauptvorlagen (267 Vorgänge, z. B. 242092: Rat 2024,
  BV 2025, neue Vorlage -05 im September 2026), zählt nur die jüngste mit Beratungen. Frühere
  Beschlüsse schließen den Vorgang nicht ab.
- **Wiederkehrende TOP-IDs.** Ein vertagter TOP behält in der nächsten Sitzung seine ID; der Server
  meldet die Beratung teils mit der ersten Sitzung, teils ohne Sitzung. `vorgang.beratungen_2026`
  verbindet eine Beratung ohne Sitzung über die TOP-ID mit der Tagesordnung 2026 und führt TOPs anderer
  Sitzungen als eigene Beratung ohne Rolle.
- **Empfehlung ohne Entscheidung.** Empfehlungen, Anregungen und Anhörungen mit „beschlossen“ schließen
  nicht ab; fehlt die verbindliche Beratung in den Daten (z. B. 260732, Anhörung im Planungsausschuss),
  bleibt der Vorgang offen.
- **Mitteilungen.** Mitteilungsvorlagen und Informationsbriefe gelten als abgeschlossen, auch wenn die
  Kenntnisnahme noch keiner Sitzung zugeordnet ist (die Information liegt mit der Vorlage vor).
- **Anfragen.** Mit Stellungnahme abgeschlossen, auch wenn diese erst später in der Sitzung behandelt
  wird. Kleine Anfragen ohne Stellungnahme in den Daten bleiben offen, obwohl sie oft schriftlich
  beantwortet sind.
- **Ebene.** `bezirk` nur, wenn alle Gremien mit bekannter Art Bezirksvertretungen sind; der Name des
  Bezirks steht auch bei `stadt`, wenn genau eine BV beteiligt ist. Ohne zugeordnete Sitzung ist kein
  Gremium bekannt (`ebene: null`).
- **Einreicher** stammen aus Titel und Typ der Hauptvorlage (`originators`); der Server liefert sie fast nie.
- **Umfang.** Grundlage sind Stammnummern mit Dokument 2026. Ältere Vorgänge, die 2026 nur beraten
  wurden, fehlen; ebenso die Vorgänge 261749 (nur als PDF bekannt) und 241355 (kein Dokument 2026).
- **Tagesbezug.** `zukünftig`, `zuletzt`, `naechster_schritt` und der Status hängen vom Laufdatum ab; zwei
  Läufe am selben Tag ergeben dieselbe Datei.
"""


# --- Report -------------------------------------------------------------------------

def cell(text):
    return (text or "–").replace("|", "/")


def report(vorgaenge, failures, gaps, today):
    docs = [d for v in vorgaenge for d in v["dokumente"]]
    berat = [b for v in vorgaenge for b in v["beratungen"]]
    with_berat = {b["reference"] for b in berat}
    lines = ["# Vorgänge 2026 in Bonn – Bericht", "",
             f"Stand der Daten: `papers_2026.jsonl`, `meetings_2026.jsonl` und `cache/`; "
             f"„künftig“ gilt relativ zum Lauf am {today}.", "",
             "## Zahlen", "",
             f"- Vorgänge: {len(vorgaenge)}, Dokumente: {len(docs)} (davon aus 2026: "
             f"{sum(1 for d in docs if (d['datum'] or '') >= '2026')}), Beratungen: {len(berat)}",
             f"- Fehlgeschlagene Abrufe: {len(failures)}", ""]
    statuses = ["offen", "vertagt", "abgeschlossen", "unklar"]
    by_type = defaultdict(Counter)
    for v in vorgaenge:
        by_type[v["typ"] or "(ohne Typ)"][v["status"]] += 1
    lines += ["## Status × Typ der Hauptvorlage", "",
              "| Typ | " + " | ".join(statuses) + " | gesamt |",
              "|---|" + "---:|" * (len(statuses) + 1)]
    for typ, c in sorted(by_type.items(), key=lambda kv: -sum(kv[1].values())):
        lines.append(f"| {typ} | " + " | ".join(str(c[s]) for s in statuses)
                     + f" | {sum(c.values())} |")
    total = Counter(v["status"] for v in vorgaenge)
    lines.append("| **gesamt** | " + " | ".join(f"**{total[s]}**" for s in statuses)
                 + f" | **{len(vorgaenge)}** |")
    lines += ["", "## Ebenen", ""]
    for (ebene, bezirk), n in Counter((v["ebene"], v["bezirk"]) for v in vorgaenge).most_common():
        lines.append(f"- {ebene or 'ohne Gremium'}"
                     + (f" · Bezirk {bezirk}" if bezirk else "") + f": {n}")
    no_berat = [d for d in docs if d["reference"] not in with_berat]
    lines += ["", "## Lücken", "",
              f"- Dokumente ohne Beratung: {len(no_berat)} ("
              + ", ".join(f"{t} {n}" for t, n in Counter(d["paper_type"] for d in no_berat)
                          .most_common()) + ")",
              f"- Vorgänge ohne jede Beratung: {sum(1 for v in vorgaenge if not v['beratungen'])}",
              f"- Beratungen ohne Sitzung (geplant, nicht zugeordnet): "
              f"{sum(1 for b in berat if not b['datum'])}, davon mit Ergebnis "
              f"{sum(1 for b in berat if not b['datum'] and b['ergebnis'])}",
              f"- Vergangene Beratungen ohne Ergebnis: "
              f"{sum(1 for b in berat if b['datum'] and b['datum'] < today and not b['ergebnis'])}",
              f"- Beratungen ohne Rolle (nur aus der Tagesordnung): "
              f"{sum(1 for b in berat if b['rolle'] is None)}",
              f"- Beratungen mit Ergebnis, aber ohne Beschluss-PDF: "
              f"{sum(1 for b in berat if b['ergebnis'] and not b['beschluss_pdf'])}",
              f"- Beratungen mit Sitzung, aber ohne Einladungs-PDF: "
              f"{sum(1 for b in berat if b['sitzung_url'] and not b['einladung_pdf'])}",
              f"- Dokumente ohne PDF: {sum(1 for d in docs if not d['pdf'])}",
              f"- Vorgänge ohne Einreicher: {sum(1 for v in vorgaenge if not v['einreicher'])}",
              f"- Stammnummern, die 2026 auf einer Tagesordnung stehen, aber kein Dokument von 2026 "
              f"haben (nicht enthalten): {gaps['nur_tagesordnung']}"]
    for f in failures[:10]:
        lines.append(f"- Abruf fehlgeschlagen: `{f['tool']}` {f['args']}: {f['fehler']}")
    lines += ["", "## Häufigste Status-Gründe", ""]
    generic = lambda g: re.sub(r"\d{6}\S*( ST)?", "…", re.sub(
        r" in [^„“;]*? am (\d\d\.\d\d\.\d{4}|ohne Datum)", " in … am …", g))
    pattern = Counter((v["status"], generic(v["status_grund"])) for v in vorgaenge)
    for (s, g), n in pattern.most_common(25):
        lines.append(f"- {n} × {s}: {g}")

    judged = json.loads(SAMPLE.read_text()) if SAMPLE.exists() else {}
    sample = random.Random(2026).sample(sorted(v["stammnummer"] for v in vorgaenge), 10)
    by_st = {v["stammnummer"]: v for v in vorgaenge}
    lines += ["", "## Stichprobe (10 zufällige Vorgänge)", ""]
    for st in sample:
        v = by_st[st]
        hist = "; ".join(f"{b['datum'] or 'o. D.'} {b['gremium'] or '?'} "
                         f"{b['rolle'] or '?'}: {b['ergebnis'] or '–'}"
                         for b in v["beratungen"]) or "keine Beratung"
        j = judged.get(st)
        verdict = (("stimmt" if j["ok"] else "falsch") + f" – {j['notiz']}") if j else "nicht beurteilt"
        lines += [f"- **{st}** {cell(v['titel'])[:90]} ({v['typ']}) → **{v['status']}**: "
                  f"{v['status_grund']}", f"  - Beratungen: {hist}", f"  - Prüfung: {verdict}"]
    lines += ["", GRENZFAELLE.strip()]
    (OUT / "bericht.md").write_text("\n".join(lines) + "\n")


def only_agenda(idx, groups):
    """Stammnummern on a 2026 agenda without any 2026 paper."""
    return len({stamm(r) for r in idx["agenda"]} - set(groups) - {None})


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    idx = build_index()
    groups = collect_groups(idx)
    failures = []
    details, other = fetch(groups, idx, failures)
    if failures:
        print(f"{len(failures)} Abrufe fehlgeschlagen, erster: {failures[0]}", file=sys.stderr)
    if "--nur-abruf" in sys.argv:
        return
    today = date.today().isoformat()
    idx["failed"] = {f["args"].get("paper_id") for f in failures
                     if f["tool"] == "get_paper_meetings"}
    gremienart = {o["id"]: o.get("classification") for o in load_jsonl("organizations.jsonl")}
    vorgaenge = [build_vorgang(st, groups[st], details, other.get(st, {}), idx, gremienart,
                               today) for st in sorted(groups)]
    vorgaenge.sort(key=lambda v: (v["zuletzt"] or "", v["stammnummer"]), reverse=True)
    (OUT / "vorgaenge_2026.json").write_text(
        json.dumps(vorgaenge, ensure_ascii=False, indent=1) + "\n")
    report(vorgaenge, failures, {"nur_tagesordnung": only_agenda(idx, groups)}, today)
    counts = Counter(v["status"] for v in vorgaenge)
    print(f"Vorgänge {len(vorgaenge)}, " + ", ".join(f"{k} {n}" for k, n in sorted(counts.items())),
          file=sys.stderr)


if __name__ == "__main__":
    main()
