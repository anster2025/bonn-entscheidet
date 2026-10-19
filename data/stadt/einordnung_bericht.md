# Einordnung der Vorgänge 2026 – Bericht

Erzeugt von `einordnung.py` aus `data/stadt/vorgaenge_2026.json`; „künftig“ relativ zum Lauf am 2026-10-19.

## Verfahren × Status

| Verfahren | offen | vertagt | abgeschlossen | unklar | gesamt |
|---|---:|---:|---:|---:|---:|
| beschlussvorlage | 88 | 10 | 220 | 1 | 319 |
| mitteilung | 0 | 2 | 292 | 0 | 294 |
| grosse-anfrage | 35 | 55 | 165 | 0 | 255 |
| buergerantrag | 63 | 50 | 119 | 0 | 232 |
| antrag-bv | 20 | 62 | 138 | 5 | 225 |
| ausschuss-entscheidung | 2 | 0 | 137 | 0 | 139 |
| antrag-rat | 45 | 16 | 77 | 0 | 138 |
| nichtoeffentlich | 20 | 1 | 98 | 0 | 119 |
| dringlichkeitsantrag | 19 | 3 | 42 | 0 | 64 |
| bauleitplanung | 10 | 3 | 22 | 0 | 35 |
| kleine-anfrage | 8 | 1 | 9 | 0 | 18 |
| einwohnerfrage | 3 | 2 | 10 | 0 | 15 |
| dringlichkeitsentscheidung | 1 | 0 | 2 | 0 | 3 |

## Sicherheit der Zuordnung

- hoch: 1660
- mittel: 196

Gründe bei Sicherheit „mittel“:

- 90 × Beschlussvorlage; das entscheidende Gremium ist noch nicht bekannt.
- 75 × Beschlussvorlage, die Bezirksvertretung entscheidet selbst (Sache bleibt im Bezirk).
- 14 × Antrag ohne bekanntes Gremium; angenommen: Rat oder Ausschuss.
- 9 × Beschlussvorlage zur Bauleitplanung (Titel).
- 4 × Antrag ohne bekanntes Gremium; der Titel nennt die Bezirksebene.
- 2 × Antrag mit Beratung in Rat oder Ausschuss.
- 2 × Antrag, beraten nur in Bezirksvertretungen.

## Nächster Termin und Deckblätter

- Offene oder vertagte Vorgänge: 519, davon mit konkretem nächstem Termin: 300 (58 %)
  - Quelle: kalender 244, deckblatt 56
  - offen: 95 von 314, vertagt: 205 von 205
- Abgeschlossene Vorgänge mit späterem Termin (z. B. Kenntnisnahme der Antwort): 10
- Dokumente, deren Deckblatt gebraucht wird: 1194; Deckblatt-Text vorhanden: 127, davon mit erkannter Beratungsfolge: 122
- Alle Dokumente mit Beratungsfolge-Plan: 151
- Plan-Zeilen ohne zugeordnetes Gremium: 0
- Aktueller Knoten ist erwartet (nächster Schritt): 307

## Stichprobe (20 zufällige Vorgänge, Seed 2027)

- **253838** Bildung des Naturschutzbeirates (Beschlussvorlage, abgeschlossen)
  - Verfahren: `beschlussvorlage` (hoch): Beschlussvorlage, verbindlich entscheidet der Rat.
  - Aktueller Knoten: Entscheidung: Rat (09.07.2026)
  - Worum: Ein Vorschlag der Verwaltung, über den die Politik beschließen soll.
  - Erster Mitwirken-Hinweis: Die Entscheidung ist gefallen. Die Verwaltung setzt sie um; den Stand hält die Beschlusskontrolle fest, deren Datenbank nicht öffentlich ist. Nach dem Stand fragen kann eine Fraktion per Anfrage; neue Anstöße gibst du per Bürgerantrag. – jederzeit
