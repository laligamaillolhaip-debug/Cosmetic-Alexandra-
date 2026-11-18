const profileId = requireProfile();
renderTopbar("chat.html");
const input = document.getElementById("chatInput");
const sendButton = document.getElementById("sendBtn");
const status = document.getElementById("chatStatus");
const chatError = document.getElementById("chatError");
let busy = false;
let historyReady = false;
sendButton.innerHTML = svg("send", 19);
const suggestions = [
  "Как правильно наносить средства?",
  "Как сократить стоимость ухода?",
  "Что делать с раздражением после бритья?",
  "Как сочетать средства из моего плана?",
];
const suggestRow = document.getElementById("suggestRow");
suggestions.forEach(text => {
  const button = document.createElement("button");
  button.type = "button";
  button.disabled = true;
  button.append(document.createTextNode(text));
  const arrow = document.createElement("span");
  arrow.textContent = "↗";
  arrow.setAttribute("aria-hidden", "true");
  button.appendChild(arrow);
  button.onclick = () => sendMessage(text);
  suggestRow.appendChild(button);
});

function updateControls() {
  sendButton.disabled = busy || !historyReady || !input.value.trim();
  suggestRow.querySelectorAll("button").forEach(button => button.disabled = busy || !historyReady);
  document.getElementById("charCount").textContent = `${input.value.length} / 1000`;
}

function appendMsg(role, text) {
  const area = document.getElementById("chatArea");
  const div = document.createElement("div");
  div.className = `msg ${role === "user" ? "me" : "ai"}`;
  div.textContent = text;
  area.appendChild(div);
  area.scrollTop = area.scrollHeight;
  return div;
}

async function sendMessage(text) {
  const value = (text ?? input.value).trim();
  if (!value || busy || !historyReady) return;
  if (value.length > 1000) { chatError.textContent = "Вопрос должен быть не длиннее 1000 символов."; return; }
  busy = true;
  input.value = "";
  chatError.textContent = "";
  updateControls();
  appendMsg("user", value);
  const pending = appendMsg("assistant", "");
  const stopThinking = showThinking(pending, "Готовим ответ");
  status.textContent = "Ассистент отвечает";
  try {
    const { reply } = await api(`/api/chat/${profileId}`, {
      method: "POST", body: JSON.stringify({ message: value }),
    });
    pending.textContent = reply;
    status.textContent = "История сохраняется";
  } catch (err) {
    pending.textContent = "Не удалось получить ответ. Попробуй отправить вопрос ещё раз.";
    pending.classList.add("is-error");
    chatError.textContent = err.message;
    status.textContent = "Ответ недоступен";
    if (!input.value) input.value = value;
  } finally {
    stopThinking();
    busy = false;
    updateControls();
    const area = document.getElementById("chatArea");
    area.scrollTop = area.scrollHeight;
  }
}

document.getElementById("chatForm").onsubmit = event => { event.preventDefault(); sendMessage(); };
input.addEventListener("input", updateControls);
input.addEventListener("keydown", event => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault(); sendMessage();
  }
});

async function loadHistory() {
  try {
    const { messages } = await api(`/api/chat/${profileId}/history`);
    messages.forEach(message => appendMsg(message.role, message.content));
    if (!messages.length) appendMsg("assistant", "Привет. Давай разберёмся в твоём уходе. Я учитываю анкету и сохранённый план — спрашивай о средствах, порядке нанесения или сочетании компонентов.");
    status.textContent = "История сохраняется";
    historyReady = true;
  } catch (err) {
    status.textContent = "История недоступна";
    chatError.textContent = "Не удалось загрузить историю: " + err.message + ". Обнови страницу, чтобы повторить.";
  }
  updateControls();
}

document.getElementById("budgetContext").textContent = Store.getBudget() ? fmtPrice(Store.getBudget()) : "Не указан";
api(`/api/profile/${profileId}`).then(profile => {
  document.getElementById("skinContext").textContent = profile.skin_types.map(type => SKIN_TYPE_LABELS[type] || type).join(" · ");
  document.getElementById("budgetContext").textContent = fmtPrice(profile.budget_month);
}).catch(() => { document.getElementById("skinContext").textContent = "Анкета и сохранённый план"; });
loadHistory();
