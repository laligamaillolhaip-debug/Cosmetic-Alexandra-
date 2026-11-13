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

