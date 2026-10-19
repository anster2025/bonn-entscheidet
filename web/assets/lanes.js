// Swimlanes für „Bonn entscheidet“: Bahnen je Akteur, Kästen mit Pfeilen, ordinale Zeitachse (eine Spalte je Datum).
// Zwei Quellen, ein Renderer:
//   zeigeVorgang(el, vorgang, daten)    echte Daten aus daten/vorgang/<nr>.json (knoten, dokumente)
//   zeigeVerfahren(el, verfahren, daten) allgemeiner Ablauf aus daten/verfahren.json (schritte, kanten, ausgaenge)
// daten = daten/verfahren.json (bahnen, verfahren, abkuerzungen).
// Ganzer Ablauf: tatsächliche Knoten (ohne `quelle`) und, solange der Vorgang nicht abgeschlossen ist, alle
// möglichen nächsten Schritte (erwartete Knoten: belegte Termine, Sitzungskalender, üblicher Ablauf) gestrichelt.
// Erwartete Schritte ohne Datum bekommen eigene Spalten „Termin offen“ hinter heute bzw. dem vorigen Schritt.
// Der letzte tatsächliche Schritt ist der aktuelle Stand (volle Farbe), frühere Schritte erscheinen blasser. Wenige Schritte in einem Gremium
// (brauchtDiagramm() = false): kein Diagramm, nur eine Zeile Termine; opts.immer erzwingt das Diagramm
// (Bereich „Vorgänge“: dort ist es das einzige Diagramm).
// Breit: Bahnen mit Kästen (HTML-Buttons) und Linien (SVG); die Spalten passen sich der Breite an (Text bricht um,
// Schrift bleibt ≥ 15 px). Passt das Diagramm nicht in die Breite, bleibt es waagerecht und scrollt seitlich
// (Bahnnamen bleiben links stehen; beim Zeichnen steht der aktuelle Schritt im Blick). Nur unter ENG px Breite (Handy)
// setzt zeichne() .ln-eng und die Seite zeigt dieselben Kästen als senkrechte Liste, Bahnname vor jedem Kasten.
// Farbe je Bahn (Klasse b-<bahn>, Tokens --bahn-<id> in ratsblatt.css); Zustände über Farbe und Form: erledigt =
// blasse Fläche + 1 px Rand, aktuell = volle Fläche + 3 px Rand in der dunklen Bahnfarbe, möglich = gestrichelt ohne Fläche.
// Einzelheiten öffnen als Popover am Kasten (popover.js).

import { oeffne, schliesse, offenFuer } from "./popover.js";

export const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

// ------------------------------------------------------------------ Datum
const pad = n => String(n).padStart(2, "0");
export function heuteISO() {
  const d = new Date();
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}
const tage = (a, b) => Math.round((Date.UTC(+b.slice(0, 4), +b.slice(5, 7) - 1, +b.slice(8, 10)) - Date.UTC(+a.slice(0, 4), +a.slice(5, 7) - 1, +a.slice(8, 10))) / 864e5);
export const ddmm = s => `${s.slice(8, 10)}.${s.slice(5, 7)}.`;
export const dmy = s => `${s.slice(8, 10)}.${s.slice(5, 7)}.${s.slice(0, 4)}`;

// ------------------------------------------------------------------ Bahnen und Benennung
const BAHN = {
  ew: "Einwohner:\u200Binnen", rm: "Fraktionen", bvm: "Bezirks­verordnete", vw: "Verwaltung · OB",
  bv: "Bezirks­vertretung", aus: "Ausschüsse", rat: "Rat",
};
const bahnName = (id, daten) => BAHN[id] || (daten.bahnen.find(b => b.id === id) || {}).name || id;
const bahnLang = (id, daten) => (daten.bahnen.find(b => b.id === id) || {}).name || BAHN[id] || id;
const GREMIUM_BAHNEN = ["bv", "aus", "rat"];

export function kurzGremium(g) {
  if (!g) return "";
  if (g.startsWith("Bezirksvertretung ")) return "BV " + g.slice(18);
  if (/^Ausschuss für Beteiligung/.test(g)) return "Bürgerausschuss";
  const m = g.match(/^Ausschuss für ([^,\s]+)/);
  return m ? "Ausschuss " + m[1] : g;
}
const TYP = { "Anregungen und Beschwerden": "Bürgerantrag" };
export const typName = t => TYP[t] || t || "Vorlage";

const bahnVonPapier = (typ, einreicher, name) => {
  const e = new Set(einreicher || []);
  if (e.has("Bürger:innen") || typ === "Anregungen und Beschwerden" || typ === "Einwohnerfrage") return "ew";
  if (/^(Stellungnahme|Beschlussvorlage|Mitteilungsvorlage|Dringlichkeitsentscheidung)/.test(typ || "") || e.has("Verwaltung")) return "vw";
  return /bezirksfraktion/i.test(name || "") ? "bvm" : "rm";
};
// Folgevorlagen schreibt die Verwaltung, auch zu Bürgeranträgen; nur Anträge bleiben bei ihren Einreichern
const bahnVonFolge = (typ, name) => { const b = bahnVonPapier(typ, [], name); return b === "ew" ? "vw" : b; };
const bahnVonGremium = g => g && g.startsWith("Bezirksvertretung") ? "bv" : g === "Rat" ? "rat" : "aus";

const ERGEBNIS = { beschlossen: "beschlossen", abgelehnt: "abgelehnt", vertagt: "vertagt", "zur Kenntnis": "zur Kenntnis", erledigt: "erledigt" };
const ergebnisWort = k => ERGEBNIS[k.ergebnis_gruppe] || null;
const ROLLE_WORT = { "Entscheidung": "entscheidet", "Empfehlung": "empfiehlt", "Anhörung": "Anhörung", "Kenntnisnahme": "Kenntnisnahme", "Anregung": "Anregung" };

