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

