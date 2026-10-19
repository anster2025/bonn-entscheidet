"""Check the citizen page's data. Exit code 1 if any error is found.

  data/verfahren.json   verfahren.check (lanes, sources, short labels of at most 3 words, edges) and
                        seite.check (organe, filter tags "buerger", fahrplan)
  web/daten/            einordnung.check (exactly one current node per Vorgang, known vor/nach ids, legal
                        references with URL, known procedure ids, einfluss_regeln, einordnung_extra.worum)
"""
import sys

import einordnung
import seite
import verfahren


def main():
    src = verfahren.load()
    fehler = [f"data/verfahren.json: {e}" for e in verfahren.check(src) + seite.check(src)]
    fehler += [f"web/daten: {e}" for e in einordnung.check()]
    for e in fehler:
        print(f"ERROR {e}")
    print(f"Prüfung: {len(src['verfahren'])} Verfahren, {len(src['organe'])} Organe, Webdaten – {len(fehler)} Fehler")
    sys.exit(1 if fehler else 0)


if __name__ == "__main__":
    main()