// Weiche Trennstellen in langen Komposita, damit schmale Kästen sauber umbrechen statt abzuschneiden.
const trenne = s => String(s ?? "").replace(/(\p{L}{3,}?)(ausschuss|antrag|anträge|vorlage|nahme|fraktion|vertretung|verordnete|entscheid|beschluss|machung)/giu, "$1­$2");

// Abkürzungen im Popover als <abbr>; Eingabe ist bereits escaped.
function abbr(html, daten) {
  const ab = daten.abkuerzungen || {};
  const keys = Object.keys(ab).sort((a, b) => b.length - a.length).map(k => k.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  if (!keys.length) return html;
  const re = new RegExp(`(^|[\\s(„-])(${keys.join("|")})(?=$|[\\s),.;:“])`, "g");
  return html.replace(re, (_, vor, k) => `${vor}<abbr title="${esc(ab[k])}">${k}</abbr>`);
}

// ------------------------------------------------------------------ Geometrie
// boxW = Wunschbreite, minW = kleinste Breite, darunter scrollt das Diagramm seitlich mit boxW (schmal: Liste, .ln-eng); luft = Abstand zwischen Spalten,
// bruch = Zusatzabstand vor einem Zeitsprung (> 70 Tage), heuteRand = Platz für „heute“ hinter der letzten Spalte.
const GEO = {
  vorgang: { label: 132, pad: 10, achse: 52, boxW: 160, minW: 100, luft: 24, bruch: 26, heuteRand: 34, boxH: 44, klein: 32, gap: 6 },
  verfahren: { label: 132, pad: 8, achse: 34, boxW: 176, minW: 100, luft: 24, bruch: 0, heuteRand: 0, boxH: 44, klein: 30, gap: 6 },
};
const SCHRIFT = { gross: 15, klein: 15, zeile: 1.3 };
const ENG = 600;  // Breite des Diagrammbereichs, unter der die senkrechte Liste übernimmt (≈ 640 px Fenster)  // wie .ln-k in ratsblatt.css

// ------------------------------------------------------------------ Status-treue Auswahl
const BELEGT = new Set(["sitzung", "tagesordnung", "deckblatt"]);  // nächster Termin mit Beleg im Ratsinfo
const tatsaechlich = k => !k.quelle && !k.erwartet;

export function naechsterTermin(v, heute = heuteISO()) {
  return v.knoten.filter(k => k.erwartet && k.datum && k.datum >= heute && BELEGT.has(k.quelle))
    .sort((a, b) => a.datum.localeCompare(b.datum))[0] || null;
}

// false: höchstens 2 tatsächliche Schritte und nur ein Gremium; dann kein Diagramm, nur eine Zeile Termine.
export function brauchtDiagramm(v, heute = heuteISO()) {
  const echt = v.knoten.filter(tatsaechlich);
  const gremien = new Set([...echt, naechsterTermin(v, heute)].filter(k => k && k.art === "beratung").map(k => k.gremium || "?"));
  return !(echt.length <= 2 && gremien.size <= 1);
}

// ------------------------------------------------------------------ Modell: Vorgang
function vorgangModell(v, daten, heute) {
  const verf = daten.verfahren.find(x => x.id === (v.verfahren || {}).id);
  const eingangBahn = bahnVonPapier(v.typ, v.einreicher, v.titel);
  const extraBahn = { "eingang-verwaltung": "vw", stellungnahme: "vw", aenderungsantrag: "rm", folgevorlage: eingangBahn === "ew" ? "vw" : eingangBahn };
  const offen = v.status !== "abgeschlossen";
  const gezeigt = v.knoten.filter(k => tatsaechlich(k) || (offen && k.erwartet && (!k.datum || k.datum >= heute)));
  const echt = gezeigt.filter(tatsaechlich);
  const jetzt = echt.filter(k => k.art !== "dokument").pop() || echt[echt.length - 1] || null;
  let letzteGremiumBahn = "aus";
  const items = [], kanten = [];

  gezeigt.forEach((k, i) => {
    const it = { id: k.id, datum: k.datum || null, ord: i, quelle: k, typ: "knoten", zustand: k.erwartet ? "erwartet" : k === jetzt ? "aktuell" : "erledigt" };
    if (k.art === "eingang") {
      it.bahn = eingangBahn;
      const wer = (k.einreicher || v.einreicher || []).filter(e => e !== "Verwaltung" && e !== "Bürger:innen");
      it.z1 = typName(v.typ) + (wer.length ? " " + wer[0] + (wer.length > 1 ? " u. a." : "") : "");
      it.z2 = eingangBahn === "vw" ? "vorgelegt" : "eingereicht";
      it.stark = true;
    } else if (k.art === "beratung") {
      it.bahn = letzteGremiumBahn = bahnVonGremium(k.gremium);
      it.z1 = kurzGremium(k.gremium) || "Gremium";
      const w = ergebnisWort(k);
      if (w) { it.z2 = w; it.stark = true; }
      else if (it.zustand === "erwartet") it.z2 = ROLLE_WORT[k.rolle] || "Beratung";
      else { it.z2 = ["Anhörung", "Kenntnisnahme"].includes(k.rolle) ? ROLLE_WORT[k.rolle] : "ohne Ergebnis"; it.leise = true; }
    } else if (k.art === "dokument") {
      it.bahn = k.dokument_art === "stellungnahme" ? "vw" : k.dokument_art === "aenderungsantrag" ? bahnVonPapier("Änderungsantrag", [], k.name) : bahnVonFolge(k.typ, k.name);
      it.z1 = k.dokument_art === "stellungnahme" ? "Stellungnahme" : k.dokument_art === "aenderungsantrag" ? aaName(k.name) : "Weitere Vorlage";
      it.klein = true;
    } else {
      const sid = (k.schritt || {}).id;
      const s = verf && verf.schritte.find(x => x.id === sid);
      it.bahn = s ? s.bahn : extraBahn[sid] || letzteGremiumBahn;
      it.z1 = (s && s.label) || String(k.titel || "").split(/,\s/)[0].replace(/\s*\([^)]*\)/g, "");
    }
    it.z1 = trenne(it.z1);
    if (it.z2) it.z2 = trenne(it.z2);
    it.detail = () => detailKnoten(k, v, daten, it);
    it.aria = ariaKnoten(k, it);
    items.push(it);
    if (i) kanten.push([gezeigt[i - 1].id, k.id]);
  });

  // Begleitdokumente, die nicht schon Knoten sind: Stellungnahmen, Änderungsanträge
  const refs = new Set(v.knoten.map(k => k.reference).filter(Boolean));
  const beratungen = gezeigt.filter(k => k.art === "beratung" && k.datum);
  (v.dokumente || []).forEach((d, i) => {
    if (!d.datum || refs.has(d.reference) || !["stellungnahme", "aenderungsantrag"].includes(d.art)) return;
    const id = `d${i}`;
    const it = {
      id, datum: d.datum, ord: 1000 + i, quelle: d, typ: "dokument", zustand: "erledigt", klein: true,
      bahn: d.art === "stellungnahme" ? "vw" : bahnVonPapier("Änderungsantrag", [], d.name),
      z1: trenne(d.art === "stellungnahme" ? "Stellungnahme" : aaName(d.name)),
    };
    it.detail = () => detailDokument(d, v, daten);
    it.aria = `${dmy(d.datum)}, ${it.z1.replace(/­/g, "")}, Dokument ${d.reference}`;
    items.push(it);
    const ziel = beratungen.find(k => k.datum >= d.datum && (k.punkte || []).some(p => p.reference === d.reference))
      || beratungen.find(k => k.datum >= d.datum);
    if (ziel) kanten.push([id, ziel.id]);
  });

  // Ordinale Spalten: eine je Datum; Zeitsprünge über 70 Tage bekommen eine Bruchmarke. Ein Schritt ohne Datum
  // bekommt den Schlüssel „<Datum davor oder heute>~<n>“ und steht damit in eigener Spalte hinter seinem Vorgänger.
  let basis = "", n = 0;
  for (const it of items.filter(x => x.typ === "knoten")) {
    if (it.datum) { basis = it.datum; it.schluessel = it.datum; }
    else it.schluessel = `${basis > heute ? basis : heute}~${String(++n).padStart(3, "0")}`;
  }
  for (const it of items) it.schluessel ||= it.datum;
  const datenListe = [...new Set(items.map(x => x.schluessel))].sort();
  let vorher = null;
  const spalten = datenListe.map(d => {
    if (d.includes("~")) return { datum: d, label: "Termin offen", offen: true };
    const s = { datum: d, label: ddmm(d) };
    if (vorher && tage(vorher, d) > 70) s.bruch = tage(vorher, d);
    if (!vorher || d.slice(0, 4) !== vorher.slice(0, 4)) s.jahr = d.slice(0, 4);
    vorher = d;
    return s;
  });
  for (const it of items) it.spalte = datenListe.indexOf(it.schluessel);
  const heuteNach = datenListe.length > 0 && heute > datenListe[datenListe.length - 1].slice(0, 10);

  const bahnen = daten.bahnen.map(b => b.id).filter(b => items.some(it => it.bahn === b));
  return { art: "vorgang", g: GEO.vorgang, items, kanten, spalten, bahnen, heute, heuteNach, ecke: "Datum", aktuell: items.find(i => i.zustand === "aktuell") };
}

