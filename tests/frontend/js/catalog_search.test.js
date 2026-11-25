// Поиск каталога
const assert = require("node:assert/strict");
const { test } = require("node:test");
const { openPage, response, waitFor, inputEvent } = require("./harness");

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
