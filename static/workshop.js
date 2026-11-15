/* Server-memory workshop. Personal content is never stored in browser storage. */
(() => {
  "use strict";
  const el = (id) => document.getElementById(id);
  const show = (id, visible) => { el(id).hidden = !visible; };
  const text = (id, value) => { el(id).textContent = value || ""; };
  const node = (tag, value, className) => {
    const result = document.createElement(tag);
    if (value !== undefined) result.textContent = value;
    if (className) result.className = className;
    return result;
  };
  const kinds = { root: "Roots · what matters", ingredient: "Ingredients to carry forward", future_ingredient: "Ingredients to develop", direction: "Possible contributions", theme: "Possible connections" };
  let config = null;
  let state = null;
  let currentVersion = 0;
  let imported = [];
  let legacyPresent = false;
  let mode = "live";
  let useImported = false;
  let selectedImported = new Set();
  let manual = [{ title: "", details: "" }];
  let decisions = {};
  let busy = false;
  let renderedVersion = null;

  function confirmInPage(message, confirmLabel = "Continue") {
    const dialog = el("workshop-confirm");
    // A second click must not queue another destructive confirmation.
    if (dialog.open) return Promise.resolve(false);
    text("workshop-confirm-message", message);
    text("workshop-confirm-accept", confirmLabel);
    dialog.returnValue = "cancel";
    return new Promise((resolve) => {
      const cancel = (event) => { event.preventDefault(); dialog.close("cancel"); };
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

  async function request(path, data) {
    const controller = new AbortController();
    const options = { credentials: "same-origin", cache: "no-store", signal: controller.signal };
    if (data !== undefined) {
      options.method = "POST";
      options.headers = { "Content-Type": "application/json", "X-Coach-Request": "1" };
      options.body = JSON.stringify(data);
    }
    const timer = window.setTimeout(() => controller.abort(), 90000);
    try {
      const response = await fetch(path, options);
      let result;
      try { result = await response.json(); } catch (_) { throw new Error("The workshop returned an unreadable response. Your saved progress is unchanged."); }
      if (!response.ok) throw new Error(typeof result.error === "string" ? result.error : "That step could not be completed. Please try again.");
      return result;
    } catch (error) {
      if (error.name === "AbortError") throw new Error("This step took too long. Reload saved progress before retrying; the server may still be finishing it.");
      if (error instanceof TypeError) throw new Error("The local workshop could not be reached. Check that the server is still running.");
      throw error;
    } finally { window.clearTimeout(timer); }
  }

  function announce(message) { text("workshop-status", message); }
  function displayError(message) { text("error-message", message); show("workshop-error", true); announce(message); }
  function updateControls() {
    document.querySelectorAll("#workshop-body button, #workshop-body input, #workshop-body textarea").forEach((control) => { control.disabled = busy || !config; });
    el("personal-mode").disabled = busy || !config || Boolean(state) || mode === "live" || config.available === false;
    el("sample-mode").disabled = busy || !config || Boolean(state) || mode === "sample";
    const manualValid = manual.length > 0 && manual.every((item) => item.title.trim() && item.details.trim());
    el("start-workshop").disabled = busy || !config || Boolean(state) || (mode === "live" && (config.available === false || !(useImported ? selectedImported.size : manualValid)));
    el("add-experience").disabled = busy || manual.length >= 3;
    el("save-answer").disabled = busy || !state || state.phase !== "reflect" || !el("reflection-answer").value.trim();
    el("skip-answer").disabled = busy || !state || state.phase !== "reflect";
    el("synthesize-ai").disabled = busy || !config || !config.live_ready || !state || state.phase !== "synthesize";
    el("synthesize-own").disabled = busy || !state || state.phase !== "synthesize";
    const completeDecisions = state && (state.proposals || []).every((item) => decisions[item.id] && (decisions[item.id].decision !== "edit" || decisions[item.id].wording.trim()));
    el("save-review").disabled = busy || !state || state.phase !== "review" || !completeDecisions;
    el("recover-workshop").disabled = busy;
    el("workshop-conversation").setAttribute("aria-busy", String(busy));
    show("workshop-working", busy);
    text("reflection-count", `${el("reflection-answer").value.length.toLocaleString()} / 1,200`);
  }

  async function perform(action, message = "Saving your progress…") {
    if (busy) return;
    busy = true;
    show("workshop-error", false);
    text("working-message", message);
    updateControls();
    try { await action(); } catch (error) { displayError(error.message); }
    finally { busy = false; updateControls(); }
  }

  function acceptState(next) {
    state = next;
    currentVersion = next.version;
    mode = next.mode;
    legacyPresent = false;
    render();
    try {
      window.AIAnalytics?.setMode(state.mode);
      const properties = { phase: state.phase };
      const stepId = config.steps[state.step_index]?.id;
      if (stepId) properties.step = stepId;
      window.AIAnalytics?.track("workshop_progress", properties);
    } catch (_) {}
    const heading = el({ reflect: "reflection-title", synthesize: "synthesis-title", review: "review-title", complete: "complete-title" }[state.phase]);
    if (heading) heading.focus();
    announce(state.phase === "complete" ? "Your reviewed workshop is ready to export." : "Progress saved.");
  }

  function renderManual() {
    const container = el("manual-cards");
    container.replaceChildren();
    manual.forEach((item, index) => {
      const field = node("fieldset", undefined, "workshop-entry");
      field.append(node("legend", `Experience ${index + 1}`));
      [["title", "A short name", 120], ["details", "What you did or experienced", 1200]].forEach(([key, labelText, limit]) => {
        const label = node("label", labelText);
        const input = node(key === "title" ? "input" : "textarea");
        if (key === "title") input.type = "text";
        input.id = `manual-${index}-${key}`;
        input.maxLength = limit;
        input.value = item[key];
        label.htmlFor = input.id;
        input.addEventListener("input", () => { item[key] = input.value; updateControls(); });
        field.append(label, input);
      });
      if (manual.length > 1) {
        const remove = node("button", "Remove this experience", "button button-small button-quiet");
        remove.type = "button";
        remove.addEventListener("click", () => { manual.splice(index, 1); renderManual(); updateControls(); });
        field.append(remove);
      }
      container.append(field);
    });
  }

  function renderImported() {
    const container = el("imported-cards");
    container.replaceChildren();
    imported.forEach((item) => {
      const card = node("div", undefined, "workshop-entry");
      const label = node("label", undefined, "workshop-choice");
      const checkbox = node("input");
      checkbox.type = "checkbox";
      checkbox.checked = selectedImported.has(item.id);
      checkbox.addEventListener("change", () => { checkbox.checked ? selectedImported.add(item.id) : selectedImported.delete(item.id); updateControls(); });
      label.append(checkbox, node("span", item.title));
      card.append(label, node("p", item.details, "small-copy"));
      if (item.user_edited) card.append(node("small", "Edited and approved by you."));
      container.append(card);
    });
  }

  function renderStart() {
    show("legacy-note", legacyPresent);
    show("sample-intro", mode === "sample");
    show("experience-inputs", mode !== "sample");
    show("start-disclosure", mode !== "sample");
    show("availability-note", config.available === false);
    text("availability-note", config.error || "The book workshop's private source notes are not configured. You can still explore the fictional example.");
    show("experience-choice", imported.length > 0);
    show("imported-cards", useImported);
    show("manual-cards", !useImported);
    show("add-experience", !useImported);
    el("use-imported").setAttribute("aria-pressed", String(useImported));
    el("use-manual").setAttribute("aria-pressed", String(!useImported));
    text("start-workshop", mode === "sample" ? "Try the fictional workshop →" : "Use these experiences →");
    renderManual();
    renderImported();
  }

  function methodReferences(ids) {
    return (config.method.references || []).filter((reference) => (ids || []).includes(reference.id));
  }
  function referenceLabel(reference) { return `${reference.title} — ${reference.locator}`; }
  function evidenceLabel(reference) {
    const step = config.steps.find((item) => item.id === reference || `reflection:${item.id}` === reference);
    if (step) return `Your reflection: ${step.title}`;
    const experience = (state.accepted_experiences || []).find((item) => item.id === reference || `experience:${item.id}` === reference);
    return experience ? `Chosen experience: ${experience.title}` : "Your submitted words";
  }

  function renderProposals() {
    const container = el("proposal-cards");
    container.replaceChildren();
    decisions = {};
    const proposals = state.proposals || [];
    show("empty-proposals", proposals.length === 0);
    proposals.forEach((item, index) => {
      const field = node("fieldset", undefined, "workshop-entry");
      field.append(node("legend", kinds[item.kind] || "Proposed addition"), node("p", item.wording));
      if (item.origin === "user" || item.authorship === "user_words" || item.user_authored) field.append(node("p", "In your own words.", "small-copy"));
      const evidence = node("div", undefined, "workshop-evidence");
      evidence.append(node("h4", "Supporting personal words"));
      (item.evidence || []).forEach((quote) => { evidence.append(node("blockquote", quote.text), node("cite", evidenceLabel(quote.ref_id))); });
      field.append(evidence, node("p", `Method: ${methodReferences(item.method_ids).map(referenceLabel).join("; ")}`, "workshop-method"));
      const choices = node("div", undefined, "review-decisions");
      const editLabel = node("label", "Your wording");
      const editor = node("textarea");
      editor.id = `proposal-edit-${index}`;
      editor.maxLength = 1200;
      editor.value = item.wording;
      editLabel.htmlFor = editor.id;
      editor.hidden = editLabel.hidden = true;
      const editNote = node("p", "Edits are your own wording. The original evidence is kept for comparison and may not support every change.", "small-copy");
      editNote.hidden = true;
      [["accept", "Keep"], ["edit", "Edit"], ["reject", "Leave out"]].forEach(([value, labelText]) => {
        const label = node("label");
        const radio = node("input");
        radio.type = "radio";
        radio.name = `decision-${index}`;
        radio.value = value;
        radio.addEventListener("change", () => {
          decisions[item.id] = { id: item.id, decision: value, wording: editor.value };
          editor.hidden = editLabel.hidden = editNote.hidden = value !== "edit";
          updateControls();
          if (value === "edit") editor.focus();
        });
        label.append(radio, node("span", labelText));
        choices.append(label);
      });
      editor.addEventListener("input", () => { if (decisions[item.id]) decisions[item.id].wording = editor.value; updateControls(); });
      field.append(choices, editLabel, editor, editNote);
      container.append(field);
    });
  }

  function landscapeSection(title, items, renderItem) {
    const section = node("section", undefined, "workshop-landscape-section");
    section.append(node("h3", title));
    const list = node("ul");
    items.forEach((item) => { const li = node("li"); renderItem(li, item); list.append(li); });
    section.append(list);
    return section;
  }

  function renderLandscape() {
    const experiences = el("landscape-experience-cards");
    const records = el("landscape-records");
    experiences.replaceChildren();
    records.replaceChildren();
    show("landscape-placeholder", !state);
    show("reflection-history", Boolean(state && state.reflections.length));
    show("export-workshop", Boolean(state));
    show("reset-workshop", Boolean(state));
    if (!state) return;
    experiences.append(landscapeSection("Your chosen experiences", state.accepted_experiences || [], (li, item) => { li.append(node("strong", item.title), node("span", item.details)); }));
    Object.entries(kinds).forEach(([kind, label]) => {
      const selected = (state.records || []).filter((item) => item.kind === kind);
      if (selected.length) records.append(landscapeSection(label, selected, (li, item) => {
        li.append(node("span", item.wording), node("small", item.user_edited || item.decision === "edit" ? "Edited by you" : "Reviewed and kept by you"));
      }));
    });
    const skipped = state.reflections.filter((item) => item.status === "skipped");
    if (skipped.length) records.append(landscapeSection("Still open", skipped, (li, item) => { li.textContent = config.steps.find((step) => step.id === item.id)?.title || "A reflection left open"; }));
    const history = el("history-list");
    history.replaceChildren();
    state.reflections.forEach((item) => {
      const box = node("div", undefined, "workshop-history-item");
      const step = config.steps.find((candidate) => candidate.id === item.id);
      box.append(node("h4", step?.title || "Reflection"), node("p", item.status === "skipped" ? "Left open for now." : item.text));
      const revise = node("button", "Revise from here", "button button-small button-quiet");
      revise.type = "button";
      revise.addEventListener("click", async () => {
        if (!await confirmInPage("Revise from this reflection? Earlier answers stay. This answer and all later reflections and landscape results will need to be redone.", "Revise from here")) return;
        perform(async () => acceptState(await request("/api/workshop/revise", { version: state.version, step_id: item.id })));
      });
      box.append(revise);
      history.append(box);
    });
  }

  function render() {
    if (!config) return;
    const phase = state?.phase || "start";
    const step = state && config.steps[state.step_index];
    const isSample = mode === "sample";
    el("workshop-mode").classList.toggle("is-live", !isSample);
    text("mode-title", isSample ? "Fictional example · no AI calls" : "Your experience · your choices");
    text("mode-description", isSample ? "A fixed walkthrough with fictional material, clearly separate from your own work." : "Seven guided reflections. AI connections are an optional final step.");
    try { window.AIAnalytics?.setMode(mode); } catch (_) {}
    ["start", "reflection", "synthesis", "review", "complete"].forEach((id) => show(`${id}-section`, ({ reflect: "reflection", synthesize: "synthesis" }[phase] || phase) === id));
    let progress = 0;
    if (phase === "reflect") progress = state.step_index < 3 ? 1 : state.step_index < 5 ? 2 : 3;
    if (["synthesize", "review", "complete"].includes(phase)) progress = 4;
    [...el("workshop-progress").children].forEach((li, index) => {
      li.classList.toggle("is-current", index === progress);
      li.classList.toggle("is-done", index < progress || phase === "complete");
      if (index === progress) li.setAttribute("aria-current", "step"); else li.removeAttribute("aria-current");
    });
    text("step-label", phase === "start" ? "CHOOSE YOUR EXPERIENCES" : phase === "reflect" ? `REFLECTION ${state.step_index + 1} OF ${config.steps.length}` : phase === "complete" ? "REVIEWED BY YOU" : "REVIEW YOUR LANDSCAPE");
    if (phase === "start") renderStart();
    if (phase === "reflect" && step) {
      text("reflection-title", step.title);
      text("reflection-prompt", step.prompt);
      text("reflection-help", step.help);
      text("step-source", `Adapted from ${methodReferences(step.method_ids).map(referenceLabel).join("; ")}`);
      el("reflection-answer").readOnly = isSample;
      if (state.version !== renderedVersion) el("reflection-answer").value = isSample ? config.sample_answers[step.id] || "" : "";
    }
    if (phase === "synthesize") {
      show("synthesize-ai", !isSample && config.live_ready);
      show("ai-disclosure", !isSample && config.live_ready);
      show("ai-unavailable", !isSample && !config.live_ready);
      text("synthesize-own", isSample ? "See the fictional review →" : "Keep my own words");
    }
    if (phase === "review" && state.version !== renderedVersion) renderProposals();
    if (phase === "complete") text("completion-summary", `${(state.records || []).length} reviewed additions kept. Anything you left out is excluded from your landscape.`);
    renderLandscape();
    renderedVersion = state?.version ?? null;
    updateControls();
  }

  async function loadSaved() {
    const saved = await request("/api/workshop/state");
    state = saved.state || null;
    currentVersion = saved.current_version ?? state?.version ?? 0;
    imported = saved.imported_experiences || [];
    legacyPresent = Boolean(saved.legacy_present);
    selectedImported = new Set(imported.map((item) => item.id));
    useImported = imported.length > 0;
    if (state) mode = state.mode;
    renderedVersion = null;
    render();
  }

  el("personal-mode").addEventListener("click", () => { mode = "live"; render(); });
  el("sample-mode").addEventListener("click", () => { mode = "sample"; render(); });
  el("use-imported").addEventListener("click", () => { useImported = true; renderStart(); updateControls(); });
  el("use-manual").addEventListener("click", () => { useImported = false; renderStart(); updateControls(); });
  el("add-experience").addEventListener("click", () => { if (manual.length < 3) manual.push({ title: "", details: "" }); renderManual(); updateControls(); el(`manual-${manual.length - 1}-title`).focus(); });
  el("start-workshop").addEventListener("click", async () => {
    if (legacyPresent && !await confirmInPage("Start this workshop and replace the earlier exercise? Export the earlier exercise first if you want a copy.", "Start this workshop")) return;
    perform(async () => {
      const payload = { mode, version: currentVersion };
      if (mode === "live" && useImported) Object.assign(payload, { use_document: true, experience_ids: [...selectedImported] });
      else if (mode === "live") payload.experiences = manual.map((item) => ({ title: item.title.trim(), details: item.details.trim() }));
      acceptState(await request("/api/workshop/start", payload));
    });
  });
  el("reflection-answer").addEventListener("input", updateControls);
  el("reflection-form").addEventListener("submit", (event) => { event.preventDefault(); perform(async () => acceptState(await request("/api/workshop/answer", { version: state.version, answer: el("reflection-answer").value, skip: false }))); });
  el("skip-answer").addEventListener("click", () => perform(async () => acceptState(await request("/api/workshop/answer", { version: state.version, answer: "", skip: true }))));
  const synthesize = (ownWords) => perform(async () => acceptState(await request("/api/workshop/synthesize", { version: state.version, own_words: ownWords })), ownWords ? "Organizing your own words…" : "Considering the connections. This can take a moment…");
  el("synthesize-ai").addEventListener("click", () => synthesize(false));
  el("synthesize-own").addEventListener("click", () => synthesize(true));
  el("review-form").addEventListener("submit", (event) => {
    event.preventDefault();
    perform(async () => {
      const reviewed = (state.proposals || []).map((item) => {
        const choice = decisions[item.id];
        return choice.decision === "edit" ? choice : { id: choice.id, decision: choice.decision };
      });
      acceptState(await request("/api/workshop/review", { version: state.version, decisions: reviewed }));
    });
  });
  el("recover-workshop").addEventListener("click", async () => {
    if (!config) { perform(initialize, "Reconnecting to the workshop…"); return; }
    if (!await confirmInPage("Reload the last saved progress? Text you have not submitted and unsaved review choices will be discarded.", "Reload saved progress")) return;
    perform(loadSaved, "Reloading saved progress…");
  });
  el("reset-workshop").addEventListener("click", async () => {
    if (!await confirmInPage("Clear this workshop and start over? Export first if you want a copy.", "Start over")) return;
    perform(async () => { await request("/api/reset", {}); manual = [{ title: "", details: "" }]; await loadSaved(); });
  });

  async function initialize() {
    try {
      config = await request("/api/workshop/config");
      config.steps = config.steps || [];
      config.sample_answers = config.sample_answers || {};
      config.method = config.method || {};
      if (config.available === false) mode = "sample";
      text("method-adaptation", config.method.adaptation);
      text("method-coverage", config.method.coverage);
      const list = el("method-references");
      (config.method.references || []).forEach((reference) => list.append(node("li", referenceLabel(reference))));
      await loadSaved();
    } catch (error) { displayError(error.message); }
    finally { show("workshop-loading", false); show("workshop-body", true); updateControls(); }
  }
  initialize();
})();