function ariaKnoten(k, it) {
  const wann = k.datum ? dmy(k.datum) : "Termin offen";
  const z1 = String(it.z1).replace(/­/g, "");
  const jetzt = it.zustand === "aktuell" ? " (aktueller Stand)" : "";
  if (k.art === "beratung") {
    const was = ergebnisWort(k) || (it.zustand === "erwartet" ? "voraussichtlich" : "ohne Ergebnis");
    return `${wann}, ${k.gremium || "Gremium unbekannt"}${k.rolle ? ", " + k.rolle : ""}: ${was}${jetzt}`;
  }
  if (k.art === "eingang") return `${wann}, ${z1} ${it.z2}${jetzt}`;
  return `${wann}, ${k.titel || z1}${jetzt}`;
}

const aaName = name => {
  const m = String(name || "").match(/^(.+?)-Änderungsantrag/);
  return "Änderungsantrag" + (m ? " " + m[1] : "");
};

// ------------------------------------------------------------------ Modell: Verfahren
const ACHSE = { tage: b => "Tage bis zur " + b, wochen: () => "Wochen ab Eingang", phasen: () => "Phase" };

function verfahrenModell(vf, daten) {
  const cols = [...new Set(vf.schritte.map(s => s.col))].sort((a, b) => a - b);
  const tick = c => (vf.layout.ticks.find(t => t.col === c) || {}).label || "";
  const spalten = cols.map(c => ({ label: trenne(tick(c)) }));
  const items = vf.schritte.map((s, i) => ({
    id: s.id, bahn: s.bahn, spalte: cols.indexOf(s.col), ord: i, quelle: s, typ: "schritt", zustand: "neutral",
    z1: trenne(s.label || s.was), detail: () => detailSchritt(s, vf, daten, tick(s.col)),
    aria: `${tick(s.col)}, ${bahnLang(s.bahn, daten)}: ${s.was}`,
  }));
  const kanten = (vf.kanten || []).map(([a, b]) => [a, b]);
  // Ausgänge als Seitenäste am entscheidenden Schritt
  const gremium = items.filter(it => GREMIUM_BAHNEN.includes(it.bahn));
  let anker = null;
  if (vf.achse === "tage") anker = gremium.filter(it => it.quelle.t === 0).sort((a, b) => GREMIUM_BAHNEN.indexOf(a.bahn) - GREMIUM_BAHNEN.indexOf(b.bahn))[0];
  if (!anker) anker = gremium.filter(it => /entscheid|beschließt/i.test(it.quelle.was)).sort((a, b) => a.spalte - b.spalte)[0];
  if (!anker) anker = (gremium.length ? gremium : items).slice().sort((a, b) => b.spalte - a.spalte || a.ord - b.ord)[0];
  (vf.ausgaenge || []).forEach((a, i) => {
    const id = `x${i}`;
    items.push({
      id, bahn: anker.bahn, spalte: anker.spalte, ord: 500 + i, quelle: a, typ: "ausgang", zustand: "ausgang", klein: true, einzug: 30,
      z1: trenne(a.wenn), detail: () => detailAusgang(a, vf, daten, anker), aria: `Ausgang, wenn ${a.wenn}: ${a.dann}`,
    });
    kanten.push([anker.id, id, "ast"]);
  });
  const bahnen = daten.bahnen.map(b => b.id).filter(b => items.some(it => it.bahn === b));
  return { art: "verfahren", g: GEO.verfahren, items, kanten, spalten, bahnen, heute: null, heuteNach: false, ecke: (ACHSE[vf.achse] || ACHSE.phasen)(vf.bezug), aktuell: null };
}

