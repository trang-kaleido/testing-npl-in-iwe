# PRD — Local-NLP Inline Diagnostics Spike

> Status: ready-for-agent. Stored locally (not published to the issue tracker) by request.
> Companion docs: `CONTEXT.md` (glossary), `docs/adr/0001-no-per-event-generation.md`, `fixtures/init-outputs/`.

## Problem Statement

KALEIDO is an IELTS writing IDE where students write essays one sentence at a time. Today, every **stall**, every **accuracy** check, and any inline completion fires an LLM call — slow and expensive at scale. We suspect these per-event assists have enough exploitable linguistic structure (dependency parses, verb-argument frames, collocations) to be served by local, deterministic NLP instead — the way coding IDEs get instant, free completions from ASTs, LSPs, and tries. We don't know if that's true, or which tools deliver it, and we can't tell by reasoning. We need to **feel it against real, live typing**.

## Solution

A throwaway, single-prompt writing surface — a real IDE-style text buffer (CodeMirror 6), **not** a chat box and **not** a side panel — that delivers the three in-scope assists as **inline diagnostics** powered entirely by local NLP with **no per-event LLM generation**. The team types a real IELTS sentence and judges, by feel, whether the local-NLP path is good enough to replace the LLM for **ghost text**, **stall**, and **accuracy**.

## User Stories

**Writer-facing**

1. As a writer, I want a real text buffer I can type into continuously, so that my natural hesitation, backspacing, and pausing happen as they really would.
2. As a writer, when I pause ~2 seconds mid-sentence, I want a small suggestion at my cursor, so that I can get unstuck without leaving the text.
3. As a writer, I want the **stall** suggestion to offer the likely next word or argument *relevant to my topic*, so that it feels like the editor understands what I'm writing.
4. As a writer, when I have a verb but no object, I want the tooltip to offer likely objects, so that I can complete my clause.
5. As a writer, when I have a word that needs a partner, I want a shortlist of valid collocations, so that I can pick natural phrasing.
6. As a writer, when I'm hunting for a word to fill a slot, I want topically-relevant candidates, so that I can find the word I mean.
7. As a writer, when I've finished a thought and need to connect to the next, I want a cohesion-linker suggestion, so that my sentences flow.
8. As a writer, I want stall suggestions ranked by relevance to this paragraph's idea, not just general frequency, so that the top suggestion is usually the one I want.
9. As a writer, I want faint gray **ghost text** as I type when there's one obvious continuation, so that I can accept it with Tab and keep flow.
10. As a writer, I want ghost text to complete fixed phrases and dependent prepositions (e.g. "have an impact" → "on"), so that I never stall on mechanical continuations.
11. As a writer, I want to dismiss ghost text by just typing past it, so that it never blocks me.
12. As a writer, when I end a sentence with a terminator, I want grammar errors in that **completed sentence** underlined, so that I see mistakes inline.
13. As a writer, I want to hover an underlined error and see an explanation plus a suggested fix, so that I can correct it.
14. As a writer, I want errors color-coded by type (grammar / spelling / style), so that I can tell a real grammar catch from a style nag at a glance.
15. As a writer, I want every assist rendered inside the buffer at the relevant span — never in a sidebar or chat — so that feedback is where my attention already is.
16. As a writer, I want the canned init scaffolding (openers, seeded vocabulary, templates) available for the sentence I'm writing, so that I have the same support the real product gives.

**Experimenter-facing**

17. As an experimenter, I want to swap the tool behind any one event without touching the editor, so that I can compare candidate tools by feel quickly.
18. As an experimenter, I want the stall and accuracy logic behind a clean local HTTP endpoint, so that I can iterate on NLP in Python independently of the front end.
19. As an experimenter, I want ghost text computed client-side, so that per-keystroke completion is instant with no network in the hot path.
20. As an experimenter, I want to add new essay prompts (init outputs) as fixtures, so that I can test the assists across topics.
21. As an experimenter, I want the stall toolbox to re-rank candidates against the slot's seeded vocabulary and `seed_destination`, so that I can see whether context-aware ranking makes suggestions feel smart.
22. As an experimenter, I want every assist to run with no per-event LLM call, so that the test honestly measures local NLP.
23. As an experimenter, I want to run the whole thing locally with minimal setup, so that I can start typing quickly.
24. As an experimenter, I want accuracy to show LanguageTool's full raw output, so that I can judge its true breadth before deciding whether to filter.

## Implementation Decisions

