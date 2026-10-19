// Bereich „Politische Vorgänge in Bonn“: links Filter und Liste, rechts ein Vorgang (ab 960 px zweispaltig).
// Route #vorgaenge[?filter][/<nr>]; Filter: status, gremium (Klasse), art (Klasse), partei (beteiligte Fraktion),
// thema (aus einordnung.py), zeit (Jahr oder „eigen“ mit
// von/bis), q. Zeitraum: ein Vorgang passt, wenn einer seiner Termine (termine + nächster Termin) darin liegt. Alles steht in der
// URL; Auswahl und Filterwechsel legen einen Verlauf-Eintrag an (Zurück-Taste), Tippen in der Suche nicht.
// Breit ohne /<nr>: der erste Treffer wird gewählt (replaceState). Schmal: Liste, Auswahl öffnet das Detail als
// eigene Ansicht mit „← Zur Liste“ (Filter bleiben erhalten).
// Daten: daten/vorgaenge-index.json (Liste, Gremien als Positionen) und daten/vorgang/<nr>.json (Detail), von
// einordnung.py. Nichtöffentliche Sammelpunkte (verfahren „nichtoeffentlich“) sind ausgeblendet.
// Detail: Titel, eine Metazeile (Stand), „Mitreden bis …“ als Popover, ein Satz zur Art des Vorgangs (unter
// „Worum geht's?“ nur, wenn ein KI-Inhaltssatz dazukommt), genau ein Diagramm
// (lanes.js, immer).

import { esc, ddmm, dmy, heuteISO, kurzGremium, zeigeVorgang } from "./lanes.js";

const SEITE = 50;
const breit = matchMedia("(min-width: 960px)");
const zahl = n => n.toLocaleString("de-DE");
const T = '<span class="meta-trenner" aria-hidden="true">·</span>';

// ------------------------------------------------------------------ Klassen für die Filter
const STATUS = [["offen", "offen"], ["vertagt", "vertagt"], ["abgeschlossen", "abgeschlossen"], ["unklar", "unklar"]];
export const STATUS_WORT = { offen: "offen", vertagt: "vertagt", abgeschlossen: "abgeschlossen", unklar: "Stand unklar" };

// Gremienart aus dem Namen; ein Vorgang gehört zu jeder Klasse, in der er beraten wurde oder wird
const BEZIRKE = ["Bonn", "Bad Godesberg", "Beuel", "Hardtberg"];
const slug = s => s.toLowerCase().replace(/ /g, "-");
const GREMIUM = [
  { id: "rat", name: "Rat", gruppe: "Stadt", bahn: "rat", passt: g => g === "Rat" },
  { id: "hauptausschuss", name: "Hauptausschuss", gruppe: "Stadt", bahn: "aus", passt: g => g === "Hauptausschuss" },
  { id: "ausschuss", name: "Fachausschüsse", gruppe: "Stadt", bahn: "aus", passt: g => /ausschuss/i.test(g) && g !== "Hauptausschuss" },
  { id: "bv", name: "alle Bezirksvertretungen", gruppe: "Bezirke", bahn: "bv", passt: g => g.startsWith("Bezirksvertretung ") },
  ...BEZIRKE.map(b => ({ id: "bv-" + slug(b), name: "Bezirksvertretung " + b, gruppe: "Bezirke", bahn: "bv", passt: g => g === "Bezirksvertretung " + b })),
  { id: "beirat", name: "Beiräte und Kommissionen", gruppe: "Weitere", bahn: "aus", passt: g => /beirat|kommission|Integrationsrat/i.test(g) },
  { id: "ohne", name: "noch ohne Gremium", gruppe: "Weitere", bahn: null, passt: null },
];
const bahnVon = g => !g ? null : g === "Rat" ? "rat" : g.startsWith("Bezirksvertretung") ? "bv" : "aus";

