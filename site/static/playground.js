// The playground on the home page: an editor, Run and Stop, and a panel that shows what
// your program shows and asks questions in place.

const $ = (id) => document.getElementById(id);
const code = $("code");
const gutter = $("gutter");
const output = $("output");
const status = $("status");
const runButton = $("run");
const stopButton = $("stop");
const examples = JSON.parse($("examples-data").textContent);

const MAX_LINES = 2000;
const WAITING = 0, ANSWERED = 1, STOPPED = 2;

let worker = null;
let ctrl, data, interrupt;
let runId = 0;
let running = false;
let stopTimer = null;
let files = {};
let exampleFiles = {};
let pending = [];
let drawScheduled = false;

// Editor -----------------------------------------------------------------------------

function drawGutter(bad = new Set()) {
  const count = code.value.split("\n").length;
  gutter.innerHTML = Array.from({ length: count }, (_, i) =>
    bad.has(i + 1) ? `<span class="bad">${i + 1}</span>` : String(i + 1)).join("\n");
  code.style.height = "auto";
  code.style.height = code.scrollHeight + "px";
}

code.addEventListener("input", () => drawGutter());
code.addEventListener("keydown", (event) => {
  if (event.key === "Tab" && !event.shiftKey) {
    event.preventDefault();
    insertAtCursor("    ");
  } else if (event.key === "Enter" && !event.metaKey && !event.ctrlKey) {
    event.preventDefault();
    const start = code.selectionStart;
    const lineStart = code.value.lastIndexOf("\n", start - 1) + 1;
    const indent = code.value.slice(lineStart, start).match(/^\s*/)[0];
    insertAtCursor("\n" + indent);
  } else if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
    event.preventDefault();
    if (!runButton.disabled) run();
  }
});

function insertAtCursor(text) {
  const { selectionStart: s, selectionEnd: e, value } = code;
  code.value = value.slice(0, s) + text + value.slice(e);
  code.selectionStart = code.selectionEnd = s + text.length;
  drawGutter();
}

function replaceLine(number, text) {
  const lines = code.value.split("\n");
  lines.splice(number - 1, 1, ...text.split("\n"));
  code.value = lines.join("\n");
  drawGutter();
}

// Examples, links and files --------------------------------------------------------------

const picker = $("examples");
for (const example of examples) {
  const option = document.createElement("option");
  option.value = example.name;
  option.textContent = example.title;
  picker.append(option);
}
picker.addEventListener("change", () => loadExample(picker.value));

function loadExample(name) {
  const example = examples.find((e) => e.name === name) || examples[0];
  code.value = example.code;
  exampleFiles = { ...example.files };
  files = { ...example.files };
  output.textContent = "";
  drawGutter();
  drawFiles();
}

