    const profileId = requireProfile();
    let currentTod = "morning";
    let planData = null;
    let favData = [];

    renderTopbar("plan.html");

    document.getElementById("favTitle").innerHTML = svg("heart", 18) + "Избранное";

    document.getElementById("todTabs").innerHTML = `
      <button class="seg active" data-tod="morning">${svg("sun", 16)}Утро</button>
      <button class="seg" data-tod="evening">${svg("moon", 16)}Вечер</button>`;
    document.querySelectorAll(".seg").forEach(btn => btn.onclick = () => setTod(btn.dataset.tod));

    function setTod(tod) {
      currentTod = tod;
      document.querySelectorAll(".seg").forEach(s => s.classList.toggle("active", s.dataset.tod === tod));
      renderPlan();
    }

    function renderPlan() {
      const body = document.getElementById("planBody");
      if (!planData) return;
      body.innerHTML = `<div class="routine-columns">${["morning", "evening"].map(tod => {
        const items = planData.plan[tod];
        const morning = tod === "morning";
        return `<section class="routine ${tod === currentTod ? "is-selected" : ""}">
          <header class="routine-heading"><div><span class="editorial-label">${morning ? "01 / Начало дня" : "02 / Завершение дня"}</span><h2>${morning ? "Утро" : "Вечер"}<span aria-hidden="true">${svg(morning ? "sun" : "moon", 24)}</span></h2></div><span class="routine-count">${items.length} шаг.</span></header>
          <div class="plan-column" data-drop-list data-tod="${tod}">${items.length ? items.map((item, i) => planItemHtml(item, i + 1)).join("") : '<div class="empty-state">Пока нет средств. Добавь из каталога или подбери с ИИ.</div>'}</div>
        </section>`;
      }).join("")}</div>`;
      body.querySelectorAll("[data-remove-item]").forEach(btn => {
        btn.onclick = async (e) => {
          e.preventDefault(); e.stopPropagation();
          try {
            await api(`/api/plan/${profileId}/items/${btn.dataset.removeItem}`, { method: "DELETE" });
            await loadPlan();
          } catch(err) { setPlannerMessage(err.message, true); }
        };
      });
    }

    function planItemHtml(item, num) {
      const p = item.product;
      return `
        <div class="plan-item" data-draggable="plan" data-item-id="${item.item_id}">
          <span class="drag-handle" data-drag-handle title="Перетащить">${svg("grip", 17)}</span>
          <span class="step-num">${num}</span>
          <div class="thumb sm">${svg(p.icon, 24)}</div>
          <div class="product-info">
            <a class="product-name" href="product.html?id=${p.id}">${escapePlanText(p.name)}</a>
            <div class="product-brand">${escapePlanText(p.brand)} · ${escapePlanText(item.category_label)}</div>
            <div class="plan-reason">${escapePlanText(item.reason)}</div>
          </div>
          <div class="plan-actions">
            ${priceHtml(item.price)}
            <button class="mini-btn" data-remove-item="${item.item_id}" title="Убрать из плана">${svg("close", 15)}</button>
          </div>
        </div>`;
    }

    function renderFavorites() {
      const list = document.getElementById("favList");
      document.getElementById("favCount").textContent = favData.length ? `${favData.length} шт.` : "";
      if (!favData.length) {
        list.innerHTML = `<div class="fav-empty">Пока ничего не добавлено.<br>Жми на сердечко в каталоге — средства появятся здесь.</div>`;
        return;
      }
      list.innerHTML = favData.map(({ product, price }) => `
        <div class="fav-item" data-draggable="fav" data-product-id="${product.id}">
          <span class="drag-handle" data-drag-handle title="Перетащить в план">${svg("grip", 16)}</span>
          <div class="thumb sm" style="width:40px;height:40px;">${svg(product.icon, 20)}</div>
          <div style="flex:1; min-width:0;">
            <div class="fav-name">${product.name}</div>
            <div class="fav-price">${price ? fmtPrice(price.price) : "—"}</div>
          </div>
          <button class="mini-btn add" data-add="${product.id}" title="Добавить в план">${svg("plus", 15)}</button>
        </div>`).join("");

      list.querySelectorAll("[data-add]").forEach(btn => {
        btn.onclick = () => addToPlan(btn.dataset.add, currentTod);
      });
    }

    async function addToPlan(productId, tod) {
      await api(`/api/plan/${profileId}/items`, {
        method: "POST",
        body: JSON.stringify({ product_id: productId, time_of_day: tod }),
      });
      await loadPlan();
    }

    DnD.onAddToPlan = (productId, tod) => addToPlan(productId, tod);
    DnD.onReorder = async (tod, itemIds) => {
      await api(`/api/plan/${profileId}/reorder`, {
        method: "POST",
        body: JSON.stringify({ time_of_day: tod, item_ids: itemIds }),
      });
      const byId = new Map(planData.plan[tod].map(i => [i.item_id, i]));
      planData.plan[tod] = itemIds.map(id => byId.get(id)).filter(Boolean);
      await loadPlan();
    };

    async function loadPlan() {
      planData = await api(`/api/plan/${profileId}`);
      const { spent, budget } = planData;
      document.getElementById("spentVal").textContent = fmtPrice(spent);
      document.getElementById("budgetOf").textContent = `из ${fmtPrice(budget)}`;
      document.getElementById("budgetMeter").style.width = Math.min(100, (spent / budget) * 100) + "%";
      const left = budget - spent;
      document.getElementById("budgetLeft").textContent =
        left >= 0 ? `осталось ${fmtPrice(left)}` : `перерасход ${fmtPrice(-left)}`;
      document.getElementById("budgetLeft").style.color = left >= 0 ? "var(--success)" : "var(--warning)";
      Store.setBudget(budget);
      const source = planData.profile.plan_source;
      document.getElementById("planOrigin").textContent = source === "ai" ? "Подобрано с ИИ" : source === "edited" ? "С твоими изменениями" : "Базовый подбор";
      document.getElementById("planSummary").textContent = planData.profile.plan_summary || "Два блока на каждый день. Меняй порядок и добавляй подходящие средства из избранного.";
      renderPlan();
    }

    async function loadFavorites() {
      const data = await api(`/api/favorites/${profileId}`);
      favData = data.items;
      Favorites.ids = new Set(data.ids);
      renderFavorites();
    }

    loadPlan().then(loadPendingDraft).catch(err => {
      document.getElementById("planBody").innerHTML = `<p class="error-text">${err.message}</p>`;
    });
    loadFavorites();


