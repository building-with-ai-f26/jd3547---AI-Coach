/* Shared by the public Product Page and local workshop. No personal text belongs here.
 * Privacy controls: https://posthog.com/docs/session-replay/privacy
 * Network controls: https://posthog.com/docs/session-replay/network-recording
 */
(() => {
  "use strict";
  const surface = document.currentScript?.dataset.analyticsSurface === "local_app" ? "local_app" : "product_page";
  const config = window.AI_COACH_ANALYTICS;
  const canonicalURL = surface === "local_app" ? "http://127.0.0.1:8787/" : "https://building-with-ai-f26.github.io/jd3547---AI-Coach/";
  const title = surface === "local_app" ? "AI Coach — Local workshop" : "AI Coach — Product Page";
  const testRun = new URLSearchParams(window.location.search).get("analytics_test") === "build2-nov11";
  let mode = surface === "local_app" ? "sample" : null;
  let sdk = null;
  let queue = [];

  const controls = Object.freeze({
    "sample-mode-button": "sample_mode", "live-mode-button": "live_mode",
    "choose-upload-button": "choose_upload", "choose-paste-button": "choose_paste",
    "upload-button": "find_experiences", "approve-experiences-button": "approve_experiences",
    "document-start-button": "find_question", "start-button": "start_exercise",
    "answer-button": "answer_question", "accept-button": "accept_theme", "edit-button": "edit_theme",
    "reject-button": "reject_theme", "save-edit-button": "save_edit", "cancel-edit-button": "cancel_edit",
    "retry-button": "retry", "reset-button": "open_reset", "confirm-reset-button": "confirm_reset",
    "export-button": "export", "source-link": "read_source"
  });
  const productLinks = Object.freeze({
    "#live-demo": "try_product", "#prd": "read_prd", "#build-log": "read_build_log",
    "assets/prototype-nov-02.jpg": "view_prototype", "assets/document-landscape-nov-04.jpg": "view_document_demo"
  });
  const allowedControls = new Set([...Object.values(controls), ...Object.values(productLinks)]);
  const schemas = Object.freeze({
    "$pageview": {},
    "ui_click": { control: allowedControls },
    "mode_selected": {},
    "background_selected": { input_method: new Set(["upload", "paste"]) },
    "document_selected": { valid: "boolean" },
    "document_import_started": {},
    "document_import_ready": { card_count: "count" },
    "experiences_approved": { card_count: "count" },
    "coaching_question_ready": { input_method: new Set(["upload", "paste", "sample"]) },
    "theme_proposed": {},
    "theme_reviewed": { decision: new Set(["accept", "edit", "reject"]) },
    "exercise_exported": {},
    "exercise_reset": {},
    "step_failed": { stage: new Set(["share", "import_review", "imported", "question", "review", "complete"]), failure: new Set(["stale", "request_failed"]) }
  });

  function baseProperties() {
    const properties = { app_surface: surface, analytics_version: 1, $current_url: canonicalURL,
      $pathname: surface === "local_app" ? "/" : "/jd3547---AI-Coach/", $title: title,
      $referrer: "", $referring_domain: "", $geoip_disable: true };
    if (mode) properties.app_mode = mode;
    if (testRun) properties.test_run = "build2-nov11";
    return properties;
  }

  function safeProperties(name, properties) {
    const schema = schemas[name];
    if (!schema) return null;
    const safe = baseProperties();
    Object.entries(schema).forEach(([key, rule]) => {
      const value = properties?.[key];
      if (rule instanceof Set ? rule.has(value) : rule === "count" ? Number.isInteger(value) && value >= 0 && value <= 6 : typeof value === rule) safe[key] = value;
    });
    return safe;
  }

  function track(name, properties = {}) {
    const safe = safeProperties(name, properties);
    if (!safe) return;
    try {
      if (sdk) sdk.capture(name, safe);
      else if (queue.length < 50) queue.push([name, safe]);
    } catch (_) { /* Analytics must never prevent an exercise from working. */ }
  }
  window.AIAnalytics = Object.freeze({
    track,
    setMode(next) { if (surface === "local_app" && ["sample", "live"].includes(next)) mode = next; }
  });

  // No SDK request at all when disabled or the browser requests no tracking.
  if (!config?.enabled || !/^phc_[A-Za-z0-9]+$/.test(config.projectToken || "") ||
      config.apiHost !== "https://us.i.posthog.com" || navigator.doNotTrack === "1" || navigator.globalPrivacyControl === true) return;

  // Rebuild ordinary event properties, dropping SDK-added referrers, campaigns,
  // DOM text, and future accidental properties. Replay data has already passed
  // the recorder masking/blocking configuration below and must stay intact.
  function beforeSend(event) {
    if (!event || (event.event !== "$snapshot" && !schemas[event.event])) return null;
    const original = event.properties || {};
    const properties = event.event === "$snapshot" ? baseProperties() : safeProperties(event.event, original);
    ["token", "distinct_id", "$device_id", "$session_id", "$window_id", "$lib", "$lib_version", "$time", "$sent_at", "$is_identified", "$process_person_profile"].forEach((key) => {
      if (["string", "number", "boolean"].includes(typeof original[key])) properties[key] = original[key];
    });
    if (event.event === "$snapshot") {
      ["$snapshot_data", "$snapshot_bytes", "$snapshot_method"].forEach((key) => {
        if (Object.prototype.hasOwnProperty.call(original, key)) properties[key] = original[key];
      });
    }
    // Preserve the mode at the time of a queued event, not a later selected mode.
    if (["sample", "live"].includes(original.app_mode) && surface === "local_app") properties.app_mode = original.app_mode;
    event.properties = properties;
    return event;
  }

  const options = {
    api_host: config.apiHost,
    asset_host: "https://us-assets.i.posthog.com",
    defaults: "2025-11-30",
    strict_script_versioning: true,
    persistence: "memory",
    disable_persistence: true,
    person_profiles: "never",
    ip: false,
    respect_dnt: true,
    save_referrer: false,
    save_campaign_params: false,
    disable_capture_url_hashes: true,
    autocapture: false,
    capture_pageview: false,
    capture_pageleave: false,
    capture_dead_clicks: false,
    rageclick: false,
    capture_heatmaps: false,
    enable_heatmaps: false,
    capture_exceptions: false,
    capture_performance: false,
    enable_recording_console_log: false,
    logs: { captureConsoleLogs: false },
    metrics: { network: false },
    disable_surveys: true,
    disable_product_tours: true,
    disable_conversations: true,
    disable_web_experiments: true,
    opt_in_site_apps: false,
    advanced_disable_feature_flags: true,
    mask_all_text: true,
    mask_all_element_attributes: true,
    disable_session_recording: false,
    session_recording: {
      maskAllInputs: true,
      maskTextSelector: "*",
      maskInputFn: () => "[hidden]",
      maskTextFn: (text) => text.trim() ? "[hidden]" : "",
      blockSelector: ".ph-no-capture, [data-analytics-private], img, video, canvas",
      recordCanvas: false,
      recordBody: false,
      recordHeaders: false,
      captureJsonLd: false,
      // Replay Meta events call this with only {name}; null would drop their
      // viewport metadata. Keep a fixed URL and none of the original fields.
      maskCapturedNetworkRequestFn: () => ({ name: canonicalURL })
    },
    before_send: beforeSend,
    on_request_error: () => {},
    loaded(instance) {
      sdk = instance;
      try {
        instance.register(baseProperties());
        const pending = queue;
        queue = [];
        pending.forEach(([name, properties]) => instance.capture(name, properties));
      } catch (_) { /* A blocked analytics request must not interrupt the app. */ }
    }
  };

  document.addEventListener("click", (event) => {
    const target = event.target?.closest?.("button, a");
    if (!target || target.disabled) return;
    const control = surface === "local_app" ? controls[target.id] : productLinks[target.getAttribute("href")];
    if (control) track("ui_click", { control });
  }, { capture: true }); // Observe the click before app handlers disable busy controls.
  track("$pageview");

  // Official snippet queue shape. The SDK loads asynchronously; app.js does not
  // wait for it, and pre-load events contain only the allowlisted fields above.
  const stub = [];
  stub._i = [[config.projectToken, options, "posthog"]];
  stub.__SV = 1;
  window.posthog = stub;
  const script = document.createElement("script");
  script.async = true;
  script.crossOrigin = "anonymous";
  script.referrerPolicy = "no-referrer";
  script.src = "https://us-assets.i.posthog.com/static/array.js";
  script.onerror = () => { queue = []; };
  document.head.append(script);
})();
