const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");
const { JSDOM, VirtualConsole } = require("jsdom");

const ROOT = path.resolve(__dirname, "../..");
const FRONTEND = path.join(ROOT, "frontend");
const PAGE_NAMES = fs.readdirSync(FRONTEND).filter(name => name.endsWith(".html"));

function response(body = {}, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? "OK" : "Bad Request",
    json: async () => body,
  };
}

function openPage(pageName, { fetch: fetchMock, storage = {} } = {}) {
  const html = fs.readFileSync(path.join(FRONTEND, pageName), "utf8");
  const virtualConsole = new VirtualConsole();
  const dom = new JSDOM(html, {
    url: `http://localhost/${pageName}`,
    runScripts: "outside-only",
    pretendToBeVisual: true,
    virtualConsole,
  });
  const { window } = dom;
  const requests = [];

  for (const [key, value] of Object.entries(storage)) {
    window.localStorage.setItem(key, value);
  }

  window.fetch = async (input, options = {}) => {
    const url = new URL(String(input), window.location.href);
    requests.push({ url, options });
    return fetchMock ? fetchMock(url, options, window) : response();
  };

  const sources = [];
  for (const script of window.document.querySelectorAll("script")) {
    const source = script.src
      ? fs.readFileSync(path.join(FRONTEND, new URL(script.src).pathname.replace(/^\/+/, "")), "utf8")
      : script.textContent;
    if (source.trim()) sources.push(source);
  }
  window.eval(sources.join("\n;\n"));

  return { dom, window, document: window.document, requests };
}

async function waitFor(predicate, message = "condition was not met") {
  const deadline = Date.now() + 2000;
  while (!predicate()) {
    if (Date.now() >= deadline) throw new Error(message);
    await new Promise(resolve => setTimeout(resolve, 10));
  }
}

function inputEvent(window) {
  return new window.Event("input", { bubbles: true });
}