function escapePlanText(value) {
  const node = document.createElement("span"); node.textContent = String(value ?? ""); return node.innerHTML;
}
let draft = null;
function setPlannerMessage(message, error = false) {
  const node = document.getElementById("plannerStatus");
  node.textContent = message; node.classList.toggle("error-text", error);
}
document.getElementById("generatePlan").onclick = async () => {
  const button = document.getElementById("generatePlan");
  button.disabled = true;
  draft = null;
  document.getElementById("aiDraft").hidden = true;
  const stop = showThinking(document.getElementById("plannerStatus"), "ИИ выбирает средства на утро и вечер");
  try {
    draft = await api(`/api/plan/${profileId}/ai-draft`, {method:"POST"});
    stop(); setPlannerMessage("Предложение готово. Посмотри оба блока перед применением.");
    showDraft(draft);
  } catch(err) { stop(); setPlannerMessage(err.message, true); }
  finally { button.disabled = false; }
};
document.getElementById("applyDraft").onclick = async () => {
  if (!draft) return;
  const button = document.getElementById("applyDraft"); button.disabled = true;
  try {
    await api(`/api/plan/${profileId}/ai-draft/${draft.draft_id}/apply`, {method:"POST"});
    draft = null; document.getElementById("aiDraft").hidden = true;
    await loadPlan(); setPlannerMessage("Новый уход сохранён. Календарь уже использует этот план.");
  } catch(err) { setPlannerMessage(err.message, true); }
  finally { button.disabled = false; }
};
document.getElementById("dismissDraft").onclick = async () => {
  if (!draft) return;
  const button = document.getElementById("dismissDraft"); button.disabled = true;
  try {
    await api(`/api/plan/${profileId}/ai-draft/${draft.draft_id}`, {method:"DELETE"});
    draft = null; document.getElementById("aiDraft").hidden = true;
    setPlannerMessage("Сохранённый план остался без изменений.");
  } catch(err) { setPlannerMessage(err.message, true); }
  finally { button.disabled = false; }
};

function showDraft(result) {
  draft = result;
    document.getElementById("draftSummary").textContent = draft.summary;
    document.getElementById("draftPrice").textContent = `${fmtPrice(draft.spent)} / бюджет ${fmtPrice(draft.budget)}`;
    document.getElementById("draftRoutines").innerHTML = ["morning", "evening"].map(tod => `<section><h3>${tod === "morning" ? "Утро" : "Вечер"}</h3><ol>${draft.plan[tod].map(item => `<li><span>${escapePlanText(item.product.name)}</span><small>${escapePlanText(item.reason)}</small></li>`).join("")}</ol></section>`).join("");
    document.getElementById("aiDraft").hidden = false;
}
async function loadPendingDraft() {
  try {
    const response = await api(`/api/plan/${profileId}/ai-draft`);
    if (response.draft) {
      showDraft(response.draft);
      setPlannerMessage("Предложение готово. Посмотри оба блока перед применением.");
    }
  } catch { /* текущий сохранённый план доступен и без черновика */ }
}
