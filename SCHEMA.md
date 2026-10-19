# Datenformate · Bürgerseite „Bonn entscheidet“

Alle Datumsangaben ISO (`YYYY-MM-DD`).

## Webdaten der Bürgerseite (`web/daten/`)

Erzeugt von `einordnung.py` (Vorgänge) und `seite.py` (`verfahren.json`), kompaktes JSON ohne Einrückung, nur bei
Änderung neu geschrieben. Datumsangaben sind ISO (`YYYY-MM-DD`). `lint.py` prüft die Dateien über `einordnung.check()`.

### `web/daten/vorgaenge-index.json`

Die Liste für „Politische Vorgänge in Bonn“ (`vorgaenge.js`), vom Browser einmal geladen.

```json
{"hinweis": "…",
 "gremien": ["Ausschuss für …", "Bezirksvertretung Bonn", "Rat", …],
 "vorgaenge": [{"stammnummer": "261933", "titel": "…", "typ": "Antrag", "status": "offen",
                "status_grund": "Kurzform des Status-Grunds (≤ 80 Zeichen)", "verfahren": "antrag-bv",
                "ebene": "bezirk", "bezirk": "Bonn", "gremien": [4, 17],
                "zuletzt": "2026-10-16", "termine": ["2026-09-30", "2026-10-16"], "einreicher": ["Grüne"], "thema": "Verkehr & Mobilität", "gremium": 15, "naechster": ["2026-11-03", 15],
                "suchtext": "Einreicher und weitere Drucksachennummern"}]}
```

- `gremien` (je Vorgang), `gremium` und `naechster[1]` sind **Positionen** in der Liste `gremien` oben; `naechster` = `[datum, gremium]`, das Gremium kann `null` sein.
- `gremium`: wo der Vorgang steht (Gremium des aktuellen Knotens, sonst das zuletzt beratende, sonst das des nächsten Termins); die Liste zeigt es mit Bahnfarbe.
- `einreicher` (wie im Vorgang) und `thema` (eins von `THEMEN` in `einordnung.py`: erster Fachausschuss, sonst Stichwörter im Titel, sonst „Sonstiges“) speisen den Bereich „Statistik“ (`statistik.js`).
- `termine`: sortierte Daten aller tatsächlichen Schritte und Dokumente; danach filtert die Seite nach Jahr und Zeitraum (zusammen mit `naechster[0]`).
- Leere Felder (`null`, `false`, `0`, `[]`, `""`) fehlen, um die Datei klein zu halten.
- `status`: `offen | vertagt | abgeschlossen | unklar`; `verfahren`: Id aus `data/verfahren.json` (`verfahren` oder `einordnung_extra.verfahren`); `ebene`: `stadt | bezirk`, fehlt ohne bekanntes Gremium.

### `web/daten/vorgang/<stammnummer>.json`

Ein Vorgang mit Flussdiagramm, beim Öffnen geladen. Veraltete Dateien löscht `einordnung.py`.

