# No per-event language generation; local neural encoders permitted

The spike tests whether KALEIDO's stall, accuracy, and ghost-text events can be served without an LLM. We draw the boundary at **language _generation_, not neural models**: no event may generate text at runtime (no per-event model call that writes words), but events may freely use local, deterministic, free tools that only _analyze or vectorize_ — including neural ones (spaCy parsing, LanguageTool, a local SBERT sentence encoder for relevance re-ranking). Init remains the only component that generates language, via the LLM, and is out of scope for the spike.

We permit a local SBERT encoder because the goal is to test SOTA NLP _without generation_ at full strength; restricting to averaged classical word vectors would cripple the context-aware re-ranking for no real gain, since SBERT is a frozen model loaded once, not a per-event API call.

## Considered options

- **Strictly symbolic** (parses + collocation tables + word lists only) — rejected as an unfairly weak test that would undersell a hypothesis that may well be right.

## Consequences

"No LLM" in this project means "no per-event generation," _not_ "no machine learning." All spike results must be read with that boundary in mind: a reviewer expecting a purely symbolic system should know that neural parsers and a neural sentence encoder are deliberately permitted.
