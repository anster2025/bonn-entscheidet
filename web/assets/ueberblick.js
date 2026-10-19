// „Gesamtüberblick“ im Bereich Verstehen: wie Einwohner:innen, Fraktionen, Rat, Ausschüsse, Bezirksvertretungen,
// Beiräte und Verwaltung zusammenarbeiten. Breit ein Schaubild (SVG, viewBox skaliert mit der Breite) mit
// beschrifteten Pfeilen; jedes Gremium ist ein Knopf und öffnet sein Popover (kurz, Aufgaben, wer, Rechtsgrundlage).
// Schmal (CSS) dieselben Gremien als Karten untereinander. Daten: organe aus daten/verfahren.json.
//   zeigeUeberblick(el, daten)

import { esc } from "./lanes.js";
import { oeffne, schliesse, offenFuer } from "./popover.js";

// Knoten: Organ-Id, Farbklasse, Rechteck im viewBox 1000 × 500, Unterzeile
const KNOTEN = [
  { id: "ew", b: "ew", x: 200, y: 8, w: 600, h: 62, unter: "wählen Rat, Bezirksvertretungen und Oberbürgermeister:in" },
  { id: "fr", b: "rm", x: 20, y: 140, w: 240, h: 72, unter: "bringen Anträge und Anfragen ein" },
  { id: "rat", b: "rat", x: 380, y: 130, w: 240, h: 92, unter: "entscheidet, was er nicht abgibt" },
  { id: "bv", b: "bv", x: 740, y: 140, w: 240, h: 72, unter: "für die vier Stadtbezirke" },
  { id: "beirat", b: "bvm", x: 20, y: 290, w: 240, h: 66, unter: "beraten, entscheiden nicht" },
  { id: "aus", b: "aus", x: 330, y: 290, w: 160, h: 66, unter: "Verkehr, Planen, Umwelt …" },
  { id: "ha", b: "aus", x: 510, y: 290, w: 160, h: 66, unter: "entscheidet Eiliges" },
  { id: "vw", b: "vw", x: 200, y: 428, w: 600, h: 62, unter: "bereitet Vorlagen vor und setzt Beschlüsse um" },
];
// Pfeile: Pfad, Beschriftung (x, y, Ausrichtung), doppelt = Spitze an beiden Enden
const PFEILE = [
  { d: "M500,70 L500,128", t: "wählen", x: 508, y: 104, a: "start" },
  { d: "M740,70 C740,104 860,100 860,138", t: "wählen · fragen · Bürgeranträge", x: 812, y: 94, a: "start" },
  { d: "M260,70 C260,100 140,104 140,138", t: "gründen Fraktionen im Rat", x: 190, y: 94, a: "end" },
  { d: "M262,176 L378,176", t: "Anträge", x: 320, y: 168, a: "middle" },
  { d: "M622,164 L738,164", t: "hört an", x: 680, y: 156, a: "middle" },
  { d: "M738,192 L622,192", t: "empfiehlt", x: 680, y: 210, a: "middle" },
  { d: "M440,222 L440,288", t: "überträgt Aufgaben", x: 432, y: 260, a: "end" },
  { d: "M570,288 L570,222", t: "empfehlen", x: 578, y: 260, a: "start" },
  { d: "M262,323 L328,323", t: "beraten", x: 295, y: 315, a: "middle" },
  { d: "M410,426 L410,358", t: "", x: 0, y: 0, a: "start" },
  { d: "M590,426 L590,358", t: "Vorlagen", x: 500, y: 396, a: "middle" },
  { d: "M790,426 C860,410 860,300 860,214", t: "Vorlagen", x: 868, y: 330, a: "start" },
];

const kopf = (titel, meta) => `<div class="ln-d-kopf"><h2 class="ln-d-titel">${titel}</h2></div><p class="ln-d-meta">${meta}</p>`;
function organHTML(o) {
  const recht = (o.recht || []).filter(r => r.url).map(r => `<a href="${esc(r.url)}">${esc(r.label)}</a>`).join('<span class="ln-trenner" aria-hidden="true"> · </span>');
  return kopf(esc(o.name), esc(o.wer || ""))
    + `<p class="ln-d-satz">${esc(o.kurz)}</p>`
    + `<ul class="ue-macht">${(o.macht || []).map(m => `<li>${esc(m)}</li>`).join("")}</ul>`
    + (recht ? `<p class="ln-d-recht"><span class="vh">Rechtsgrundlage: </span>${recht}</p>` : "");
}

function schaubild(organe) {
  const knoten = KNOTEN.filter(k => organe[k.id]).map(k => {
    const o = organe[k.id], cx = k.x + k.w / 2;
    return `<g class="ue-k b-${k.b}" data-o="${k.id}" tabindex="0" role="button" aria-haspopup="dialog" aria-expanded="false" aria-label="${esc(o.name)}: ${esc(o.kurz)}">
      <rect x="${k.x}" y="${k.y}" width="${k.w}" height="${k.h}" rx="8"/>
      <text class="ue-name" x="${cx}" y="${k.y + k.h / 2 - 4}">${esc(o.name)}</text>
      <text class="ue-unter" x="${cx}" y="${k.y + k.h / 2 + 16}">${esc(k.unter)}</text></g>`;
  }).join("");
  const pfeile = PFEILE.map(p => `<path class="ue-p" d="${p.d}" marker-end="url(#ue-spitze)"/>`
    + (p.t ? `<text class="ue-t" x="${p.x}" y="${p.y}" text-anchor="${p.a}">${esc(p.t)}</text>` : "")).join("");
  return `<svg class="ue-svg" viewBox="0 0 1000 500" role="group" aria-label="Schaubild: wie die Gremien zusammenarbeiten. Jedes Gremium öffnet Einzelheiten.">
    <defs><marker id="ue-spitze" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="8" markerHeight="8" orient="auto"><path class="ue-spitze" d="M0,0.5 L7.5,4 L0,7.5 z"/></marker></defs>
    ${pfeile}${knoten}</svg>`;
}

function karten(organe) {
  return `<ul class="ue-karten">${KNOTEN.filter(k => organe[k.id]).map(k => {
    const o = organe[k.id];
    return `<li class="ue-karte b-${k.b}"><h2>${esc(o.name)}</h2><p>${esc(o.kurz)}</p><ul>${(o.macht || []).map(m => `<li>${esc(m)}</li>`).join("")}</ul></li>`;
  }).join("")}</ul>`;
}

export function zeigeUeberblick(el, daten) {
  const organe = Object.fromEntries(daten.organe.map(o => [o.id, o]));
  if (!el.childElementCount) {
    el.innerHTML = schaubild(organe) + karten(organe);
    const auf = g => offenFuer(g) ? schliesse(false) : oeffne(g, organHTML(organe[g.dataset.o]));
    el.addEventListener("click", e => { const g = e.target.closest(".ue-k"); if (g) auf(g); });
    el.addEventListener("keydown", e => {
      const g = e.target.closest(".ue-k");
      if (g && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); auf(g); }
    });
  }
}
