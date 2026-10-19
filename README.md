# Bonn entscheidet · Bürgerseite für den Bonner Rat

Statische Bürgerseite für alle Ratsvorgänge der Stadt Bonn 2026: wie politische Prozesse laufen, wo ein Vorgang
steht, was als Nächstes kommt, dazu Statistiken und ein Feed mit Neuem. Python 3, nur Standardbibliothek; die Seite
ist reines HTML/CSS/JavaScript ohne Build-Schritt. Formate der Webdaten: [`SCHEMA.md`](SCHEMA.md).

## Schnellstart

Voraussetzung: Python 3 (nur Standardbibliothek, keine weiteren Pakete).

**Seite ansehen:** Die fertige Seite liegt in `web/`.

```bash
git clone https://github.com/anster2025/bonn-entscheidet.git
cd bonn-entscheidet
python3 -m http.server --directory web 8000
```

Dann http://localhost:8000 öffnen. Die Daten haben den Stand des letzten Uploads (siehe „Stand der Daten“ auf der Startseite).

**Daten selbst aktualisieren:** `./aktualisieren.sh` holt Neues vom OParl-Spiegel und schreibt Seite und Feed neu.
Der erste Lauf dauert deutlich länger (Größenordnung eine Stunde), weil `cache/` nicht im Repository liegt und alle
Vorgänge einmal abgerufen werden; danach nur noch Minuten. Täglich automatisch (Linux, systemd):
`systemd/installieren.sh`.

## Pipeline

| Schritt | Befehl | Ergebnis |
|---|---|---|
| Rohdaten 2026 (einmalig) | `python3 collect_overview.py` | `data/organizations.jsonl`, `papers_2026.jsonl`, `meetings_2026.jsonl` |
| Neues und Geändertes (live) | `python3 abruf_neu.py [--offene] [--seit JJJJ-MM-TT]` | ergänzt `data/*.jsonl`, frischt die betroffenen Einträge in `cache/` auf |
| Vorgänge ganz Bonn | `python3 collect_2026.py [--nur-abruf]` | `data/stadt/vorgaenge_2026.json`, `data/stadt/bericht.md` |
| Inhaltssätze (halbautomatisch) | `python3 zusammenfassung.py run [--limit N]` | `data/zusammenfassung.json` per `claude -p` aus gecachten Dokumenttexten |
| Einordnung | `python3 einordnung.py [--aktualisieren] [--abruf]` | `web/daten/vorgaenge-index.json`, `web/daten/vorgang/<nr>.json`, `data/stadt/einordnung_bericht.md` |
| Seite | `python3 seite.py` | `web/index.html`, `web/assets/`, `web/daten/verfahren.json` |
| Feed | `python3 feed.py` | `web/feed.xml`, Verlauf `data/stadt/feed.json` |
| Prüfung | `python3 lint.py` | `data/verfahren.json` und `web/daten/`; Exit-Code 1 bei Fehlern |
| Alles offline | `./stadt.sh [--aktualisieren] [--abruf] [--zusammenfassung]` | collect_2026 → (zusammenfassung) → einordnung → seite → lint |
| Täglich (Timer) | `./aktualisieren.sh [--offene]` | abruf_neu → collect_2026 → einordnung `--aktualisieren` → seite → feed → lint |

Gemeinsame Helfer: `mcp_client.py` (MCP-Aufrufe mit Cache), `daten.py` (`load_jsonl`, `write_if_changed`),
`vorgang.py` (Vorgänge, Status), `verfahren.py` (Verfahren aus `data/verfahren.json`: Layout, Kanten, Prüfung),
`recht.py` (Rechtsgrundlagen als Links). Server-Antworten liegen in `cache/` (nicht im Repository).

## Bürgerseite

http://127.0.0.1:8767/index.html, ausgeliefert von `bonn-rat-seite.service` (`python3 -m http.server` auf `web/`,
eingerichtet mit `systemd/installieren.sh`). Quellen: `templates/index.html` und
`templates/assets/` (`app.js` Router, `vorgaenge.js`, `statistik.js`, `ueberblick.js`, `lanes.js` Ablaufdiagramme,
`popover.js`, `ratsblatt.css` Designsystem, `fonts/` Fraunces und Atkinson Hyperlegible Next, lokal, OFL);
`web/` wird erzeugt.

Aufbau: fester Kopf (Banner, Menüknöpfe Start · Verstehen · Vorgänge · Statistik), nur der Inhalt scrollt.

- `#start`: Einführung in Du-Form, „Wo kommen die Daten her?“ (Quellen, Stand, Feed-Link).
- `#verstehen[/<verfahren>]`: „Zeig mir“ mit Auswahl; Standard ist der Gesamtüberblick (Schaubild der Gremien,
  `ueberblick.js`), sonst ein Ablauf aus `data/verfahren.json` als Swimlane. Ausgänge als abzweigende Pfeile.
