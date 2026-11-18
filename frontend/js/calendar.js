const profileId = requireProfile();
renderTopbar("calendar.html");
let currentTod = "morning";
let selectedDate = new Date().toLocaleDateString("sv-SE");
let dayData = null;
let dayRequest = 0;
const calendarError = document.getElementById("calendarError");

document.getElementById("todTabs").innerHTML = `
  <button class="seg active" data-tod="morning" aria-pressed="true">${svg("sun", 16)}Утро</button>
  <button class="seg" data-tod="evening" aria-pressed="false">${svg("moon", 16)}Вечер</button>`;
document.querySelectorAll("[data-tod]").forEach(btn => btn.onclick = () => setTod(btn.dataset.tod));

function buildDateStrip() {
  const dow = ["вс", "пн", "вт", "ср", "чт", "пт", "сб"];
  const today = new Date();
  const todayIso = today.toLocaleDateString("sv-SE");
  const cells = [];
  for (let i = -3; i <= 3; i++) {
    const d = new Date(today);
    d.setDate(today.getDate() + i);
    const iso = d.toLocaleDateString("sv-SE");
    const label = d.toLocaleDateString("ru-RU", { weekday: "long", day: "numeric", month: "long" });
    cells.push(`<button class="date-cell ${iso === selectedDate ? "today" : ""} ${iso === todayIso ? "is-current" : ""}" data-date="${iso}" aria-pressed="${iso === selectedDate}" aria-label="${label}"><span class="dow">${dow[d.getDay()]}</span>${d.getDate()}</button>`);
  }
  document.getElementById("dateStrip").innerHTML = cells.join("");
  document.querySelectorAll("[data-date]").forEach(btn => {
    btn.onclick = () => { selectedDate = btn.dataset.date; buildDateStrip(); loadDay(); };
  });
}

function setTod(tod) {
  currentTod = tod;
  document.querySelectorAll("[data-tod]").forEach(btn => {
    const active = btn.dataset.tod === tod;
    btn.classList.toggle("active", active);
    btn.setAttribute("aria-pressed", String(active));
  });
  document.getElementById("blockLabel").textContent = tod === "morning" ? "Утренний уход" : "Вечерний уход";
  renderChecklist();
}

function renderChecklist() {
  const el = document.getElementById("checklist");
  if (!dayData) return;
  const items = dayData.checklist[currentTod];
  const done = items.filter(item => item.done).length;
  const percent = items.length ? Math.round(done / items.length * 100) : 0;
  document.getElementById("progressVal").innerHTML = `${done} <span>/ ${items.length}</span>`;
  document.getElementById("progressFill").style.width = percent + "%";
  document.getElementById("progressMeter").setAttribute("aria-valuenow", percent);
  document.getElementById("progressCaption").textContent = !items.length ? "В этом блоке пока нет средств" : done === items.length ? "Готово. Уход на этот блок завершён." : "Выполнено шагов: " + done + " из " + items.length;
  el.replaceChildren();
  if (!items.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "На это время ничего не запланировано. Добавь средства на странице плана.";
    el.appendChild(empty);
    return;
  }
  items.forEach(({product, done}, index) => {
    const row = document.createElement("div");
    row.className = `calendar-item ${done ? "is-done" : ""}`;
    row.innerHTML = `<span class="calendar-step">${String(index + 1).padStart(2, "0")}</span><div><a class="calendar-product"></a><p class="calendar-brand"></p></div><button class="check ${done ? "done" : ""}" type="button" role="checkbox" aria-checked="${done}">✓</button>`;
    const link = row.querySelector("a");
    link.textContent = product.name;
    link.href = "product.html?id=" + encodeURIComponent(product.id);
    row.querySelector(".calendar-brand").textContent = product.brand;
    const button = row.querySelector("button");
    button.setAttribute("aria-label", product.name + ": отметить выполнение");
    button.onclick = () => toggle(button, product.id, !done);
    el.appendChild(row);
  });
}

async function toggle(button, productId, done) {
  button.disabled = true;
  calendarError.textContent = "";
  try {
    await api(`/api/calendar/${profileId}/toggle`, {
      method: "POST",
      body: JSON.stringify({ date: selectedDate, time_of_day: currentTod, product_id: productId, done }),
    });
    await loadDay();
  } catch (err) {
    calendarError.textContent = "Не удалось сохранить отметку: " + err.message;
    button.disabled = false;
  }
}

async function loadDay() {
  const request = ++dayRequest;
  dayData = null;
  const list = document.getElementById("checklist");
  list.setAttribute("aria-busy", "true");
  list.textContent = "Загружаем средства…";
  calendarError.textContent = "";
  const date = new Date(selectedDate + "T12:00:00");
  const label = date.toLocaleDateString("ru-RU", { day: "numeric", month: "long" });
  document.getElementById("dateTitle").textContent = selectedDate === new Date().toLocaleDateString("sv-SE") ? "Сегодня" : label;
  document.getElementById("dateLabel").textContent = date.toLocaleDateString("ru-RU", { month: "long", year: "numeric" });
  try {
    const data = await api(`/api/calendar/${profileId}?for_date=${selectedDate}`);
    if (request !== dayRequest) return;
    dayData = data;
    renderChecklist();
  } catch (err) {
    if (request !== dayRequest) return;
    list.replaceChildren();
    document.getElementById("progressCaption").textContent = "Не удалось загрузить уход";
    document.getElementById("progressVal").textContent = "—";
    document.getElementById("progressFill").style.width = "0%";
    document.getElementById("progressMeter").setAttribute("aria-valuenow", "0");
    calendarError.textContent = err.message;
  } finally {
    if (request === dayRequest) list.setAttribute("aria-busy", "false");
  }
}
buildDateStrip();
loadDay();
