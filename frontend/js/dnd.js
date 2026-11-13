/**
 * Перетаскивание на pointer-событиях: работает и мышью, и пальцем
 * (нативный HTML5 drag-and-drop на телефонах не работает).
 *
 * Разметка:
 *   [data-draggable="plan"|"fav"]  — что тащим
 *   [data-drag-handle]              — за что тащим (внутри элемента)
 *   [data-drop-list][data-tod]      — куда можно бросить
 *
 * Обработчики назначаются снаружи: DnD.onReorder / DnD.onAddToPlan.
 */
const DnD = {
  onReorder: null,     // (timeOfDay, itemIds[]) => void
  onAddToPlan: null,   // (productId, timeOfDay) => void
  _drag: null,
  THRESHOLD: 6,
};

(function () {
  function cleanup() {
    const d = DnD._drag;
    if (!d) return;
    d.ghost?.remove();
    d.source.classList.remove("dragging-source");
    document.querySelectorAll(".drop-zone-active").forEach(el => el.classList.remove("drop-zone-active"));
    document.body.style.userSelect = "";
    DnD._drag = null;
  }

  function makeGhost(source, width) {
    const ghost = source.cloneNode(true);
    ghost.classList.add("drag-ghost");
    ghost.style.width = width + "px";
    ghost.style.margin = "0";
    document.body.appendChild(ghost);
    return ghost;
  }

  document.addEventListener("pointerdown", (e) => {
    const handle = e.target.closest("[data-drag-handle]");
    if (!handle) return;
    const source = handle.closest("[data-draggable]");
    if (!source) return;

    const rect = source.getBoundingClientRect();
    DnD._drag = {
      source,
      handle,
      type: source.dataset.draggable,
      startX: e.clientX, startY: e.clientY,
      offsetX: e.clientX - rect.left,
      offsetY: e.clientY - rect.top,
      width: rect.width,
      started: false,
      ghost: null,
    };
    handle.setPointerCapture(e.pointerId);
  });

  document.addEventListener("pointermove", (e) => {
    const d = DnD._drag;
    if (!d) return;

    if (!d.started) {
      const dist = Math.hypot(e.clientX - d.startX, e.clientY - d.startY);
      if (dist < DnD.THRESHOLD) return;
      d.started = true;
      d.ghost = makeGhost(d.source, d.width);
      d.source.classList.add("dragging-source");
      document.body.style.userSelect = "none";
    }

    d.ghost.style.left = (e.clientX - d.offsetX) + "px";
    d.ghost.style.top = (e.clientY - d.offsetY) + "px";

    if (d.type === "plan") {
      // живая перестановка внутри своего списка
      const list = d.source.closest("[data-drop-list]");
      if (!list) return;
      const siblings = [...list.querySelectorAll('[data-draggable="plan"]')].filter(el => el !== d.source);
      let placed = false;
      for (const sib of siblings) {
        const r = sib.getBoundingClientRect();
        if (e.clientY < r.top + r.height / 2) {
          list.insertBefore(d.source, sib);
          placed = true;
          break;
        }
      }
      if (!placed) list.appendChild(d.source);
    } else if (d.type === "fav") {
      // подсветка колонки плана, над которой держим
      const under = document.elementFromPoint(e.clientX, e.clientY);
      const zone = under?.closest("[data-drop-list]");
      document.querySelectorAll(".drop-zone-active").forEach(el => {
        if (el !== zone) el.classList.remove("drop-zone-active");
      });
      if (zone) zone.classList.add("drop-zone-active");
      d.dropZone = zone || null;
    }
  });

})();