| Feld | Inhalt |
|---|---|
| `stammnummer`, `titel`, `typ`, `einreicher`, `status`, `status_grund`, `ebene`, `bezirk`, `gremien`, `zuletzt` | wie in `data/stadt/vorgaenge_2026.json`; `status_grund` hier ungekürzt |
| `verfahren` | `{id, titel, kurz, sicherheit: hoch|mittel, grund}` |
| `worum` | ein bis zwei kurze Sätze unter der Metazeile: Art der Sache, Einreicher:in, entscheidendes Gremium; ohne Datum und Stand (die stehen in der Metazeile). Vorlagen je Verfahren in `einordnung_extra.worum` von `data/verfahren.json`: `[satz, satz mit {entscheider}]`, `{von}` = „ von der CDU“ usw.; der zweite Satz entfällt ohne bekanntes Entscheidungsgremium und wenn das Gremium schon in der Metazeile steht (Stand-Gremium oder nächster belegter Termin; außer bei Eilentscheidungen) |
| `worum_ki` | ein Satz zum Inhalt (≤ 30 Wörter) aus `data/zusammenfassung.json` (`zusammenfassung.py`), sonst `null`; die Seite kennzeichnet ihn als „automatisch zusammengefasst“ |
| `knoten` | Flussdiagramm, in Reihenfolge (siehe unten) |
| `naechster_termin` | `{datum, gremium, gremienart, rolle, sitzung_url, quelle}` oder `null`; `quelle`: `sitzung | tagesordnung | deckblatt | kalender` |
| `mitwirken` | `[{id, was, frist, frist_datum, rechtsgrundlagen, beleg}]` aus `einfluss_regeln`; `frist_datum` ist absolut, die Seite vergleicht mit dem heutigen Datum |
| `dokumente` | `[{reference, name, typ, datum, art, pdf, ratsinfo, beratungsfolge_plan}]`; `art`: `eingang | stellungnahme | aenderungsantrag | folgevorlage`; `beratungsfolge_plan`: Zeilen vom Deckblatt `[{gremium, gremium_id, gremienart, datum, rolle}]`, `[]` ohne Tabelle, `null` ohne Deckblatt-Text |
| `verwandte` | `[{reference, name}]` verlinkte Dokumente anderer Stammnummern |

Jeder Knoten hat `id` (`k01`, `k02`, …), `art`, `titel`, `datum` (oder `null`), `status` (`erledigt | geplant`),
`erwartet` (bool, voraussichtlicher Schritt), `aktuell` (genau ein Knoten ist `true`), `vor`/`nach` (Ids der Nachbarn),
`schritt` (`{id, was}` in der Verfahrensvorlage oder `null`), `rechtsgrundlagen` (`[{label, url}]`), `beleg` und optional `hinweis` und `quelle` (`ratsinfo | sitzung | tagesordnung | deckblatt | kalender | verfahren`). Je nach `art`:

- `eingang`: das Ausgangsdokument mit `reference`, `pdf`, `ratsinfo`, `einreicher`
- `beratung`: eine Sitzung mit `gremium`, `gremienart`, `rolle`, `rolle_text`, `ergebnis` (Rohtext), `ergebnis_gruppe`
  (`beschlossen | abgelehnt | vertagt | zur Kenntnis | erledigt | offen`), `top`, `sitzung_url`, `einladung_pdf`,
  `beschluss_pdf` und `punkte` (alle Dokumente des Vorgangs in diesem TOP: `{reference, art, rolle, ergebnis, ergebnis_gruppe, top, beschluss_pdf, pdf, ratsinfo}`)
- `dokument`: Begleitdokument ohne eigene Beratung, mit `dokument_art`, `name`, `typ`, `reference`, `pdf`, `ratsinfo`
- `vorlage`: voraussichtlicher Schritt aus der Verfahrensvorlage (`quelle: verfahren`), ohne Datum

### `web/daten/verfahren.json`

Von `seite.py` aus `data/verfahren.json`: Bahnen, Akteure, Fristen, Zuständigkeit, Organe, Verfahren (mit `layout`,
`kanten`, Filter-Tags `wer`/`ziel`/`ebene`, `mitwirken`, `anzahl_2026`), Glossar und Abkürzungen. Belege sind um
`recht` (`[{label, url}]`) ergänzt; die `note`-Felder der Quelldatei (Notizen des früheren Vaults) fallen weg. Texte,
die Leser:innen ansprechen (`organe`, `buerger.*.mitwirken.was`, `einfluss_regeln.was`, `fahrplan`), stehen in Du-Form.

### `web/feed.xml` und `data/stadt/feed.json`

Von `feed.py`. Ein Eintrag je Änderung zwischen zwei Läufen: `{id: "<nr>:<neu|schritt|termin>:<datum>", zeit, nr,
titel, text, thema, gremium}`; `id` ist stabil, derselbe Termin erzeugt keinen zweiten Eintrag. Atom-`category`
trägt Thema und Gremium, damit Feedreader filtern können.
