Kick-off Build Brief

## Why We're Building This

KALEIDO is an IELTS writing IDE. Students write essays one sentence at a time. Right now, every moment a student pauses (a "stall") or finishes a sentence triggers an LLM call to generate help. That works, but it's slow and expensive at scale.

We have a hypothesis: stall detection and accuracy checking ([2] and [3] in our architecture — see below) might not need an LLM at all. Coding IDEs get instant, free completions using deterministic structures (ASTs, LSPs, tries) instead of calling a model for every keystroke. We think natural language has enough code-like structure (dependency parses, verb-argument frames, collocation lists) that the same trick could work here — using local NLP tools instead of an LLM for these two specific events.

We have **not** decided which tools to use yet. There are several real candidates (e.g. spaCy for parsing, LanguageTool for grammar checking, FrameNet/VerbNet/the Academic Collocation List for content lookups) and we want to test before committing. This tool exists to let us run that test against **real, live human typing**.

## The Three-Call Architecture 

([1] is NOT in scope)

| Call               | Trigger                     | What it does                                                                                 | In scope for this tool?                  |
| ------------------ | --------------------------- | -------------------------------------------------------------------------------------------- | ---------------------------------------- |
| **[1] init**       | New sentence slot opens     | Generates full guidance (TA&CC, openers, seeded vocab)                                       | **No.** Manually scaffolded — see below. |
| **[2] stall**      | ~2s pause mid-sentence      | Helps the student get unstuck                                                                | **Yes — this is what we're testing.**    |
| **[3] accuracy**   | Period detected             | Flags grammar errors (articles, agreement, tense, prepositions)                              | **Yes — this is what we're testing.**    |
| **[4] ghost text** | Continuous, every keystroke | Deterministic next-token/phrase completion for fixed patterns (e.g. "have an impact" → "on") | **Yes — new tier, part of this test.**   |


## What This Tool Must Feel Like

**This must be a real typing/IDE interface, not a chat interface — and no separate output panel either.** The whole point is to observe natural writing behavior — hesitation, backspacing, mid-word pauses — and to test feedback delivered the way real coding IDEs do it: rendered directly inside the text buffer, at the point it's relevant, not off in a sidebar or console. This is **inline diagnostics**, the same pattern behind LSP's `publishDiagnostics` and behind Copilot-style inline completions — as opposed to _out-of-band_ feedback (a separate panel showing results elsewhere on screen).

Concretely, the two events use two different inline idioms, both standard in any code editor:

- **[2] stall → cursor-anchored tooltip.** A small floating suggestion that appears right at the cursor as you type or pause, not pinned to a fixed panel location (Copilot-style inline completions and hover-cards).
- **[3] accuracy → diagnostic squiggle + hover.** When an error is flagged, underline the exact span of text it applies to (red/yellow wavy underline, the standard ESLint/TypeScript pattern). The explanation and suggested fix appear in a small popover on hover or when the cursor sits on that span.
- **[4] Ghost text → inline gray suggestion at the cursor.** As the student types, deterministic completions (collocations, fixed phrase continuations) appear as faint inline text immediately after the cursor, accepted with Tab and dismissed by just continuing to type past them — the standard Copilot-style pattern. Fires continuously, no pause required.

**Important note:** A plain `<textarea>` cannot render inline decorations or anchored popovers — it has no way to style part of its own text or attach a positioned widget to a span but we are not reinventing the wheel. This exact problem — anchor a decoration or popover to an arbitrary span of live text, update it as the text changes — is already solved by mature code-editor libraries (CodeMirror, Monaco, the engine behind VS Code). They have first-class extension APIs for decorations, hover providers, and cursor-anchored widgets. The general term for this in one phrase: **inline diagnostics**, borrowed directly from the Language Server Protocol as the north star — LSP literally has a `publishDiagnostics` mechanism that renders this way. 