// Art: Verfahren aus einordnung.py in wenige verständliche Klassen
export const ART = [
  { id: "antrag", name: "Antrag", verfahren: ["antrag-rat", "antrag-bv", "dringlichkeitsantrag"] },
  { id: "anfrage", name: "Anfrage", verfahren: ["grosse-anfrage", "kleine-anfrage"] },
  { id: "einwohner", name: "Bürgerantrag, Einwohnerfrage", verfahren: ["buergerantrag", "einwohnerfrage", "einwohnerantrag", "buergerbegehren"] },
  { id: "vorlage", name: "Vorlage der Verwaltung", verfahren: ["beschlussvorlage", "ausschuss-entscheidung", "bauleitplanung", "dringlichkeitsentscheidung"] },
  { id: "mitteilung", name: "Mitteilung", verfahren: ["mitteilung"] },
  { id: "sonst", name: "Sonstiges", verfahren: [] },
];
const artVon = vid => (ART.find(a => a.verfahren.includes(vid)) || ART[ART.length - 1]).id;
const ART_WORT = {
  "antrag-rat": "Antrag", "antrag-bv": "Antrag", dringlichkeitsantrag: "Dringlichkeitsantrag", "grosse-anfrage": "Große Anfrage",
  "kleine-anfrage": "Kleine Anfrage", buergerantrag: "Bürgerantrag", einwohnerfrage: "Einwohnerfrage", beschlussvorlage: "Vorlage",
  "ausschuss-entscheidung": "Vorlage", bauleitplanung: "Bebauungsplan", dringlichkeitsentscheidung: "Eilentscheidung", mitteilung: "Mitteilung",
};
// „Bürgerantrag: …“ neben der Art „Bürgerantrag“ sagt dasselbe zweimal
// Fraktionen unter den Einreichern (gemeinsame Anträge gehören zu jeder beteiligten); Themen mit „Sonstiges“ zuletzt
const KEINE_PARTEI = new Set(["Verwaltung", "Bürger:innen", "interfraktionell"]);
export const parteienVon = v => (v.einreicher || []).filter(e => !KEINE_PARTEI.has(e));
let PARTEIEN = [], THEMEN = [];
const nachHaeufigkeit = (werte, zuletzt) => {
  const n = {};
  for (const w of werte) n[w] = (n[w] || 0) + 1;
  return Object.keys(n).sort((a, b) => (a === zuletzt) - (b === zuletzt) || n[b] - n[a] || a.localeCompare(b));
};
const PRAEFIX = /^(Bürgerantrag|Einwohnerfrage|Informationsbrief|Mitteilungsvorlage|Mitteilung|Antrag|Große Anfrage|Kleine Anfrage):\s+/;

// ------------------------------------------------------------------ Daten
let IDX = null, idxP = null;
const details = new Map();
const lade = url => fetch(url).then(r => { if (!r.ok) throw new Error(`${url}: ${r.status}`); return r.json(); });

export function index() {
  return idxP ||= lade("daten/vorgaenge-index.json").then(raw => {
    const namen = raw.gremien;
    IDX = raw.vorgaenge.filter(v => v.verfahren !== "nichtoeffentlich").map(v => {
      const gremien = (v.gremien || []).map(i => namen[i]);
      const naechster = v.naechster && v.naechster[1] != null ? namen[v.naechster[1]] : null;
      const alle = [...new Set([...gremien, naechster].filter(Boolean))];
      const klassen = new Set(GREMIUM.filter(k => k.passt && alle.some(k.passt)).map(k => k.id));
      if (!alle.length) klassen.add("ohne");
      return { ...v, gremium: v.gremium != null ? namen[v.gremium] : null, klassen, art: artVon(v.verfahren),
        daten: [...(v.termine || []), ...(v.naechster ? [v.naechster[0]] : [])],
        titelKurz: (v.titel || "").replace(PRAEFIX, ""), such: `${v.titel} ${v.stammnummer} ${v.suchtext || ""}`.toLowerCase() };
    }).sort((a, b) => (b.zuletzt || "").localeCompare(a.zuletzt || "") || b.stammnummer.localeCompare(a.stammnummer));
    IDX.nachNr = new Map(IDX.map(v => [v.stammnummer, v]));
    PARTEIEN = nachHaeufigkeit(IDX.flatMap(parteienVon));
    THEMEN = nachHaeufigkeit(IDX.map(v => v.thema || "Sonstiges"), "Sonstiges");
    return IDX;
  });
}

function detail(nr) {
  if (!details.has(nr)) details.set(nr, lade(`daten/vorgang/${encodeURIComponent(nr)}.json`).catch(e => { details.delete(nr); throw e; }));
  return details.get(nr);
}

// ------------------------------------------------------------------ URL
const LEER = { status: "", gremium: "", art: "", partei: "", thema: "", zeit: "", von: "", bis: "", q: "" };
const ISO = /^\d{4}-\d{2}-\d{2}$/;

