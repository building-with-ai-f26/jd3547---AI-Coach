# AI Coach

> **One-line pitch:** An AI personal branding coach that helps professionals connect their experiences, strengths, and ambitions into a clear story about who they are and the value they bring.

- **Builder:** Jason Daniels (`@jd3547-nyu`)
- **Pod:** [Pod Name / Number]
- **Product Page & Living PRD:** [AI Coach Product Page](https://building-with-ai-f26.github.io/jd3547---AI-Coach/)
- **App:** currently local. Build 3 now requires a publicly usable app by November 23 at noon; deployment is still pending.

To use the prototype, go to [Run on your Mac](#run-on-your-mac). The Product Page above describes the project; the working app opens separately on your laptop.

## Start here: Build 1

**Due Monday, November 9 at noon, New York time.** No class November 3; keep building that week.

1. Join the [class organization](https://github.com/building-with-ai-f26), then use this template to create a **public** repo named `<netid>-<project-slug>`. Ask Christian or Hew if the organization is missing from the owner list.
2. Set up Git and one coding agent during the week of October 27. Follow the [Icerynk setup guide](https://www.icerynk.com/c/fa26-tech-gb-2160-dm2-f2/content/pre-class-setup-github-openrouter-your-coding-agent).
3. Publish [`docs/index.html`](./docs/index.html): **Settings → Pages → Deploy from a branch → main → /docs → Save**. When deployment finishes, open `https://building-with-ai-f26.github.io/<your-repo-name>/`.
4. Fill in PRD v1: a reachable user, their painful before/after workflow, one core workflow, and three non-goals.
5. Build a rough local prototype. Add a screenshot or GIF and an honest Build 1 log to the Product Page, including progress, learning, problems, costs, and hours.
6. Push meaningful commits on **at least two separate days each week outside class**, including the November 3 break.
7. Submit your **Product Page URL and repository URL in Icerynk**. Come ready to demo the prototype in two minutes on November 10.

Create your PostHog account in Week 1. Install it on the Product Page and local app in **Build 2**, then verify events. The Product Page is public from Build 1. The current Build 3 assignment supersedes the original schedule: the working app must be publicly usable by November 23 at noon.

## Repository map

| File / folder | Purpose |
| --- | --- |
| [`app.py`](./app.py) | Local server, exercise steps, session handling, and export. |
| [`coach.py`](./coach.py) | Fictional example, model requests, and response checks. |
| [`workshop.py`](./workshop.py) | Body of Work questions, typed landscape records, source/evidence checks, and review transitions. |
| [`introductions.py`](./introductions.py) | Audience/settings filters, bounded introduction drafts, and explicit review. |
| [`documents.py`](./documents.py) | PDF text reading with file, page, memory, and time limits. |
| [`templates/app.html`](./templates/app.html), [`static/`](./static/) | The app's browser interface. |
| [`content/method.json`](./content/method.json) | Reviewed coaching source and its coverage limits. |
| [`requirements.txt`](./requirements.txt) | Python packages needed to run the app. |
| [`.env.example`](./.env.example) | Safe placeholder settings. The private `.env` copy stays on your computer. |
| [`docs/index.html`](./docs/index.html) | Required public pitch, living PRD, and weekly build log. Update with actual work and evidence. |
| [`docs/assets/analytics-config.js`](./docs/assets/analytics-config.js), [`docs/assets/analytics.js`](./docs/assets/analytics.js) | Shared public PostHog settings and the limited analytics events used by both pages. |
| [`Intent.md`](./Intent.md), [`Plan.md`](./Plan.md), [`journal/`](./journal/) | Optional drafting aids. No duplicate submission is required. |
| [`AGENTS.md`](./AGENTS.md) | Local run commands, project context, and agent rules. Build 2 onward. |
| [`CLAUDE.md`](./CLAUDE.md) | Tells Claude Code to follow `AGENTS.md`. |
| [`tests/`](./tests/) | Verification guidance. Build 4 offers Track A domain evals **or** Track B user replays. |
| [`SPONSOR_MEMO.md`](./SPONSOR_MEMO.md) | One-page recommendation backed by actual usage, full costs, and risks. Due December 14 at noon. |

[Icerynk](https://www.icerynk.com/c/fa26-tech-gb-2160-dm2-f2/content) holds the assignment instructions and submissions.

## Run on your Mac

This prototype runs on your laptop. The quick exercise uses pasted background or reviewed résumé/CV experiences: one reflection question → proposed theme → accept, edit, or reject. A separate **Body of Work mini-workshop** adds roots, ingredients, and future contribution to the same local app. It covers selected exercises, not the complete book or expert roundtable.

Use a normal Terminal prompt for the commands below. If Terminal is currently showing a conversation with a coding agent, open a new Terminal window. Run each command by pressing Return.

### 1. Open the project folder

For Jason's existing Desktop copy:

```bash
cd ~/Desktop/jd3547---AI-Coach
```

If you saved the project somewhere else, use that folder's path instead. The folder should contain `app.py` and `requirements.txt`.

Check Python:

```bash
python3 --version
```

The app requires Python 3.9 or newer. If Python is missing, use the [official Python installer for macOS](https://www.python.org/downloads/macos/), reopen Terminal, and return to the project folder.

### 2. Install the app's packages

On your first setup, create a separate Python environment for this project. It is a folder named `.venv` that holds the app's packages:

```bash
python3 -m venv .venv
```

If this project already has a working `.venv`, skip that command. Install the packages listed by the project:

```bash
.venv/bin/python -m pip install -r requirements.txt
```

Wait until installation finishes and the Terminal prompt returns. If it reports an error, resolve that error before continuing. Run the package-install command again when `requirements.txt` changes. The commands use this project's Python directly, so there is no separate environment activation step.

### 3. Start the app

```bash
.venv/bin/python app.py
```

Open **[http://127.0.0.1:8787](http://127.0.0.1:8787)** in your browser. `127.0.0.1` means your own computer; this does not publish the app online. Leave that Terminal window open while using it.

### 4. Stop or restart

Click the Terminal window running the app and press **Control+C** to stop it. To restart, run `.venv/bin/python app.py` again, then refresh the browser. Restart after changing `.env` or Python code.

Stopping the server clears the current exercise. Use **Export** first if you want to keep a copy. If Terminal reports that port `8787` is already in use, check for another Terminal window already running this app and stop that copy before starting another.

### Try it without a key

The fictional walkthrough works immediately. Its background, answer and suggestion are prepared examples, not AI analysis. You can review, edit, accept or reject the suggestion and download an exercise record. It makes no paid API calls.

### Connect live coaching

Live coaching needs an OpenRouter API key and usable account credit. A Claude chat subscription does not supply this key. The fictional walkthrough does not require either.

From the project folder, create the private settings file only if it is missing:

```bash
cp -n .env.example .env
```

The `-n` means **do not overwrite an existing file**. If `.env` already exists, keep its settings and edit only what needs to change. Open it locally:

```bash
nano .env
```

Replace the placeholder on the `OPENROUTER_API_KEY` line with your own key. Leave the `OPENROUTER_MODEL` setting as supplied unless you intentionally choose another supported model. In Nano, press **Control+O**, then **Return** to save, and **Control+X** to leave. Stop and restart the app, then refresh the browser.

Keep this key private: do not paste it into a chat, screenshot, browser script, or Git commit. `.gitignore` excludes `.env`; `.env.example` must contain placeholders only. The [OpenRouter quickstart](https://openrouter.ai/docs/quickstart) explains its API access. If the app shows an AI-service error, check your local key, configured model, and account credit; enabling the live button only means settings are present, not that a request has succeeded.

Live mode sends your submitted background and answer, plus the method card, to OpenRouter and the configured model provider. It normally makes one request for the question and another for the suggestion. A question-format failure that returns within 20 seconds gets one automatic regeneration, which can add model cost; the second response must pass the same checks. Source, schema, transport, and credit errors are not automatically retried. Accepting, editing and rejecting do not make more requests. Failed requests display an error; they never switch silently to sample results. A working connection does not establish coaching quality.

### Try the Body of Work mini-workshop

Open **[http://127.0.0.1:8787/workshop](http://127.0.0.1:8787/workshop)** while the server runs. Choose the fixed fictional example, or confirm one to three experiences in your own words. You can also bring selected PDF experience cards that you have already approved in the quick exercise. Starting a workshop replaces that browser session's prior exercise; export it first if you want to keep it.

Seven questions explore what matters to you, the experiences behind it, whom you want to help, the ingredients you want to use or develop, and a possible future contribution. You can leave a question open. At the end, keep your own words or explicitly request AI suggestions, then accept, edit, or reject each proposed addition. Current ingredients and future learning goals stay separate. Revising an earlier question keeps earlier answers but clears that answer, later answers, and their results so you can work through them again.

Personal mode needs a reviewed local source guide, stored **outside the repository** at `~/.config/ai-coach/body-of-work-v1.json`. Jason's local setup includes this guide; a fresh clone does not. If it is missing, the app explains that personal workshop mode is unavailable, while the fictional example remains available. To use an existing reviewed guide elsewhere, set `BODY_OF_WORK_SOURCE_PATH` to its absolute path in your private `.env`, then restart. Do not point this setting at the full book: it expects the versioned guide format described in `workshop.py`.

The fixed questions and keeping your own words do not need an API key. **AI suggestions** require the OpenRouter connection above and make one request per explicit attempt, using the selected experiences, submitted answers, and a bounded private guide. There is no automatic retry. Review and export make no AI calls. The book file and detailed analysis are not browser assets or export content; only limited method attribution is shown.

Refresh can restore a submitted workshop while its server-memory session remains active. Unsaved typing is not restored. Export is a record, not a way to resume after the server stops. The quick exercise remains available at `/`; its speech-to-text option has not been extended to this workshop.

### Speak your reflection

In **Use my experience** mode, reach the reflection question, then choose **Speak your answer**. Allow microphone access when your browser asks. Speak in English, select **Stop dictation**, review/edit the text, and submit it normally. Each recording attempt is limited to 60 seconds. **Cancel dictation** removes that attempt's words and restores the text you had before starting. Existing text survives permission or connection failures. Switching away from the page stops listening.

This uses the browser's speech service, with no additional API key or app transcription charge. It is not supported in every browser or embedded preview; try Chrome at `http://127.0.0.1:8787/`, or use keyboard dictation/typing if unavailable. The fictional walkthrough stays read-only. Browser speech recognition may send audio to an external service and require internet access; AI Coach does not record or save audio. Only the reviewed text is sent through the existing coaching request when you submit. See [browser speech recognition details](https://developer.mozilla.org/en-US/docs/Web/API/SpeechRecognition).

Eight focused mock speech-recognition checks passed November 11. They cover text preservation, cancel/stop, late callbacks, errors, limits, and unavailable browsers. Actual microphone recognition still needs a hands-on check in the user's browser; these checks do not establish transcription accuracy.

### Upload a résumé or CV

Choose **Use my experience**, then the PDF upload option. Select one PDF with selectable text and click **Find experiences**. Selecting the file alone does not send it to the AI service. Processing sends the extracted document text to OpenRouter and the configured model in one additional request, which uses your API credit.

Review the proposed experience cards and the supporting quote/page for each. You can change a title or description and select the cards you want to keep. Adding the selected experiences puts only those approved cards on the landscape. **Find a question** then uses the approved titles and descriptions; rejected cards and the remaining document text are not sent to the coaching step. The original supporting passage stays visible for comparison with your edits. You can export approved experiences before continuing to coaching.

The first version accepts one PDF up to 5 MB, 10 pages, and 30,000 extracted characters, producing at most six proposed cards. Password-protected files, unreadable/scanned pages, and documents exceeding those limits are rejected with guidance to paste text or use a smaller document. This version does not read Word files or perform OCR. Extraction can miss or misinterpret material even when a file is accepted, so check the source passages and edit or leave out inaccurate cards.

The original PDF is processed in memory and is not saved by the app. Extracted text is sent to the configured provider only for card generation; the app retains the proposed cards and their supporting passages for review. After review, only the selected cards remain in the exercise. Uploaded career material is separate from the fixed expert-source library.

### Source and limitations

The quick exercise adapts Pamela Slim's approach to finding themes across experiences, described in Dorie Clark's [article](https://dorieclark.com/blog/build-personal-brand/), section “Identify Your Themes.” Its source card remains in `content/method.json`.

For the mini-workshop, all nine chapters and the conclusion of the supplied *Body of Work* transcription were reviewed on November 15. Its original app questions shorten and reorder “Identify Your Roots” (Chapter 2), “Determine Your Ingredients” (Chapter 3), and “Body of Work” (Chapter 1). This is an adaptation, not the full exercises, a replica of Slim, or an endorsed service. The supplied text has OCR gaps and no verified print-page mapping; source references use chapters, exercise titles, and transcription lines. User evidence and method references are kept separate.

Suggestions remain tentative. The app checks that evidence quotations occur in the user's input and source IDs are known; those checks do **not** prove that a model's interpretation is correct or useful. The user decides what to keep. Edited statements are user-authored and can go beyond the original evidence.

The app stores exercise content, including imported cards and their evidence, in server memory. It does not save exercise content in browser storage or a database. An opaque cookie identifies the exercise; it contains no background text or API key and lasts one hour. The server removes sessions inactive for over an hour when another session request arrives. Stopping the server clears all of its sessions; **Start over** clears the current exercise. Refreshing the quick exercise restarts its visible flow; the book workshop can restore submitted steps from the still-active server session. Neither flow has durable saved-session recovery.

An export is a downloaded JSON file: a structured record you can keep locally, not a resumable saved session. It may contain your background, answer, document name, approved experiences and evidence, and a theme still marked as a proposal. Unreviewed import cards cannot be exported, and rejected experience cards and rejected themes are excluded. Keep private résumés, PDFs, exports, and screenshots containing personal material **outside this public Git repository**. They are not all automatically covered by `.gitignore`.

The workshop export distinguishes accepted records, pending proposals, and skipped reflections. Rejected proposal wording and the private source guide are excluded. Exact quotations verify where words came from, not whether an interpretation is correct; edited wording is marked as user-authored.

Resetting or stopping the app does not delete a downloaded export or information already sent to OpenRouter and its model provider. Their data handling is separate from the app's local memory; this app does not promise provider-side deletion or a particular retention period.

### PostHog usage measurements

The Product Page and local app share two files: `docs/assets/analytics-config.js` supplies the PostHog project token, US collection address, and `enabled` switch; `docs/assets/analytics.js` defines the events and privacy settings. Flask serves these same files under `/analytics/` for the local app. You do not need a personal PostHog API key to run the app.

The **public PostHog project ingestion token** identifies the project that receives events and is intended to be visible in browser code. It does not provide access to the private dashboard. This is different from a **secret OpenRouter key** or a **personal PostHog API key**; neither secret belongs in these files, the browser, or a commit.

Analytics is enabled in the shared configuration. It skips loading when the browser sends Do Not Track or Global Privacy Control. To disable collection for your local copy, change `enabled: true` to `enabled: false` in `analytics-config.js` and refresh the page. Changing the public Product Page requires publishing that file change as well. Turning collection off does not delete already collected events.

The event list is deliberately limited: pageviews, named button/link clicks, mode/input choices, PDF import and approval milestones, question/theme milestones, review decisions, export, reset, and broad failure categories. Properties distinguish `product_page` from `local_app` and fictional `sample` mode from `live` mode. Some events include a count of cards. Events do not include filenames, document text, personal background, answers, evidence quotations, or suggested wording. Full incoming URLs, search parameters, and referrers are replaced or omitted; a fixed test marker is the exception described below.

Session replay is **configured** to mask all text and input values and block images and personal-content containers. Automatic click/form capture, console logs, network bodies/headers, and canvas recording are disabled. The helper also disables person profiles and identification, and configures analytics identifiers to stay in memory; anonymous session identifiers are still sent with events. The app's opaque exercise cookie is separate.

**Verified November 11, 2026:** browser checks using fictional material confirmed event receipt and masked session replay in PostHog for both the local app and the published Product Page. This covers the tested flows and interface at that time; recheck after interface or analytics changes. It does not establish outside-user adoption or coaching quality. PostHog receives events and masked replay data externally, subject to the project's PostHog settings. Local reset, server shutdown, and browser refresh do not delete that remote data.

For the builder, the [Build 2 dashboard](https://us.posthog.com/project/697808/dashboard/2337055) requires access to the private PostHog project. To check the installation:

1. Start the app and open `http://127.0.0.1:8787/?analytics_test=build2-nov11`. Use the fictional walkthrough and review/export/reset it.
2. After the Product Page changes are published, open its normal URL with `?analytics_test=build2-nov11` appended and try its navigation links.
3. In PostHog, look for events with `test_run = build2-nov11` on both `app_surface` values. Inspect a replay using only fictional material and check that private content is hidden. Test events are builder checks, not outside-user evidence.
4. Record the actual receipt/replay result and any limitations in the [Build 2 log](./docs/index.html#build-log). A successful local test or a configured token alone does not prove that PostHog received events.

### Run the local checks

From the project folder, run:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

These checks use fictional inputs and simulated provider responses. They check application behavior without paid model calls; they do not establish the quality of live coaching. A final `OK` means that run passed. See [`tests/README.md`](./tests/README.md) for the class's later evaluation options.

If you already have Node.js, an optional check of the analytics allowlists and privacy configuration is:

```bash
node tests/analytics.test.js
```

It uses built-in Node modules and no network calls. Node is not required to run the app; this is a separate developer check, not proof that PostHog received events.

On November 11, 2026, all **73 Python checks and 10 JavaScript checks passed**. No paid live-model calls were made during that day's setup and analytics checks.


## Opening lines and Build 3

Start at `/workshop` with an optional introduction you use today and up to three settings. For each, name the audience and purpose; optionally specify what to emphasize or leave out and a tone. These preferences do not establish facts about you. Complete the existing Body of Work reflections and review your landscape, then draft, edit, and explicitly keep a short introduction for each context. You can write versions yourself without an AI request. The original draft and context-specific versions are included in your workshop export; they share the workshop's memory-only lifetime.

The introduction exercise is app-authored, drawing on a publicly documented introduction by Jen Gottlieb in [The Art of Charm's guide](https://theartofcharm.com/art-of-conversation/how-to-introduce-yourself-in-a-group/). The name → audience → helpful work → benefit structure is an inference from that example, not a verified transcription of her Brand Snap method. It is separate from the private Pamela Slim method guide and implies no endorsement.

The optional introduction request uses approved experience summaries, reviewed landscape additions, the starting introduction, and presentation settings. It excludes the book guide, raw PDFs, and unreviewed reflections. A starting introduction is a draft, not citable evidence. Evidence quotation checks do not establish the truth of a claim; read every version before keeping it.

See [the two-day Build 3 plan](journal/build-3-nov22-23.md). Deployment, the live security audit, live analytics verification, and submission remain required before November 23 at noon. The local feature work does not complete those requirements.