- **260781** Informationsbrief - Kanalbauarbeiten Heerstraße (Informationsbrief, abgeschlossen)
  - Verfahren: `mitteilung` (hoch): Dokumenttyp „Informationsbrief“: nur zur Kenntnis.
  - Aktueller Knoten: Eingang: Informationsbrief (27.04.2026)
  - Worum: Eine Information der Verwaltung an die Politik; beschlossen wird nichts.
  - Erster Mitwirken-Hinweis: Der Vorgang ist ohne eigenen Beschluss erledigt. Eigene Fragen stellst du in der Einwohnerfragestunde einer Bezirksvertretung; eine Fraktion kann per Anfrage nachhaken. – jederzeit
- **253208** Bürgerantrag: Einrichtung von Raucherzonen an den oberirdischen Straßenbahnhaltestellen (Anregungen und Beschwerden, abgeschlossen)
  - Verfahren: `buergerantrag` (hoch): Dokumenttyp „Anregungen und Beschwerden“ (Bürgerantrag nach § 24 GO NRW).
  - Aktueller Knoten: Entscheidung: Ausschuss für Beteiligung der Bürgerinnen und Bürger (29.04.2026)
  - Worum: Ein Bürgerantrag: Einwohner:innen wenden sich mit einer Anregung oder Beschwerde an die Stadt.
  - Erster Mitwirken-Hinweis: Der Vorgang ist ohne eigenen Beschluss erledigt. Eigene Fragen stellst du in der Einwohnerfragestunde einer Bezirksvertretung; eine Fraktion kann per Anfrage nachhaken. – jederzeit
- **220577** Grüne/SPD/LINKE: Aufwertung der historischen Dransdorfer Ortsmitte - mehr Gestaltung, meh… (Antrag, unklar)
  - Verfahren: `antrag-bv` (hoch): Antrag, beraten nur in Bezirksvertretungen.
  - Aktueller Knoten: Empfehlung: Bezirksvertretung Bonn (05.04.2022)
  - Worum: Ein Antrag von der SPD, den Grünen und der Linken für den Stadtbezirk.
  - Erster Mitwirken-Hinweis: Bring dein Anliegen selbst ein: als Bürgerantrag, schriftlich und mit Namen. Zuständig ist die Bezirksvertretung Bonn; die nächste erreichbare Sitzung ist am 24.11.2026. – 21 Tage vor der Sitzung, also bis 03.11.2026
- **261248** Beauftragung zur Prüfung gemäß § 2 Abs. 5 der Rechnungsprüfungsordnung der Stadt Bonn - h… (Mitteilungsvorlage, abgeschlossen)
  - Verfahren: `mitteilung` (hoch): Dokumenttyp „Mitteilungsvorlage“: nur zur Kenntnis.
  - Aktueller Knoten: Eingang: Mitteilungsvorlage (21.06.2026)
  - Worum: Eine Information der Verwaltung an die Politik; beschlossen wird nichts.
  - Erster Mitwirken-Hinweis: Der Vorgang ist ohne eigenen Beschluss erledigt. Eigene Fragen stellst du in der Einwohnerfragestunde einer Bezirksvertretung; eine Fraktion kann per Anfrage nachhaken. – jederzeit
- **260423** Kommunale Konferenz Alter und Pflege der Bundesstadt Bonn -Tätigkeitsbericht für das Jahr… (Mitteilungsvorlage, abgeschlossen)
  - Verfahren: `mitteilung` (hoch): Dokumenttyp „Mitteilungsvorlage“: nur zur Kenntnis.
  - Aktueller Knoten: Kenntnisnahme: Ausschuss für Soziales, Migration, Gesundheit, Wohnen und Senioren (14.04.2026)
  - Worum: Eine Information der Verwaltung an die Politik; beschlossen wird nichts.
  - Erster Mitwirken-Hinweis: Der Vorgang ist ohne eigenen Beschluss erledigt. Eigene Fragen stellst du in der Einwohnerfragestunde einer Bezirksvertretung; eine Fraktion kann per Anfrage nachhaken. – jederzeit
