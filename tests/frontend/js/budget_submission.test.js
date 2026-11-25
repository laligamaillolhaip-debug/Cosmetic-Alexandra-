// Отправка бюджета
const assert = require("node:assert/strict");
const { test } = require("node:test");
const { openPage, response, waitFor } = require("./harness");

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
