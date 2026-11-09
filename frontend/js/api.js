const API_BASE = "";

const Store = {
  getProfileId() { return localStorage.getItem("yadro_profile_id"); },
  setProfileId(id) { localStorage.setItem("yadro_profile_id", id); },
  getBudget() { return Number(localStorage.getItem("yadro_budget") || 0); },
  setBudget(v) { localStorage.setItem("yadro_budget", v); },
  getEmail() { return localStorage.getItem("yadro_email"); },
  setEmail(v) { localStorage.setItem("yadro_email", v); },
  clear() {
    ["yadro_profile_id", "yadro_budget", "yadro_quiz", "yadro_email"]
      .forEach(k => localStorage.removeItem(k));
  },
  getQuiz() {
    try { return JSON.parse(localStorage.getItem("yadro_quiz") || "null"); }
    catch { return null; }
  },
  setQuiz(v) { localStorage.setItem("yadro_quiz", JSON.stringify(v)); },
};

async function api(path, opts = {}, { noRedirect = false } = {}) {
  const res = await fetch(API_BASE + path, {
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",   // кука сессии уходит вместе с запросом
    ...opts,
  });
  if (!res.ok) {
    // 401 — не вошёл или сессия истекла, 403 — чужой профиль
    if ((res.status === 401 || res.status === 403) && !noRedirect) {
      Store.clear();
      window.location.href = "login.html";
      throw new Error("Нужно войти в аккаунт");
    }
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch {}
    throw new Error(detail);
  }
  return res.json();
}

function requireProfile() {
  const id = Store.getProfileId();
  if (!id) {
    window.location.href = "login.html";
    throw new Error("no profile");
  }
  return id;
}

/* ---------- иконки ---------- */
const ICONS = {
  cleanser: '<path d="M9.5 3h5M10.5 3v3.5L7 12.5V19a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2v-6.5L13.5 6.5V3"/><path d="M8 15h8"/>',
  moisturizer: '<rect x="6" y="8" width="12" height="13" rx="3"/><path d="M9 8V5.5A1.5 1.5 0 0 1 10.5 4h3A1.5 1.5 0 0 1 15 5.5V8"/><path d="M10 14h4"/>',
  spf: '<circle cx="12" cy="12" r="4"/><path d="M12 2.5v2.2M12 19.3v2.2M2.5 12h2.2M19.3 12h2.2M5.2 5.2l1.6 1.6M17.2 17.2l1.6 1.6M5.2 18.8l1.6-1.6M17.2 6.8l1.6-1.6"/>',
  serum: '<path d="M10 2.5h4M11 2.5v4.2l-2.6 2.6A3 3 0 0 0 7.5 11.5V19a2.5 2.5 0 0 0 2.5 2.5h4a2.5 2.5 0 0 0 2.5-2.5v-7.5a3 3 0 0 0-.9-2.2L13 6.7V2.5"/><circle cx="12" cy="15" r="1.4"/>',
  home: '<path d="M3 11.5 12 4l9 7.5"/><path d="M5.5 10.5V19a1.5 1.5 0 0 0 1.5 1.5h10a1.5 1.5 0 0 0 1.5-1.5v-8.5"/>',
  plan: '<path d="M8 3.5h8M9.5 3.5v3M14.5 3.5v3"/><rect x="4" y="6.5" width="16" height="14" rx="4"/><path d="M9 12.5l2 2 4-4"/>',
  catalog: '<rect x="3.5" y="3.5" width="7" height="7" rx="2.2"/><rect x="13.5" y="3.5" width="7" height="7" rx="2.2"/><rect x="3.5" y="13.5" width="7" height="7" rx="2.2"/><rect x="13.5" y="13.5" width="7" height="7" rx="2.2"/>',
  calendar: '<rect x="3.5" y="5" width="17" height="16" rx="4"/><path d="M8 3v4M16 3v4M3.5 10.5h17"/><circle cx="8.5" cy="15" r="1"/><circle cx="12" cy="15" r="1"/><circle cx="15.5" cy="15" r="1"/>',
  chat: '<path d="M20.5 12c0 4.4-3.8 8-8.5 8-1.3 0-2.6-.3-3.7-.8L3.5 20.5l1.4-4.4A7.7 7.7 0 0 1 3.5 12c0-4.4 3.8-8 8.5-8s8.5 3.6 8.5 8z"/>',
  heart: '<path d="M12 20.5s-7.5-4.9-7.5-10a4.3 4.3 0 0 1 7.5-2.8 4.3 4.3 0 0 1 7.5 2.8c0 5.1-7.5 10-7.5 10z"/>',
  sparkle: '<path d="M12 3l1.9 5.3L19 10l-5.1 1.7L12 17l-1.9-5.3L5 10l5.1-1.7L12 3z"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6l1.4 1.4M17 17l1.4 1.4M5.6 18.4L7 17M17 7l1.4-1.4"/>',
  moon: '<path d="M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5z"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="M20.5 20.5L16.5 16.5"/>',
  back: '<path d="M15 5l-7 7 7 7"/>',
  grip: '<circle cx="9" cy="6" r="1.3"/><circle cx="15" cy="6" r="1.3"/><circle cx="9" cy="12" r="1.3"/><circle cx="15" cy="12" r="1.3"/><circle cx="9" cy="18" r="1.3"/><circle cx="15" cy="18" r="1.3"/>',
  close: '<path d="M6 6l12 12M18 6L6 18"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  send: '<path d="M4 12l16-8-6 16-2.5-6.5L4 12z"/>',
  logout: '<path d="M14.5 5.5V4A1.5 1.5 0 0 0 13 2.5H6A1.5 1.5 0 0 0 4.5 4v16A1.5 1.5 0 0 0 6 21.5h7a1.5 1.5 0 0 0 1.5-1.5v-1.5"/><path d="M19.5 12H10M16 8.5l3.5 3.5L16 15.5"/>',
  user: '<circle cx="12" cy="8.5" r="3.8"/><path d="M4.5 20c1.4-4 4.6-5.5 7.5-5.5s6.1 1.5 7.5 5.5"/>',
  edit: '<path d="M16.5 4.5l3 3L8 19l-4 1 1-4 11.5-11.5z"/>',
  wallet: '<rect x="3" y="6" width="18" height="13" rx="3.5"/><path d="M3 10h18"/><circle cx="17" cy="14.5" r="1.2"/>',
  reset: '<path d="M4 12a8 8 0 1 1 2.5 5.8"/><path d="M4 7v5h5"/>',
};