// ------------------------------------------------------------------ Textmaß: Zeilen je Kasten statt „…“
let mctx = null;
function messer(familie, px, gewicht) {
  mctx ||= document.createElement("canvas").getContext("2d");
  mctx.font = `${gewicht} ${px}px ${familie}`;
  return t => mctx.measureText(t).width * 1.04;
}
// Zeilen für text bei breite px: Umbruch an Leerzeichen, an weichen Trennstellen (mit Strich), notfalls im Wort.
function zeilenZahl(text, breite, mess) {
  const leer = mess(" "), strich = mess("-");
  let n = 1, x = 0;
  for (const wort of String(text).split(/\s+/).filter(Boolean)) {
    let teile = wort.split("­"), start = x ? x + leer : 0;
    while (teile.length) {
      const ganz = mess(teile.join(""));
      if (start + ganz <= breite) { start += ganz; break; }
      let k = teile.length - 1;
      while (k > 0 && start + mess(teile.slice(0, k).join("")) + strich > breite) k--;
      if (k > 0) { teile = teile.slice(k); n++; start = 0; continue; }
      if (start > 0) { n++; start = 0; continue; }
      const w = mess(teile[0]), voll = Math.ceil(w / breite) - 1;
      n += voll; start = w - voll * breite; teile = teile.slice(1);
    }
    x = start;
  }
  return n;
}

// ------------------------------------------------------------------ Layout (gemeinsam)
function layout(M, breite, familie) {
  const g = M.g, n = M.spalten.length;
  // Spaltenbreite: so breit wie möglich bis boxW, so schmal wie nötig bis minW
  const extra = M.spalten.reduce((s, sp) => s + (sp.bruch ? g.bruch : 0), 0) + (M.heuteNach ? g.heuteRand : 0);
  const frei = breite - g.label - 2 * g.pad - extra - (n - 1) * g.luft;
  // passt es selbst mit minW nicht, wird ohnehin seitlich gescrollt: dann die volle Wunschbreite (weniger Umbruch)
  const passend = Math.floor(frei / n);
  const boxW = M.boxW = passend < g.minW ? g.boxW : Math.min(g.boxW, passend);
  let x = g.label + g.pad;
  M.spalten.forEach((s, i) => { if (i) x += boxW + g.luft + (s.bruch ? g.bruch : 0); s.x = x; });

  // Höhe je Kasten aus dem Textmaß
  const mg = messer(familie, SCHRIFT.gross, 400), mgs = messer(familie, SCHRIFT.gross, 650);
  const mk = messer(familie, SCHRIFT.klein, 400), mks = messer(familie, SCHRIFT.klein, 650);
  for (const it of M.items) {
    it.w = boxW - (it.einzug || 0);
    const innen = it.w - 20, px = it.klein ? SCHRIFT.klein : SCHRIFT.gross;
    const zeilen = zeilenZahl(it.z1, innen, it.klein ? mk : mg) + (it.z2 ? zeilenZahl(it.z2, innen, it.stark ? (it.klein ? mks : mgs) : (it.klein ? mk : mg)) : 0);
    it.h = Math.max(it.klein ? g.klein : g.boxH, Math.ceil(zeilen * px * SCHRIFT.zeile + (it.klein ? 8 : 12)));
  }
  const stapel = new Map();
  const sortiert = M.items.slice().sort((a, b) => a.spalte - b.spalte || a.ord - b.ord);
  for (const it of sortiert) {
    const key = it.spalte + "|" + it.bahn;
    const y = stapel.get(key) || 0;
    it.dy = y;
    stapel.set(key, y + it.h + g.gap);
  }
  M.bahnTop = {}; M.bahnH = {};
  let y = g.achse;
  for (const b of M.bahnen) {
    let inhalt = g.boxH;
    for (const [k, v] of stapel) if (k.endsWith("|" + b)) inhalt = Math.max(inhalt, v - g.gap);
    M.bahnTop[b] = y; M.bahnH[b] = inhalt + 2 * g.pad;
    y += M.bahnH[b];
  }
  for (const it of M.items) {
    it.x = M.spalten[it.spalte].x + (it.einzug || 0);
    it.y = M.bahnTop[it.bahn] + g.pad + it.dy;
  }
  M.H = y;
  M.W = M.spalten[n - 1].x + boxW + g.pad + (M.heuteNach ? g.heuteRand : 0);

  // heute: zwischen den Spalten nach Tagen interpoliert, hinter der letzten Spalte im heuteRand
  M.heuteX = null;
  if (M.heute && M.spalten[0].datum && M.heute >= M.spalten[0].datum) {
    const sp = M.spalten, j = sp.findIndex(s => s.datum > M.heute), mitte = s => s.x + boxW / 2;
    if (j === -1) {
      const a = sp[n - 1];
      M.heuteX = a.datum === M.heute ? mitte(a) : a.x + boxW + g.heuteRand / 2;
    } else if (j > 0) {
      const a = sp[j - 1], b = sp[j];
      const l = a.x + boxW + 6, r = b.x - 6;
      M.heuteX = a.datum === M.heute ? mitte(a) : l + (r - l) * tage(a.datum, M.heute) / Math.max(1, tage(a.datum, b.datum));
    }
  }
  // Zeitfolge für Tastatur und Textalternative
  const bi = b => M.bahnen.indexOf(b);
  M.folge = M.items.slice().sort((a, b) => a.spalte - b.spalte || bi(a.bahn) - bi(b.bahn) || a.dy - b.dy);
}

