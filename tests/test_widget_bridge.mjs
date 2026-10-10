import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

const html = fs.readFileSync(new URL("../sticker_widget.html", import.meta.url), "utf8");
const script = html.match(/<script>([\s\S]*?)<\/script>/)?.[1];
assert.ok(script, "widget script should exist");

const listeners = [];
const posted = [];
const status = { style: {}, textContent: "表情包正在跑来…" };
const image = {
  style: {},
  alt: "",
  onload: null,
  onerror: null,
  _src: "",
  set src(value) {
    this._src = value;
    queueMicrotask(() => this.onload?.());
  },
  get src() {
    return this._src;
  },
};

function dispatch(data) {
  for (const listener of listeners) {
    listener({ source: parentWindow, data });
  }
}

const parentWindow = {
  postMessage(message) {
    posted.push(message);
    if (message.method === "ui/initialize") {
      queueMicrotask(() =>
        dispatch({
          jsonrpc: "2.0",
          id: message.id,
          result: {
            protocolVersion: "2026-01-26",
            hostInfo: { name: "test-host", version: "1.0.0" },
            hostCapabilities: {},
            hostContext: {},
          },
        })
      );
    }
    if (message.method === "ui/notifications/initialized") {
      queueMicrotask(() =>
        dispatch({
          jsonrpc: "2.0",
          method: "ui/notifications/tool-result",
          params: {
            structuredContent: {
              image_url: "https://stickers.little-archive.com/stickers/turtle-plate",
              alt: "餐盘上的小龟",
            },
          },
        })
      );
    }
  },
};

const windowObject = {
  parent: parentWindow,
  openai: undefined,
  addEventListener(type, listener) {
    if (type === "message") listeners.push(listener);
  },
  setInterval() {
    return 1;
  },
  clearInterval() {},
};

const documentElement = { scrollWidth: 440, scrollHeight: 120 };
const documentObject = {
  documentElement,
  body: { scrollWidth: 440, scrollHeight: 120 },
  getElementById(id) {
    return id === "sticker" ? image : status;
  },
};

class ResizeObserver {
  constructor(callback) {
    this.callback = callback;
  }
  observe() {
    this.callback();
  }
}

vm.runInNewContext(script, {
  console,
  document: documentObject,
  window: windowObject,
  ResizeObserver,
  Promise,
  Math,
  queueMicrotask,
});

await new Promise((resolve) => setImmediate(resolve));
await new Promise((resolve) => setImmediate(resolve));

assert.equal(posted[0].method, "ui/initialize");
assert.equal(posted[0].params.protocolVersion, "2026-01-26");
assert.ok(posted.some((message) => message.method === "ui/notifications/initialized"));
assert.ok(posted.some((message) => message.method === "ui/notifications/size-changed"));
assert.equal(image.src, "https://stickers.little-archive.com/stickers/turtle-plate");
assert.equal(image.alt, "餐盘上的小龟");
assert.equal(image.style.display, "block");
assert.equal(status.style.display, "none");

console.log("MCP Apps widget handshake test passed.");
