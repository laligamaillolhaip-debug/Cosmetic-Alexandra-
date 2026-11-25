// Границы бюджета
const assert = require("node:assert/strict");
const { test } = require("node:test");
const { openPage, response, waitFor, inputEvent } = require("./harness");

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
