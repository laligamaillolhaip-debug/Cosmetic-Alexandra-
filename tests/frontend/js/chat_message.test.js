// Проверка чата
const assert = require("node:assert/strict");
const { test } = require("node:test");
const { openPage, response, waitFor, inputEvent } = require("./harness");

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
  document.getElementById("chatForm").requestSubmit();
  assert.equal(requests.some(request => request.url.pathname === "/api/chat/profile-1"), false);

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