- `#vorgaenge[?filter][/<nr>]`: links einklappbare Filter (Suche, Status, Gremium, Art, Fraktion, Thema,
  Zeitraum: Jahr oder eigener Zeitraum) und Liste, rechts der Vorgang mit Ablaufdiagramm. Erledigte Schritte
  blass, der aktuelle in voller Farbe, mögliche nächste Schritte gestrichelt; breite Diagramme scrollen seitlich
  (zum aktuellen Schritt), unter 640 px Fensterbreite senkrechte Liste.
- `#statistik[?filter]`: Ringdiagramme zu Stand, Art, Fraktionen, Themen mit Filtern und Link „In der Liste ansehen“.

Farben je Akteur (`--bahn-<id>`), Akzent `#ffa54f`, Kontraste an den Tokens in `ratsblatt.css`.
Rechtsgrundlagen werden über `recht.py` zu öffentlichen Links (bonn.de, recht.nrw.de, gesetze-im-internet.de);
bei einer neuen Fassung der GO NRW `URL_GO_NRW` anpassen.

## Daten ganz Bonn 2026

`collect_2026.py` bündelt alle Dokumente aus `papers_2026.jsonl` nach Stammnummer zu Vorgängen (Stand 18.10.2026:
1.856 Vorgänge, 3.880 Dokumente, 5.879 Beratungen). Für jedes Dokument holt es `get_paper` und `get_paper_meetings`
(gecacht in `cache/`, ein zweiter Lauf braucht kein Netz) und verbindet die Beratungen mit den Tagesordnungen aus
`meetings_2026.jsonl`. Die gemeinsamen Helfer liegen in `vorgang.py`.

Der Status (`vorgang.status_2026`) hat vier Werte mit Begründung: `offen`, `vertagt`, `abgeschlossen`, `unklar`.
Gelesen wird an der aktuellen Hauptvorlage (`vorgang.current_main`): die jüngste Vorlage mit Beratungen, ohne
Stellungnahmen und Änderungsanträge. Eine spätere Mitteilung oder bereits beantwortete Anfrage zu einem Antrag
oder einer Beschlussvorlage ersetzt diese nicht. Die Regeln und Grenzfälle stehen in `data/stadt/bericht.md`.
Status und „künftig“ hängen vom Laufdatum ab.

## Einordnung

`einordnung.py` ordnet jeden Vorgang einem Verfahren aus `data/verfahren.json` zu (nach Dokumenttyp, Einreicher und
Gremienart, mit Sicherheit „hoch“ oder „mittel“). Daraus baut es das Flussdiagramm: tatsächliche Schritte,
aktueller Knoten und erwartete Schritte. Erwartete Schritte stammen aus der Beratungsfolge auf dem Deckblatt
(`--abruf` holt fehlende Deckblätter), aus Tagesordnungen künftiger Sitzungen (`--aktualisieren`), aus dem
Sitzungskalender oder aus der Verfahrensvorlage; jeder ist mit seiner Quelle markiert. Die Mitwirkungshinweise
kommen aus den Regeln `einfluss_regeln` in `verfahren.json`, jeweils mit Frist und Rechtsgrundlage. Ohne Option
arbeitet der Schritt nur mit lokalen Daten. Prüfbericht mit Stichprobe: `data/stadt/einordnung_bericht.md`.

## Zusammenfassungen

`zusammenfassung.py` ergänzt „Worum geht's?“ um einen Inhaltssatz, wo der Text des Hauptdokuments im Cache liegt
(`cache/get_file_text/`, Deckblatt-Auszug bis 6.000 Zeichen über `einordnung.haupttext`: Ursprungsdokument, sonst
aktuelle Hauptvorlage, sonst das erste Dokument mit Text; Stand 18.10.2026: 117 Vorgänge ohne nichtöffentliche):

- `ask`: headless `claude -p` (Abo, Prompt `zusammenfassung_prompt.md`, nur die Werkzeuge Read/Write) schreibt je
  Vorgang einen neutralen Satz (≤ 30 Wörter, ohne Bewertung) oder `null`, 20 Vorgänge je Aufruf, neueste zuerst.
  Ergebnisse liegen in `cache/zusammenfassung.json` unter `<stammnummer>|<sha1 des Texts>` und werden nie erneut
  erfragt; ändert sich der Text, wird neu gefragt.
- `merge`: schreibt `data/zusammenfassung.json` (`{stammnummer: {satz, reference}}`); `einordnung.py` übernimmt es als `worum_ki`.
- `run`: beides. Option `--limit N`. Dauer: rund 15 s für 5 Vorgänge (ein Aufruf); alle rund 4–6 Minuten.

`stadt.sh` ruft den Schritt nur mit `--zusammenfassung` auf. Ohne die Option gelten die gespeicherten Sätze.

## Datenquellen und Lizenzen

