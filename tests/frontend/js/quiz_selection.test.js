// Выбор анкеты
const assert = require("node:assert/strict");
const { test } = require("node:test");
const { openPage, response, waitFor } = require("./harness");

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
