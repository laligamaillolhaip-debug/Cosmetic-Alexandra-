// Лимит сообщения
const assert = require("node:assert/strict");
const { test } = require("node:test");
const { openPage, response, waitFor } = require("./harness");

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
