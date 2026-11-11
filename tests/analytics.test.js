/* Optional: node tests/analytics.test.js. Uses built-in modules, no SDK/network. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const source = fs.readFileSync(path.join(__dirname, "../docs/assets/analytics.js"), "utf8");

function boot(overrides = {}) {
  const scripts = [];
  const handlers = {};
  const handlerOptions = {};
  const window = {
    location: { search: "?analytics_test=build2-nov11&email=private@example.com#secret" },
    AI_COACH_ANALYTICS: { enabled: true, projectToken: "phc_testonly", apiHost: "https://us.i.posthog.com" }
  };
  const document = {
    currentScript: { dataset: { analyticsSurface: "local_app" } },
    createElement: () => ({}),
    head: { append: (script) => scripts.push(script) },
    addEventListener: (name, callback, options) => { handlers[name] = callback; handlerOptions[name] = options; }
  };
  const navigator = { doNotTrack: "0" };
  if (overrides.surface) document.currentScript.dataset.analyticsSurface = overrides.surface;
  if (overrides.enabled === false) window.AI_COACH_ANALYTICS.enabled = false;
  if (overrides.dnt) navigator.doNotTrack = "1";
  if (overrides.gpc) navigator.globalPrivacyControl = true;
  if (overrides.search !== undefined) window.location.search = overrides.search;
  vm.runInNewContext(source, { window, document, navigator, URLSearchParams });
  const options = window.posthog?._i[0][1];
  const sent = [];
  const sdk = {
    register: () => {},
    capture: (event, properties) => {
      const filtered = options.before_send({ event, properties: { ...properties,
        distinct_id: "anonymous-id", $session_id: "session-id", $window_id: "window-id",
        $current_url: "https://private.example/?secret=do-not-send", $referrer: "private-referrer",
        $set: { email: "private@example.com" }, $set_once: { filename: "private-cv.pdf" },
        $initial_current_url: "private-url", $elements: [{ text: "private words" }] } });
      if (filtered) sent.push(filtered);
    }
  };
  return { window, scripts, handlers, handlerOptions, options, sent, sdk };
}

let passed = 0;
function test(name, run) {
  run();
  passed += 1;
  console.log(`PASS ${name}`);
}

test("SDK starts asynchronously with strict privacy options before any capture", () => {
  const { scripts, options } = boot();
  assert.equal(scripts.length, 1);
  assert.equal(scripts[0].async, true);
  assert.equal(scripts[0].referrerPolicy, "no-referrer");
  assert.equal(scripts[0].src, "https://us-assets.i.posthog.com/static/array.js");
  for (const key of ["autocapture", "capture_pageview", "capture_pageleave", "capture_exceptions", "capture_performance", "capture_heatmaps", "enable_recording_console_log", "ip"]) assert.equal(options[key], false, key);
  assert.equal(options.person_profiles, "never");
  assert.equal(options.persistence, "memory");
  assert.equal(options.disable_persistence, true);
  assert.equal(options.session_recording.maskAllInputs, true);
  assert.equal(options.session_recording.maskTextSelector, "*");
  assert.equal(options.session_recording.maskInputFn("secret"), "[hidden]");
  assert.equal(options.session_recording.maskTextFn("private-cv.pdf"), "[hidden]");
  assert.match(options.session_recording.blockSelector, /data-analytics-private/);
  assert.equal(options.session_recording.recordBody, false);
  assert.equal(options.session_recording.recordHeaders, false);
  assert.equal(options.session_recording.recordCanvas, false);
  assert.equal(options.logs.captureConsoleLogs, false);
  assert.equal(options.metrics.network, false);
});

test("allowlist drops user data, campaign URLs, and unknown event names", () => {
  const { window, options, sdk, sent } = boot({ search: "?analytics_test=build2-nov11&email=private@example.com" });
  window.AIAnalytics.track("document_import_ready", { card_count: 2, filename: "private-cv.pdf", text: "private words" });
  window.AIAnalytics.track("private words", { text: "private words" });
  options.loaded(sdk);
  assert.equal(sent.length, 2);
  assert.equal(sent[0].event, "$pageview");
  assert.equal(sent[1].properties.card_count, 2);
  assert.equal(sent[1].properties.test_run, "build2-nov11");
  assert.equal(sent[1].properties.$geoip_disable, true);
  assert.equal(sent[1].properties.$current_url, "http://127.0.0.1:8787/");
  assert.equal(sent[1].properties.$session_id, "session-id");
  assert.doesNotMatch(JSON.stringify(sent), /private|example\.com|secret/);
  assert.equal(options.before_send({ event: "$autocapture", properties: { text: "private" } }), null);
});

test("enum/count bounds prevent data leakage through allowed property names", () => {
  const { window, options, sdk, sent } = boot();
  options.loaded(sdk);
  window.AIAnalytics.track("ui_click", { control: "private words" });
  window.AIAnalytics.track("document_import_ready", { card_count: 999 });
  window.AIAnalytics.track("theme_reviewed", { decision: "private words" });
  assert.equal(sent[1].properties.control, undefined);
  assert.equal(sent[2].properties.card_count, undefined);
  assert.equal(sent[3].properties.decision, undefined);
});

test("queued mode is preserved and unsupported mode/test tokens are discarded", () => {
  const { window, options, sdk, sent } = boot({ search: "?analytics_test=someone@example.com" });
  window.AIAnalytics.track("theme_proposed");
  window.AIAnalytics.setMode("live");
  window.AIAnalytics.track("theme_proposed");
  window.AIAnalytics.setMode("private");
  options.loaded(sdk);
  assert.equal(sent[1].properties.app_mode, "sample");
  assert.equal(sent[2].properties.app_mode, "live");
  assert.equal(sent[2].properties.test_run, undefined);
});

test("clicks send static labels and never DOM text or link destinations", () => {
  const { handlers, options, sdk, sent } = boot();
  options.loaded(sdk);
  handlers.click({ target: { closest: () => ({ id: "upload-button", textContent: "private", disabled: false }) } });
  handlers.click({ target: { closest: () => ({ id: "private-cv.pdf", disabled: false }) } });
  assert.equal(sent.length, 2);
  assert.equal(sent[1].properties.control, "find_experiences");
  assert.doesNotMatch(JSON.stringify(sent), /private/);
});

test("product page has separate surface and fixed click/page identifiers", () => {
  const { handlers, options, sdk, sent } = boot({ surface: "product_page" });
  options.loaded(sdk);
  handlers.click({ target: { closest: () => ({ getAttribute: () => "#live-demo" }) } });
  assert.equal(sent[0].properties.app_surface, "product_page");
  assert.equal(sent[0].properties.app_mode, undefined);
  assert.equal(sent[1].properties.control, "try_product");
});

test("click is counted before the app disables its button while starting work", () => {
  const { handlers, handlerOptions, options, sdk, sent } = boot();
  options.loaded(sdk);
  const button = { id: "accept-button", disabled: false };
  const event = { target: { closest: () => button } };
  const capture = handlerOptions.click === true || handlerOptions.click?.capture === true;
  if (capture) handlers.click(event);
  // The actual app's target handler sets busy and disables controls immediately.
  button.disabled = true;
  if (!capture) handlers.click(event);
  assert.equal(sent.length, 2);
  assert.equal(sent[1].properties.control, "accept_theme");
});

test("disabled/DNT/GPC avoids SDK download and remains safe for app calls", () => {
  for (const overrides of [{ enabled: false }, { dnt: true }, { gpc: true }]) {
    const { window, scripts } = boot(overrides);
    assert.equal(scripts.length, 0);
    assert.doesNotThrow(() => window.AIAnalytics.track("theme_proposed"));
  }
});

test("SDK failure does not throw into workflow", () => {
  const { window, scripts, options } = boot();
  scripts[0].onerror();
  assert.doesNotThrow(() => window.AIAnalytics.track("theme_proposed"));
  options.loaded({ register: () => {}, capture: () => { throw new Error("blocked"); } });
  assert.doesNotThrow(() => window.AIAnalytics.track("theme_proposed"));
});

test("replay preserves page metadata without an isInitial flag and strips all private request fields", () => {
  const { options } = boot();
  const redact = options.session_recording.maskCapturedNetworkRequestFn;
  // SDK 1.447.12 calls the callback with only {name} for rrweb Meta events.
  // Returning null makes it drop the whole event, including viewport dimensions.
  const meta = { type: 4, data: { href: "https://private/?secret=1#private", width: 1280, height: 800 } };
  const page = redact({ name: meta.data.href });
  assert.ok(page?.name, "Replay metadata must survive URL masking");
  meta.data.href = page.name;
  assert.equal(meta.data.href, "http://127.0.0.1:8787/");
  assert.equal(meta.data.width, 1280);
  assert.equal(meta.data.height, 800);
  assert.equal(JSON.stringify(redact({ name: "https://private/?secret=1", requestBody: "private", requestHeaders: { authorization: "private" } })), JSON.stringify({ name: "http://127.0.0.1:8787/" }));
  const redacted = redact({ isInitial: true, name: "https://private/?secret=1", responseBody: "private" });
  assert.equal(redacted.name, "http://127.0.0.1:8787/");
  assert.equal(redacted.responseBody, undefined);
});
console.log(`${passed} analytics safeguard tests passed (stub SDK; no network).`);