function lies(rest) {
  const m = rest.match(/^(?:\?([^/]*))?(?:\/(\w+))?(?:\?(.*))?$/) || [];
  const p = new URLSearchParams(m[1] || m[3] || "");
  const f = { ...LEER };
  if (STATUS.some(s => s[0] === p.get("status"))) f.status = p.get("status");
  const g = p.get("gremium") || "";
  f.gremium = GREMIUM.some(k => k.id === g) ? g : (GREMIUM.find(k => k.passt && k.id !== "bv" && k.passt(g)) || {}).id || "";  // alte Links: voller Name
  const a = p.get("art") || "";
  f.art = ART.some(k => k.id === a) ? a : a ? artVon(a) : "";  // alte Links: Verfahrens-Id
  if (PARTEIEN.includes(p.get("partei"))) f.partei = p.get("partei");
  if (THEMEN.includes(p.get("thema"))) f.thema = p.get("thema");
  const z = p.get("zeit") || "";
  if (/^\d{4}$/.test(z)) f.zeit = z;
  else if (z === "eigen") {
    f.zeit = z;
    if (ISO.test(p.get("von") || "")) f.von = p.get("von");
    if (ISO.test(p.get("bis") || "")) f.bis = p.get("bis");
  }
  f.q = (p.get("q") || "").trim();
  return { f, nr: m[2] || "" };
}

function query(f) {
  const p = new URLSearchParams();
  for (const k of ["status", "gremium", "art", "partei", "thema", "zeit"]) if (f[k]) p.set(k, f[k]);
  if (f.zeit === "eigen") for (const k of ["von", "bis"]) if (f[k]) p.set(k, f[k]);
  if (f.q) p.set("q", f.q);
  const s = p.toString();
  return s ? "?" + s : "";
}
const hashVon = (f, nr) => `#vorgaenge${query(f)}${nr ? "/" + nr : ""}`;

// ------------------------------------------------------------------ Filtern
function passt(v, f, ohne) {
  if (ohne !== "status" && f.status && v.status !== f.status) return false;
  if (ohne !== "gremium" && f.gremium && !v.klassen.has(f.gremium)) return false;
  if (ohne !== "art" && f.art && v.art !== f.art) return false;
  if (ohne !== "partei" && f.partei && !parteienVon(v).includes(f.partei)) return false;
  if (ohne !== "thema" && f.thema && (v.thema || "Sonstiges") !== f.thema) return false;
  if (ohne !== "zeit" && f.zeit && !imZeitraum(v, f)) return false;
  if (f.q && !f.q.toLowerCase().split(/\s+/).every(w => v.such.includes(w))) return false;
  return true;
}
const treffer = f => IDX.filter(v => passt(v, f));
function imZeitraum(v, f) {
  const [a, b] = f.zeit === "eigen" ? [f.von || "0000", f.bis || "9999"] : [f.zeit + "-01-01", f.zeit + "-12-31"];
  return v.daten.some(d => d >= a && d <= b);
}
const spanneWort = f => f.von && f.bis ? `${dmy(f.von)} – ${dmy(f.bis)}` : f.von ? `ab ${dmy(f.von)}` : f.bis ? `bis ${dmy(f.bis)}` : "eigener Zeitraum";

function zaehle(f, feld, wert) {
  const n = {};
  for (const v of IDX) if (passt(v, f, feld)) for (const w of wert(v)) n[w] = (n[w] || 0) + 1;
  return n;
}

// ------------------------------------------------------------------ Elemente
const $ = id => document.getElementById(id);
let el = null;
function elemente() {
  if (el) return el;
  el = {
    raster: $("vg-raster"), box: $("vg-filter-box"), form: $("vg-filter"), q: $("vg-q"), status: $("vg-status"),
    gremium: $("vg-gremium"), art: $("vg-art"), partei: $("vg-partei"), thema: $("vg-thema"), zeit: $("vg-zeit"), spanne: $("vg-spanne"), von: $("vg-von"), bis: $("vg-bis"), zahl: $("vg-zahl"), aktiv: $("vg-aktiv"),
    liste: $("vg-liste"), detail: $("vg-detail"),
  };
  if (!breit.matches) el.box.open = false;  // schmal: Filter eingeklappt; breit offen, aber einklappbar; aktive Filter stehen darunter
  bediene();
  return el;
}

