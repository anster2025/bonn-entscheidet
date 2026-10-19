"""Shared helpers for the data files of the citizen page: data/*.jsonl and writing only on change."""
import json
from pathlib import Path

DATA = Path(__file__).parent / "data"


def load_jsonl(name):
    with open(DATA / name) as f:
        return [json.loads(line) for line in f]


def write_if_changed(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.read_text() != text:
        path.write_text(text)
