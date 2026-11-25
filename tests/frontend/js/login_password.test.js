// Проверка пароля
const assert = require("node:assert/strict");
const { test } = require("node:test");
const { openPage } = require("./harness");

test("login accepts any six-character password, including Unicode and symbols", t => {
  const page = openPage("login.html");
  t.after(() => page.dom.window.close());
  const password = page.document.getElementById("password");

  for (const value of ["пароль🔑", "a!@#$%"]) {
    password.value = value;
    assert.equal(password.checkValidity(), true);
  }
});
