// Bereich „Statistik“: Anteile der Vorgänge als Ringdiagramme (Torten mit Loch für die Gesamtzahl).
// Route #statistik[?zeit=<jahr>&status=…&art=…&partei=…&thema=…]. Ein Klick auf ein Segment oder eine Tabellenzeile
// setzt den Filter dieser Größe (noch einmal: aufheben); die Filterzeile oben stellt dasselbe als Auswahlfelder dar.
// „In der Liste ansehen“ öffnet #vorgaenge mit denselben Filtern (gleiche Parameternamen).
// Jedes Diagramm zählt unter allen Filtern außer seinem eigenen und hebt die gewählte Kategorie hervor.
// Daten: daten/vorgaenge-index.json über index() aus vorgaenge.js (termine, einreicher, thema von einordnung.py).
// Farbe folgt der Kategorie, nie dem Rang: feste Plätze --st-1…6 (geprüfte Palette, Reihenfolge = Ring), Parteien in
// ihren üblichen Farben (--p-…); was keinen Platz hat, ist grau (--st-0) und wird im Ring zu „weitere“ zusammengefasst.
// Höchstens 6 farbige Segmente; die Tabelle daneben nennt jede Kategorie mit Anzahl und Anteil (auch für Screenreader).

import { esc } from "./lanes.js";
import { index, STATUS_WORT, ART, parteienVon } from "./vorgaenge.js";

const zahl = n => n.toLocaleString("de-DE");
const jahreVon = v => new Set(v.daten.map(d => d.slice(0, 4)));
const PARTEI_FARBE = { "Grüne": "gruene", CDU: "cdu", SPD: "spd", FDP: "fdp", BBB: "bbb", Linke: "linke" };
const THEMA_PLATZ = ["Verkehr & Mobilität", "Finanzen, Wirtschaft & Verwaltung", "Kultur, Sport & Freizeit", "Bauen & Stadtplanung", "Umwelt & Klima", "Soziales & Gesundheit"];

// Größen: id = URL-Parameter, wert(v) = Kategorien eines Vorgangs, kategorien() = [[id, name, farbe]] in Ringfolge
const GROESSEN = [
  { id: "status", titel: "Stand", wert: v => [v.status],
    kategorien: () => ["offen", "vertagt", "abgeschlossen", "unklar"].map((s, i) => [s, STATUS_WORT[s], i < 3 ? `var(--st-${i + 1})` : null]) },
  { id: "art", titel: "Art der Einreichung", wert: v => [v.art],
    kategorien: () => ART.map((a, i) => [a.id, a.name, a.id === "sonst" ? null : `var(--st-${i + 1})`]) },
  { id: "partei", titel: "Eingereicht von Fraktionen", mehrfach: true, mitte: "mit Fraktion",
    hinweis: "Gemeinsame Anträge zählen für jede beteiligte Fraktion. Ohne Vorlagen der Verwaltung und Bürgeranträge.",
    wert: parteienVon,
    kategorien: () => {
      const n = {};
      for (const v of IDX) for (const p of parteienVon(v)) n[p] = (n[p] || 0) + 1;
      return Object.keys(n).sort((a, b) => n[b] - n[a]).map(p => [p, p, PARTEI_FARBE[p] ? `var(--p-${PARTEI_FARBE[p]})` : null]);
    } },
  { id: "thema", titel: "Themen",
    hinweis: "Zugeordnet über den beratenden Fachausschuss, sonst über Stichwörter im Titel – eine Näherung.",
    wert: v => [v.thema || "Sonstiges"],
    kategorien: () => {
      const alle = [...new Set(IDX.map(v => v.thema || "Sonstiges"))];
      const rest = alle.filter(t => !THEMA_PLATZ.includes(t)).sort((a, b) => a === "Sonstiges" ? 1 : b === "Sonstiges" ? -1 : a.localeCompare(b));
      return [...THEMA_PLATZ.filter(t => alle.includes(t)).map((t, i) => [t, t, `var(--st-${i + 1})`]), ...rest.map(t => [t, t, null])];
    } },
];

let IDX = null, KAT = null, el = null, f = null;
const LEER = { zeit: "", status: "", art: "", partei: "", thema: "" };