// ------------------------------------------------------------------ Zustand und Ansicht
let zustand = { f: { ...LEER }, nr: "" }, gezeigt = 0, gezeigtListe = 0, listenSchluessel = null, detailNr = null, lauf = 0, merkeFokus = false;

export async function vorgaenge(rest, datenLaden) {
  const e = elemente();
  const [, daten] = await Promise.all([index(), datenLaden()]);
  let { f, nr } = lies(rest);
  const liste = treffer(f);
  // breit ohne Auswahl: den ersten Treffer wählen, ohne neuen Verlauf-Eintrag
  if (!nr && breit.matches && liste.length) {
    nr = liste[0].stammnummer;
    history.replaceState(null, "", hashVon(f, nr));
  }
  const vorher = zustand;
  zustand = { f, nr };
  const schluessel = query(f);
  if (schluessel !== listenSchluessel) gezeigt = SEITE;
  // die gewählte Zeile soll in der Liste stehen
  const pos = nr ? liste.findIndex(v => v.stammnummer === nr) : -1;
  if (pos >= gezeigt) gezeigt = Math.ceil((pos + 1) / SEITE) * SEITE;
  if (schluessel !== listenSchluessel || gezeigt !== gezeigtListe || !el.liste.childElementCount) {
    formular(f);
    zeigeListe(liste, schluessel !== listenSchluessel);
  } else markiere(nr);  // nur die Auswahl wechselt: Liste und Fokus bleiben stehen
  listenSchluessel = schluessel;

  const ansicht = breit.matches ? "beide" : nr ? "detail" : "liste";
  const ansichtVorher = e.raster.dataset.ansicht;
  e.raster.dataset.ansicht = ansicht;
  if (!nr) { e.detail.innerHTML = ""; detailNr = null; }
  else if (nr !== detailNr || !e.detail.childElementCount) await zeigeDetail(nr, f, daten);

  // Fokus: schmal Liste → Detail auf den Titel, Detail → Liste auf die zuletzt gewählte Zeile
  if (ansichtVorher === "liste" && ansicht === "detail") {
    $("vg-titel")?.focus({ preventScroll: true });
    $("inhalt").scrollTo(0, 0);
  } else if (ansichtVorher === "detail" && ansicht === "liste" && vorher.nr) {
    const z = zeile(vorher.nr);
    if (z) { z.focus({ preventScroll: true }); z.scrollIntoView({ block: "center" }); }
  } else if (merkeFokus && nr) {
    zeile(nr)?.focus({ preventScroll: true });
  }
  merkeFokus = false;
  const v = nr && IDX.nachNr.get(nr);
  return v ? `${v.titelKurz} · Politische Vorgänge in Bonn` : "Politische Vorgänge in Bonn";
}