- **Editor:** CodeMirror 6 in the browser. Free-form buffer — no sentence-slot machinery. `current sentence` = last terminator → cursor; `completed sentence` = the span closed when a terminator is typed.
- **Three provider seams, one per event, editor-agnostic** (the single architectural investment; everything else is the cheapest thing that works):
  - **Ghost provider** — client-side function, prefix-driven, returns a single *forced* continuation or nothing (fixed phrases, dependent prepositions / colligations, grammar-pattern projections). Backed by a precomputed trie. No backend.
  - **Stall provider** — local HTTP `POST /stall`. Input: current sentence + cursor context + active init context (seeded vocabulary, `seed_destination`). Output: ranked suggestion list. Internals: spaCy parse → candidate generation (verb frames, collocation tables, reverse-collocation, linker bank) covering case #1 argument-missing, #2 collocation, #4 lexical retrieval, #6 cohesion → **generate-then-re-rank** by relevance to init context using a local SBERT encoder. Triggered on ~2s pause while the current sentence is unfinished.
  - **Accuracy provider** — local HTTP `POST /accuracy`. Input: completed sentence. Output: `diagnostics[]` of `{span, category, message, replacements}`. Internals: LanguageTool, **raw/unfiltered**, on the completed sentence only, LT alone. Triggered on terminator.
- **Backend:** one thin Python (FastAPI) service exposing `/stall` and `/accuracy`. spaCy and SBERT load in-process once; LanguageTool runs as a local sidecar HTTP server the service calls.
- **Boundary rule (ADR-0001):** no per-event language *generation*. Local analyzers/encoders (spaCy, LanguageTool, SBERT) are permitted. Init is the only generator and is out of scope (canned fixtures).
- **Init context:** loaded from `fixtures/init-outputs/*.md` (seed sample `car-dependence.md`; `_TEMPLATE.md` placeholder). One prompt is enough to start; more are added as fixtures and tested one at a time.
- **Ghost vs stall division:** *cardinality* — one forced continuation → ghost; an open set of valid options → stall. Collocation menus are stall-only.
- **Delivery (inline diagnostics):** stall → cursor-anchored tooltip; accuracy → diagnostic squiggle + hover popover, color-coded by category; ghost → faint inline gray text, Tab to accept, type-past to dismiss.
- **Ranking detail:** start with seeded-vocabulary lemma overlap; escalate to SBERT cosine similarity against `seed_destination` when overlap is too sparse to discriminate.
- **Build order:** [3] accuracy (tracer bullet — proves the editor ↔ backend ↔ inline-diagnostic loop with least NLP) → [2] stall (reuses the proven seam and popover) → [4] ghost (client-only, independent, slots in last).

## Testing Decisions

- **Primary evaluation is manual / gut-feel** through the live editor — no telemetry, no logging, by deliberate choice. A good "result" here is: *does the assist feel right on real typing?*
- Where automated tests add value, they sit at the **provider seams** and assert *external behavior*, never internals:
  - **Accuracy provider:** given a sentence with a known article / agreement / tense / preposition error, returns a diagnostic spanning the right text with a message and replacement; given a clean sentence, returns none (modulo LT's own noise).
  - **Stall provider:** given "The government should reduce" plus the `car-dependence` init context, returns topic-relevant object candidates (e.g. *emissions*, *pollution*) ranked above generic ones.
  - **Ghost provider:** given "have an impact", returns "on"; given an open-set prefix ("make a"), returns nothing (defers to stall).
- **Prior art:** none — greenfield. These are the first tests. Keep them few and behavioral.

## Out of Scope

- [1] **init** generation (LLM) — supplied as canned fixtures only.
- **Sentence-slot** UI / enforced one-sentence-at-a-time flow — free buffer instead.
- **Telemetry, logging, session capture, accounts, hosting** — local, gut-feel only.
- **Cross-sentence accuracy** (article definiteness by prior mention, tense consistency across sentences) — completed sentence only.
- **Content / idea help** (case #5, the "blank-mind" stall) — init's job, not the toolbox's.
- **Production code quality / merging into KALEIDO** — throwaway spike.

## Further Notes

- Candidate tools are not finally chosen; the seam exists precisely so they can be swapped by feel.
- Concrete data resources are picked at build time. Recommendations: for ghost, an academic formulas / fixed-phrase list plus a dependent-preposition list, filtered to single-continuation entries; for stall, spaCy plus a collocation source (e.g. the Academic Collocation List), static or SBERT embeddings, and a standard linker inventory.
- Everything outside the provider seam may be quick and dirty — styling, state, wiring — because the artifact is disposable.