function encode(text) {
  const bytes = new TextEncoder().encode(text);
  let binary = "";
  bytes.forEach((b) => (binary += String.fromCharCode(b)));
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function decode(text) {
  const binary = atob(text.replace(/-/g, "+").replace(/_/g, "/"));
  return new TextDecoder().decode(Uint8Array.from(binary, (c) => c.charCodeAt(0)));
}

async function loadFromLink() {
  const params = new URLSearchParams(location.hash.slice(1));
  if (!params.has("code")) {
    loadExample(examples[0].name);
    return;
  }
  try {
    code.value = decode(params.get("code"));
  } catch {
    loadExample(examples[0].name);
    return;
  }
  files = {};
  for (const name of (params.get("files") || "").split(",").filter(Boolean)) {
    const response = await fetch(`/play/files/${encodeURIComponent(name)}`);
    if (response.ok) files[name] = await response.text();
  }
  exampleFiles = { ...files };
  drawGutter();
  drawFiles();
}

$("copy").addEventListener("click", async () => {
  const link = `${location.origin}/#code=${encode(code.value)}`;
  history.replaceState(null, "", link);
  try {
    await navigator.clipboard.writeText(link);
    status.textContent = "Copied a link to your program. Anyone who opens it sees this program.";
  } catch {
    status.textContent = "Copy the link from your browser's address bar.";
  }
});

function drawFiles() {
  const list = $("file-list");
  list.innerHTML = "";
  const names = Object.keys(files).sort();
  if (!names.length) {
    const li = document.createElement("li");
    li.textContent = "No files yet. Files your program saves show up here.";
    list.append(li);
  }
  for (const name of names) {
    const li = document.createElement("li");
    const open = document.createElement("button");
    open.className = "link";
    open.textContent = name;
    open.addEventListener("click", () => openFile(name));
    li.append(open);
    list.append(li);
  }
}

function openFile(name) {
  $("file-view").hidden = false;
  $("file-name").textContent = name;
  $("file-text").value = files[name];
  const link = $("file-download");
  link.href = URL.createObjectURL(new Blob([files[name]], { type: "text/plain" }));
  link.download = name;
}

$("file-save").addEventListener("click", () => {
  files[$("file-name").textContent] = $("file-text").value;
  status.textContent = "Kept your changes to the file.";
});

$("upload").addEventListener("change", async (event) => {
  for (const file of event.target.files) files[file.name] = await file.text();
  drawFiles();
});

$("reset-files").addEventListener("click", () => {
  if (confirm("This undoes your changes to the files. Put back the example's files?")) {
    files = { ...exampleFiles };
    drawFiles();
    $("file-view").hidden = true;
  }
});

for (const tab of document.querySelectorAll('[role="tab"]')) {
  tab.addEventListener("click", () => {
    for (const other of document.querySelectorAll('[role="tab"]')) {
      other.setAttribute("aria-selected", String(other === tab));
      $(other.getAttribute("aria-controls")).hidden = other !== tab;
    }
  });
}

// Output -----------------------------------------------------------------------------

let shownLines = 0;

function show(text, className) {
  pending.push([text, className]);
  if (!drawScheduled) {
    drawScheduled = true;
    requestAnimationFrame(drawPending);
  }
}

// Each batch of lines becomes one block, so even a program that shows thousands of lines
// a second can't slow the page down. Only the last MAX_LINES lines are kept.
function drawPending() {
  drawScheduled = false;
  if (!pending.length) return;
  const fragment = document.createDocumentFragment();
  let block = null;
  let blockClass = null;
  for (const [text, className] of pending) {
    if (!block || className !== blockClass) {
      block = document.createElement("div");
      if (className) block.className = className;
      block.dataset.lines = "0";
      block.textContent = "";
      fragment.append(block);
      blockClass = className;
    }
    block.textContent += (block.dataset.lines === "0" ? "" : "\n") + text;
    const count = text.split("\n").length;
    block.dataset.lines = String(Number(block.dataset.lines) + count);
    shownLines += count;
  }
  pending = [];
  output.append(fragment);
  let trimmed = false;
  while (shownLines > MAX_LINES && output.firstElementChild) {
    const first = output.firstElementChild;
    if (first === output.lastElementChild) {
      // One very long block: keep only its last lines.
      const lines = first.textContent.split("\n");
      const keep = lines.slice(-MAX_LINES);
      first.textContent = keep.join("\n");
      first.dataset.lines = String(keep.length);
      shownLines = keep.length;
      trimmed = true;
      break;
    }
    shownLines -= Number(first.dataset.lines || 1);
    first.remove();
    trimmed = true;
  }
  if (trimmed) {
    const note = document.createElement("div");
    note.className = "stopped";
    note.dataset.lines = "1";
    note.textContent = "(earlier lines hidden)";
    output.prepend(note);
    shownLines += 1;
  }
  output.scrollTop = output.scrollHeight;
}

function askInPlace(question) {
  drawPending();
  const line = document.createElement("div");
  line.className = "asked";
  line.textContent = question + " ";
  const box = document.createElement("input");
  box.className = "answer-box";
  box.setAttribute("aria-label", question);
  line.append(box);
  output.append(line);
  output.scrollTop = output.scrollHeight;
  box.focus();
  box.addEventListener("keydown", (event) => {
    if (event.key !== "Enter") return;
    const answer = box.value;
    const shown = document.createElement("span");
    shown.className = "answer";
    shown.textContent = answer;
    box.replaceWith(shown);
    const bytes = new TextEncoder().encode(answer).slice(0, data.length);
    data.set(bytes);
    Atomics.store(ctrl, 1, bytes.length);
    Atomics.store(ctrl, 0, ANSWERED);
    Atomics.notify(ctrl, 0);
  });
}

function showProblems(message) {
  drawPending();
  const box = document.createElement("div");
  box.className = "problem";
  box.textContent = message.text;
  const bad = new Set();
  for (const problem of message.problems || []) {
    if (problem.line) bad.add(problem.line);
    for (const idea of problem.ideas || []) {
      const button = document.createElement("button");
      button.className = "idea";
      button.textContent = `Use this: ${idea.trim()}`;
      button.addEventListener("click", () => {
        replaceLine(problem.line, idea);
        status.textContent = `Changed line ${problem.line}. Press Run to try again.`;
      });
      box.append(document.createElement("br"), button);
    }
  }
  output.append(box);
  drawGutter(bad);
}

// Running ------------------------------------------------------------------------------

function startWorker() {
  ctrl = new Int32Array(new SharedArrayBuffer(8));
  data = new Uint8Array(new SharedArrayBuffer(65536));
  interrupt = new Uint8Array(new SharedArrayBuffer(1));
  worker = new Worker("/worker.js", { type: "module" });
  worker.onmessage = onMessage;
  worker.onerror = () => {
    status.textContent = "Plain couldn't start in this browser. You can install it on your computer instead.";
  };
  worker.postMessage({ type: "init", ctrl, data, interrupt });
}

function onMessage(event) {
  const message = event.data;
  if (message.run !== undefined && message.run !== runId) return;   // from a run you stopped
  switch (message.type) {
    case "ready":
      runButton.disabled = false;
      status.textContent = "Plain is ready. Press Run.";
      break;
    case "failed":
      status.textContent = "Plain couldn't start in this browser. You can install it on your computer instead.";
      break;
    case "show":
      show(message.text);
      break;
    case "clear":
      pending = [];
      shownLines = 0;
      output.textContent = "";
      break;
    case "ask":
      askInPlace(message.text);
      break;
    case "problems":
      showProblems(message);
      break;
    case "crash":
      console.error(message.text);
      show("Plain itself went wrong. Please tell us at plain-lang.dev/help.", "problem");
      finish();
      break;
    case "done":
      if (message.files) {
        files = message.files;
        drawFiles();
      }
      finish();
      break;
  }
}

function run() {
  runId += 1;
  output.textContent = "";
  shownLines = 0;
  pending = [];
  drawGutter();
  running = true;
  runButton.disabled = true;
  stopButton.disabled = false;
  status.textContent = "Running your program.";
  worker.postMessage({ type: "run", source: code.value, files, run: runId });
}

function finish() {
  drawPending();
  running = false;
  clearTimeout(stopTimer);
  runButton.disabled = false;
  stopButton.disabled = true;
  if (!status.textContent.startsWith("Changed")) status.textContent = "Your program has finished.";
}

function stop() {
  if (!running) return;
  interrupt[0] = 2;
  Atomics.store(ctrl, 0, STOPPED);
  Atomics.notify(ctrl, 0);
  stopTimer = setTimeout(() => {
    // The program didn't stop on its own (it may be waiting on a website). Start a fresh Plain.
    worker.terminate();
    show("Stopped.", "stopped");
    runId += 1;
    finish();
    runButton.disabled = true;
    status.textContent = "Getting Plain ready again.";
    startWorker();
  }, 1000);
  const watch = (event) => {
    if (event.data.type === "done") {
      clearTimeout(stopTimer);
      worker.removeEventListener("message", watch);
    }
  };
  worker.addEventListener("message", watch);
}

runButton.addEventListener("click", run);
stopButton.addEventListener("click", stop);

if (!self.crossOriginIsolated) {
  status.textContent = "Your browser can't run the playground. Try a recent Chrome, Edge, Firefox or Safari, or install Plain on your computer.";
} else {
  startWorker();
}
loadFromLink();