// ------------------------------------------------------------------ Linien
function pfad(M, a, b, art) {
  const r = 6;
  if (art === "ast") {
    const x0 = a.x + 9, y0 = a.y + a.h, y1 = b.y + b.h / 2, x1 = b.x - 2;
    return `M${x0},${y0} L${x0},${y1 - r} Q${x0},${y1} ${x0 + r},${y1} L${x1},${y1}`;
  }
  if (b.x > a.x + a.w - 1) {
    const x0 = a.x + a.w, y0 = a.y + a.h / 2, x1 = b.x - 2, y1 = b.y + b.h / 2;
    if (Math.abs(y1 - y0) < 1) return `M${x0},${y0} L${x1},${y1}`;
    const xm = Math.max(x0 + 10, x1 - 14), s = y1 > y0 ? 1 : -1, rr = Math.min(r, Math.abs(y1 - y0) / 2);
    return `M${x0},${y0} L${xm - rr},${y0} Q${xm},${y0} ${xm},${y0 + s * rr} L${xm},${y1 - s * rr} Q${xm},${y1} ${xm + rr},${y1} L${x1},${y1}`;
  }
  // gleiche Spalte: senkrecht; liegt ein Kasten dazwischen, rechts außen herum
  const oben = Math.min(a.y, b.y), unten = Math.max(a.y + a.h, b.y + b.h);
  const hindernis = M.items.some(x => x !== a && x !== b && x.spalte === a.spalte && x.y > oben && x.y + x.h < unten);
  if (hindernis) {
    const xr = Math.max(a.x + a.w, b.x + b.w), xg = xr + 9, y0 = a.y + a.h / 2, y1 = b.y + b.h / 2, s = y1 > y0 ? 1 : -1;
    return `M${a.x + a.w},${y0} L${xg - r},${y0} Q${xg},${y0} ${xg},${y0 + s * r} L${xg},${y1 - s * r} Q${xg},${y1} ${xg - r},${y1} L${b.x + b.w + 2},${y1}`;
  }
  const xa = a.x + Math.min(a.w, b.w) / 2;
  return b.y > a.y ? `M${xa},${a.y + a.h} L${xa},${b.y - 2}` : `M${xa},${a.y} L${xa},${b.y + b.h + 2}`;
}

// ------------------------------------------------------------------ HTML
let uid = 0;
const KNOPF = 'type="button" aria-haspopup="dialog" aria-expanded="false"';

function kastenHTML(it, M, tabbar) {
  const cls = ["ln-k", "b-" + it.bahn, ...it.zustand.split(" ").map(z => "ist-" + z), it.klein ? "ln-k-klein" : ""].filter(Boolean).join(" ");
  const aktuell = it.zustand === "aktuell";
  return `<button ${KNOPF} class="${cls}" data-k="${esc(it.id)}" tabindex="${tabbar ? 0 : -1}" aria-label="${esc(it.aria)}"${aktuell ? ' aria-current="step"' : ""}
    style="left:${it.x}px;top:${it.y}px;width:${it.w}px;height:${it.h}px">${zeilen(it)}</button>`;
}
const zeilen = it => `<span class="ln-z1">${esc(it.z1)}</span>${it.z2 ? `<span class="ln-z2${it.stark ? " stark" : ""}${it.leise ? " leise" : ""}">${esc(it.z2)}</span>` : ""}`;

function diagrammHTML(M, id) {
  const g = M.g, mk = `lnp${id}`, bw = M.boxW;
  const tabId = (M.aktuell || M.folge[0] || {}).id;
  const achse = M.spalten.map((s, i) => {
    // Zeitsprung-Marke entfällt, wenn „heute“ in derselben Lücke steht (die Linie zeigt den Abstand schon)
    const heuteDrin = M.heuteX != null && i && M.heuteX > M.spalten[i - 1].x + bw && M.heuteX < s.x;
    const bruch = s.bruch && !heuteDrin ? `<span class="ln-bruch" style="left:${(M.spalten[i - 1].x + bw + s.x) / 2}px" title="${s.bruch} Tage">${bruchSVG()}<span class="ln-bruch-t">${esc(dauer(s.bruch))}</span></span>` : "";
    return `${bruch}<span class="ln-tick" style="left:${s.x}px;width:${bw}px">${s.jahr ? `<span class="ln-jahr">${s.jahr}</span>` : ""}<b>${esc(s.label)}</b></span>`;
  }).join("");
  const bahnen = M.bahnen.map((b, i) => `<div class="ln-bahn b-${esc(b)}" style="height:${M.bahnH[b]}px"><div class="ln-bahn-name" style="width:${g.label}px">${farbe(b)}${esc(bahnName(b, M.daten))}</div></div>`).join("");
  const byId = Object.fromEntries(M.items.map(i => [i.id, i]));
  const linien = M.kanten.map(([a, b, art]) => {
    const p = byId[a], q = byId[b];
    if (!p || !q) return "";
    const zukunft = [p, q].some(x => x.zustand === "erwartet");
    return `<path class="ln-pfeil${zukunft ? " zukunft" : ""}${art === "ast" ? " ast" : ""}" d="${pfad(M, p, q, art)}" marker-end="url(#${mk})"/>`;
  }).join("");
  const heute = M.heuteX != null ? `<line class="ln-heute" x1="${M.heuteX}" y1="${g.achse - 14}" x2="${M.heuteX}" y2="${M.H}"/>` : "";
  const heuteT = M.heuteX != null ? `<span class="ln-heute-t" style="left:${M.heuteX}px">heute</span>` : "";
  const marker = `<marker id="${mk}" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" markerUnits="userSpaceOnUse" orient="auto"><path class="ln-spitze" d="M0,0.5 L7.5,4 L0,7.5 z"/></marker>`;
  return `<div class="ln-scroll" role="group" aria-label="Ablauf als Diagramm. Ein Kasten öffnet Einzelheiten, Pfeiltasten wechseln den Kasten.">
  <div class="ln-flaeche" style="width:${M.W}px;height:${M.H}px">
    <div class="ln-achse" style="height:${g.achse}px"><div class="ln-ecke" style="width:${g.label}px">${esc(M.ecke)}</div>${achse}${heuteT}</div>
    ${bahnen}
    <svg class="ln-linien" width="${M.W}" height="${M.H}" aria-hidden="true" focusable="false"><defs>${marker}</defs>${heute}${linien}</svg>
    ${M.items.map(it => kastenHTML(it, M, it.id === tabId)).join("")}
  </div></div>`;
}

