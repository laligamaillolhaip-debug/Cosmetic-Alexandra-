// Проверка email
const assert = require("node:assert/strict");
const { test } = require("node:test");
const { openPage } = require("./harness");

test("login email accepts the backend format and rejects malformed characters", t => {
  const page = openPage("login.html");
  t.after(() => page.dom.window.close());
  const email = page.document.getElementById("email");
  const password = page.document.getElementById("password");

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
