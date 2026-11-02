/* This page keeps its working state in memory. It never stores an API key. */
(() => {
  "use strict";

  const el = (id) => document.getElementById(id);
  let config = null;
  let session = null;
  let mode = "sample";
  let busy = false;
  let editing = false;
  let retryAction = null;

  const setText = (id, value) => { el(id).textContent = value == null ? "" : String(value); };
  const show = (id, visible) => { el(id).hidden = !visible; };
  const announce = (message) => setText("page-status", message);

  async function request(path, body) {
    const controller = new AbortController();
    const options = { credentials: "same-origin", cache: "no-store", signal: controller.signal };
    if (body !== undefined) {
      options.method = "POST";
      options.headers = { "Content-Type": "application/json", "X-Coach-Request": "1" };
      options.body = JSON.stringify(body);
    }
    let response;
    const timeout = window.setTimeout(() => controller.abort(), 90000);
    try {
      response = await fetch(path, options);
    } catch (error) {
      if (error.name === "AbortError") throw new Error("This step took longer than expected. Your input is still here; try again, or start over if the workshop says this step has already changed.");
      throw new Error("The local workshop couldn't be reached. Check that it is still running, then try again.");
    } finally {
      window.clearTimeout(timeout);
    }
    let data;
    try {
      data = await response.json();
    } catch (_) {
      throw new Error("The workshop returned an unreadable response. You can try this step again.");
    }
    if (!response.ok) {
      const error = new Error(typeof data.error === "string" ? data.error : "This step couldn't be completed. Please try again.");
      error.status = response.status;
      throw error;
    }
    return data;
  }

  function updateControls() {
    document.querySelectorAll("[data-action]").forEach((button) => { button.disabled = busy; });
    const ready = Boolean(config);
    const hasSession = Boolean(session);
    el("sample-mode-button").disabled = busy || !ready || hasSession || mode === "sample";
    el("live-mode-button").disabled = busy || !ready || !config.live_ready || hasSession || mode === "live";
    el("live-mode-button").title = ready && !config.live_ready ? "Personal coaching needs a server-side API connection." : hasSession ? "Start over to switch modes." : "";
    el("start-button").disabled = busy || !ready || hasSession || !el("background").value.trim();
    el("answer-button").disabled = busy || !session || session.stage !== "question" || !el("answer").value.trim();
    el("export-button").disabled = busy || !hasSession;
    el("reset-button").disabled = busy || !ready || (!hasSession && (mode === "sample" || !el("background").value.trim()));
    el("retry-button").disabled = busy || !retryAction;
    el("background").disabled = busy || !ready;
    el("answer").disabled = busy || !session;
    el("edit-theme").disabled = busy;
    el("edit-statement").disabled = busy;
    el("confirm-reset-button").disabled = busy;
    el("conversation").setAttribute("aria-busy", String(busy));
    show("working-status", busy);
  }

  function clearError() {
    show("error-panel", false);
    retryAction = null;
  }

  async function perform(action, workingMessage) {
    if (busy) return;
    busy = true;
    clearError();
    setText("working-text", workingMessage);
    updateControls();
    try {
      await action();
    } catch (error) {
      setText("error-text", error.message || "Something interrupted this step. Please try again.");
      // A stale request needs a fresh exercise, rather than repeating the same version.
      retryAction = error.status === 409 ? null : () => perform(action, workingMessage);
      show("retry-button", Boolean(retryAction));
      show("error-panel", true);
      announce("The step could not finish. Your input has been kept.");
    } finally {
      busy = false;
      updateControls();
    }
  }

  function updateCounts() {
    const limit = config ? config.max_chars : 6000;
    ["background", "answer"].forEach((id) => {
      setText(`${id}-count`, `${el(id).value.length.toLocaleString()} / ${limit.toLocaleString()}`);
    });
    updateControls();
  }

  function fillSource() {
    const source = config.source;
    setText("source-method", source.method_summary);
    setText("source-excerpt", source.excerpt);
    show("source-excerpt-wrap", Boolean(source.excerpt));
    setText("source-section", source.section);
    setText("source-note", source.note);
    setText("source-limitations", source.limitations);
    const link = el("source-link");
    link.textContent = `${source.title} ↗`;
    try {
      const url = new URL(source.url);
      if (url.protocol !== "https:" && url.protocol !== "http:") throw new Error("Unsupported source link");
      link.href = url.href;
    } catch (_) {
      link.removeAttribute("href");
    }
  }

  function renderMode() {
    const isSample = mode === "sample";
    document.querySelector(".mode-panel").classList.toggle("is-live", !isSample);
    setText("mode-title", isSample ? "Fictional example · no AI call" : "Your experience · live coaching");
    setText("mode-description", isSample ? "A prerecorded walkthrough. The background, reflection, and original insight are fictional." : "A source-informed question and a draft insight, created from the experiences you share.");
    setText("exercise-mode-badge", isSample ? "FICTIONAL EXAMPLE" : "YOUR EXPERIENCE");
    el("exercise-mode-badge").classList.toggle("badge-live", !isSample);
    show("setup-note", !config.live_ready);
    show("background-fixture-label", isSample);
    show("answer-fixture-label", isSample);
    show("landscape-mode-label", isSample);
    show("live-privacy-note", !isSample);
    el("background").readOnly = isSample;
    el("answer").readOnly = isSample;
    el("background").maxLength = config.max_chars;
    el("answer").maxLength = config.max_chars;
    setText("start-button-label", isSample ? "Try the fictional example" : "Find a question");
    setText("start-note", isSample ? "No personal information needed" : "One question at a time");
    setText("answer-button-label", isSample ? "See the example insight" : "Explore the connection");
    setText("share-description", isSample ? "Follow a fictional person's two experiences through a short reflection. The example lets you see each step before using your own material." : "Bring a few experiences, rather than trying to sum yourself up. A project, a role, or a moment you care about is enough to begin.");
    setText("background-help", isSample ? "Example material is fixed for this demonstration." : "Two short experiences give us a place to start.");
    setText("answer-help", isSample ? "This fictional reflection is part of the example." : "A few honest sentences are enough.");
    setText("landscape-grounding-text", isSample ? "Grounded in the fictional background and reflection." : "Grounded in your background and reflection.");
  }

  function renderEvidence(proposal) {
    const list = el("evidence-list");
    list.replaceChildren();
    (proposal.evidence || []).forEach((evidence) => {
      const item = document.createElement("li");
      const passage = document.createElement("p");
      passage.textContent = evidence.text;
      const label = document.createElement("span");
      label.textContent = `${mode === "sample" ? "Fictional " : ""}${evidence.from === "answer" ? "reflection" : "background"}`;
      item.append(passage, label);
      list.append(item);
    });
  }

  function render() {
    if (!config) { updateControls(); return; }
    renderMode();
    const stage = session ? session.stage : "share";
    const complete = stage === "complete";
    const reviewing = stage === "review" || complete;
    const index = stage === "share" ? 0 : stage === "question" ? 1 : 2;
    ["share", "reflect", "review"].forEach((name, step) => {
      const item = el(`progress-${name}`);
      item.classList.toggle("is-current", index === step && !complete);
      item.classList.toggle("is-done", step < index || complete);
      item.querySelector(".step-dot").textContent = step < index || complete ? "✓" : String(step + 1);
      if (step === index) item.setAttribute("aria-current", "step");
      else item.removeAttribute("aria-current");
    });
    setText("card-step-label", complete ? "EXERCISE COMPLETE" : `STEP ${index + 1} OF 3`);
    show("share-step", stage === "share");
    show("question-step", stage === "question");
    show("review-step", reviewing);
    show("review-actions", reviewing && !complete && !editing);
    show("edit-form", editing && !complete);
    show("completion-message", complete);
    show("landscape-empty", !reviewing);
    show("landscape-result", reviewing && session.decision !== "reject");
    show("landscape-rejected", complete && session.decision === "reject");
    setText("landscape-empty-title", stage === "question" ? "Notice before you name it." : "A little room to notice.");
    setText("landscape-empty-description", stage === "question" ? "The reflection comes first. A possible thread will appear here after this answer." : "A possible theme will appear here after your reflection. Nothing is accepted automatically.");

    if (session) {
      el("background").value = session.background;
      setText("coaching-question", session.question);
    }
    if (reviewing) {
      const proposal = session.accepted || session.proposal;
      show("proposal-card", Boolean(proposal));
      show("evidence-section", Boolean(proposal));
      if (proposal) {
        setText("proposal-theme", proposal.theme);
        setText("proposal-statement", proposal.statement);
        renderEvidence(proposal);
        setText("landscape-theme", proposal.theme);
        setText("landscape-statement", proposal.statement);
      } else {
        setText("proposal-theme", "");
        setText("proposal-statement", "");
        el("evidence-list").replaceChildren();
      }
      setText("landscape-status", complete ? (session.decision === "edit" ? "Edited & accepted by you" : "Accepted by you") : "For your consideration");
      el("landscape-status").classList.toggle("is-accepted", complete);
      setText("review-background", session.background);
      setText("review-question", session.question);
      setText("review-answer", session.answer);
      const rejected = session.decision === "reject";
      setText("review-title", complete ? (rejected ? "That connection didn't fit." : "A thread worth keeping.") : "Does this feel like you?");
      setText("review-description", complete ? (rejected ? "You set this interpretation aside. No theme has been added to the landscape." : "You reviewed this interpretation and chose what belongs in the landscape.") : "This is a possible connection, not a verdict. Keep it, put it in your own words, or set it aside.");
      setText("completion-title", mode === "sample" ? "Fictional example complete" : rejected ? "You made the call" : "Added to your landscape");
      setText("completion-description", mode === "sample" ? "You've seen one full exercise. You can export the clearly labeled example or start over." : "Export to keep a copy of the exercise, including the evidence and source. You can start fresh whenever you're ready.");
    }
    updateCounts();
  }

  function acceptState(data) {
    if (!data || !["question", "review", "complete"].includes(data.stage) || !Number.isInteger(data.version)) {
      throw new Error("The workshop returned an incomplete step. Please try again.");
    }
    session = data;
    mode = data.mode;
    editing = false;
    if (data.stage === "question") el("answer").value = mode === "sample" ? config.sample.answer : "";
    if (data.answer != null) el("answer").value = data.answer;
    render();
    const heading = data.stage === "question" ? "question-title" : "review-title";
    el(heading).focus();
    announce(data.stage === "question" ? "Your reflection question is ready." : data.stage === "review" ? "A possible thread is ready for your review." : "Your review has been saved for this session.");
  }

  async function loadConfig() {
    const data = await request("/api/config");
    if (!data || !data.source || !data.sample || typeof data.max_chars !== "number") throw new Error("The exercise configuration is incomplete.");
    config = data;
    el("background").value = config.sample.background;
    fillSource();
    render();
  }

  function selectMode(nextMode) {
    if (busy || session || !config || (nextMode === "live" && !config.live_ready)) return;
    mode = nextMode;
    el("background").value = mode === "sample" ? config.sample.background : "";
    el("answer").value = "";
    clearError();
    render();
    el("share-title").focus();
  }

  function submitReview(decision) {
    if (!session || session.stage !== "review") return;
    perform(async () => {
      const payload = { version: session.version, decision };
      if (decision === "edit") {
        payload.theme = el("edit-theme").value.trim();
        payload.statement = el("edit-statement").value.trim();
      }
      acceptState(await request("/api/review", payload));
    }, "Keeping your review…");
  }

  el("sample-mode-button").addEventListener("click", () => selectMode("sample"));
  el("live-mode-button").addEventListener("click", () => selectMode("live"));
  el("background").addEventListener("input", updateCounts);
  el("answer").addEventListener("input", updateCounts);
  el("background-form").addEventListener("submit", (event) => {
    event.preventDefault();
    if (!config || !el("background").value.trim()) return;
    perform(async () => {
      acceptState(await request("/api/start", { mode, background: el("background").value.trim() }));
    }, mode === "sample" ? "Opening the example question…" : "Finding one useful question…");
  });
  el("answer-form").addEventListener("submit", (event) => {
    event.preventDefault();
    if (!session || !el("answer").value.trim()) return;
    perform(async () => {
      acceptState(await request("/api/answer", { version: session.version, answer: el("answer").value.trim() }));
    }, mode === "sample" ? "Opening the example insight…" : "Looking for a possible connection…");
  });
  el("accept-button").addEventListener("click", () => submitReview("accept"));
  el("reject-button").addEventListener("click", () => submitReview("reject"));
  el("edit-button").addEventListener("click", () => {
    if (busy || !session || session.stage !== "review") return;
    editing = true;
    el("edit-theme").value = session.proposal.theme;
    el("edit-statement").value = session.proposal.statement;
    render();
    el("edit-theme").focus();
  });
  el("cancel-edit-button").addEventListener("click", () => { editing = false; render(); el("edit-button").focus(); });
  el("edit-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const theme = el("edit-theme").value.trim();
    const statement = el("edit-statement").value.trim();
    if (!theme || !statement) return;
    submitReview("edit");
  });
  el("retry-button").addEventListener("click", () => { if (retryAction) retryAction(); });
  el("reset-button").addEventListener("click", () => { if (!busy) el("reset-dialog").showModal(); });
  el("confirm-reset-button").addEventListener("click", () => {
    el("reset-dialog").close();
    perform(async () => {
      await request("/api/reset", {});
      session = null;
      editing = false;
      el("background").value = mode === "sample" ? config.sample.background : "";
      el("answer").value = "";
      el("edit-theme").value = "";
      el("edit-statement").value = "";
      el("reflection-details").open = false;
      render();
      el("share-title").focus();
      announce("The exercise has been cleared. You can begin again.");
    }, "Opening a fresh page…");
  });
  el("export-button").addEventListener("click", () => {
    if (!session) return;
    perform(async () => {
      const data = await request("/api/export");
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const objectUrl = URL.createObjectURL(blob);
      const download = document.createElement("a");
      download.href = objectUrl;
      download.download = `ai-coach-${mode === "sample" ? "fictional-example" : "exercise"}.json`;
      document.body.append(download);
      download.click();
      download.remove();
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
      announce("Your exercise export is ready to download.");
    }, "Preparing your export…");
  });

  perform(loadConfig, "Loading the exercise…");
})();