// ------------------------------------------------------------------ Filter-Formular
function formular(f) {
  const e = el;
  if (document.activeElement !== e.q) e.q.value = f.q;
  const ns = zaehle(f, "status", v => [v.status]);
  const alleS = Object.values(ns).reduce((a, b) => a + b, 0);
  e.status.innerHTML = [["", "alle", alleS], ...STATUS.map(([id, name]) => [id, name, ns[id] || 0])].map(([id, name, n]) =>
    `<option value="${id}"${f.status === id ? " selected" : ""}>${esc(name)} (${zahl(n)})</option>`).join("");
  e.status.value = f.status;
  const ng = zaehle(f, "gremium", v => v.klassen), alleG = IDX.filter(v => passt(v, f, "gremium")).length;
  const gruppen = [...new Set(GREMIUM.map(k => k.gruppe))];
  e.gremium.innerHTML = `<option value="">alle Gremien (${zahl(alleG)})</option>` + gruppen.map(g => `<optgroup label="${g}">${GREMIUM.filter(k => k.gruppe === g)
    .map(k => `<option value="${k.id}"${f.gremium === k.id ? " selected" : ""}>${esc(k.name)} (${zahl(ng[k.id] || 0)})</option>`).join("")}</optgroup>`).join("");
  const na = zaehle(f, "art", v => [v.art]), alleA = IDX.filter(v => passt(v, f, "art")).length;
  e.art.innerHTML = `<option value="">alle Arten (${zahl(alleA)})</option>` + ART.filter(a => IDX.some(v => v.art === a.id))
    .map(a => `<option value="${a.id}"${f.art === a.id ? " selected" : ""}>${esc(a.name)} (${zahl(na[a.id] || 0)})</option>`).join("");
  const np = zaehle(f, "partei", parteienVon), alleP = IDX.filter(v => passt(v, f, "partei")).length;
  e.partei.innerHTML = `<option value="">alle (${zahl(alleP)})</option>` + PARTEIEN.map(x => `<option value="${esc(x)}">${esc(x)} (${zahl(np[x] || 0)})</option>`).join("");
  const nt = zaehle(f, "thema", v => [v.thema || "Sonstiges"]), alleT = IDX.filter(v => passt(v, f, "thema")).length;
  e.thema.innerHTML = `<option value="">alle Themen (${zahl(alleT)})</option>` + THEMEN.map(x => `<option value="${esc(x)}">${esc(x)} (${zahl(nt[x] || 0)})</option>`).join("");
  e.partei.value = f.partei;
  e.thema.value = f.thema;
  const nz = zaehle(f, "zeit", v => new Set(v.daten.map(d => d.slice(0, 4)))), alleZ = IDX.filter(v => passt(v, f, "zeit")).length;
  const jahre = Object.keys(nz).sort().reverse();
  e.zeit.innerHTML = `<option value="">alle Jahre (${zahl(alleZ)})</option>` + jahre.map(j => `<option value="${j}">${j} (${zahl(nz[j])})</option>`).join("")
    + `<option value="eigen">eigener Zeitraum …</option>`;
  e.gremium.value = f.gremium;
  e.art.value = f.art;
  e.zeit.value = f.zeit;
  e.spanne.hidden = f.zeit !== "eigen";
  e.von.value = f.von; e.bis.value = f.bis;
  e.von.max = f.bis || ""; e.bis.min = f.von || "";
  // aktive Filter als entfernbare Knöpfe (schmal, bei eingeklappten Filtern); breit stehen sie in den Feldern, dort nur „zurücksetzen“
  const aktiv = [
    f.status && ["status", STATUS_WORT[f.status]],
    f.gremium && ["gremium", GREMIUM.find(k => k.id === f.gremium).name],
    f.art && ["art", ART.find(a => a.id === f.art).name],
    f.partei && ["partei", f.partei],
    f.thema && ["thema", f.thema],
    f.zeit && ["zeit", f.zeit === "eigen" ? spanneWort(f) : f.zeit],
    f.q && ["q", `„${f.q}“`],
  ].filter(Boolean);
  e.aktiv.innerHTML = aktiv.length ? `<ul>${aktiv.map(([k, t]) => `<li><button type="button" class="vg-weg" data-weg="${k}" aria-label="Filter ${esc(t)} entfernen">${esc(t)} <span aria-hidden="true">×</span></button></li>`).join("")}<li><button type="button" class="vg-weg vg-alle" data-weg="alle">${aktiv.length > 1 ? "Alle zurücksetzen" : "Filter zurücksetzen"}</button></li></ul>` : "";
  e.box.querySelector(".vg-filter-n").textContent = aktiv.length ? ` (${aktiv.length} aktiv)` : "";
}

// ------------------------------------------------------------------ Liste
const MONAT = new Intl.DateTimeFormat("de-DE", { month: "long", year: "numeric" });
const monat = iso => iso ? MONAT.format(new Date(+iso.slice(0, 4), +iso.slice(5, 7) - 1, 1)) : "ohne Datum";
const datumKurz = iso => !iso ? "" : iso.slice(0, 4) === heuteISO().slice(0, 4) ? ddmm(iso) : dmy(iso);

function zeileHTML(v, f, gewaehlt) {
  const g = v.gremium;
  const meta = [  // Gremium mit Farbquadrat zuerst, damit die Quadrate untereinander stehen
    g ? `<span class="vg-g"><span class="ln-farbe b-${bahnVon(g)}" aria-hidden="true"></span>${esc(kurzGremium(g))}</span>` : "",
    esc(ART_WORT[v.verfahren] || "Vorgang"),
    esc(STATUS_WORT[v.status] || v.status),
    v.zuletzt ? `<time datetime="${v.zuletzt}">${datumKurz(v.zuletzt)}</time>` : "",
  ].filter(Boolean).join(T);
  return `<li><a class="vg-zeile" href="${esc(hashVon(f, v.stammnummer))}" data-nr="${esc(v.stammnummer)}" tabindex="-1"${gewaehlt ? ' aria-current="true"' : ""}>
    <span class="vg-z-titel">${esc(v.titelKurz)}</span><span class="vg-z-meta">${meta}</span></a></li>`;
}

