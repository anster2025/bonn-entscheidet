"""Step 1: raw pull of all 2026 papers, meetings and bodies of Bonn (input for collect_2026.py).

Writes to data/:
  organizations.jsonl   all active bodies
  papers_2026.jsonl     every paper published in 2026 (list view)
  meetings_2026.jsonl   every 2026 meeting with full agenda (get_meeting)
  consultations_sample.jsonl
                        consultation history for a stratified sample of
                        papers (up to SAMPLE_PER_TYPE per paper type)
"""
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

import mcp_client as m

DATA = Path(__file__).parent / "data"
YEAR_FROM, YEAR_TO = "2026-01-01", "2026-12-31"
SAMPLE_PER_TYPE = 25


def write_jsonl(name, rows):
    DATA.mkdir(exist_ok=True)
    with open(DATA / name, "w") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"{name}: {len(rows)}", file=sys.stderr)


def main():
    orgs = list(m.paginate("search_organizations", "organizations"))
    write_jsonl("organizations.jsonl", orgs)

    papers = list(m.paginate("search_papers", "papers", search_mode="list",
                             published_after=YEAR_FROM, published_before=YEAR_TO,
                             sort="oldest"))
    write_jsonl("papers_2026.jsonl", papers)

    meetings = list(m.paginate("search_meetings", "meetings", when="any",
                               include_cancelled=True,
                               **{"from": YEAR_FROM, "to": YEAR_TO}))
    full = []
    for i, mt in enumerate(meetings, 1):
        print(f"\rmeeting {i}/{len(meetings)}", end="", file=sys.stderr)
        full.append(m.call("get_meeting", meeting_id=mt["id"]))
    print(file=sys.stderr)
    write_jsonl("meetings_2026.jsonl", full)

    by_type = defaultdict(list)
    for p in papers:
        by_type[p["paper_type"]].append(p)
    rng = random.Random(2026)
    sample = []
    for ptype, group in sorted(by_type.items()):
        sample += rng.sample(group, min(SAMPLE_PER_TYPE, len(group)))
    rows = []
    for i, p in enumerate(sample, 1):
        print(f"\rconsultations {i}/{len(sample)}", end="", file=sys.stderr)
        rows.append(m.call("get_paper_meetings", paper_id=p["id"]))
    print(file=sys.stderr)
    write_jsonl("consultations_sample.jsonl", rows)


if __name__ == "__main__":
    main()