const farbe = b => `<span class="ln-farbe b-${esc(b)}" aria-hidden="true"></span>`;
const dauer = t => t >= 60 ? `${Math.round(t / 30.4)} Monate` : `${t} Tage`;
const bruchSVG = () => `<svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true"><path d="M2,11 L6,1 M6,11 L10,1"/></svg>`;

function listeHTML(M) {
  const jahre = M.art === "vorgang" && new Set(M.items.filter(it => it.datum).map(it => it.datum.slice(0, 4))).size > 1;
  const datum = it => M.art !== "vorgang" ? M.spalten[it.spalte].label : !it.datum ? "offen" : jahre ? dmy(it.datum) : ddmm(it.datum);
  let heuteGesetzt = M.heuteX == null && !M.heuteNach, letztesDatum = null;
  const zeilenL = M.folge.map(it => {
    let vor = "";
    if (!heuteGesetzt && (it.schluessel || "") > M.heute) { heuteGesetzt = true; vor = `<li class="ln-l-heute" aria-hidden="true"><span>heute ${ddmm(M.heute)}</span></li>`; }
    const aktuell = it.zustand === "aktuell";
    const cls = ["ln-k", "ln-k-liste", "b-" + it.bahn, ...it.zustand.split(" ").map(z => "ist-" + z), it.klein ? "ln-k-klein" : ""].join(" ");
    const dt = datum(it), zeigeDt = dt !== letztesDatum || vor;
    letztesDatum = dt;
    return `${vor}<li class="ln-l${it.typ === "ausgang" ? " ln-l-ast" : ""}"><span class="ln-l-wann">${zeigeDt ? esc(dt) : ""}</span><span class="ln-l-wer">${farbe(it.bahn)}${esc(bahnName(it.bahn, M.daten))}</span>
      <button ${KNOPF} class="${cls}" data-k="${esc(it.id)}" tabindex="${it === (M.aktuell || M.folge[0]) ? 0 : -1}" aria-label="${esc(it.aria)}"${aktuell ? ' aria-current="step"' : ""}>${zeilen(it)}</button></li>`;
  }).join("");
  return `<ol class="ln-liste${jahre ? " ln-jahre" : ""}" role="list" aria-label="Ablauf als Liste">${zeilenL}${heuteGesetzt ? "" : `<li class="ln-l-heute" aria-hidden="true"><span>heute ${ddmm(M.heute)}</span></li>`}</ol>`;
}

function textHTML(M) {
  return `<ol class="vh">${M.folge.map(it => `<li>${esc(it.aria)}${it.zustand === "erwartet" && !/voraussichtlich/.test(it.aria) ? " (voraussichtlich)" : ""}</li>`).join("")}</ol>`;
}

// Legende: eine Zeile je Diagramm, nur die gestrichelten Zustände, die vorkommen (erledigt/aktuell erklären sich über die Farbe)
// Ausgänge brauchen keinen Eintrag: der abzweigende Pfeil mit dem Wort daran erklärt sich selbst
const LEGENDE = [["erwartet", "möglicher nächster Schritt"]];
function legendeHTML(M, quer) {
  const da = LEGENDE.filter(([z]) => M.items.some(it => it.zustand.split(" ").includes(z)));
  const teile = da.map(([z, t]) => `<span><i class="lg ist-${z}"></i>${t}</span>`);
  if (quer) teile.push(`<span class="ln-quer-t">↔ seitlich verschieben für den ganzen Ablauf</span>`);
  return teile.length ? `<p class="ln-legende" aria-hidden="true">${teile.join("")}</p>` : "";
}

// Ohne Diagramm: eine Zeile Termine, jeder Termin öffnet sein Popover
function zeileHTML(M) {
  const t = it => `<button ${KNOPF} class="ln-t" data-k="${esc(it.id)}" aria-label="${esc(it.aria)}">${it.datum ? `<time datetime="${it.datum}">${ddmm(it.datum)}</time>` : "Termin offen:"} ${esc(it.z1)}${it.z2 ? " " + (it.stark ? `<b>${esc(it.z2)}</b>` : esc(it.z2)) : ""}${it.zustand === "erwartet" ? " (voraussichtlich)" : ""}</button>`;
  return `<p class="ln-termine">${M.folge.map(t).join('<span class="meta-trenner" aria-hidden="true">·</span>')}</p>`;
}

