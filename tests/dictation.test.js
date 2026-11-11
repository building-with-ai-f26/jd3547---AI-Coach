/* node tests/dictation.test.js — built-in modules only; no microphone or network. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const source = fs.readFileSync(path.join(__dirname, "../static/dictation.js"), "utf8");

function setup({ before = "Earlier text.", maxLength = 6000, supported = true, secure = true } = {}) {
  const instances = [];
  const timers = new Map();
  let timerId = 0;
  let changes = 0;
  function element() {
    const handlers = {};
    return { value: "", textContent: "", hidden: false, disabled: false, readOnly: false,
      classList: { toggle() {} }, addEventListener(name, fn) { handlers[name] = fn; },
      emit(name) { handlers[name]?.(); } };
  }
  class MockRecognition {
    constructor() { this.stops = 0; this.aborts = 0; instances.push(this); }
    start() { this.started = true; }
    stop() { this.stops += 1; }
    abort() { this.aborts += 1; }
    result(items, resultIndex = 0) {
      this.onresult({ resultIndex, results: items.map(([transcript, isFinal]) => Object.assign([{ transcript }], { isFinal })) });
    }
  }
  const window = {
    ...element(), isSecureContext: secure,
    SpeechRecognition: supported ? MockRecognition : undefined,
    setTimeout(fn, delay) { const id = ++timerId; timers.set(id, { fn, delay }); return id; },
    clearTimeout(id) { timers.delete(id); }
  };
  const document = { ...element(), hidden: false };
  vm.runInNewContext(source, { window, document });
  const input = { ...element(), value: before, maxLength };
  const start = element(), stop = element(), cancel = element(), status = element(), preview = element();
  const controller = window.createDictation({ input, start, stop, cancel, status, preview, changed() { changes += 1; } });
  controller.setEnabled(true);
  return { input, start, stop, cancel, status, preview, controller, instances, window, document,
    get changes() { return changes; },
    tick(delay) {
      const pending = [...timers.entries()].filter(([, timer]) => timer.delay === delay);
      assert.ok(pending.length, `Expected a ${delay}ms timer`);
      pending.forEach(([id, timer]) => { timers.delete(id); timer.fn(); });
    }, timers };
}

let passed = 0;
function test(name, run) { run(); passed += 1; console.log(`PASS ${name}`); }

test("final words append once, prior text survives, and interim words stay separate", () => {
  const s = setup();
  s.start.emit("click");
  const recognition = s.instances[0];
  recognition.result([["New words.", true], ["Still thinking", false]]);
  assert.equal(s.input.value, "Earlier text. New words.");
  assert.equal(s.preview.textContent, "Still thinking");
  assert.equal(s.preview.hidden, false);
  recognition.result([["New words.", true], ["A new thought.", true]]);
  assert.equal(s.input.value, "Earlier text. New words. A new thought.");
  assert.equal(s.preview.textContent, "");
  assert.ok(s.changes > 1);
  assert.equal(s.input.readOnly, true);
});

test("Stop waits for final results and end before enabling editing", () => {
  const s = setup();
  s.start.emit("click");
  const recognition = s.instances[0];
  s.stop.emit("click");
  assert.equal(recognition.stops, 1);
  assert.equal(s.controller.active, true);
  assert.equal(s.stop.disabled, true);
  recognition.result([["Final words after stop.", true]]);
  recognition.onend();
  assert.equal(s.input.value, "Earlier text. Final words after stop.");
  assert.equal(s.controller.active, false);
  assert.equal(s.input.readOnly, false);
  assert.equal(recognition.aborts, 0);
  assert.equal(s.timers.size, 0);
});

test("Cancel restores earlier text and ignores late callbacks across a new run", () => {
  const s = setup();
  s.start.emit("click");
  const old = s.instances[0];
  old.result([["Remove this.", true], ["And this", false]]);
  s.cancel.emit("click");
  assert.equal(s.input.value, "Earlier text.");
  assert.equal(old.aborts, 1);
  assert.equal(s.preview.hidden, true);
  s.start.emit("click");
  old.result([["Late words.", true]], 0);
  old.onend();
  assert.equal(s.controller.active, true);
  assert.equal(s.input.value, "Earlier text.");
  s.instances[1].result([["Keep these.", true]]);
  assert.equal(s.input.value, "Earlier text. Keep these.");
});

test("permission and network failures preserve text and stop recognition", () => {
  for (const error of ["not-allowed", "network"]) {
    const s = setup();
    s.start.emit("click");
    const recognition = s.instances[0];
    if (error === "network") recognition.result([["Already heard.", true]]);
    const expected = s.input.value;
    recognition.onerror({ error });
    recognition.result([["Late words.", true]], 1);
    assert.equal(s.input.value, expected);
    assert.equal(s.controller.active, false);
    assert.equal(recognition.aborts, 1);
    assert.match(s.status.textContent, error === "network" ? /could not connect/ : /not allowed/);
    assert.equal(s.timers.size, 0);
  }
});

test("maximum length caps appended words and stops recording", () => {
  const s = setup({ before: "123", maxLength: 8 });
  s.start.emit("click");
  const recognition = s.instances[0];
  recognition.result([["abcdefghij", true]]);
  assert.equal(s.input.value, "123 abcd");
  assert.equal(s.controller.active, false);
  assert.equal(recognition.aborts, 1);
  assert.equal(s.start.disabled, true);
  assert.match(s.status.textContent, /Character limit/);
  s.start.emit("click");
  assert.equal(s.instances.length, 1);
});

test("60-second limit stops, then the final-result deadline aborts safely", () => {
  const s = setup();
  s.start.emit("click");
  const recognition = s.instances[0];
  s.tick(60000);
  assert.equal(recognition.stops, 1);
  assert.equal(s.controller.active, true);
  recognition.onstart(); // A delayed permission grant must not restart the timer.
  assert.match(s.status.textContent, /Finishing/);
  s.tick(4000);
  assert.equal(s.controller.active, false);
  assert.equal(recognition.aborts, 1);
  assert.equal(s.input.value, "Earlier text.");
  assert.equal(s.timers.size, 0);
});

test("hide, navigation, disabling, and reset-style stop abort without deleting finalized text", () => {
  for (const leave of [s => { s.document.hidden = true; s.document.emit("visibilitychange"); },
    s => s.window.emit("pagehide"), s => s.controller.setEnabled(false), s => s.controller.stop()]) {
    const s = setup();
    s.start.emit("click");
    const recognition = s.instances[0];
    recognition.result([["Keep this.", true], ["Unfinished", false]]);
    leave(s);
    recognition.result([["Keep this.", true], ["Late words.", true]]);
    assert.equal(s.input.value, "Earlier text. Keep this.");
    assert.equal(recognition.aborts, 1);
    assert.equal(s.controller.active, false);
    assert.equal(s.preview.hidden, true);
    assert.equal(s.timers.size, 0);
  }
});

test("unsupported or insecure browsers keep typing available without starting a microphone", () => {
  for (const options of [{ supported: false }, { secure: false }]) {
    const s = setup(options);
    s.start.emit("click");
    assert.equal(s.instances.length, 0);
    assert.equal(s.start.disabled, true);
    assert.equal(s.controller.active, false);
    assert.equal(s.input.readOnly, false);
    assert.equal(s.input.value, "Earlier text.");
    assert.match(s.status.textContent, /isn't available/);
  }
});
console.log(`${passed} dictation tests passed (mock recognition; no microphone/network).`);