function zeigeListe(liste, neu) {
  const e = el, { f, nr } = zustand;
  e.zahl.textContent = liste.length === 1 ? "1 Vorgang" : `${zahl(liste.length)} Vorgänge`;
  let html = "", m = null;
  for (const v of liste.slice(0, gezeigt)) {
    const mm = monat(v.zuletzt);
    if (mm !== m) { html += `${m ? "</ul>" : ""}<h3 class="vg-monat">${esc(mm)}</h3><ul class="vg-zeilen" role="list">`; m = mm; }
    html += zeileHTML(v, f, v.stammnummer === nr);
  }
  if (m) html += "</ul>";
  const rest = liste.length - gezeigt;
  html += rest > 0 ? `<p class="vg-mehr"><button type="button" id="vg-mehr">Weitere ${zahl(Math.min(SEITE, rest))} zeigen</button> <span class="vg-n">von ${zahl(rest)}</span></p>` : "";
  if (!liste.length) html = `<p class="vg-leer">Keine Vorgänge für diese Filter.${query(f) ? ' <button type="button" class="vg-weg" data-weg="alle">Filter zurücksetzen</button>' : ""}</p>`;
  gezeigtListe = gezeigt;
  const scroll = e.liste.scrollTop;
  e.liste.innerHTML = html;
  if (!neu) e.liste.scrollTop = scroll;
  roving();
  sichtbar(nr);
}

function markiere(nr) {
  for (const z of el.liste.querySelectorAll('.vg-zeile[aria-current]')) z.removeAttribute("aria-current");
  const z = nr && zeile(nr);
  if (z) z.setAttribute("aria-current", "true");
  if (!el.liste.contains(document.activeElement)) roving();
  sichtbar(nr);
}

// gewählte Zeile im eigenen Scrollbereich der Liste ganz sichtbar halten (nur breit, „nearest“ mit Luft); sichtbar ist
// der Teil der Liste, der im Fenster liegt (die Spalte ist fensterhoch und ragt beim Seitenanfang unten hinaus).
// Die Seite selbst scrollt nicht mit.
function sichtbar(nr) {
  const z = nr && breit.matches && zeile(nr);
  if (z) inListe(z);
}
function inListe(z) {
  const L = 12, lr = el.liste.getBoundingClientRect(), zr = z.getBoundingClientRect();
  const oben = Math.max(lr.top, 0) + L, unten = Math.min(lr.bottom, innerHeight) - L;
  if (zr.top < oben || zr.height > unten - oben) el.liste.scrollTop += zr.top - oben;
  else if (zr.bottom > unten) el.liste.scrollTop += zr.bottom - unten;
}

const zeile = nr => el.liste.querySelector(`.vg-zeile[data-nr="${CSS.escape(nr)}"]`);
const zeilen = () => [...el.liste.querySelectorAll(".vg-zeile")];

// Liste als ein Tab-Halt: die gewählte (sonst erste) Zeile ist tabbar, Pfeiltasten wechseln
function roving(ziel) {
  const zs = zeilen();
  const t = ziel || zs.find(z => z.getAttribute("aria-current")) || zs[0];
  zs.forEach(z => { z.tabIndex = z === t ? 0 : -1; });
}

