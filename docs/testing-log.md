# Testing log

Manual test notes for the local-NLP diagnostics spike. Append-only, newest entry on top.

## 2026-06-18 — accuracy squiggles (issues #1, #2)

**Setup**: LanguageTool sidecar (`erikvl87/languagetool` Docker image) + FastAPI backend + Vite frontend, run locally per `docs/dev-startup.md`.

**Bug found — squiggles didn't clear on fix**: editing the flagged word inside an already-terminated sentence (without retyping the sentence terminator) left the red squiggle in place. Root cause: `diagnosticField` in `frontend/src/editor.js` only ever repositioned diagnostics via `mapPos` on doc changes and merged new diagnostics additively — nothing ever invalidated a diagnostic once added, and a clean recheck (zero new matches) didn't dispatch at all. Fixed: edits overlapping a diagnostic's span now drop it immediately, and a recheck replaces (rather than merges with) prior diagnostics in its sentence range, including the zero-match case.

**Insight — LanguageTool's rule coverage is pattern-based, not general grammar parsing**: tested `"For example when too many person use car, air get polluted."` — only the "many person" agreement error was flagged; "use car" (missing article) and "air get polluted" (subject-verb agreement) were not, even tested in isolation. Looked like a coverage gap at first. Follow-up test narrowed it down:

- `"Many person has problem with me."` → only `MANY_NN` fires (flags "Many person").
- `"Many people has problem with me."` → only `PEOPLE_VBZ` fires (flags "has").

So LanguageTool isn't doing general subject-verb agreement parsing — `PEOPLE_VBZ` is a narrow rule keyed to the literal word "people" followed by a singular verb. "person has" doesn't match any built-in pattern, so it's silent; "people has" does. Each match is evaluated against the literal text as typed — LT never reasons about hypothetical corrections ("if error #1 were fixed, would a new error appear"). This is a structural characteristic of self-hosted LanguageTool (a large set of narrow lexical/pattern rules, no full syntactic grammar engine), not a config issue or something fixable on our side without swapping the grammar-checking backend.