- **261573** Grundstück in Bonn-Endenich, Am Burggraben 54 - Sanierung des Vorderhauses und Errichtung… (Beschlussvorlage, offen)
  - Verfahren: `beschlussvorlage` (mittel): Beschlussvorlage; das entscheidende Gremium ist noch nicht bekannt.
  - Aktueller Knoten: Anhörung: Gremium und Termin noch offen – erwartet
  - Worum: Ein Vorschlag der Verwaltung, über den die Politik beschließen soll.
  - Erster Mitwirken-Hinweis: Sprich vor der Entscheidung Fraktionen oder Gruppen an. Diese können per Änderungsantrag Änderungen beantragen, bis zum Schluss der Aussprache. – bis zum Schluss der Aussprache
- **260631** Einleitung des Vergabeverfahrens Kanal-TV-Inspektionen Castell, Nordstadt, Tannenbusch (Beschlussvorlage: Einleitung, abgeschlossen)
  - Verfahren: `ausschuss-entscheidung` (hoch): Beschlussvorlage, verbindlich entscheidet ein Ausschuss.
  - Aktueller Knoten: Entscheidung: Ausschuss für Finanzen, Beteiligungen und Vergabe (21.05.2026)
  - Worum: Ein Vorschlag der Verwaltung, über den ein Ausschuss abschließend entscheidet.
  - Erster Mitwirken-Hinweis: Die Entscheidung ist gefallen. Die Verwaltung setzt sie um; den Stand hält die Beschlusskontrolle fest, deren Datenbank nicht öffentlich ist. Nach dem Stand fragen kann eine Fraktion per Anfrage; neue Anstöße gibst du per Bürgerantrag. – jederzeit
- **261183** Arbeitsprogramm landschaftsarchitektonischer Einzelprojekte im Amt für Umwelt und Stadtgr… (Mitteilungsvorlage, abgeschlossen)
  - Verfahren: `mitteilung` (hoch): Dokumenttyp „Mitteilungsvorlage“: nur zur Kenntnis.
  - Aktueller Knoten: Kenntnisnahme: Bezirksvertretung Beuel (14.10.2026)
  - Worum: Eine Information der Verwaltung an die Politik; beschlossen wird nichts.
  - Erster Mitwirken-Hinweis: Der Vorgang ist ohne eigenen Beschluss erledigt. Eigene Fragen stellst du in der Einwohnerfragestunde einer Bezirksvertretung; eine Fraktion kann per Anfrage nachhaken. – jederzeit
- **261917** FDP-Große Anfrage: Sanierung des Bad Godesberger Tunnels (Große Anfrage, offen)
  - Verfahren: `grosse-anfrage` (hoch): Dokumenttyp „Große Anfrage“.
  - Aktueller Knoten: Kenntnisnahme: Bezirksvertretung Bad Godesberg (02.12.2026) – erwartet
  - Worum: Eine Große Anfrage von der FDP: Die Verwaltung soll in der Sitzung antworten. KI: Gefragt wird, warum der Bad Godesberger Tunnel nur sechs Jahre nach der letzten Sanierung erneut saniert wird und wie lange er danach ohne größere Arbeiten nutzbar sein soll.
  - Erster Mitwirken-Hinweis: Besuch die Sitzung: Bezirksvertretung Bad Godesberg am 02.12.2026. Sie ist öffentlich, außer bei Grundstücks-, Personal-, Darlehens-, Vertrags- und Vergabesachen. – am Sitzungstag (02.12.2026)
- **261605** Grüne-Fraktion-Dringlichkeitsantrag: Gesperrte Basketballkörbe auf Bonner Schulhöfen (Dringlichkeitsantrag, abgeschlossen)
  - Verfahren: `dringlichkeitsantrag` (hoch): Dokumenttyp „Dringlichkeitsantrag“.
  - Aktueller Knoten: Entscheidung: Sportausschuss (02.09.2026)
  - Worum: Ein Dringlichkeitsantrag von den Grünen: Die Sache soll kurzfristig auf die Tagesordnung, weil sie eilt.
  - Erster Mitwirken-Hinweis: Der Vorgang ist ohne eigenen Beschluss erledigt. Eigene Fragen stellst du in der Einwohnerfragestunde einer Bezirksvertretung; eine Fraktion kann per Anfrage nachhaken. – jederzeit