// ------------------------------------------------------------------ Detail
async function zeigeDetail(nr, f, daten) {
  const e = el, n = ++lauf;
  detailNr = nr;
  let v;
  try { v = await detail(nr); }
  catch (err) {
    if (n !== lauf) return;
    e.detail.innerHTML = `${zurueck(f)}<h2 id="vg-titel" tabindex="-1">Vorgang ${esc(nr)}</h2><p class="fehler">Diesen Vorgang gibt es in den Daten nicht${/404/.test(err.message) ? "" : " oder er konnte nicht geladen werden"}.</p>`;
    return;
  }
  if (n !== lauf) return;
  const heute = heuteISO();
  const ki = v.worum_ki ? ` ${esc(v.worum_ki)} <small class="vg-ki">(automatisch zusammengefasst)</small>` : "";
  e.detail.innerHTML = `${zurueck(f)}
    <h2 id="vg-titel" class="vg-titel" tabindex="-1">${esc(v.titel)}</h2>
    ${ki ? `<h3 class="vg-worum-h">Worum geht's?</h3>` : ""}
    ${v.worum || ki ? `<p class="vg-worum">${esc(v.worum || "")}${ki}</p>` : ""}
    <div id="vg-ln"></div>`;
  zeigeVorgang($("vg-ln"), v, daten, { heute, immer: true });
}

const zurueck = f => `<p class="vg-zurueck"><a href="${esc(hashVon(f, ""))}" data-zurueck><span aria-hidden="true">←</span> Zur Liste</a></p>`;

// ------------------------------------------------------------------ Bedienung
function setze(f, nr, ersetzen) {
  const h = hashVon(f, nr);
  if (ersetzen) { history.replaceState(null, "", h); dispatchEvent(new HashChangeEvent("hashchange")); }
  else location.hash = h;
}

// Filterwechsel: die Auswahl bleibt, wenn sie noch passt; sonst wählt die breite Ansicht den ersten Treffer
function neueFilter(f, ersetzen = false) {
  const nr = zustand.nr && breit.matches && IDX.some(v => v.stammnummer === zustand.nr && passt(v, f)) ? zustand.nr : "";
  setze(f, nr, ersetzen);
}

function bediene() {
  const e = el;
  e.form.addEventListener("submit", ev => ev.preventDefault());
  e.form.addEventListener("change", ev => {
    const t = ev.target, f = { ...zustand.f };
    if (t.name === "status") f.status = t.value;
    else if (t.name === "gremium") f.gremium = t.value;
    else if (t.name === "art") f.art = t.value;
    else if (t.name === "partei" || t.name === "thema") f[t.name] = t.value;
    else if (t.name === "zeit") { f.zeit = t.value; f.von = f.bis = ""; }
    else if (t.name === "von" || t.name === "bis") f[t.name] = ISO.test(t.value) ? t.value : "";
    else return;
    neueFilter(f);
  });
  let warte = null;
  e.q.addEventListener("input", () => {
    clearTimeout(warte);
    warte = setTimeout(() => neueFilter({ ...zustand.f, q: e.q.value.trim() }, true), 250);
  });
  e.aktiv.addEventListener("click", weg);
  e.liste.addEventListener("click", ev => {
    if (ev.target.closest(".vg-weg")) return weg(ev);
    if (ev.target.closest("#vg-mehr")) {
      const erste = zeilen().length;
      gezeigt += SEITE;
      zeigeListe(treffer(zustand.f), false);
      const z = zeilen()[erste];
      if (z) { roving(z); z.focus(); }
      return;
    }
    if (ev.target.closest(".vg-zeile")) merkeFokus = breit.matches;
  });
  e.liste.addEventListener("keydown", ev => {
    const z = ev.target.closest(".vg-zeile");
    if (!z) return;
    const zs = zeilen(), i = zs.indexOf(z);
    const ziel = { ArrowDown: zs[i + 1], ArrowUp: zs[i - 1], Home: zs[0], End: zs[zs.length - 1] }[ev.key];
    if (!(ev.key in { ArrowDown: 1, ArrowUp: 1, Home: 1, End: 1 })) return;
    ev.preventDefault();
    if (!ziel) return;
    roving(ziel);
    if (breit.matches) { ziel.focus({ preventScroll: true }); inListe(ziel); }
    else { ziel.focus(); ziel.scrollIntoView({ block: "nearest" }); }
  });
  breit.addEventListener("change", () => { if (breit.matches) e.box.open = true; if (location.hash.startsWith("#vorgaenge")) dispatchEvent(new HashChangeEvent("hashchange")); });
}

function weg(ev) {
  const b = ev.target.closest("[data-weg]");
  if (!b) return;
  const k = b.dataset.weg;
  const f = k === "alle" ? { ...LEER } : k === "zeit" ? { ...zustand.f, zeit: "", von: "", bis: "" } : { ...zustand.f, [k]: LEER[k] };
  if (k === "q" || k === "alle") el.q.value = f.q;
  neueFilter(f);
  el.q.focus({ preventScroll: true });
}
