/* Story studio: personal material stays in server memory until explicitly exported. */
(() => {
  "use strict";
  const el = id => document.getElementById(id);
  const show = (id, value) => { el(id).hidden = !value; };
  const text = (id, value) => { el(id).textContent = value || ""; };
  const make = (tag, value, className) => {
    const item = document.createElement(tag);
    if (value !== undefined) item.textContent = value;
    if (className) item.className = className;
    return item;
  };
  const kinds = { core: "Core narrative", origin: "Origin story", anecdote: "Anecdote", adaptation: "For this context" };
  const reflectionLabels = { situation: "The situation", action: "Your contribution", outcome: "What happened", learning: "What it meant to you" };
  let config = null, state = null, version = 0, selectedId = null, editingId = null;
  let busy = false, needsRecovery = false, serverWorking = false, legacyPresent = false;
  let experienceDirty = false, coreDirty = false, reviewDirty = false, importDirty = false, contextDirty = false;

  function track(action, kind) {
    try { window.AIAnalytics?.track("studio_progress", { action, ...(kind ? { kind } : {}) }); } catch (_) {}
  }
  function announce(message) { text("status", message); }
  function displayError(message) { text("error-message", message); show("error", true); announce(message); }
  function confirmInPage(message, accept = "Continue") {
    const dialog = el("confirmation");
    if (dialog.open) return Promise.resolve(false);
    text("confirmation-message", message);
    text("confirmation-accept", accept);
    dialog.returnValue = "cancel";
    return new Promise(resolve => {
      const cancel = event => { event.preventDefault(); dialog.close("cancel"); };
      const close = () => {
        dialog.removeEventListener("cancel", cancel);
        dialog.removeEventListener("close", close);
        resolve(dialog.returnValue === "confirm");
      };
      dialog.addEventListener("cancel", cancel);
      dialog.addEventListener("close", close);
      dialog.showModal();
    });
  }
  const dirty = () => experienceDirty || coreDirty || reviewDirty || importDirty || contextDirty;
  async function discardUnsaved() {
    if (!(experienceDirty || coreDirty || reviewDirty || importDirty)) return true;
    if (!(await confirmInPage("You have wording that has not been saved. Continue without those changes? Your last saved library stays.", "Continue without changes"))) return false;
    experienceDirty = coreDirty = reviewDirty = importDirty = false;
    show("experience-form", false); show("core-form", false);
    render();
    return true;
  }
  async function request(path, data, multipart = false) {
    const controller = new AbortController();
    const options = { credentials: "same-origin", cache: "no-store", signal: controller.signal };
    if (data !== undefined) {
      options.method = "POST";
      options.headers = { "X-Coach-Request": "1" };
      if (multipart) options.body = data;
      else { options.headers["Content-Type"] = "application/json"; options.body = JSON.stringify(data); }
    }
    const timer = window.setTimeout(() => controller.abort(), 90000);
    try {
      const response = await fetch(path, options);
      let result;
      try { result = await response.json(); } catch (_) {
        if (data !== undefined) needsRecovery = true;
        throw new Error("The response could not be read. Your text is still here. Reload saved progress before sending another request.");
      }
      if (!response.ok) {
        if (response.status === 409) needsRecovery = true;
        const message = typeof result.error === "string" ? result.error : "That step could not be completed.";
        const retry = response.status === 429 ? response.headers.get("Retry-After") : null;
        throw new Error(message + (retry && /^\d+$/.test(retry) ? ` Try again in about ${Math.ceil(Number(retry) / 60)} minute(s).` : "") + (response.status === 409 ? " Your unsaved text is still here. Reload the saved library before continuing." : ""));
      }
      return result;
    } catch (error) {
      if (error.name === "AbortError" || error instanceof TypeError) {
        if (data !== undefined) needsRecovery = true;
        throw new Error("The connection did not finish. The server may still be working. Your text is still here; reload saved progress before trying again. No retry was sent.");
      }
      throw error;
    } finally { window.clearTimeout(timer); }
  }
  function updateControls() {
    const locked = busy || !config || needsRecovery || serverWorking;
    document.querySelectorAll("#studio-body button, #studio-body input, #studio-body textarea, #studio-body select").forEach(control => { control.disabled = busy || !config; });
    el("recover").disabled = busy;
    const sample = state?.mode === "sample", pending = Boolean(state?.pending), importing = Boolean(state?.import_review?.length);
    const selected = state?.experiences?.find(item => item.id === selectedId);
    const aiReady = Boolean(state && (sample || config?.live_ready));
    ["start-own", "start-sample", "start-restore", "restore", "reset"].forEach(id => { el(id).disabled = locked; });
    el("start-upload").disabled = locked || !config?.live_ready;
    ["new-experience", "upload", "edit-experience", "write-core"].forEach(id => { el(id).disabled = locked || sample || pending || importing; });
    el("new-experience").disabled ||= (state?.experiences?.length || 0) >= 6;
    el("upload").disabled ||= !config?.live_ready || (state?.experiences?.length || 0) >= 6;
    el("edit-experience").disabled ||= !selected;
    el("draft-core").disabled = locked || !aiReady || pending || importing || !state?.experiences?.length;
    el("draft-origin").disabled = locked || !aiReady || pending || importing || !selected;
    el("draft-anecdote").disabled = locked || !aiReady || pending || importing || !selected;
    el("draft-adaptation").disabled = locked || !aiReady || pending || importing || !el("context-origin").value || !el("context-audience").value.trim();
    el("save-experience").disabled = locked || sample || pending || importing;
    el("keep-draft").disabled = locked || !pending;
    el("omit-draft").disabled = locked || !pending;
    el("core-form").querySelector('button[type="submit"]').disabled = locked || sample || pending || importing;
    el("import-form").querySelector('button[type="submit"]').disabled = locked || !importing;
    ["review-name", "review-text", "review-angle", "review-question"].forEach(id => { el(id).readOnly = Boolean(sample); });
    el("export").setAttribute("aria-disabled", String(!state || busy || importing || serverWorking));
    el("library").setAttribute("aria-busy", String(busy || serverWorking));
    show("working", busy || serverWorking);
    if (!busy && serverWorking) text("working-message", "The server is still finishing your previous request. Use “Reload saved library” to check for the result.");
  }
  async function perform(action, message = "Saving your library…") {
    if (busy) return;
    busy = true; show("error", false); text("working-message", message); updateControls();
    try { await action(); } catch (error) { displayError(error.message); }
    finally { busy = false; updateControls(); }
  }
  function acceptState(next, message = "Saved to your library.") {
    state = next; version = next.version; legacyPresent = false; needsRecovery = serverWorking = false;
    if (state.pending?.kind === "adaptation") contextDirty = false;
    if (!state.experiences.some(item => item.id === selectedId)) selectedId = state.experiences[0]?.id || null;
    experienceDirty = coreDirty = reviewDirty = importDirty = false;
    show("experience-form", false); show("core-form", false);
    render();
    try { window.AIAnalytics?.setMode(state.mode); } catch (_) {}
    announce(message);
  }
  function evidenceNode(evidence) {
    const container = make("div");
    if (!evidence?.length) { container.append(make("p", "This wording was written by you. It has no AI evidence check.", "small")); return container; }
    evidence.forEach(item => {
      const entry = make("div", undefined, "evidence-item");
      const id = String(item.source_id || "").split(":")[0];
      const source = state?.experiences.find(experience => experience.id === id);
      entry.append(make("small", source?.title || "Reviewed source material"), make("p", item.quote || ""));
      container.append(entry);
    });
    return container;
  }
  function renderArtifacts(containerId, items, type) {
    const container = el(containerId); container.replaceChildren();
    if (!items?.length) {
      container.append(make("p", type === "origin" ? "Choose an experience and find an origin story. You can keep several different starting points." : type === "anecdote" ? "Unpack one experience, then shape a specific moment into an anecdote." : "Your reviewed versions will appear here.", "small"));
      return;
    }
    items.slice().reverse().forEach(item => {
      const card = make("article", undefined, "artifact-card");
      if (type === "origin" && item.id === el("context-origin").value) card.classList.add("is-selected");
      card.append(make("span", item.status === "needs_review" ? "Source changed · needs review" : "Kept by you", "badge " + (item.status === "needs_review" ? "stale" : "kept")), make("h3", item.title), make("p", item.text, "artifact-text"));
      if (item.context) card.append(make("p", [item.context.audience, item.context.setting].filter(Boolean).join(" · "), "context-caption"));
      if (item.angle) { const angle = make("div", undefined, "artifact-angle"); angle.append(make("strong", "Experience emphasis"), make("p", item.angle)); card.append(angle); }
      if (item.question) { const question = make("div", undefined, "artifact-question"); question.append(make("strong", "Bring this question"), make("p", item.question)); card.append(question); }
      const evidence = make("details", undefined, "evidence"); evidence.append(make("summary", "Supporting words"), evidenceNode(item.evidence)); card.append(evidence);
      if (type === "origin" && item.status === "kept") {
        const choose = make("button", "Use this origin", "text-button"); choose.type = "button";
        choose.addEventListener("click", () => { el("context-origin").value = item.id; renderArtifacts("origins", state.origins, "origin"); updateControls(); el("context-audience").focus(); });
        card.append(choose);
      }
      if (item.status === "needs_review") card.append(make("p", "This version stays in your record but won’t be used for new drafts. Generate a fresh version from the updated material.", "small"));
      container.append(card);
    });
  }
  function renderExperience() {
    const list = el("experience-tabs"); list.replaceChildren();
    state.experiences.forEach(item => {
      const button = make("button", item.title, "experience-tab"); button.type = "button"; button.setAttribute("aria-pressed", String(item.id === selectedId));
      button.addEventListener("click", async () => { if (busy || !(await discardUnsaved())) return; selectedId = item.id; renderExperience(); updateControls(); });
      list.append(button);
    });
    const item = state.experiences.find(experience => experience.id === selectedId);
    show("empty-experiences", !state.experiences.length); show("experience-display", Boolean(item));
    if (!item) return;
    text("experience-title", item.title); text("experience-details", item.details);
    const source = el("experience-source"); source.replaceChildren();
    if (item.origin === "document" && item.evidence) {
      source.append(make("p", item.user_edited ? "Reviewed PDF experience · summary edited by you" : "Reviewed PDF experience"));
      const details = make("details"); details.append(make("summary", `Original supporting text · page ${item.evidence.page}`), make("blockquote", item.evidence.text)); source.append(details);
    } else source.append(make("p", state.mode === "sample" ? "Fictional example" : "Your own description"));
    const reflections = el("reflection-summary"); reflections.replaceChildren();
    Object.entries(reflectionLabels).forEach(([key, label]) => {
      if (!item.reflection?.[key]) return;
      const section = make("div"); section.append(make("h4", label), make("p", item.reflection[key])); reflections.append(section);
    });
  }
  function renderImport() {
    const cards = state?.import_review || []; show("import-panel", cards.length > 0);
    const container = el("import-cards"); container.replaceChildren();
    text("import-description", state?.import_document ? `Suggested experiences from ${state.import_document}` : "Suggested experiences from your document");
    cards.forEach((card, index) => {
      const article = make("article", undefined, "import-card"); article.dataset.cardId = card.id;
      const check = make("input"); check.type = "checkbox"; check.checked = true; check.dataset.field = "include";
      const label = make("label", undefined, "check-label"); label.append(check, make("span", "Keep this experience")); article.append(label);
      [["title", "A short name", 120], ["details", "Experience summary", 600]].forEach(([field, labelText, maximum]) => {
        const id = `import-${index}-${field}`, label = make("label", labelText), input = make(field === "title" ? "input" : "textarea");
        label.htmlFor = id; input.id = id; input.maxLength = maximum; input.dataset.field = field; input.value = card[field] || "";
        if (field === "title") input.type = "text"; else input.rows = 3;
        article.append(label, input);
      });
      const details = make("details", undefined, "evidence"); details.append(make("summary", `Check the source · page ${card.evidence?.page || "?"}`), make("blockquote", card.evidence?.text || "")); article.append(details); container.append(article);
    });
  }
  function renderReview() {
    const pending = state?.pending; show("review-panel", Boolean(pending));
    if (!pending) return;
    text("review-kind", kinds[pending.kind] || "Draft");
    el("review-name").value = pending.title || ""; el("review-text").value = pending.text || "";
    el("review-angle").value = pending.angle || ""; el("review-question").value = pending.question || "";
    show("review-adaptation", pending.kind === "adaptation");
    el("review-evidence").replaceChildren(evidenceNode(pending.evidence));
  }
  function render() {
    document.body.classList.toggle("has-library", Boolean(state));
    document.querySelector(".hero h1").replaceChildren(document.createTextNode("Your story,"), state ? document.createTextNode(" ") : document.createElement("br"), document.createTextNode("connected."));
    show("studio-body", Boolean(config)); show("loading", !config); show("welcome", !state); show("library", Boolean(state)); show("legacy-warning", legacyPresent);
    if (!state) { updateControls(); return; }
    show("sample-note", state.mode === "sample"); show("ai-unavailable", state.mode !== "sample" && !config.live_ready);
    text("mode-label", state.mode === "sample" ? "FICTIONAL STORY LIBRARY" : "YOUR STORY LIBRARY");
    text("core-text", state.core?.text || "What connects your experiences, interests, and direction? Start with an experience; let the thread emerge.");
    text("core-status", state.core?.status === "needs_review" ? "Material changed · revisit this" : state.core ? "Kept by you" : "To discover");
    renderExperience(); renderImport(); renderReview();
    const previous = el("context-origin").value, picker = el("context-origin"); picker.replaceChildren();
    const validOrigins = (state.origins || []).filter(item => item.status === "kept");
    if (!validOrigins.length) { const option = make("option", "Keep an origin story first"); option.value = ""; picker.append(option); }
    validOrigins.forEach(item => { const option = make("option", item.title); option.value = item.id; picker.append(option); });
    if (validOrigins.some(item => item.id === previous)) picker.value = previous;
    renderArtifacts("origins", state.origins, "origin"); renderArtifacts("anecdotes", state.anecdotes, "anecdote"); renderArtifacts("adaptations", state.adaptations, "adaptation");
    updateControls();
  }
  async function begin(mode, after) {
    if (busy || needsRecovery || serverWorking) return;
    if (legacyPresent || state) {
      if (!(await confirmInPage("Starting a new library replaces this session’s saved work. Export it first if you want to keep a copy. Unsaved typing will also be cleared.", "Start new library"))) return;
    }
    let started = false;
    await perform(async () => {
      acceptState(await request("/api/studio/start", { version, mode, replace: Boolean(legacyPresent || state) }), "Your library is ready.");
      el("context-audience").value = ""; el("context-purpose").value = ""; contextDirty = false;
      started = true;
    }, "Opening your library…");
    if (started && after) after();
  }
  function openExperience(item = null) {
    editingId = item?.id || null;
    el("experience-name").value = item?.title || ""; el("experience-description").value = item?.details || "";
    Object.keys(reflectionLabels).forEach(key => { el(`reflection-${key}`).value = item?.reflection?.[key] || ""; });
    el("reflection-fields").open = Boolean(item); experienceDirty = false;
    show("experience-form", true); show("edit-warning", Boolean(item));
    el("experience-name").focus(); updateControls();
  }
  async function generate(kind) {
    if (busy || needsRecovery || serverWorking || !state || !(await discardUnsaved())) return;
    const data = { version, kind };
    if (kind === "origin" || kind === "anecdote") {
      const collection = kind === "origin" ? state.origins : state.anecdotes;
      if (collection.some(item => item.experience_id === selectedId) && !(await confirmInPage("You already have an " + (kind === "origin" ? "origin story" : "anecdote") + " for this experience. You can review a new draft first. Keeping it will replace the earlier version; export your library first if you want both.", "Draft a new version"))) return;
      data.experience_id = selectedId;
    }
    if (kind === "adaptation") {
      data.origin_id = el("context-origin").value;
      data.context = { audience: el("context-audience").value.trim(), setting: el("context-setting").value, purpose: el("context-purpose").value.trim() };
    }
    await perform(async () => {
      track("draft_requested", kind);
      acceptState(await request("/api/studio/generate", data), "Your draft is ready to review.");
      el("review-panel").scrollIntoView({ behavior: "auto", block: "start" }); el("review-text").focus();
    }, state.mode === "sample" ? "Preparing the fictional draft…" : "Connecting your words into a draft. You’ll review it before keeping it…");
  }
  async function chooseUpload() {
    if (busy || needsRecovery || serverWorking || !(await discardUnsaved())) return;
    if (!state) await begin("live", () => { el("pdf-file").value = ""; el("pdf-file").click(); });
    else { el("pdf-file").value = ""; el("pdf-file").click(); }
  }
  async function loadSaved() {
    if (dirty() && !(await confirmInPage("Reloading saved progress will replace unsaved typing with the last server version. Copy any text you want to keep before continuing.", "Reload saved library"))) return;
    await perform(async () => {
      if (!config) config = await request("/api/studio/config");
      const saved = await request("/api/studio/state");
      state = saved.state; version = saved.current_version; legacyPresent = saved.legacy_present; serverWorking = Boolean(saved.working); needsRecovery = false;
      experienceDirty = coreDirty = reviewDirty = importDirty = false; show("experience-form", false); show("core-form", false);
      if (state && !state.experiences.some(item => item.id === selectedId)) selectedId = state.experiences[0]?.id || null;
      render();
      if (serverWorking) displayError("Your previous request is still running. Check saved progress again shortly; no new AI request has been sent.");
      else announce("Saved progress reloaded.");
    }, "Reloading saved progress…");
  }

  el("start-own").addEventListener("click", () => begin("live", () => openExperience()));
  el("start-sample").addEventListener("click", () => begin("sample"));
  el("start-upload").addEventListener("click", chooseUpload); el("upload").addEventListener("click", chooseUpload);
  el("recover").addEventListener("click", loadSaved);
  el("new-experience").addEventListener("click", async () => { if (await discardUnsaved()) openExperience(); });
  el("edit-experience").addEventListener("click", async () => { if (await discardUnsaved()) openExperience(state.experiences.find(item => item.id === selectedId)); });
  el("cancel-experience").addEventListener("click", async () => { if (experienceDirty && !(await confirmInPage("Discard the unsaved changes to this experience?", "Discard changes"))) return; experienceDirty = false; show("experience-form", false); updateControls(); });
  el("experience-form").addEventListener("input", () => { experienceDirty = true; });
  el("experience-form").addEventListener("submit", async event => {
    event.preventDefault();
    const data = { version, title: el("experience-name").value.trim(), details: el("experience-description").value.trim(), reflection: Object.fromEntries(Object.keys(reflectionLabels).map(key => [key, el(`reflection-${key}`).value.trim()])) };
    if (editingId) data.id = editingId;
    const hasDependentStories = editingId && (state.core || [...state.origins, ...state.anecdotes, ...state.adaptations].some(item => item.experience_id === editingId));
    if (experienceDirty && hasDependentStories && !(await confirmInPage("Saving this changed experience marks its related stories for review. Earlier wording stays in your record, but new drafts will use the updated material.", "Save and mark for review"))) return;
    await perform(async () => {
      const next = await request("/api/studio/experience", data);
      selectedId = editingId || next.experiences[next.experiences.length - 1]?.id;
      acceptState(next); track("experience_saved");
    });
  });
  el("write-core").addEventListener("click", async () => { if (!(await discardUnsaved())) return; el("core-input").value = state.core?.text || ""; coreDirty = false; show("core-form", true); el("core-input").focus(); });
  el("core-input").addEventListener("input", () => { coreDirty = true; });
  el("cancel-core").addEventListener("click", async () => { if (coreDirty && !(await confirmInPage("Discard the unsaved core narrative wording?", "Discard changes"))) return; coreDirty = false; show("core-form", false); });
  el("core-form").addEventListener("submit", async event => { event.preventDefault(); await perform(async () => { acceptState(await request("/api/studio/core", { version, text: el("core-input").value.trim() })); track("core_saved"); }); });
  el("draft-core").addEventListener("click", () => generate("core"));
  el("draft-origin").addEventListener("click", () => generate("origin"));
  el("draft-anecdote").addEventListener("click", () => generate("anecdote"));
  el("context-form").addEventListener("input", () => { contextDirty = true; updateControls(); });
  document.querySelectorAll("[data-audience]").forEach(button => button.addEventListener("click", () => {
    el("context-audience").value = button.dataset.audience;
    if (button.textContent === "LinkedIn") el("context-setting").value = "LinkedIn profile";
    contextDirty = true; updateControls();
  }));
  el("import-form").addEventListener("input", () => { importDirty = true; });
  el("context-origin").addEventListener("change", () => { renderArtifacts("origins", state.origins, "origin"); updateControls(); });
  el("context-form").addEventListener("submit", event => { event.preventDefault(); generate("adaptation"); });
  el("review-form").addEventListener("input", () => { reviewDirty = true; });
  el("review-form").addEventListener("submit", async event => {
    event.preventDefault(); const kind = state.pending.kind, data = { version, decision: "keep" };
    if (state.mode !== "sample") {
      data.title = el("review-name").value.trim(); data.text = el("review-text").value.trim();
      if (kind === "adaptation") { data.angle = el("review-angle").value.trim(); data.question = el("review-question").value.trim(); }
    }
    await perform(async () => { acceptState(await request("/api/studio/review", data), "Version kept. You can use it in your story library."); track("draft_reviewed", kind); });
  });
  el("omit-draft").addEventListener("click", async () => { const kind = state.pending.kind; if (reviewDirty && !(await confirmInPage("Leave out this draft and your unsaved edits? Your experiences stay in the library.", "Leave out draft"))) return; await perform(async () => { acceptState(await request("/api/studio/review", { version, decision: "omit" })); track("draft_reviewed", kind); }); });
  el("pdf-file").addEventListener("change", async () => {
    const file = el("pdf-file").files[0]; if (!file) return;
    if (file.size > (config?.document_limits?.max_bytes || 5 * 1024 * 1024) || !file.name.toLowerCase().endsWith(".pdf")) { displayError("Choose one PDF up to 5 MB with selectable text, or add an experience yourself."); return; }
    const form = new FormData(); form.append("file", file); form.append("version", String(version));
    await perform(async () => { acceptState(await request("/api/studio/documents", form, true), "Review the suggested experiences before adding them."); el("import-panel").scrollIntoView({ behavior: "auto", block: "start" }); }, "Reading your PDF and finding experience cards to review…");
  });
  el("import-form").addEventListener("submit", async event => {
    event.preventDefault();
    const cards = [...el("import-cards").querySelectorAll(".import-card")].map(card => ({ id: card.dataset.cardId, include: card.querySelector('[data-field="include"]').checked, title: card.querySelector('[data-field="title"]').value.trim(), details: card.querySelector('[data-field="details"]').value.trim() }));
    await perform(async () => { acceptState(await request("/api/studio/documents/review", { version, cards })); track("import_reviewed"); });
  });
  ["start-restore", "restore"].forEach(id => el(id).addEventListener("click", () => { el("restore-file").value = ""; el("restore-file").click(); }));
  el("restore-file").addEventListener("change", async () => {
    const file = el("restore-file").files[0]; if (!file) return;
    if (file.size > 200000) { displayError("Choose a story-library export up to 200 KB."); return; }
    let payload;
    try { payload = JSON.parse(await file.text()); } catch (_) { displayError("That file is not readable JSON. Choose a story-library export."); return; }
    if (payload?.format !== "ai-coach-story-studio-v1") { displayError("Choose an export from the story studio. Earlier workshop exports are reference records and cannot be restored here."); return; }
    if ((state || legacyPresent || dirty()) && !(await confirmInPage("Restoring this file replaces the current session’s library and any unsaved typing. Export your current library first if you want to keep it.", "Restore this library"))) return;
    await perform(async () => { acceptState(await request("/api/studio/restore", { version, payload, replace: Boolean(state || legacyPresent) })); track("restored"); }, "Checking and restoring your library…");
  });
  el("export").addEventListener("click", async event => {
    if (el("export").getAttribute("aria-disabled") === "true") { event.preventDefault(); return; }
    if (dirty() || state?.pending) { event.preventDefault(); if (await confirmInPage("This export contains kept experiences and stories. Unsaved typing and the draft awaiting review are left out. Export the kept library?", "Export kept library")) { track("exported"); window.location.assign("/api/studio/export"); } }
    else track("exported");
  });
  el("reset").addEventListener("click", async () => {
    if (!(await confirmInPage("Starting over clears this session’s library. Export it first to keep a copy you can restore. This will also clear unsaved typing.", "Start over"))) return;
    await perform(async () => { await request("/api/reset", {}); state = null; selectedId = null; experienceDirty = coreDirty = reviewDirty = importDirty = false; const saved = await request("/api/studio/state"); version = saved.current_version; legacyPresent = saved.legacy_present; needsRecovery = serverWorking = false; contextDirty = false; el("context-audience").value = ""; el("context-purpose").value = ""; render(); announce("Ready for a new library."); });
  });
  window.addEventListener("beforeunload", event => { if (dirty() || busy) { event.preventDefault(); event.returnValue = ""; } });
  loadSaved();
})();
