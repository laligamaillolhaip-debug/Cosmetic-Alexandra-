// Текст профиля
const assert = require("node:assert/strict");
const { test } = require("node:test");
const { openPage, response, waitFor } = require("./harness");

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
