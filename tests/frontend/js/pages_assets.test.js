// Проверка страниц
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");
const { JSDOM } = require("jsdom");
const { FRONTEND } = require("./harness");

test("all frontend pages and their local assets exist", () => {
  const pages = fs.readdirSync(FRONTEND).filter(name => name.endsWith(".html"));
  assert.ok(pages.length > 0);

  for (const pageName of pages) {
    const dom = new JSDOM(fs.readFileSync(path.join(FRONTEND, pageName), "utf8"));
    for (const element of dom.window.document.querySelectorAll("[src], link[href], a[href]")) {
      const value = element.getAttribute("src") || element.getAttribute("href");
      if (!value || /^(#|https?:|mailto:|data:|javascript:)/i.test(value)) continue;
      const pathname = decodeURIComponent(new URL(value, "http://localhost/").pathname);
      assert.ok(
        fs.existsSync(path.join(FRONTEND, pathname.replace(/^\/+/, ""))),
        `${pageName} references missing asset ${value}`,
      );
    }
    dom.window.close();
  }
});