function lies(rest) {
  const p = new URLSearchParams((rest.match(/^\?(.*)$/) || [])[1] || "");
  const g = { ...LEER };
  if (/^\d{4}$/.test(p.get("zeit") || "")) g.zeit = p.get("zeit");
  for (const d of GROESSEN) if (KAT[d.id].some(([id]) => id === p.get(d.id))) g[d.id] = p.get(d.id);
  return g;
}
function hashVon(g) {
  const p = new URLSearchParams();
  for (const k of Object.keys(LEER)) if (g[k]) p.set(k, g[k]);
  const s = p.toString();
  return "#statistik" + (s ? "?" + s : "");
}

function passt(v, g, ohne) {
  if (g.zeit && !jahreVon(v).has(g.zeit)) return false;
  for (const d of GROESSEN) if (d.id !== ohne && g[d.id] && !d.wert(v).includes(g[d.id])) return false;
  return true;
}

// ------------------------------------------------------------------ Ring
const R = 74, r = 46, C = 80;  // Außen-, Innenradius, Mitte (viewBox 160)
const punkt = (rad, w) => [C + rad * Math.sin(w), C - rad * Math.cos(w)];
function segment(a, b) {
  if (b - a >= Math.PI * 2 - 1e-6) b = a + Math.PI * 2 - 1e-4;  // ganzer Ring
  const gross = b - a > Math.PI ? 1 : 0;
  const [x1, y1] = punkt(R, a), [x2, y2] = punkt(R, b), [x3, y3] = punkt(r, b), [x4, y4] = punkt(r, a);
  return `M${x1.toFixed(2)},${y1.toFixed(2)} A${R},${R} 0 ${gross} 1 ${x2.toFixed(2)},${y2.toFixed(2)} L${x3.toFixed(2)},${y3.toFixed(2)} A${r},${r} 0 ${gross} 0 ${x4.toFixed(2)},${y4.toFixed(2)} Z`;
}
const prozent = (n, s) => !s ? "–" : n / s < 0.005 && n ? "<1 %" : `${Math.round(n / s * 100)} %`;

function karte(d) {
  const liste = IDX.filter(v => passt(v, f, d.id));
  const n = {};
  for (const v of liste) for (const k of new Set(d.wert(v))) n[k] = (n[k] || 0) + 1;
  const kats = KAT[d.id].filter(([id]) => n[id]);
  const summe = kats.reduce((s, [id]) => s + n[id], 0);
  const vorgaenge = d.mehrfach ? liste.filter(v => d.wert(v).length).length : liste.length;
  // Ring: farbige Kategorien einzeln, graue zusammen als „weitere“ (eine einzelne graue behält ihren Namen)
  const grau = kats.filter(k => !k[2]);
  const ring = [...kats.filter(k => k[2]).map(([id, name, farbe]) => ({ id, name, farbe, n: n[id] }))];
  if (grau.length) ring.push({ id: grau.length === 1 ? grau[0][0] : null, name: grau.length === 1 ? grau[0][1] : `weitere (${grau.map(k => k[1]).join(", ")})`, farbe: "var(--st-0)", n: grau.reduce((s, [id]) => s + n[id], 0) });
  let w = 0;
  const segs = ring.map(s => {
    const a = w; w += s.n / summe * Math.PI * 2;
    const an = f[d.id] && s.id !== f[d.id] ? " st-aus" : "";
    return `<path class="st-seg${s.id ? "" : " st-sammel"}${an}" d="${segment(a, w)}" style="fill:${s.farbe}" data-g="${d.id}" data-k="${esc(s.id || "")}" data-n="${s.n}" data-name="${esc(s.name)}" data-p="${esc(prozent(s.n, summe))}"/>`;
  }).join("");
  const zeilen = kats.map(([id, name, farbe]) => {
    const an = f[d.id] === id;
    return `<tr${an ? ' class="st-an"' : ""}><th scope="row"><button type="button" data-g="${d.id}" data-k="${esc(id)}" aria-pressed="${an}"><i class="st-farbe" style="background:${farbe || "var(--st-0)"}" aria-hidden="true"></i>${esc(name)}</button></th><td>${zahl(n[id])}</td><td>${prozent(n[id], summe)}</td></tr>`;
  }).join("");
  return `<section class="st-karte" aria-labelledby="st-h-${d.id}">
    <h2 id="st-h-${d.id}">${esc(d.titel)}</h2>
    <div class="st-inhalt">
      <figure class="st-ring">${summe ? `<svg viewBox="0 0 160 160" aria-hidden="true" focusable="false">${segs}</svg>` : `<div class="st-leer-ring"></div>`}
        <figcaption><b>${zahl(vorgaenge)}</b><span>${d.mitte || "Vorgänge"}</span></figcaption></figure>
      ${summe ? `<table class="st-tabelle"><caption class="vh">${esc(d.titel)}: Anzahl und Anteil</caption><thead class="vh"><tr><th scope="col">Kategorie</th><th scope="col">Anzahl</th><th scope="col">Anteil</th></tr></thead><tbody>${zeilen}</tbody></table>` : `<p class="st-leer">Keine Vorgänge für diese Auswahl.</p>`}
    </div>
    ${d.hinweis ? `<p class="st-hinweis">${esc(d.hinweis)}</p>` : ""}
  </section>`;
}