- **260075** Bildung und Besetzung eines Projektbeirates „Sanierung Stadthalle Bad Godesberg“ (Beschlussvorlage, abgeschlossen)
  - Verfahren: `beschlussvorlage` (hoch): Beschlussvorlage, verbindlich entscheidet der Rat.
  - Aktueller Knoten: Entscheidung: Rat (05.02.2026)
  - Worum: Ein Vorschlag der Verwaltung, über den die Politik beschließen soll.
  - Erster Mitwirken-Hinweis: Die Entscheidung ist gefallen. Die Verwaltung setzt sie um; den Stand hält die Beschlusskontrolle fest, deren Datenbank nicht öffentlich ist. Nach dem Stand fragen kann eine Fraktion per Anfrage; neue Anstöße gibst du per Bürgerantrag. – jederzeit
- **260613** GRÜNE-Antrag - Maßnahmen zur Sicherung von Gesundheit und Verkehrssicherheit auf den Ausw… (Antrag, vertagt)
  - Verfahren: `antrag-rat` (hoch): Antrag mit Beratung in Rat oder Ausschuss.
  - Aktueller Knoten: Empfehlung: Ausschuss für Umwelt, Klima und Lokale Agenda (15.07.2026)
  - Worum: Ein Antrag aus der Politik von den Grünen.
  - Erster Mitwirken-Hinweis: Besuch die Sitzung: Ausschuss für Umwelt, Klima und Lokale Agenda am 25.11.2026. Sie ist öffentlich, außer bei Grundstücks-, Personal-, Darlehens-, Vertrags- und Vergabesachen. – am Sitzungstag (25.11.2026)
- **260067** Volt-Antrag: Bestandsaufnahme laufender Aktivitäten zur Digitalisierung und Verwaltungsmo… (Antrag, abgeschlossen)
  - Verfahren: `antrag-rat` (hoch): Antrag mit Beratung in Rat oder Ausschuss.
  - Aktueller Knoten: Entscheidung: Rat (05.02.2026)
  - Worum: Ein Antrag aus der Politik von Volt. Der Rat soll darüber beschließen.
  - Erster Mitwirken-Hinweis: Die Entscheidung ist gefallen. Die Verwaltung setzt sie um; den Stand hält die Beschlusskontrolle fest, deren Datenbank nicht öffentlich ist. Nach dem Stand fragen kann eine Fraktion per Anfrage; neue Anstöße gibst du per Bürgerantrag. – jederzeit
- **260491** Tagesordnungspunkte in nichtöffentlicher Sitzung des Schulausschusses (Tagesordnungspunkte in nichtöffentlicher Sitzung, abgeschlossen)
  - Verfahren: `nichtoeffentlich` (hoch): Platzhalter für nichtöffentliche Tagesordnungspunkte.
  - Aktueller Knoten: Kenntnisnahme: Schulausschuss (16.04.2026)
  - Worum: Ein Sammelpunkt für den nichtöffentlichen Teil einer Sitzung; die Inhalte sind nicht öffentlich.
  - Erster Mitwirken-Hinweis: Diese Punkte werden nichtöffentlich beraten, etwa Grundstücks-, Personal-, Darlehens-, Vertrags- und Vergabesachen. Die Inhalte sind nicht einsehbar. – keine
- **261109** GRÜNEN-Große Anfrage: Bauliche Verbesserungen für den Fuß- und Radverkehr am Rheinufer in… (Große Anfrage, vertagt)
  - Verfahren: `grosse-anfrage` (hoch): Dokumenttyp „Große Anfrage“.
  - Aktueller Knoten: Kenntnisnahme: Bezirksvertretung Bad Godesberg (02.09.2026)
  - Worum: Eine Große Anfrage von den Grünen: Die Verwaltung soll in der Sitzung antworten.
  - Erster Mitwirken-Hinweis: Besuch die Sitzung: Bezirksvertretung Bad Godesberg am 04.11.2026. Sie ist öffentlich, außer bei Grundstücks-, Personal-, Darlehens-, Vertrags- und Vergabesachen. – am Sitzungstag (04.11.2026)
