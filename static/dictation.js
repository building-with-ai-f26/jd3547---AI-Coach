/* Browser dictation only: no audio uploads, persistence, or analytics here. */
(() => {
  "use strict";
  window.createDictation = ({ input, start, stop, cancel, status, preview, changed }) => {
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    let current = null;
    let enabled = false;
    const supported = Boolean(Recognition) && window.isSecureContext;
    const message = (text) => { status.textContent = text; };
    const controls = () => {
      start.disabled = !supported || !enabled || Boolean(current) || input.value.length >= input.maxLength;
      stop.hidden = cancel.hidden = !current;
      stop.disabled = Boolean(current?.stopping);
      start.hidden = Boolean(current);
      input.readOnly = Boolean(current);
      status.classList.toggle("is-listening", Boolean(current));
      changed();
    };
    function finish(run, text, abort = true) {
      if (current !== run) return;
      current = null; // Ignore late callbacks before aborting.
      window.clearTimeout(run.limitTimer);
      window.clearTimeout(run.finishTimer);
      if (abort) { try { run.recognition.abort(); } catch (_) {} }
      preview.textContent = "";
      preview.hidden = true;
      message(text);
      controls();
    }
    function endListening() {
      const run = current;
      if (!run || run.stopping) return;
      run.stopping = true;
      window.clearTimeout(run.limitTimer);
      message("Finishing your words…");
      controls();
      run.finishTimer = window.setTimeout(() => finish(run, "Dictation stopped. Review the text before submitting."), 4000);
      try { run.recognition.stop(); }
      catch (_) { finish(run, "Dictation stopped. Your text is still here."); }
    }
    function cancelListening() {
      if (!current) return;
      const run = current;
      input.value = run.before;
      finish(run, "Dictation canceled. Your earlier text is unchanged.");
    }
    start.addEventListener("click", () => {
      if (!supported || !enabled || current || input.value.length >= input.maxLength) return;
      let recognition;
      try { recognition = new Recognition(); }
      catch (_) { message("Dictation is unavailable here. You can keep typing or try Chrome."); return; }
      const run = { recognition, before: input.value, seen: new Set(), stopping: false };
      current = run;
      recognition.lang = "en-US";
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.maxAlternatives = 1;
      recognition.onstart = () => {
        if (current !== run || run.stopping) return;
        message("Listening… Speak in English, then select Stop. Maximum 60 seconds.");
      };
      recognition.onresult = (event) => {
        if (current !== run) return;
        let interim = "";
        for (let index = event.resultIndex; index < event.results.length; index += 1) {
          const result = event.results[index];
          const text = result[0].transcript.trim();
          if (result.isFinal && !run.seen.has(index)) {
            run.seen.add(index);
            const separator = input.value && !/\s$/.test(input.value) ? " " : "";
            const addition = separator + text;
            const remaining = Math.max(0, input.maxLength - input.value.length);
            input.value += addition.slice(0, remaining);
            if (addition.length >= remaining) {
              finish(run, "Character limit reached. Review or shorten your text before continuing.");
              return;
            }
          } else if (!result.isFinal) interim += `${text} `;
        }
        preview.textContent = interim.trim().slice(0, Math.max(0, input.maxLength - input.value.length));
        preview.hidden = !preview.textContent;
        changed();
      };
      recognition.onerror = (event) => {
        const errors = {
          "not-allowed": "Microphone access was not allowed. Enable it in browser settings, or keep typing.",
          "service-not-allowed": "This browser cannot use its speech service. Try Chrome or keep typing.",
          "audio-capture": "No microphone is available. Check your microphone or keep typing.",
          "network": "The speech service could not connect. Check your connection or keep typing.",
          "no-speech": "No speech was detected. Try again or keep typing.",
          "language-not-supported": "English dictation is unavailable in this browser. You can keep typing."
        };
        finish(run, (errors[event.error] || "Dictation stopped. Try again or keep typing.") + " Your text is still here.");
      };
      recognition.onend = () => finish(run, input.value === run.before
        ? "No words were added. Try again or keep typing."
        : "Dictation stopped. Review and edit your text before submitting.", false);
      message("Waiting for microphone access… You can cancel at any time.");
      preview.textContent = "";
      preview.hidden = true;
      controls();
      // Includes permission waiting, so a delayed grant cannot start an unbounded session.
      run.limitTimer = window.setTimeout(endListening, 60000);
      try { recognition.start(); }
      catch (_) { finish(run, "Dictation could not start. Try Chrome or keep typing. Your text is still here."); }
    });
    stop.addEventListener("click", endListening);
    cancel.addEventListener("click", cancelListening);
    const leave = () => { if (current) finish(current, "Dictation stopped. Review your text before continuing."); };
    document.addEventListener("visibilitychange", () => { if (document.hidden) leave(); });
    window.addEventListener("pagehide", leave);
    message(supported ? "Speak in English for up to 60 seconds. Review your text before submitting."
      : "Dictation isn't available in this browser. Open this app in Chrome, or use your keyboard's dictation or type.");
    return {
      get active() { return Boolean(current); },
      setEnabled(value) {
        enabled = value;
        if (!enabled && current) leave();
        start.disabled = !supported || !enabled || Boolean(current) || input.value.length >= input.maxLength;
      },
      cancel: cancelListening,
      stop: leave
    };
  };
})();
