"""Content sentence ("worum_ki") per Vorgang for the citizen page, half automatic.

Flow:
  ask    for Vorgänge whose main document text is cached (cache/get_file_text, the cover-page
         excerpt of einordnung.haupttext) headless `claude -p` (zusammenfassung_prompt.md, tools
         Read/Write, subscription) writes ONE neutral German sentence (≤ 30 words) on the content,
         or null when the text says no more than the title. Results are kept in
         cache/zusammenfassung.json, keyed by "<stammnummer>|<sha1 of the text, 12 chars>",
         and never asked twice (null included); a changed text is asked again.
  merge  data/zusammenfassung.json = {stammnummer: {satz, reference}} for the current texts;
         einordnung.py reads it as "worum_ki".

Nichtöffentliche Sammelpunkte are skipped. Newest activity first, so --limit N takes the latest.

Usage:
  python3 zusammenfassung.py ask   [--limit N]
  python3 zusammenfassung.py merge
  python3 zusammenfassung.py run   [--limit N]   (ask, merge)
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

import einordnung
from daten import write_if_changed

ROOT = Path(__file__).parent
SRC = ROOT / "data/stadt/vorgaenge_2026.json"
CACHE = ROOT / "cache/zusammenfassung.json"   # {"<st>|<hash>": {"satz", "reference", "datum"}}
OUT = einordnung.ZUSAMMENFASSUNG
INP, OUTP = ROOT / "cache/zusammenfassung_input.json", ROOT / "cache/zusammenfassung_output.json"
BATCH = 20          # Vorgänge per claude call
TIMEOUT = "20m"
MAX_WOERTER = 35    # a little slack over the 30 asked for; longer answers stay open
OHNE = {"Tagesordnungspunkte in nichtöffentlicher Sitzung"}


def kandidaten():
    """[(vorgang, reference, text, key)] with cached main text, newest activity first."""
    out = []
    for v in json.loads(SRC.read_text()):
        if v["typ"] in OHNE:
            continue
        ref, text = einordnung.haupttext(v)
        if not text:
            continue
        text = re.sub(r"[ \t]+", " ", re.sub(r"\n{3,}", "\n\n", text)).strip()
        key = f"{v['stammnummer']}|{hashlib.sha1(text.encode()).hexdigest()[:12]}"
        out.append((v, ref, text, key))
    out.sort(key=lambda x: (x[0]["zuletzt"] or "", x[0]["stammnummer"]), reverse=True)
    return out


def lade():
    return json.loads(CACHE.read_text()) if CACHE.exists() else {}


def run_ask(limit):
    cache = lade()
    todo = [k for k in kandidaten() if k[3] not in cache][:limit]
    if not todo:
        print("zusammenfassung: nichts zu fragen", file=sys.stderr)
        return
    prompt = (ROOT / "zusammenfassung_prompt.md").read_text()
    env = dict(os.environ, PATH=f"{Path.home()}/.local/bin:{os.environ.get('PATH', '')}")
    heute = date.today().isoformat()
    for i in range(0, len(todo), BATCH):
        batch = todo[i:i + BATCH]
        print(f"zusammenfassung batch {i // BATCH + 1}: {len(batch)} Vorgänge", file=sys.stderr)
        INP.write_text(json.dumps([{"stammnummer": v["stammnummer"], "titel": v["titel"], "typ": v["typ"],
                                    "text": text} for v, _, text, _ in batch], ensure_ascii=False, indent=1))
        OUTP.unlink(missing_ok=True)
        t0 = time.monotonic()
        proc = subprocess.run(["timeout", TIMEOUT, "claude", "-p", prompt,
                               "--allowedTools", "Read,Write", "--output-format", "text"],
                              cwd=ROOT, env=env, capture_output=True, text=True)
        dauer = time.monotonic() - t0
        if proc.returncode != 0 or not OUTP.exists():
            print(f"zusammenfassung failed ({proc.returncode}, {dauer:.0f} s): {proc.stderr[-300:]}", file=sys.stderr)
            continue
        try:
            result = json.loads(OUTP.read_text())
        except json.JSONDecodeError:
            print("zusammenfassung output is not JSON; batch skipped", file=sys.stderr)
            continue
        valid = {}
        for r in result if isinstance(result, list) else []:
            satz = r.get("satz")
            if "satz" in r and (satz is None or isinstance(satz, str) and 0 < len(satz.split()) <= MAX_WOERTER):
                valid[str(r.get("stammnummer"))] = satz.strip() if satz else None
        got = 0
        for v, ref, _, key in batch:
            if v["stammnummer"] in valid:
                cache[key] = {"satz": valid[v["stammnummer"]], "reference": ref, "datum": heute}
                got += 1
        print(f"  {got}/{len(batch)} in {dauer:.0f} s" + (" (fehlende bleiben offen)" if got < len(batch) else ""),
              file=sys.stderr)
        CACHE.write_text(json.dumps(dict(sorted(cache.items())), ensure_ascii=False, indent=1) + "\n")


def run_merge():
    cache, out, offen = lade(), {}, 0
    for v, ref, _, key in kandidaten():
        e = cache.get(key)
        if e is None:
            offen += 1
        elif e["satz"]:
            out[v["stammnummer"]] = {"satz": e["satz"], "reference": e["reference"]}
    write_if_changed(OUT, json.dumps(dict(sorted(out.items())), ensure_ascii=False, indent=1) + "\n")
    print(f"zusammenfassung.json: {len(out)} Sätze, {offen} Vorgänge mit Text noch nicht gefragt", file=sys.stderr)


def main():
    args = sys.argv[1:]
    cmd = args[0] if args and not args[0].startswith("-") else "run"
    limit = int(args[args.index("--limit") + 1]) if "--limit" in args else None
    if cmd not in ("ask", "merge", "run"):
        sys.exit(__doc__)
    if cmd in ("ask", "run"):
        run_ask(limit)
    run_merge()


if __name__ == "__main__":
    main()
