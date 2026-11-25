# Story Studio: November 23, 2026

This source update follows the successful Build 3 submission at 8:51 AM New York time. It does not replace that receipt or change the observed deployment: Render still serves revision `b83f1cb`, with automatic deploys off. The approved task is to recode and push; a new public deployment is separate.

## Product decision

The builder approved the story-studio concept after clarifying the need for a coherent core narrative, multiple authentic origin stories, concrete anecdotes, and different aspects of résumé experiences for different audiences. Origin selection and audience emphasis are independent. The app should help discover the material, not require a settled career destination or fabricate a more convenient identity.

## Current-source flow

- `/` and `/workshop`: Story Studio. `/reflection` and `/book-workshop`: retained earlier flows.
- Add an experience or upload and review one bounded résumé/CV PDF. Only approved cards enter the library.
- Explore one experience through optional situation, action, outcome, and learning notes.
- Save own core wording or explicitly request a draft. Develop different origins and anecdotes, review supporting evidence, and keep, edit, or omit the result.
- Choose a kept origin plus audience, setting, and purpose to prepare an introduction, résumé angle, and conversation question.
- Export and restore a validated story-library JSON file. Sessions remain temporary; no database, account, or automatic backup is added.

The studio is app-authored. The private Body of Work guide remains with the separate book workshop. No personal résumé, source transcript, book content, or builder-specific draft from the concept is published as sample data.

## Boundaries

AI requests are explicit and bounded. Audience and aspirations are presentation context, not evidence of past results. Generated material stays pending until reviewed. Editing evidence invalidates dependent material for later use. PDF parsing, same-origin requests, opaque sessions, version guards, shared rate limits, and replay-blocked personal content remain required.

The sample is fictional and does not call the provider. User wording can be saved without an API key. AI drafting and PDF extraction require the configured key. There are no new package, account, database, or hosting requirements.

## Verification and follow-up

Implementation began November 23; the final interface check and push preparation finished November 25. The existing suite passed all 152 Python checks, including the new studio transitions, stale-source handling, bounded export/restore, session/version guards, PDF review, and shared production quotas. All 13 analytics JavaScript checks passed with a stub SDK; the final studio script passed its syntax check. No dependencies were added.

In the local browser, a fictional library-volunteer example completed manual experience/reflection entry, one real AI origin request, wording edits and explicit review, a user-written core, one real AI audience adaptation, review, and a JSON download. These were two provider requests, not a model-quality evaluation. The first drafts were too long and included unsupported interpretations; the prompts were subsequently tightened for concise, source-grounded wording. That final prompt revision has not had another live-model check.

The browser's file-upload steps each remained open beyond the one-hour session lifetime; restore correctly returned a stale-session error and recovery reopened the studio. Browser restoration was therefore not completed. Deterministic export/restore checks passed, including keeping the previous exportable library when a mutation would exceed the file limit. The fixed fictional example also completed core/origin review, and a 390 × 844 viewport had no horizontal overflow. This is a responsive browser check, not a physical-phone or outside-user test. No new live PostHog receipt or replay result is claimed. The November 23 morning deployment/security evidence applies to `b83f1cb`, not this new source.

Before publishing the redesign to Render, record the exact pushed revision, protect any active session with an export, and verify the new live flow and privacy boundaries. Test whether a target user can leave with one useful, authentic story at reasonable effort; the comparison with ordinary prompting remains open.

## Time and spending

Additional time and API spending for this redesign have not been recorded. Do not reuse the earlier two-hour Build 3 estimate as a measurement of this later work.