- **Code:** MIT-Lizenz, siehe `LICENSE`.
- **Ratsinformationen:** Ratsinformationssystem der Bundesstadt Bonn, über die OParl-Schnittstelle von der Stadt
  Bonn als offene Daten unter [CC0](https://creativecommons.org/publicdomain/zero/1.0/deed.de) bereitgestellt
  ([Open-Data-Katalog NRW](https://ckan.open.nrw.de/dataset/ratsinformationssystem-oparl-api-bn)). Abgerufen über
  den OParl-Lite-Spiegel `https://oparl.bonn.machdenstaat.de` (MCP, nur lesend), weil die Original-API
  `bonn.sitzung-online.de/public/oparl` per Captcha gesperrt ist. PDFs verlinken auf `bonn.sitzung-online.de`.
  Die Daten in `data/` und `web/daten/` sind daraus abgeleitet; Einordnung, Themen und Statistik sind eigene
  Auswertungen ohne Gewähr und keine Rechtsberatung.
- **Verfahrenswissen:** handgepflegt in `data/verfahren.json`, belegt mit Gemeindeordnung NRW und Bonner Ortsrecht
  (Links in `recht.py`).
- **Schriften:** Fraunces, Atkinson Hyperlegible Next (SIL OFL 1.1), siehe `templates/assets/fonts/LIZENZ.txt`.

## Bekannte Lücken

- Manche Vorlagen gibt es nur als Datei (`nur_datei`), ohne OParl-Eintrag; ihre Beratungsfolge stammt aus dem Deckblatt.
- Künftige Beratungen haben oft noch keine Sitzung („Sitzung nicht zugeordnet“); Termine teils aus dem
  Sitzungskalender angenommen (`quelle: kalender`), die Seite sagt dann „voraussichtlich“.
- Einreicher stehen selten in den Daten und werden aus dem Titel gelesen. Themen sind eine Näherung
  (Fachausschuss, sonst Stichwörter im Titel, `THEMEN` in `einordnung.py`).
- Den Deckblatt-Text hat der Server bisher nur für einen Teil der Hauptdokumente extrahiert;
  `python3 einordnung.py --abruf` versucht die übrigen erneut. Nur Vorgänge mit Text bekommen einen Inhaltssatz.
- Der Spiegel verknüpft Tagesordnungspunkte erst Tage nach einer Sitzung mit Vorlagen (siehe Aktualisierung).
- Ältere Vorgänge, die 2026 nur beraten wurden und kein Dokument von 2026 haben, fehlen (151 Stammnummern).

## Aktualisierung und Feed

`mcp_client.py` speichert jede Serverantwort dauerhaft in `cache/`; ein bloßer Neulauf sieht deshalb nichts Neues.
`abruf_neu.py` fragt live (ohne Cache) genau das ab, was sich geändert haben kann, und überschreibt dabei die
Cache-Einträge, die die folgenden Offline-Schritte lesen:

- **Neue Vorlagen** seit dem letzten Lauf (`search_papers`, `published_after`, 2 Tage Überlappung).
- **Sitzungen** von 28 Tagen vor dem letzten Lauf bis 14 Tage voraus (`search_meetings` + `get_meeting`). Der
  Spiegel verknüpft Tagesordnungspunkte erst einige Tage nach der Sitzung mit Vorlagen; bis dahin ordnet der
  exakte Titel zu. Einen Filter „geändert seit“ gibt es nicht, Änderungen an Vorgängen findet der Lauf über diese Sitzungen.
- **Betroffene Vorgänge** (alle Dokumente derselben Stammnummer): `get_paper` und `get_paper_meetings` live.
- **Sonntags** (oder `--offene`) zusätzlich alle nicht abgeschlossenen Vorgänge als Sicherheitsnetz.

Stand des letzten Laufs: `data/stadt/abruf_stand.json`. `feed.py` vergleicht den Index vor dem Lauf
(`data/stadt/index_vorher.json`) mit dem neuen und schreibt neue Vorgänge, neue Schritte und neue Termine in
`data/stadt/feed.json` (Verlauf, 300 Einträge) und `web/feed.xml` (Atom, 100 Einträge). Links zeigen auf
`BONN_RAT_URL` (Standard `http://127.0.0.1:8767/`); für eine öffentlich gehostete Seite die Variable setzen.

Timer: `systemd/bonn-rat-update.{service,timer}`. `systemd/installieren.sh` setzt den Pfad dieses Ordners in die
Vorlagen ein (Platzhalter `@PROJEKT@`), schreibt die Units nach `~/.config/systemd/user/` und startet Seite und Timer.
Status `systemctl --user list-timers bonn-rat-update.timer`, Protokoll `journalctl --user -u bonn-rat-update.service -n 50`.
Die Seite deckt 2026 ab (`papers_2026.jsonl`, `JAHR_ENDE` in `abruf_neu.py`); zum Jahreswechsel anpassen.
