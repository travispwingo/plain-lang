// Runs Plain inside Pyodide, off the page's main thread, so "ask" and "wait" can block here
// without freezing the page.
import { loadPyodide } from "/pyodide/314.0.7/pyodide.mjs";

let pyodide = null;
let browser = null;

self.plainPost = (type, payload) => {
  self.postMessage({ type, ...JSON.parse(payload) });
};

async function boot(message) {
  self.plainCtrl = message.ctrl;
  self.plainData = message.data;
  pyodide = await loadPyodide({ indexURL: "/pyodide/314.0.7/" });
  pyodide.setInterruptBuffer(message.interrupt);
  const zip = await (await fetch("/play/plainlang.zip")).arrayBuffer();
  pyodide.unpackArchive(zip, "zip", { extractDir: "/home/pyodide/lib" });
  pyodide.runPython("import sys; sys.path.insert(0, '/home/pyodide/lib')");
  browser = pyodide.pyimport("plainlang.browser");
  self.postMessage({ type: "ready" });
}

self.onmessage = async (event) => {
  const message = event.data;
  if (message.type === "init") {
    self.plainInterrupt = message.interrupt;
    try {
      await boot(message);
    } catch (error) {
      self.postMessage({ type: "failed", text: String(error) });
    }
    return;
  }
  if (message.type === "run") {
    Atomics.store(self.plainInterrupt, 0, 0);
    Atomics.store(self.plainCtrl, 0, 0);
    try {
      browser.run_in_page(message.source, JSON.stringify(message.files), message.run, message.seed ?? undefined);
    } catch (error) {
      self.postMessage({ type: "crash", run: message.run, text: String(error) });
    }
    Atomics.store(self.plainInterrupt, 0, 0);
    return;
  }
  if (message.type === "check") {
    try {
      self.postMessage({ type: "checked", id: message.id, problems: JSON.parse(browser.check_in_page(message.source)) });
    } catch (error) {
      self.postMessage({ type: "checked", id: message.id, problems: [] });
    }
  }
};
