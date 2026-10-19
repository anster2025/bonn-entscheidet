// Router der Bürgerseite „Bonn entscheidet“: je Hash-Route eine Ansicht (section[data-ansicht] in index.html).
//   #start (Standard), #daten            Startseite; #daten springt zu „Wo kommen die Daten her?“
//   #verstehen[/<verfahren>]             ein Ablauf aus daten/verfahren.json als Swimlane (lanes.js);
//                                        ohne Angabe oder /ueberblick: Gesamtüberblick der Gremien (ueberblick.js)
//   #vorgaenge[?filter][/<nr>]           Vorgänge in Bonn: Filter + Liste, ein Vorgang (vorgaenge.js)
//   #statistik[?filter]                  Anteile der Vorgänge als Ringdiagramme (statistik.js)
// Alte Routen leiten weiter (replaceState): #verfolgen… → #vorgaenge…, #vorgang/<nr> → #vorgaenge/<nr>,
// #verstehen?… → #verstehen. Menüknopf (auch Start) mit aria-current, document.title je Route, Fokus auf die h1 bei Ansichtswechsel.

import { zeigeVerfahren, esc } from "./lanes.js";
import { schliesse } from "./popover.js";
import { vorgaenge } from "./vorgaenge.js";
import { statistik } from "./statistik.js";
import { zeigeUeberblick } from "./ueberblick.js";

const SEITE = "Bonn entscheidet";
const UEBERBLICK = "ueberblick";
const UEBERBLICK_KURZ = "So arbeiten Einwohner:innen, Fraktionen, Rat, Ausschüsse, Bezirksvertretungen und Verwaltung zusammen. Ein Klick auf ein Gremium zeigt, was es darf.";
const lade = url => fetch(url).then(r => { if (!r.ok) throw new Error(`${url}: ${r.status}`); return r.json(); });
let datenP = null;
const daten = () => datenP ||= lade("daten/verfahren.json");

function umleiten(h) {
  let m;
  if ((m = h.match(/^#verfolgen(.*)$/))) return "#vorgaenge" + m[1];
  if ((m = h.match(/^#vorgang\/(\w+)/))) return "#vorgaenge/" + m[1];
  if (/^#verstehen\?/.test(h)) return "#verstehen";
  return h;
}

// ------------------------------------------------------------------ Ansichten: liefern den Seitentitel
const ANSICHTEN = {
  start: async () => null,
  daten: async () => null,
  verstehen,
  vorgaenge: rest => vorgaenge(rest, daten),
  statistik,
};
const BEREICH = { start: "start", daten: "start", verstehen: "verstehen", vorgaenge: "vorgaenge", statistik: "statistik" };

const wahl = document.getElementById("wahl-verfahren");
const lnVerfahren = document.getElementById("ln-verfahren");
const ueberblick = document.getElementById("ueberblick");
let gezeigt = null;

async function verstehen(rest) {
  const d = await daten();
  if (!wahl.options.length) {
    const gruppen = new Map();
    for (const v of d.verfahren) {
      if (!gruppen.has(v.gruppe)) gruppen.set(v.gruppe, []);
      gruppen.get(v.gruppe).push(v);
    }
    wahl.innerHTML = `<option value="${UEBERBLICK}">Gesamtüberblick</option>` + [...gruppen].map(([g, vs]) => `<optgroup label="${esc(g)}">${vs.map(v => `<option value="${esc(v.id)}">${esc(v.titel)}</option>`).join("")}</optgroup>`).join("");
    wahl.addEventListener("change", () => { location.hash = "#verstehen/" + wahl.value; });
  }
  const id = rest.replace(/^\//, "");
  const v = d.verfahren.find(x => x.id === id);
  if (id && id !== UEBERBLICK && !v) history.replaceState(null, "", "#verstehen");
  lnVerfahren.hidden = !v;
  ueberblick.hidden = !!v;
  if (!v) {
    wahl.value = UEBERBLICK;
    document.getElementById("verfahren-kurz").textContent = UEBERBLICK_KURZ;
    zeigeUeberblick(ueberblick, d);
    return "Gesamtüberblick · Politische Prozesse verstehen";
  }
  wahl.value = v.id;
  document.getElementById("verfahren-kurz").textContent = v.kurz;
  if (gezeigt !== v.id || !lnVerfahren.childElementCount) zeigeVerfahren(lnVerfahren, v, d);
  gezeigt = v.id;
  return `${v.titel} · Politische Prozesse verstehen`;
}

// ------------------------------------------------------------------ Router
const ansichten = [...document.querySelectorAll("[data-ansicht]")];
const menue = [...document.querySelectorAll(".menue a[data-bereich]")];
const fuss = document.querySelector(".fuss");
let lauf = 0, vorher = null;

async function route() {
  let h = location.hash || "#start";
  const neu = umleiten(h);
  if (neu !== h) { history.replaceState(null, "", neu); h = neu; }
  const m = h.match(/^#([a-z]+)(.*)$/);
  let teil = m && ANSICHTEN[m[1]] ? m[1] : null;
  if (!teil) { history.replaceState(null, "", "#start"); teil = "start"; }
  const rest = m && teil === m[1] ? m[2] : "";
  const bereich = BEREICH[teil], nr = ++lauf;

  schliesse(false);
  ansichten.forEach(s => { s.hidden = s.dataset.ansicht !== bereich; });
  fuss.hidden = bereich === "start";
  menue.forEach(a => a.dataset.bereich === bereich ? a.setAttribute("aria-current", "page") : a.removeAttribute("aria-current"));

  let titel;
  try {
    titel = await ANSICHTEN[teil](rest);
  } catch (e) {
    console.error(e);
    const s = ansichten.find(x => x.dataset.ansicht === bereich);
    s.querySelector(".fehler")?.remove();
    s.insertAdjacentHTML("beforeend", `<p class="fehler">Die Daten konnten nicht geladen werden. Bitte lade die Seite neu.</p>`);
  }
  if (nr !== lauf) return;
  document.title = titel ? `${titel} · ${SEITE}` : SEITE;

  if (teil === "daten") {
    const z = document.getElementById("h-daten");
    z.focus({ preventScroll: true });
    z.scrollIntoView({ block: "start" });
  } else if (vorher !== null && vorher !== bereich) {
    document.getElementById(`h-${bereich}`).focus({ preventScroll: true });
    document.getElementById("inhalt").scrollTo(0, 0);  // nur der Inhalt scrollt, der Kopf steht
  }
  vorher = bereich;
  document.documentElement.dataset.bereit = "1";
}

// Sprunglink: Fokus auf den Inhalt, ohne den Hash (und damit die Route) zu ändern
document.querySelector("[data-sprung]").addEventListener("click", e => {
  e.preventDefault();
  document.getElementById("inhalt").focus();
});

addEventListener("hashchange", route);
route();
