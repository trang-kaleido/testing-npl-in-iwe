# Testing log

Manual test notes for the local-NLP diagnostics spike. Append-only, newest entry on top.

## 2026-06-18 — ghost text data source replaced (issue #6)

**Bug found**: the shipped trie (`FORCED_CONTINUATIONS` in `frontend/src/ghost.js`) was 14 hand-typed phrase→continuation pairs with no cited source — it only ever matched those exact 14 strings, so there was nothing generalizable to test. Reopened #6.

**Fix**: replaced it with a list extracted and empirically validated from the STREUSLE corpus (`scripts/extract_ghost_continuations.py`, see that file for the pinned commit and method) — a prefix only counts as "forced" if every occurrence of it anywhere in the corpus is followed by the same word, with at least 2 occurrences. Result: 6 entries (`as soon`→` as`, `in front`→` of`, `in the middle`→` of`, `according`→` to`, `in need`→` of`, `when it comes`→` to`), down from 14, but every entry is now corpus-validated rather than invented.

**Domain-fit gap (open)**: STREUSLE is hand-annotated Yelp reviews, not academic writing. Checked directly: none of the original IELTS-register phrases ("in terms of", "with regard to", "as opposed to", "a wide range of", etc.) occur in the corpus at all, except "regardless of" / "in spite of" (which didn't pass the ≥2-occurrence cardinality check). So the shipped list proves the extraction *method* works, but doesn't yet cover academic-register ghost text — that needs a different, academic-domain corpus with comparable MWE annotation, which wasn't found in this pass.

**Implemented**: edits that overlap an existing diagnostic's span (manual retyping or clicking a suggestion) now trigger an automatic recheck of that sentence, instead of only rechecking when the user retypes the sentence terminator. This closes the "sequential reveal" gap from the entry below: correcting `"Many person has problem with me."` to `"Many people has problem with me."` now immediately surfaces the newly-revealed `PEOPLE_VBZ` flag on "has", without waiting for the user to retype the period.

**Future scope — this does not fix LT's coverage gaps**: the recheck loop only helps when a fix changes the literal text enough to match a *different* existing LT rule. It does nothing for errors LT has no rule for at all, in any phrasing — e.g. the missing-article ("use car") and subject-verb-agreement ("air get polluted") misses noted below never get caught no matter how many times the sentence is rechecked, since there's no pattern to match in the first place. Closing that gap means changing the grammar-checking backend, not rechecking more.

**Note for future investigation**: Grammarly's pipeline is reportedly a hybrid — a layer of fast, narrow, rule/pattern-based checks (similar in spirit to LanguageTool: explainable, low-latency, high-precision) combined with a neural GEC (Grammar Error Correction) model that handles the broader, parsing-dependent corrections rule-based systems miss, with a ranking/merge step reconciling both sets of suggestions. Worth verifying this against primary sources before committing engineering effort, but it maps onto our two earlier options (swap vs. augment): an "augment" path would mean keeping LT for its cheap/explainable matches and adding a GEC model alongside it for the rest, rather than fully replacing LT.

## 2026-06-18 — accuracy squiggles (issues #1, #2)

**Setup**: LanguageTool sidecar (`erikvl87/languagetool` Docker image) + FastAPI backend + Vite frontend, run locally per `docs/dev-startup.md`.

**Bug found — squiggles didn't clear on fix**: editing the flagged word inside an already-terminated sentence (without retyping the sentence terminator) left the red squiggle in place. Root cause: `diagnosticField` in `frontend/src/editor.js` only ever repositioned diagnostics via `mapPos` on doc changes and merged new diagnostics additively — nothing ever invalidated a diagnostic once added, and a clean recheck (zero new matches) didn't dispatch at all. Fixed: edits overlapping a diagnostic's span now drop it immediately, and a recheck replaces (rather than merges with) prior diagnostics in its sentence range, including the zero-match case.

**Insight — LanguageTool's rule coverage is pattern-based, not general grammar parsing**: tested `"For example when too many person use car, air get polluted."` — only the "many person" agreement error was flagged; "use car" (missing article) and "air get polluted" (subject-verb agreement) were not, even tested in isolation. Looked like a coverage gap at first. Follow-up test narrowed it down:

- `"Many person has problem with me."` → only `MANY_NN` fires (flags "Many person").
- `"Many people has problem with me."` → only `PEOPLE_VBZ` fires (flags "has").

So LanguageTool isn't doing general subject-verb agreement parsing — `PEOPLE_VBZ` is a narrow rule keyed to the literal word "people" followed by a singular verb. "person has" doesn't match any built-in pattern, so it's silent; "people has" does. Each match is evaluated against the literal text as typed — LT never reasons about hypothetical corrections ("if error #1 were fixed, would a new error appear"). This is a structural characteristic of self-hosted LanguageTool (a large set of narrow lexical/pattern rules, no full syntactic grammar engine), not a config issue or something fixable on our side without swapping the grammar-checking backend.
