"""Public links for the legal references (Belege) used in data/verfahren.json.

`rechtsgrundlagen("§ 24 GO NRW, GeschO § 27")` returns
[{"label": "Gemeindeordnung NRW § 24", "url": ...}, {"label": "Geschäftsordnung des Rates § 27", "url": ...}].
Used by seite.py (Verstehen) and einordnung.py (Vorgänge).
"""
import json
import re
from pathlib import Path

# Bonner Ortsrecht auf bonn.de (Volltexte)
_ORTSRECHT = "https://www.bonn.de/service-bieten/stadtpolitik-ortsrecht/ortsrecht/"
URL_HS = _ORTSRECHT + "rat-ausschuesse-allgemeines/hauptsatzung.php"
URL_BEZS = _ORTSRECHT + "rat-ausschuesse-allgemeines/bezirkssatzung.php"
URL_GESCHO = _ORTSRECHT + "rat-ausschuesse-allgemeines/geschaeftsordnung-des-rates-der-bundesstadt-bonn.php"
URL_BETEILIGUNGSSATZUNG = (_ORTSRECHT + "recht-sicherheit/"
                           "satzung-zum-verfahren-bei-einwohnerantraegen-buergerbegehren-und-buergerentscheiden.php")
URL_LEITLINIEN = "https://www.bonn.de/medien-global/amt-30/ortsrecht/Bonn_Leitlinien_fuer_Beteiligung_2026.pdf"

ZUSTO_JSON = Path(__file__).parent / "data/zustaendigkeitsordnung.json"

# GO NRW on recht.nrw.de, consolidated version in force since 01.01.2026 (checked 18.10.2026,
# HTTP 200). The old /lmi/owa/br_text_anzeigen addresses give 404 since the portal relaunch;
# a newer version gets a new address, so check this link when the GO NRW changes.
URL_GO_NRW = ("https://recht.nrw.de/lrgv/gesetz/"
              "01012026-gemeindeordnung-fuer-das-land-nordrhein-westfalen-bekanntmachung-der/")
URL_BAUGB = "https://www.gesetze-im-internet.de/bbaug/"


def _zusto_url():
    try:
        return json.loads(ZUSTO_JSON.read_text())["quelle"]
    except (OSError, KeyError, ValueError):
        return None


# Short form -> (full name, URL)
GESETZE = {
    "GeschO": ("Geschäftsordnung des Rates", URL_GESCHO),
    "HS": ("Hauptsatzung", URL_HS),
    "BezS": ("Bezirkssatzung", URL_BEZS),
    "ZustO": ("Zuständigkeitsordnung", _zusto_url()),
    "Satzung": ("Satzung Einwohnerantrag und Bürgerbegehren", URL_BETEILIGUNGSSATZUNG),
    "Leitlinien": ("Leitlinien Beteiligung", URL_LEITLINIEN),
    "GO NRW": ("Gemeindeordnung NRW", URL_GO_NRW),
    "BauGB": ("Baugesetzbuch", URL_BAUGB),
}
PREFIX = ("GeschO", "HS", "BezS", "ZustO", "Satzung", "Leitlinien")
SUFFIX = ("GO NRW", "BauGB")

# "§ 24 GO NRW", "§ 3 Abs. 2 BauGB": paragraph first, law after.
_SUFFIX_RE = re.compile(r"(§§?\s*[^;§]*?)\s*\b(" + "|".join(map(re.escape, SUFFIX)) + r")\b")
# "GeschO §§ 7 Abs. 4, 9": law first, paragraphs until the next law name.
_LAWS = "|".join(PREFIX)
_PREFIX_RE = re.compile(rf"\b({_LAWS})\b\s*(.*?)(?=\s*[,;]\s*(?:\b(?:{_LAWS})\b|§)|\s*$)")


def rechtsgrundlagen(beleg):
    """Parse a Beleg string into [{label, url}], in order of appearance; unknown parts are dropped."""
    if not beleg:
        return []
    found = []
    rest = beleg
    for m in _SUFFIX_RE.finditer(beleg):
        found.append((m.start(), m.group(2), m.group(1).strip(" ,(")))
        rest = rest[:m.start()] + " " * (m.end() - m.start()) + rest[m.end():]
    for m in _PREFIX_RE.finditer(rest):
        found.append((m.start(), m.group(1), m.group(2).strip(" ,;)")))
    out, seen = [], set()
    for _, kurz, para in sorted(found):
        name, url = GESETZE[kurz]
        label = f"{name} {para}".strip()
        if label not in seen and url:
            seen.add(label)
            out.append({"label": label, "url": url})
    return out


if __name__ == "__main__":
    for b in ["GeschO §§ 7 Abs. 4, 9, 11, 26, 27", "§ 24 GO NRW, GeschO § 27", "ZustO; HS § 7 Abs. 2",
              "§ 25 GO NRW; Satzung § 2 Abs. 2", "§ 3 Abs. 2 BauGB", "ZustO VII 2.15, X 1.2", "§ 54 GO NRW, GeschO § 19",
              "HS § 10a", "Satzung § 3 Abs. 2, 4", "§ 37 Abs. 6 GO NRW, GeschO § 23 Abs. 7"]:
        print(f"{b!r:45} -> {[r['label'] for r in rechtsgrundlagen(b)]}")