// ------------------------------------------------------------------ Popover-Inhalte
const link = (href, text) => href ? `<a href="${esc(href)}">${text}</a>` : "";
const links = arr => arr.filter(Boolean).join('<span class="ln-trenner" aria-hidden="true"> · </span>');
const recht = (r = []) => links(r.map(x => link(x.url, esc(x.label))));
const satz = t => t ? `<p class="ln-d-satz">${t}</p>` : "";
const rechtZeile = r => recht(r) ? `<p class="ln-d-recht"><span class="vh">Rechtsgrundlage: </span>${recht(r)}</p>` : "";
const dokZeile = html => html ? `<p class="ln-d-doks">${html}</p>` : "";
const QUELLE = { sitzung: "laut Ratsinformationssystem", ratsinfo: "laut Ratsinformationssystem", tagesordnung: "laut Tagesordnung", deckblatt: "laut Beratungsfolge auf dem Deckblatt", kalender: "angenommen nach dem Sitzungskalender", verfahren: "möglicher Schritt nach dem üblichen Ablauf" };
const gross = s => s ? s[0].toUpperCase() + s.slice(1) : "";

// Popover eines Knotens: Kopf (Titel, Datum), ein Satz (was geschah, welche Rolle), Dokumente, Rechtsgrundlage
function detailKnoten(k, v, daten, it) {
  const voraus = it.zustand === "erwartet";
  const quelle = QUELLE[k.quelle];
  let titel, text = "";
  if (k.art === "beratung") {
    titel = `${esc(k.gremium || "Gremium unbekannt")}${ergebnisWort(k) ? ": " + esc(ergebnisWort(k)) : ""}`;
    const rolle = (k.rolle_text || "").split(";")[0];
    const erg = k.ergebnis && k.ergebnis !== ergebnisWort(k) ? ` – im Protokoll: „${esc(k.ergebnis)}“` : !k.ergebnis && !voraus ? " – ein Ergebnis ist nicht eingetragen" : "";
    text = (rolle ? `Das Gremium ${esc(rolle)}` : "Beratung") + erg + "." + (k.hinweis ? " " + esc(k.hinweis) : "");
  } else if (k.art === "eingang") {
    titel = `${esc(typName(v.typ))} ${esc(it.z2)}`;
    const wer = (k.einreicher || v.einreicher || []).join(", ") || bahnLang(it.bahn, daten);
    text = `${it.z2 === "vorgelegt" ? "Vorgelegt" : "Eingereicht"} von ${esc(wer)}.`;
  } else {
    titel = esc(k.titel || it.z1.replace(/­/g, ""));
    const was = k.art === "dokument" ? k.name : (k.schritt || {}).was;
    if (was && was !== k.titel) text = abbr(esc(was), daten);
  }
  const meta = [k.datum ? `<time datetime="${k.datum}">${dmy(k.datum)}</time>` : "Termin offen", voraus ? `voraussichtlich${quelle ? ", " + quelle : ""}` : "", it.zustand === "aktuell" ? "aktueller Stand" : "", k.top ? `TOP ${esc(k.top)}` : ""].filter(Boolean).join(" · ");
  const punkte = (k.punkte || []).filter(p => p.pdf || p.beschluss_pdf || p.ratsinfo);
  let doks;
  if (punkte.length > 1) {
    const sitzung = links([link(k.einladung_pdf, "Einladung"), link(k.sitzung_url, "Sitzung")]);
    doks = `<ul class="ln-doks">${punkte.map(p => `<li><span class="num">${abbr(esc(p.reference), daten)}</span> ${links([link(p.pdf, "Vorlage"), link(p.beschluss_pdf, "Beschluss"), link(p.ratsinfo, "Ratsinfo")])}${p.ergebnis && p.ergebnis !== k.ergebnis ? ` <span class="ln-leise">„${esc(p.ergebnis)}“</span>` : ""}</li>`).join("")}</ul>${dokZeile(sitzung)}`;
  } else {
    const p = punkte[0] || {};
    doks = dokZeile(links([link(k.pdf || p.pdf, "Vorlage"), link(k.beschluss_pdf || p.beschluss_pdf, "Beschluss"), link(k.einladung_pdf, "Einladung"), link(k.sitzung_url, "Sitzung"), link(k.ratsinfo || p.ratsinfo, "Ratsinfo")]));
  }
  return kopf(titel, meta) + satz(text) + doks + rechtZeile(k.rechtsgrundlagen);
}

function detailDokument(d, v, daten) {
  const titel = d.art === "stellungnahme" ? "Stellungnahme der Verwaltung" : aaName(d.name);
  return kopf(esc(titel), `<time datetime="${d.datum}">${dmy(d.datum)}</time> · <span class="num">${abbr(esc(d.reference), daten)}</span>`)
    + satz(esc(d.name)) + dokZeile(links([link(d.pdf, "Dokument"), link(d.ratsinfo, "Ratsinfo")]));
}

function detailSchritt(s, vf, daten, wann) {
  return kopf(esc(s.was), `${esc(wann)} · ${esc(bahnLang(s.bahn, daten))}`) + satz(s.detail ? abbr(esc(s.detail), daten) : "") + rechtZeile(s.recht);
}

function detailAusgang(a, vf, daten, anker) {
  return kopf(`Wenn ${esc(a.wenn)}`, `nach: ${esc(String(anker.z1).replace(/­/g, ""))}`) + satz(abbr(esc(gross(a.dann)), daten)) + rechtZeile(a.recht);
}

const kopf = (titel, meta) => `<div class="ln-d-kopf"><h2 class="ln-d-titel">${titel}</h2></div><p class="ln-d-meta">${meta}</p>`;

// ------------------------------------------------------------------ Rendern und Bedienen
// Zustand je Element in el._ln (M, byId, breite); Ereignisse und ResizeObserver nur einmal je Element.
function zeichne(el, M, daten, ohneDiagramm) {
  M.daten = daten;
  el.classList.add("ln");
  el.classList.toggle("ln-ohne", !!ohneDiagramm);
  el.dataset.art = M.art;
  const st = el._ln || (el._ln = bediene(el));
  Object.assign(st, { M, zeile: !!ohneDiagramm, byId: Object.fromEntries(M.items.map(i => [i.id, i])) });
  rendere(el, st);
  return { el };
}