test("all frontend pages and their local assets exist", () => {
  assert.ok(PAGE_NAMES.length > 0);

  for (const pageName of PAGE_NAMES) {
    const dom = new JSDOM(fs.readFileSync(path.join(FRONTEND, pageName), "utf8"));
    for (const element of dom.window.document.querySelectorAll("[src], link[href], a[href]")) {
      const value = element.getAttribute("src") || element.getAttribute("href");
      if (!value || /^(#|https?:|mailto:|data:|javascript:)/i.test(value)) continue;
      const pathname = decodeURIComponent(new URL(value, "http://localhost/").pathname);
      assert.ok(
        fs.existsSync(path.join(FRONTEND, pathname.replace(/^\/+/, ""))),
        `${pageName} references missing asset ${value}`,
      );
    }
    dom.window.close();
  }
});

test("login email accepts the backend format and rejects malformed characters", t => {
  const page = openPage("login.html");
  t.after(() => page.dom.window.close());
  const { document } = page;
  const email = document.getElementById("email");
  const password = document.getElementById("password");

  assert.equal(email.required, true);
  assert.equal(email.minLength, 3);
  assert.equal(email.maxLength, 160);
  assert.equal(email.inputMode, "email");
  assert.equal(email.checkValidity(), false);

  for (const value of [
    "plain-text",
    "user@@example.com",
    "user name@example.com",
    "user@example.c",
    "user@example.12",
    "user@example.com<script>",
  ]) {
    email.value = value;
    assert.equal(email.checkValidity(), false, `${JSON.stringify(value)} should be rejected`);
  }

  for (const value of ["user@example.com", "ё@почта.рф", " user@example.com "]) {
    email.value = value;
    assert.equal(email.checkValidity(), true, `${JSON.stringify(value)} should be accepted`);
  }

  const emailAtMaximum = `a@${"b".repeat(155)}.co`;
  assert.equal(emailAtMaximum.length, 160);
  email.value = emailAtMaximum;
  assert.equal(email.checkValidity(), true);

  assert.equal(password.required, true);
  assert.equal(password.minLength, 6);
  assert.equal(password.maxLength, 200);
});

test("login accepts any six-character password, including Unicode and symbols", t => {
  const page = openPage("login.html");
  t.after(() => page.dom.window.close());
  const password = page.document.getElementById("password");

  for (const value of ["пароль🔑", "a!@#$%"]) {
    password.value = value;
    assert.equal(password.checkValidity(), true);
  }
});

test("login submits trimmed email and displays server validation errors", async t => {
  const page = openPage("login.html", {
    fetch: async () => response({ detail: "Некорректные данные" }, 400),
  });
  t.after(() => page.dom.window.close());

  const { window, document, requests } = page;
  const email = document.getElementById("email");
  const password = document.getElementById("password");
  const form = document.getElementById("form");

  email.value = "";
  password.value = "пароль🔑";
  assert.equal(form.checkValidity(), false);
  assert.equal(requests.length, 0, "required fields must block submission");

  email.value = "  ё@почта.рф  ";
  document.querySelector('[data-mode="register"]').click();
  const submitEvent = new window.Event("submit", { bubbles: true, cancelable: true });
  form.dispatchEvent(submitEvent);
  assert.equal(submitEvent.defaultPrevented, true);
  await waitFor(() => requests.length === 1, "registration request was not sent");
  await waitFor(() => document.getElementById("msg").textContent === "Некорректные данные");

  assert.equal(requests[0].url.pathname, "/api/auth/register");
  assert.deepEqual(JSON.parse(requests[0].options.body), {
    email: "ё@почта.рф",
    password: "пароль🔑",
  });
  assert.equal(requests[0].options.credentials, "same-origin");
  assert.equal(document.getElementById("submitBtn").disabled, false);
  assert.equal(document.getElementById("msg").classList.contains("error"), true);
  assert.equal(window.location.pathname, "/login.html");
});

test("quiz requires at least one skin type but allows no concerns", async t => {
  const page = openPage("quiz.html", {
    fetch: async () => response({
      skin_types: [
        { id: "dry", label: "Сухая", hint: "" },
        { id: "oily", label: "Жирная", hint: "" },
      ],
      concerns: [{ id: "acne", label: "Акне" }],
    }),
  });
  t.after(() => page.dom.window.close());

  const { document } = page;
  const next = document.getElementById("nextBtn");
  await waitFor(() => document.querySelectorAll("#skinTypeOptions .option-card").length === 2);
  assert.equal(next.disabled, true);
  assert.match(document.getElementById("summary").textContent, /хотя бы один вариант/);

  const skinType = document.querySelector('#skinTypeOptions [data-id="dry"]');
  skinType.click();
  assert.equal(next.disabled, false);
  skinType.click();
  assert.equal(next.disabled, true);

  skinType.click();
  next.click();
  assert.equal(document.getElementById("stepLabel").textContent, "Шаг 2 из 2");
  assert.equal(next.disabled, false);
  assert.match(document.getElementById("summary").textContent, /Можно пропустить/);

  document.querySelector('#concernOptions [data-id="acne"]').click();
  assert.match(document.getElementById("summary").textContent, /Отмечено: 1/);
});

test("budget slider enforces min, max and step boundaries", async t => {
  const page = openPage("budget.html", {
    fetch: async () => response({ budget_presets: [] }),
  });
  t.after(() => page.dom.window.close());

  const { window, document } = page;
  const slider = document.getElementById("budgetSlider");
  await waitFor(() => slider.style.background !== "");

  assert.equal(slider.min, "1000");
  assert.equal(slider.max, "20000");
  assert.equal(slider.step, "100");

  slider.value = "999";
  slider.dispatchEvent(inputEvent(window));
  assert.equal(slider.value, "1000");
  assert.equal(document.getElementById("budgetVal").textContent.replace(/\s/g, " "), "1 000");

  slider.value = "20001";
  slider.dispatchEvent(inputEvent(window));
  assert.equal(slider.value, "20000");
  assert.equal(document.getElementById("budgetVal").textContent.replace(/\s/g, " "), "20 000");

  slider.value = "1050";
  assert.equal(slider.validity.stepMismatch, true);
});

test("budget submits both allowed boundary values without changing them", async t => {
  const submittedBudgets = [];
  const page = openPage("budget.html", {
    storage: {
      yadro_quiz: JSON.stringify({ skin_types: ["dry"], concerns: [] }),
    },
    fetch: async (url, options) => {
      if (url.pathname === "/api/meta/options") return response({ budget_presets: [] });
      if (url.pathname === "/api/profile" && options.method === "POST") {
        submittedBudgets.push(JSON.parse(options.body).budget_month);
        return response({ detail: "test error" }, 400);
      }
      return response({}, 404);
    },
  });
  t.after(() => page.dom.window.close());

  const { window, document } = page;
  await waitFor(() => document.getElementById("budgetSlider").style.background !== "");

  for (const budget of [1000, 20000]) {
    window.setBudget(budget);
    document.getElementById("submitBtn").click();
    await waitFor(() => submittedBudgets.length === (budget === 1000 ? 1 : 2));
    await waitFor(() => !document.getElementById("submitBtn").disabled);
  }

  assert.deepEqual(submittedBudgets, [1000, 20000]);
});

test("chat rejects whitespace, accepts the 1000-character boundary and trims messages", async t => {
  const page = openPage("chat.html", {
    storage: { yadro_profile_id: "profile-1" },
    fetch: async (url, options) => {
      if (url.pathname === "/api/chat/profile-1/history") return response({ messages: [] });
      if (url.pathname === "/api/profile/profile-1") {
        return response({ skin_types: ["oily"], budget_month: 5000 });
      }
      if (url.pathname === "/api/chat/profile-1" && options.method === "POST") {
        return response({ reply: "Ответ" });
      }
      return response({}, 404);
    },
  });
  t.after(() => page.dom.window.close());

  const { window, document, requests } = page;
  const input = document.getElementById("chatInput");
  const send = document.getElementById("sendBtn");
  await waitFor(() => document.getElementById("chatStatus").textContent === "История сохраняется");

  assert.equal(input.required, true);
  assert.equal(input.maxLength, 1000);
  input.value = " \n\t";
  input.dispatchEvent(inputEvent(window));
  assert.equal(send.disabled, true);

  input.value = `  ${"x".repeat(996)}  `;
  input.dispatchEvent(inputEvent(window));
  assert.equal(document.getElementById("charCount").textContent, "1000 / 1000");
  assert.equal(send.disabled, false);
  document.getElementById("chatForm").requestSubmit();
  await waitFor(() => requests.some(request => request.url.pathname === "/api/chat/profile-1"));

  const chatRequest = requests.find(request => request.url.pathname === "/api/chat/profile-1");
  assert.equal(JSON.parse(chatRequest.options.body).message.length, 996);
  await waitFor(() => document.getElementById("chatArea").textContent.includes("Ответ"));
});

test("chat JavaScript guard rejects more than 1000 characters", async t => {
  const posts = [];
  const page = openPage("chat.html", {
    storage: { yadro_profile_id: "profile-1" },
    fetch: async (url, options) => {
      if (url.pathname === "/api/chat/profile-1/history") return response({ messages: [] });
      if (url.pathname === "/api/profile/profile-1") return response({ skin_types: [], budget_month: 0 });
      if (url.pathname === "/api/chat/profile-1" && options.method === "POST") posts.push(options);
      return response({ reply: "ok" });
    },
  });
  t.after(() => page.dom.window.close());

  const { window, document } = page;
  await waitFor(() => document.getElementById("chatStatus").textContent === "История сохраняется");
  window.eval(`sendMessage(${JSON.stringify("x".repeat(1001))})`);
  assert.equal(document.getElementById("chatError").textContent, "Вопрос должен быть не длиннее 1000 символов.");
  assert.equal(posts.length, 0);
});

test("catalog search trims input and safely encodes punctuation", async t => {
  const productRequests = [];
  const page = openPage("catalog.html", {
    storage: { yadro_profile_id: "profile-1" },
    fetch: async url => {
      if (url.pathname === "/api/favorites/profile-1") return response({ ids: [] });
      if (url.pathname === "/api/profile/profile-1") return response({ budget_month: 5000 });
      if (url.pathname === "/api/products") {
        productRequests.push(url);
        return response({ items: [], categories: [] });
      }
      return response({}, 404);
    },
  });
  t.after(() => page.dom.window.close());

  const { window, document } = page;
  await waitFor(() => productRequests.length > 0);
  const search = document.getElementById("searchInput");
  search.value = "  SPF 50% & gel=1?  ";
  search.dispatchEvent(inputEvent(window));
  await waitFor(() => productRequests.some(url => url.searchParams.has("query")));

  const searchedUrl = productRequests.find(url => url.searchParams.has("query"));
  assert.equal(searchedUrl.searchParams.get("query"), "SPF 50% & gel=1?");
  assert.equal(searchedUrl.searchParams.get("max_price"), "5000");
});

test("profile renders unknown Unicode labels as text, not markup", async t => {
  const page = openPage("profile.html", {
    storage: { yadro_profile_id: "profile-1" },
    fetch: async () => response({
      budget_month: 1200,
      skin_types: ["<script>invalid()</script>"],
      concerns: ["<img src=x>"],
      is_owner: false,
    }),
  });
  t.after(() => page.dom.window.close());

  const { document } = page;
  await waitFor(() => document.querySelector(".skin-types"));
  assert.equal(document.querySelector(".skin-types script, .concern-list img"), null);
  assert.match(document.querySelector(".skin-types").textContent, /<script>invalid\(\)<\/script>/);
  assert.match(document.querySelector(".concern-list").textContent, /<img src=x>/);
});