- **260065** Seniorenzentren der Bundesstadt Bonn Wirtschaftsplan 2026 (Beschlussvorlage, abgeschlossen)
  - Verfahren: `beschlussvorlage` (hoch): Beschlussvorlage, verbindlich entscheidet der Rat.
  - Aktueller Knoten: Entscheidung: Rat (05.02.2026)
  - Worum: Ein Vorschlag der Verwaltung, über den die Politik beschließen soll.
  - Erster Mitwirken-Hinweis: Die Entscheidung ist gefallen. Die Verwaltung setzt sie um; den Stand hält die Beschlusskontrolle fest, deren Datenbank nicht öffentlich ist. Nach dem Stand fragen kann eine Fraktion per Anfrage; neue Anstöße gibst du per Bürgerantrag. – jederzeit
- **260310** Grundstück in Bonn-Mehlem, Etzelstraße, Hildebrandstraße Gemarkung Mehlem, Flur 7, Flurst… (Beschlussvorlage, offen)
  - Verfahren: `beschlussvorlage` (mittel): Beschlussvorlage; das entscheidende Gremium ist noch nicht bekannt.
  - Aktueller Knoten: Rat entscheidet – erwartet
  - Worum: Ein Vorschlag der Verwaltung, über den die Politik beschließen soll.
  - Erster Mitwirken-Hinweis: Sprich vor der Entscheidung Fraktionen oder Gruppen an. Diese können per Änderungsantrag Änderungen beantragen, bis zum Schluss der Aussprache. – bis zum Schluss der Aussprache
- **260336** FDP-Dringlichkeitsantrag: Erhalt der Kastanie im Spatzenbrunnenpark bis zum Ende der Brut… (Dringlichkeitsantrag, abgeschlossen)
  - Verfahren: `dringlichkeitsantrag` (hoch): Dokumenttyp „Dringlichkeitsantrag“.
  - Aktueller Knoten: Entscheidung: Bezirksvertretung Bad Godesberg (11.03.2026)
  - Worum: Ein Dringlichkeitsantrag von der FDP: Die Sache soll kurzfristig auf die Tagesordnung, weil sie eilt.
  - Erster Mitwirken-Hinweis: Die Entscheidung ist gefallen. Die Verwaltung setzt sie um; den Stand hält die Beschlusskontrolle fest, deren Datenbank nicht öffentlich ist. Nach dem Stand fragen kann eine Fraktion per Anfrage; neue Anstöße gibst du per Bürgerantrag. – jederzeit
- **261320** Informationsbrief - Kanal- und Bachkanalsanierung Clemens-August-Straße Abschnitt Clemens… (Informationsbrief, abgeschlossen)
  - Verfahren: `mitteilung` (hoch): Dokumenttyp „Informationsbrief“: nur zur Kenntnis.
  - Aktueller Knoten: Eingang: Informationsbrief (02.07.2026)
  - Worum: Eine Information der Verwaltung an die Politik; beschlossen wird nichts.
  - Erster Mitwirken-Hinweis: Der Vorgang ist ohne eigenen Beschluss erledigt. Eigene Fragen stellst du in der Einwohnerfragestunde einer Bezirksvertretung; eine Fraktion kann per Anfrage nachhaken. – jederzeit

## Prüfung der Stichprobe gegen die Rohdaten

Alle 20 Vorgänge der Stichprobe am 17.10.2026 gegen `data/stadt/vorgaenge_2026.json` (Beratungen, Dokumente)
und die Deckblätter geprüft:

- **stimmt (15):** 253838, 260781, 253208, 261248, 260423, 260631, 261183, 261917 (Deckblatt: BV Bad Godesberg
  02.12.2026, Sitzung im Kalender verlinkt), 261605, 260491, 260065, 260336, 261320, 261573, 260310.
  Bei 261573 und 260310 ist „Rat entscheidet“ nur aus der Verfahrensvorlage abgeleitet (in den Daten steht
  nur eine Anhörung); der Knoten ist als voraussichtlich markiert, die Zuordnung hat Sicherheit „mittel“.