function svg(name, size = 20, cls = "") {
  return `<svg class="${cls}" style="width:${size}px;height:${size}px" viewBox="0 0 24 24" fill="none"
    stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">${ICONS[name] || ""}</svg>`;
}
function iconSvg(name, size = 26) { return svg(ICONS[name] ? name : "serum", size); }

/* ---------- шапка и навигация ---------- */
const NAV_ITEMS = [
  { href: "plan.html", label: "План", icon: "plan" },
  { href: "catalog.html", label: "Каталог", icon: "catalog" },
  { href: "calendar.html", label: "Календарь", icon: "calendar" },
  { href: "chat.html", label: "Чат", icon: "chat" },
  { href: "profile.html", label: "Профиль", icon: "user" },
];

const SKIN_TYPE_LABELS = {
  dry: "Сухая", oily: "Жирная", combination: "Комбинированная",
  sensitive: "Чувствительная", normal: "Нормальная",
};
const CONCERN_LABELS = {
  acne: "Акне и воспаления", pores: "Расширенные поры",
  dehydration: "Обезвоженность", sensitivity: "Раздражения после бритья",
  aging: "Первые признаки старения", dullness: "Тусклый цвет лица",
};

function renderNav(active) {
  const el = document.getElementById("appnav");
  if (!el) return;
  el.innerHTML = NAV_ITEMS.map(item => `
    <a class="nav-item ${item.href === active ? "active" : ""}" href="${item.href}">
      ${svg(item.icon, 21)}<span>${item.label}</span>
    </a>`).join("");
}

function renderTopbar(activeHref) {
  const el = document.getElementById("topbar");
  if (!el) return;
  const budget = Store.getBudget();
  el.innerHTML = `
    <a class="wordmark" href="plan.html">
      <span class="mark">Я</span><span class="name">ЯДРО</span>
    </a>
    <div class="topbar-right">
      ${budget ? `<span class="topbar-budget">${budget.toLocaleString("ru-RU")} ₽/мес</span>` : ""}
      <nav id="appnav" class="appnav"></nav>
      <button class="icon-btn" id="logoutBtn" title="Выйти из аккаунта">${svg("logout", 18)}</button>
    </div>`;
  renderNav(activeHref);
  const out = document.getElementById("logoutBtn");
  if (out) out.onclick = () => Auth.logout();
}

function fmtPrice(n) { return n.toLocaleString("ru-RU") + " ₽"; }

/* ---------- источник цены ---------- */
const PRICE_SOURCES = {
  seed: {
    cls: "src-seed", label: "референс",
    title: "Ориентировочная цена по рынку, не live-данные",
  },
  feed: {
    cls: "src-feed", label: "фид",
    title: "Получено из партнёрского товарного фида магазина",
  },
  scraper: {
    cls: "src-live", label: "live",
    title: "Собрано с сайта магазина в вежливом режиме",
  },
};

function sourceInfo(priceObj) {
  return PRICE_SOURCES[priceObj?.source] || PRICE_SOURCES.seed;
}

/** Цена вместе с пометкой источника: живые цены выделяются цветом. */
function priceHtml(priceObj) {
  if (!priceObj) return `<span class="price">—</span>`;
  const s = sourceInfo(priceObj);
  return `<span class="price ${s.cls}" title="${s.title}">${fmtPrice(priceObj.price)}</span>`;
}

function sourceTag(priceObj) {
  const s = sourceInfo(priceObj);
  if (s === PRICE_SOURCES.seed) return "";
  return `<span class="src-tag ${s.cls}" title="${s.title}">${s.label}</span>`;
}

/* ---------- избранное ---------- */
const Favorites = {
  ids: new Set(),
  async load(profileId) {
    const { ids } = await api(`/api/favorites/${profileId}`);
    this.ids = new Set(ids);
    return this.ids;
  },
  has(productId) { return this.ids.has(productId); },
  async toggle(profileId, productId) {
    if (this.ids.has(productId)) {
      await api(`/api/favorites/${profileId}/${productId}`, { method: "DELETE" });
      this.ids.delete(productId);
      return false;
    }
    await api(`/api/favorites/${profileId}`, {
      method: "POST",
      body: JSON.stringify({ product_id: productId }),
    });
    this.ids.add(productId);
    return true;
  },
};