// ------------------------------------------------------------------ Filterzeile
function filterzeile() {
  const jahre = [...new Set(IDX.flatMap(v => [...jahreVon(v)]))].sort().reverse();
  const wahl = (id, label, opts, leer) => `<p class="st-feld"><label for="st-${id}">${label}</label><select id="st-${id}" name="${id}"><option value="">${leer}</option>${opts.map(([v, t]) => `<option value="${esc(v)}"${f[id] === v ? " selected" : ""}>${esc(t)}</option>`).join("")}</select></p>`;
  const aktiv = Object.keys(LEER).some(k => f[k]);
  return wahl("zeit", "Jahr", jahre.map(j => [j, j]), "alle Jahre")
    + GROESSEN.map(d => wahl(d.id, { status: "Stand", art: "Art", partei: "Fraktion", thema: "Thema" }[d.id], KAT[d.id].map(([id, name]) => [id, name]), "alle")).join("")
    + (aktiv ? `<p class="st-feld st-weg"><button type="button" data-alle>Filter zurücksetzen</button></p>` : "");
}

function zeige() {
  const treffer = IDX.filter(v => passt(v, f)).length;
  el.felder.innerHTML = filterzeile();
  el.zahl.textContent = treffer === 1 ? "1 Vorgang" : `${zahl(treffer)} Vorgänge`;
  el.liste.href = "#vorgaenge" + hashVon(f).slice("#statistik".length);
  el.liste.hidden = !treffer;
  el.raster.innerHTML = GROESSEN.map(karte).join("");
}

// ------------------------------------------------------------------ Bedienung
function setze(g) { location.hash = hashVon(g); }
function bediene() {
  el.filter.addEventListener("change", e => { const t = e.target; if (t.name in LEER) setze({ ...f, [t.name]: t.value }); });
  el.filter.addEventListener("click", e => { if (e.target.closest("[data-alle]")) setze({ ...LEER }); });
  el.raster.addEventListener("click", e => {
    const z = e.target.closest("[data-g][data-k]");
    if (!z || !z.dataset.k) return;
    const g = z.dataset.g, k = z.dataset.k;
    setze({ ...f, [g]: f[g] === k ? "" : k });
  });
  // Tooltip am Segment: Wert zuerst, dann Name; Inhalt nur über textContent
  el.raster.addEventListener("pointermove", e => {
    const s = e.target.closest(".st-seg");
    if (!s) { el.tip.hidden = true; return; }
    el.tip.replaceChildren();
    const b = document.createElement("b"); b.textContent = `${zahl(+s.dataset.n)} · ${s.dataset.p}`;
    const t = document.createElement("span"); t.textContent = s.dataset.name;
    el.tip.append(b, t);
    el.tip.hidden = false;
    const x = Math.min(e.clientX + 14, innerWidth - el.tip.offsetWidth - 8);
    el.tip.style.transform = `translate(${x}px, ${e.clientY + 14}px)`;
  });
  el.raster.addEventListener("pointerleave", () => { el.tip.hidden = true; });
}

export async function statistik(rest) {
  IDX ||= await index();
  KAT ||= Object.fromEntries(GROESSEN.map(d => [d.id, d.kategorien()]));
  if (!el) {
    const $ = id => document.getElementById(id);
    el = { filter: $("st-filter"), felder: $("st-felder"), zahl: $("st-zahl"), liste: $("st-liste"), raster: $("st-raster"), tip: $("st-tip") };
    bediene();
  }
  f = lies(rest);
  const soll = hashVon(f);
  if (location.hash !== soll && location.hash !== "#statistik") history.replaceState(null, "", soll);
  zeige();
  return "Statistik";
}