- **Grenzfall, behoben:** 260075 – das Veröffentlichungsdatum der Vorlage (06.02.) liegt nach der
  Ratsentscheidung (05.02.); der Eingangsknoten steht jetzt immer vorn.
- **Grenzfall, behoben:** 260067 – Rat hat den Antrag am 05.02. beschlossen, danach wurde eine
  Mitteilungsvorlage zur Kenntnis genommen. Der Status aus Schritt A nennt die Kenntnisnahme; der Abschluss
  zählt jetzt als „beschlossen“, damit der Mitwirken-Hinweis zur Umsetzung passt. Aktueller Knoten bleibt
  die Kenntnisnahme.
- **Grenzfall, behoben (18.10.):** 220577 – Antrag von 2022 (nur BV-Empfehlung), 2026 nur eine Große Anfrage
  mit Stellungnahme zur Kenntnis genommen. Eine spätere Anfrage oder Mitteilung ersetzt jetzt nicht mehr die
  Hauptvorlage (`vorgang.current_main`); Status `unklar`, weil eine Entscheidung in den Daten fehlt.
- **Grenzfall, behoben (18.10.):** 261109 – Große Anfrage mit Stellungnahme, die Sitzung am 02.09. wurde
  abgebrochen. Die Regel „Anfrage beantwortet“ greift erst nach der Vertagungsregel; Status `vertagt`, nächster
  Termin aus dem Kalender.
- **Annahme:** 260613 – zweimal vertagt (28.05. Mobilität, 15.07. AUKLA); der nächste Termin 25.11.2026
  ist die nächste AUKLA-Sitzung laut Kalender, nicht bestätigt (`quelle: kalender`).

Zweite Stichprobe am 18.10.2026 (15 Vorgänge, je eine Zelle Status × Verfahren, Seed 1815) gegen
`cache/get_paper_meetings` und `meetings_2026.jsonl`:

- **stimmt (13):** 261598, 261263 (Folgetermin aus dem Kalender angenommen), 260336, 252942 (`unklar`), 261804,
  260346, 260089, 261187 (Ratsberatung 11.06. ohne Ergebnis in den Rohdaten), 253195, 210685 (Große Anfrage zu
  einer Vorlage von 2021 noch offen, Termin vom Deckblatt), 260496, 260313, 261530.
- **behoben:** 240810 – die Erklärung schrieb die Tagesordnung vom 23.06.2026 (Mitteilung -02) dem Antrag zu;
  sie nennt jetzt das Dokument. 240891 – nach der Vertagung in der BV stand der Antrag am 15.09. im
  Mobilitätsausschuss (ohne Ergebnis); `vertagt` gilt jetzt nur, wenn danach keine Beratung mehr war → `offen`.

Allgemeine Grenzen:

- **Deckblätter:** Der Server hat bisher nur für 156 der 1.128 abgefragten Hauptdokumente Text
  (Extraktion läuft, etwa 1.000 PDFs pro Tag). Die übrigen stehen in
  `cache/get_file_text_ohne_text.json` und werden mit `python3 einordnung.py --abruf` erneut versucht.
- **Kalender-Termine** (`quelle: kalender`) sind Annahmen: nächste Sitzung desselben Gremiums nach einer
  Vertagung, nach einem verpassten Deckblatt-Termin oder wenn genau ein Gremium die Rolle schon hatte.
  Seite und Erklärung sagen „voraussichtlich“.
- **Tagesordnungen:** Bis 02.11.2026 steht keine Sitzung in `meetings_2026.jsonl`; künftige Sitzungen
  haben noch keine Tagesordnung (`quelle: tagesordnung` kommt erst nach `--aktualisieren` vor).
- **Rechtsgrundlagen je Rolle** sind allgemein: Empfehlung einer BV → BezS § 8, Anhörung → BezS § 9,
  Ausschuss → ZustO ohne Ziffer. Kenntnisnahmen haben meist keine eigene Rechtsgrundlage.
- **Einreicher** stammen aus dem Titel (Parteikürzel), daher „eingereicht von: Grüne“.
