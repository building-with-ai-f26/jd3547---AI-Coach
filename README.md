# AI Coach

> **One-line pitch:** An AI personal branding coach that helps professionals connect their experiences, strengths, and ambitions into a clear story about who they are and the value they bring.

- **Builder:** Jason Daniels (`@jd3547-nyu`)
- **Pod:** [Pod Name / Number]
- **Product Page & Living PRD:** [AI Coach Product Page](https://building-with-ai-f26.github.io/jd3547---AI-Coach/)
- **App:** runs locally through Week 4; add a cloud URL in Build 5.

## Start here: Build 1

**Due Monday, November 9 at noon, New York time.** No class November 3; keep building that week.

1. Join the [class organization](https://github.com/building-with-ai-f26), then use this template to create a **public** repo named `<netid>-<project-slug>`. Ask Christian or Hew if the organization is missing from the owner list.
2. Set up Git and one coding agent during the week of October 27. Follow the [Icerynk setup guide](https://www.icerynk.com/c/fa26-tech-gb-2160-dm2-f2/content/pre-class-setup-github-openrouter-your-coding-agent).
3. Publish [`docs/index.html`](./docs/index.html): **Settings → Pages → Deploy from a branch → main → /docs → Save**. When deployment finishes, open `https://building-with-ai-f26.github.io/<your-repo-name>/`.
4. Fill in PRD v1: a reachable user, their painful before/after workflow, one core workflow, and three non-goals.
5. Build a rough local prototype. Add a screenshot or GIF and an honest Build 1 log to the Product Page, including progress, learning, problems, costs, and hours.
6. Push meaningful commits on **at least two separate days each week outside class**, including the November 3 break.
7. Submit your **Product Page URL and repository URL in Icerynk**. Come ready to demo the prototype in two minutes on November 10.

Create your PostHog account in Week 1. Install it on the Product Page and local app in **Build 2**, then verify events. The Product Page is public from Build 1; the app can stay local through Week 4.

## Repository map

| File / folder | Purpose |
| --- | --- |
| [`docs/index.html`](./docs/index.html) | Required public pitch, living PRD, and weekly build log. Update with actual work and evidence. |
| [`Intent.md`](./Intent.md), [`Plan.md`](./Plan.md), [`journal/`](./journal/) | Optional drafting aids. No duplicate submission is required. |
| [`AGENTS.md`](./AGENTS.md) | Local run commands, project context, and agent rules. Build 2 onward. |
| [`tests/`](./tests/) | Verification guidance. Build 4 offers Track A domain evals **or** Track B user replays. |
| [`SPONSOR_MEMO.md`](./SPONSOR_MEMO.md) | One-page recommendation backed by actual usage, full costs, and risks. Due December 14 at noon. |

[Icerynk](https://www.icerynk.com/c/fa26-tech-gb-2160-dm2-f2/content) holds the assignment instructions and submissions.

## Local setup

This prototype runs on your laptop. Start with pasted background, or upload one résumé/CV PDF and review the experiences it finds. Approved experiences appear on your landscape and can feed the short coaching exercise: one reflection question → proposed theme → accept, edit, or reject. It is not the complete book workshop or expert roundtable.

From this project folder in Terminal, install once:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Start the app:

```bash
.venv/bin/python app.py
```

Open **http://127.0.0.1:8787** in your browser. Leave that Terminal window open while using the app. Press **Control+C** in Terminal to stop it.

### Try it without a key

The fictional walkthrough works immediately. Its background, answer and suggestion are prepared examples, not AI analysis. You can review, edit, accept or reject the suggestion and download an exercise record. It makes no paid API calls.

### Connect live coaching

Copy `.env.example` to `.env`, then put your own OpenRouter API key in the local `.env` file. Restart the app. A Claude chat subscription does not supply this key. Never put a secret in chat, browser code or a commit. The template ignores `.env`.

Live mode sends your submitted background and answer, plus the method card, to OpenRouter and the configured model provider. It makes one request for the question and another for the suggestion. Accepting, editing and rejecting do not make more requests. Failed requests display an error; they never switch silently to sample results. A working connection does not establish coaching quality.

### Upload a résumé or CV

Choose **Use my experience**, then the PDF upload option. Select one PDF with selectable text and click **Find experiences**. Selecting the file alone does not send it to the AI service. Processing sends the extracted document text to OpenRouter and the configured model in one additional request, which uses your API credit.

Review the proposed experience cards and the supporting quote/page for each. You can change a title or description and select the cards you want to keep. Adding the selected experiences puts only those approved cards on the landscape. **Find a question** then uses the approved titles and descriptions; rejected cards and the remaining document text are not sent to the coaching step. The original supporting passage stays visible for comparison with your edits. You can export approved experiences before continuing to coaching.

The first version accepts one PDF up to 5 MB, 10 pages, and 30,000 extracted characters, producing at most six proposed cards. Password-protected files, unreadable/scanned pages, and documents exceeding those limits are rejected with guidance to paste text or use a smaller document. This version does not read Word files or perform OCR. Extraction can miss or misinterpret material even when a file is accepted, so check the source passages and edit or leave out inaccurate cards.

The original PDF is processed in memory and is not saved by the app. Extracted text is sent to the configured provider only for card generation; the app retains the proposed cards and their supporting passages for review. After review, only the selected cards remain in the exercise. Uploaded career material is separate from the fixed expert-source library.

### Source and limitations

The exercise adapts Pamela Slim's approach to finding themes across experiences, described in Dorie Clark's [article](https://dorieclark.com/blog/build-personal-brand/), section “Identify Your Themes.” The source card is in `content/method.json`. This is one article-informed exercise; the full book has not been reviewed and neither author endorses the app.

Suggestions remain tentative. The app checks that evidence quotations occur in the user's input and source IDs are known; those checks do **not** prove that a model's interpretation is correct or useful. The user decides what to keep. Edited statements are user-authored and can go beyond the original evidence.

The app stores exercise content, including imported cards and their evidence, in server memory. Sessions expire after an hour of inactivity; expired content is cleared on the next session request or when the server stops. Starting over also clears the current exercise. An opaque cookie identifies the session; it contains no background text or API key. No browser storage is used. Refreshing the page restarts the visible flow; there is no saved-session recovery. A downloaded export remains on your computer and may contain personal material. Unreviewed import cards cannot be exported, and rejected experience cards and rejected themes are excluded. Keep private documents and exports outside the public repository.

### Checks and code map

```bash
.venv/bin/python -m unittest discover -s tests -v
```

- `app.py`: local server, exercise steps, session handling and export.
- `coach.py`: fictional example, model requests and output validation.
- `documents.py`: bounded, in-memory PDF reading in an isolated parser process.
- `content/method.json`: reviewed source card and coverage limits.
- `templates/app.html`, `static/`: browser interface.
- `docs/index.html`: the class Product Page, separate from the local app.
