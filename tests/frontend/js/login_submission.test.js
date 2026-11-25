// Отправка формы
const assert = require("node:assert/strict");
const { test } = require("node:test");
const { openPage, response, waitFor } = require("./harness");

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
  form.requestSubmit();
  assert.equal(requests.length, 0, "required fields must block submission");

  email.value = "not-an-email";
  assert.equal(form.checkValidity(), false);
  form.requestSubmit();
  assert.equal(requests.length, 0, "malformed email must block submission");

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
