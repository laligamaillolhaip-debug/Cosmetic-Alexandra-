// Общий стенд
const fs = require("node:fs");
const path = require("node:path");
const { JSDOM, VirtualConsole } = require("jsdom");

const ROOT = path.resolve(__dirname, "../../..");
const FRONTEND = path.join(ROOT, "frontend");

function response(body = {}, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? "OK" : "Bad Request",
    json: async () => body,
  };
}

function openPage(pageName, { fetch: fetchMock, storage = {} } = {}) {
  const html = fs.readFileSync(path.join(FRONTEND, pageName), "utf8");
  const dom = new JSDOM(html, {
    url: `http://localhost/${pageName}`,
    runScripts: "outside-only",
    pretendToBeVisual: true,
    virtualConsole: new VirtualConsole(),
  });
  const { window } = dom;
  const requests = [];

  for (const [key, value] of Object.entries(storage)) {
    window.localStorage.setItem(key, value);
  }

  window.fetch = async (input, options = {}) => {
    const url = new URL(String(input), window.location.href);
    requests.push({ url, options });
    return fetchMock ? fetchMock(url, options, window) : response();
  };

  const sources = [];
  for (const script of window.document.querySelectorAll("script")) {
    const source = script.src
      ? fs.readFileSync(path.join(FRONTEND, new URL(script.src).pathname.replace(/^\/+/, "")), "utf8")
      : script.textContent;
    if (source.trim()) sources.push(source);
  }
  window.eval(sources.join("\n;\n"));

  return { dom, window, document: window.document, requests };
}

async function waitFor(predicate, message = "condition was not met") {
  const deadline = Date.now() + 2000;
  while (!predicate()) {
    if (Date.now() >= deadline) throw new Error(message);
    await new Promise(resolve => setTimeout(resolve, 10));
  }
}

function inputEvent(window) {
  return new window.Event("input", { bubbles: true });
}

module.exports = { FRONTEND, openPage, response, waitFor, inputEvent };
