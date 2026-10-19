// Popover am Klickpunkt für „Bonn entscheidet“: ein gemeinsames Element mit nativem popover="manual",
// per JS neben dem Auslöser platziert (rechts, sonst links, sonst unter/über ihm, immer im Viewport).
// Unter 640 px erscheint es als Bottom-Sheet. Escape und Klick daneben schließen (kein eigener Schließen-Knopf);
// bei Escape geht der Fokus an den Auslöser zurück. Der Auslöser trägt aria-expanded/aria-controls.
//   oeffne(ausloeser, html)  zeigt html am Auslöser; ein Titel (h2–h4) im html benennt den Dialog
//   schliesse(fokus)         schließt; fokus = true setzt den Fokus zurück auf den Auslöser
//   offenFuer(el)            true, wenn das Popover gerade zu el gehört

const ID = "pop";
const ABSTAND = 8, RAND = 8;
const schmal = matchMedia("(max-width: 639.98px)");
let pop = null, ausloeser = null;

function element() {
  if (pop) return pop;
  pop = document.createElement("div");
  pop.id = ID;
  pop.className = "pop";
  pop.setAttribute("popover", "manual");
  pop.setAttribute("role", "dialog");
  pop.tabIndex = -1;
  document.body.append(pop);
  document.addEventListener("keydown", e => {
    if (e.key === "Escape" && offen()) { e.preventDefault(); e.stopPropagation(); schliesse(true); }
  }, true);
  document.addEventListener("pointerdown", e => {
    if (offen() && !pop.contains(e.target) && !(ausloeser && ausloeser.contains(e.target))) schliesse(false);
  }, true);
  addEventListener("resize", () => offen() && platziere());
  addEventListener("scroll", () => offen() && platziere(), { passive: true, capture: true });
  schmal.addEventListener("change", () => offen() && platziere());
  return pop;
}

export const offen = () => !!pop && pop.matches(":popover-open");
export const offenFuer = el => offen() && ausloeser === el;

export function oeffne(el, html) {
  const p = element();
  if (ausloeser && ausloeser !== el) ausloeser.setAttribute("aria-expanded", "false");
  p.innerHTML = html;
  const titel = p.querySelector("h2, h3, h4");
  if (titel) { titel.id ||= `${ID}-titel`; p.setAttribute("aria-labelledby", titel.id); p.removeAttribute("aria-label"); }
  else { p.removeAttribute("aria-labelledby"); p.setAttribute("aria-label", "Einzelheiten"); }
  ausloeser = el;
  el.setAttribute("aria-controls", ID);
  el.setAttribute("aria-expanded", "true");
  if (!offen()) p.showPopover();
  p.scrollTop = 0;
  platziere();
  p.focus({ preventScroll: true });
}

export function schliesse(fokus) {
  if (!pop) return;
  if (offen()) pop.hidePopover();
  const el = ausloeser;
  ausloeser = null;
  if (!el) return;
  el.setAttribute("aria-expanded", "false");
  if (fokus && el.isConnected) el.focus({ preventScroll: true });
}

const klemme = (x, min, max) => Math.max(min, Math.min(x, max));

function platziere() {
  const p = pop;
  if (!ausloeser || !ausloeser.isConnected) { schliesse(false); return; }
  if (schmal.matches) {
    p.classList.add("pop-sheet");
    p.style.left = p.style.top = "";
    return;
  }
  p.classList.remove("pop-sheet");
  const r = ausloeser.getBoundingClientRect();
  const vw = document.documentElement.clientWidth, vh = document.documentElement.clientHeight;
  const w = p.offsetWidth, h = p.offsetHeight;
  let left, top = null;
  if (r.right + ABSTAND + w <= vw - RAND) left = r.right + ABSTAND;          // rechts daneben
  else if (r.left - ABSTAND - w >= RAND) left = r.left - ABSTAND - w;        // links daneben
  else {                                                                     // darunter, sonst darüber
    left = klemme(r.left, RAND, vw - w - RAND);
    top = r.bottom + ABSTAND + h <= vh - RAND ? r.bottom + ABSTAND : r.top - ABSTAND - h;
  }
  if (top == null) top = r.top;
  p.style.left = `${Math.round(left)}px`;
  p.style.top = `${Math.round(klemme(top, RAND, Math.max(RAND, vh - h - RAND)))}px`;
}