function rendere(el, st) {
  const M = st.M;
  const offenHier = el.querySelector('[data-k][aria-expanded="true"]');
  if (offenHier) schliesse(false);
  st.breite = el.clientWidth;
  if (st.zeile) {
    M.folge = M.items.slice().sort((a, b) => a.schluessel.localeCompare(b.schluessel) || a.ord - b.ord);
    el.innerHTML = zeileHTML(M);
    return;
  }
  layout(M, st.breite || 1184, getComputedStyle(el).fontFamily || "sans-serif");
  const quer = M.W > st.breite + 1;
  el.classList.toggle("ln-eng", quer && st.breite < ENG);
  el.classList.toggle("ln-quer", quer && st.breite >= ENG);
  el.innerHTML = diagrammHTML(M, ++uid) + listeHTML(M) + textHTML(M) + legendeHTML(M, quer && st.breite >= ENG);
  // seitlich scrollbar: den aktuellen Schritt (sonst den letzten erledigten) mit etwas Vorlauf in den Blick
  if (quer && st.breite >= ENG) {
    const ziel = M.aktuell || M.folge.filter(it => it.zustand !== "erwartet").pop();
    const sc = el.querySelector(".ln-scroll");
    if (ziel) sc.scrollLeft = Math.max(0, ziel.x - M.g.label - M.boxW - M.g.luft);
    randZeigen(sc);
  }
}
// am rechten Ende keine Ausblendung mehr (.ln-ende)
function randZeigen(sc) {
  sc.classList.toggle("ln-ende", sc.scrollLeft + sc.clientWidth >= sc.scrollWidth - 2);
}

function bediene(el) {
  const st = {};
  el.addEventListener("click", e => {
    const b = e.target.closest("[data-k]");
    if (!b) return;
    if (offenFuer(b)) schliesse(false);
    else oeffne(b, st.byId[b.dataset.k].detail());
    if (!st.zeile) roving(el, b.dataset.k);
  });
  el.addEventListener("keydown", e => {
    const b = e.target.closest("[data-k]");
    if (!b || st.zeile) return;
    const M = st.M, it = st.byId[b.dataset.k], liste = !!b.closest(".ln-liste");
    let ziel = null;
    const i = M.folge.indexOf(it);
    if (e.key === "ArrowRight" || (liste && e.key === "ArrowDown")) ziel = M.folge[i + 1];
    else if (e.key === "ArrowLeft" || (liste && e.key === "ArrowUp")) ziel = M.folge[i - 1];
    else if (e.key === "Home") ziel = M.folge[0];
    else if (e.key === "End") ziel = M.folge[M.folge.length - 1];
    else if (e.key === "ArrowUp" || e.key === "ArrowDown") {
      const bi = M.bahnen.indexOf(it.bahn), dir = e.key === "ArrowUp" ? -1 : 1;
      const cx = it.x + it.w / 2, cy = it.y + it.h / 2;
      const abst = x => Math.abs(M.bahnen.indexOf(x.bahn) - bi) * 4 + Math.abs(x.x + x.w / 2 - cx) / (M.boxW + M.g.luft) + Math.abs(x.y - cy) / 400;
      const kand = M.items.filter(x => x !== it && (x.bahn === it.bahn ? x.spalte === it.spalte && (dir < 0 ? x.dy < it.dy : x.dy > it.dy) : (M.bahnen.indexOf(x.bahn) - bi) * dir > 0));
      kand.sort((a, b2) => abst(a) - abst(b2));
      ziel = kand[0];
    } else return;
    e.preventDefault();
    if (!ziel) return;
    roving(el, ziel.id);
    const nb = sichtbar(el, ziel.id);
    nb?.focus();
    nb?.scrollIntoView({ block: "nearest", inline: "nearest" });
  });
  el.addEventListener("scroll", e => { if (e.target.classList?.contains("ln-scroll")) randZeigen(e.target); }, true);
  // Breite ändert sich (Fenster, Drehen): Spalten neu verteilen
  new ResizeObserver(() => {
    if (st.M && !st.zeile && Math.abs(el.clientWidth - st.breite) > 24) rendere(el, st);
  }).observe(el);
  return st;
}

function roving(el, kid) {
  el.querySelectorAll("[data-k]").forEach(b => b.tabIndex = b.dataset.k === kid ? 0 : -1);
}
function sichtbar(el, kid) {
  return [...el.querySelectorAll(`[data-k="${CSS.escape(kid || "")}"]`)].find(b => b.offsetParent !== null);
}

export function zeigeVorgang(el, vorgang, daten, opts = {}) {
  const heute = opts.heute || heuteISO();
  return zeichne(el, vorgangModell(vorgang, daten, heute), daten, !opts.immer && !brauchtDiagramm(vorgang, heute));
}
export function zeigeVerfahren(el, verfahren, daten) {
  return zeichne(el, verfahrenModell(verfahren, daten), daten, false);
}

// Hilfen für die Seite: Kopfzeilen eines Vorgangs ohne Wiederholung des Diagramms.
export function metaZeile(v, daten) {
  const vf = daten.verfahren.find(x => x.id === (v.verfahren || {}).id);
  const art = typName(v.typ);
  const teile = [
    vf ? `<a href="#verstehen" data-verfahren="${esc(vf.id)}">${esc(art)}</a>` : esc(art),
    `<span class="num">${esc(v.stammnummer)}</span>`,
    esc(v.ebene === "bezirk" && v.bezirk ? "Bezirksvertretung " + v.bezirk : "gesamtstädtisch"),
  ].filter(Boolean);
  return teile.join('<span class="meta-trenner" aria-hidden="true">·</span>');
}
