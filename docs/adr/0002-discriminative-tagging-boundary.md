# Discriminative edit-tagging is analysis only for closed-class tags

ADR 0001 permits local analysis/vectorizing but bans per-event generation, without addressing discriminative sequence tagging (e.g. GECToR-style GEC, used to catch article and subject-verb-agreement errors LanguageTool's pattern rules miss). Tagging classifies each token into a fixed edit-tag label (`KEEP`, `APPEND_the`, `REPLACE_is→are`, verb-inflection tags) then deterministically applies the winning tag — no autoregressive decoding, but some tags bake in literal words.

We draw the line inside the tag vocabulary itself: a **closed-class tag set** (article insertion, a short preposition list, verb-inflection morphology — on the order of dozens of tags, fixed at training time, same shape as `_COHESION_LINKERS`) counts as bounded analysis and is permitted. **`REPLACE_X→Y` lexical tags**, which scale with vocabulary size and can run into the thousands, are excluded as effectively open-vocabulary generation.

## Considered options

- **All tags are analysis** (the whole tag set, however large, is still a per-token classification decided at training time) — rejected because a tag space in the thousands is indistinguishable in practice from open-vocabulary word choice, which is exactly what ADR 0001 draws the line against.
- **Reject discriminative tagging entirely** (any mechanism that inserts/replaces literal words is generation, closed-class or not) — rejected as overly strict: it would exclude a mechanism with the same closed-vocabulary shape as the cohesion linkers and ghost-text trie already permitted elsewhere in the spike, for no principled reason.

## Consequences

A GECToR-style integration for accuracy may only act on its closed-class tags (articles, verb inflection, a short preposition list) — exactly the gaps named in the 2026-06-18/19 testing-log entries (missing article, subject-verb agreement). Lexical replacement suggestions from such a model are out of scope; LanguageTool's `replacements` field remains the only source of literal word-swap suggestions.
