const profileId = requireProfile();
renderTopbar("profile.html");
document.getElementById("logoutAccount").onclick = () => Auth.logout();

function escapeProfileText(value) {
  const el = document.createElement("span");
  el.textContent = String(value ?? "");
  return el.innerHTML;
}

function renderProfile(p) {
  const root = document.getElementById("profileContent");
  root.classList.remove("loading");
  document.getElementById("heroBudget").textContent = Number(p.budget_month).toLocaleString("ru-RU");
  const skin = p.skin_types.map(s => `<span class="skin-type">${escapeProfileText(SKIN_TYPE_LABELS[s] || s)}</span>`).join("");
  const concerns = p.concerns.length
    ? p.concerns.map((c, i) => `<li><span>${String(i + 1).padStart(2, "0")}</span><span>${escapeProfileText(CONCERN_LABELS[c] || c)}</span></li>`).join("")
    : `<li><span>—</span><span>Особые потребности не отмечены</span></li>`;
  root.innerHTML = `
    <div class="profile-layout">
      <section aria-labelledby="skinHeading">
        <h2 class="section-heading" id="skinHeading"><span>Кожа и потребности</span><span class="section-index">01</span></h2>
        <p class="skin-heading">У каждого ухода<br>своя отправная точка.</p>
        <div class="skin-types">${skin}</div>
        <span class="profile-label concerns-label">На что обращаем внимание</span>
        <ul class="concern-list">${concerns}</ul>
        <p class="profile-note">Подбор опирается на твои ответы. Если ощущения или потребности изменились, обнови профиль.</p>
        <button type="button" class="profile-action primary-action" id="redoQuiz"><span>Обновить ответы опросника</span><span aria-hidden="true">↗</span></button>
        <button type="button" class="profile-action" id="editBudget"><span>Изменить бюджет</span><span aria-hidden="true">↗</span></button>
      </section>
      <section aria-labelledby="routineHeading">
        <h2 class="section-heading" id="routineHeading"><span>Ежедневный уход</span><span class="section-index">02</span></h2>
        <div class="routine-card">
          <p class="routine-caption">Утро / Вечер</p>
          <h3>Небольшие шаги.<br>Твой привычный ритм.</h3>
          <p>Средства и порядок нанесения уже в плане. Отмечай выполненный уход в календаре.</p>
          <a class="profile-action" href="plan.html"><span>Открыть мой план</span><span aria-hidden="true">↗</span></a>
        </div>
        <a class="routine-link" href="calendar.html"><span>Календарь ухода</span><span aria-hidden="true">↗</span></a>
        <a class="routine-link" href="catalog.html"><span>Найти средство в каталоге</span><span aria-hidden="true">↗</span></a>
        <p class="profile-note">При обновлении ответов план пересоберётся. Избранное, переписка и отметки в календаре сохранятся.</p>
      </section>
    </div>
    ${p.is_owner ? renderOwnerPanel(p) : ""}`;

  document.getElementById("redoQuiz").onclick = () => {
    Store.setQuiz({ skin_types: [...p.skin_types], concerns: [...p.concerns] });
    window.location.href = "quiz.html?edit=1";
  };
  document.getElementById("editBudget").onclick = () => {
    Store.setQuiz({ skin_types: [...p.skin_types], concerns: [...p.concerns] });
    window.location.href = "budget.html?edit=1";
  };
  if (p.is_owner) {
    document.getElementById("ownerEmail").textContent = p.account_email;
    document.getElementById("analysisText").textContent = p.analysis || "Разбор появится после первого успешного анализа на странице плана.";
    document.getElementById("restartQuiz").onclick = () => {
      if (!confirm("Открыть опросник без предварительно заполненных ответов? Текущие данные изменятся только после его завершения.")) return;
      localStorage.removeItem("yadro_quiz");
      window.location.href = "quiz.html";
    };
    let statusLoaded = false;
    document.getElementById("ownerPanel").addEventListener("toggle", event => {
      if (event.target.open && !statusLoaded) {
        statusLoaded = true;
        loadOwnerStatus();
      }
    });
  }
}

function renderOwnerPanel(p) {
  return `<details class="owner-panel" id="ownerPanel">
    <summary><span class="owner-badge">Только тебе</span><span>Статистика и состояние сервиса</span></summary>
    <div class="owner-body">
      <div class="owner-stats">
        <div class="owner-stat"><b>${Number(p.stats.plan_items)}</b><span>средств в плане</span></div>
        <div class="owner-stat"><b>${Number(p.stats.favorites)}</b><span>в избранном</span></div>
        <div class="owner-stat"><b>${Number(p.stats.done_steps)}</b><span>шагов выполнено</span></div>
      </div>
      <div class="owner-meta">
        <div><span class="profile-label">Аккаунт</span><p id="ownerEmail"></p></div>
        <div><span class="profile-label">Нейросеть</span><div id="aiStatus" class="ai-status"><span class="led"></span>Проверяем связь…</div></div>
      </div>
      <div class="owner-analysis-block"><span class="profile-label">Разбор кожи от ИИ</span><p class="owner-analysis" id="analysisText"></p></div>
      <button type="button" class="owner-reset" id="restartQuiz">Пройти опрос с начала</button>
    </div>
  </details>`;
}

async function loadOwnerStatus() {
  const el = document.getElementById("aiStatus");
  try {
    const status = await api("/api/meta/ai-status");
    el.classList.add(status.ok ? "online" : "offline");
    el.replaceChildren();
    const led = document.createElement("span");
    led.className = "led";
    const label = document.createElement("span");
    label.textContent = `${status.ok ? "Подключена" : "Нет связи"} · ${status.model}`;
    el.append(led, label);
    el.title = status.detail || "";
  } catch {
    el.textContent = "Не удалось проверить связь";
    el.classList.add("offline");
  }
}

api(`/api/profile/${profileId}`).then(renderProfile).catch(err => {
  const root = document.getElementById("profileContent");
  root.classList.remove("loading");
  root.textContent = err.message;
  root.classList.add("error-text");
});