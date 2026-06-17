# Init-output fixtures

Init ([1]) is out of scope for the spike — its guidance is supplied as **canned** content, not generated. Each file here is one essay prompt's init output: the essay question plus the per-slot scaffolding (JTBD, guidance, openers, seeded vocabulary, sentence templates).

The spike consumes these as the **context** the stall toolbox re-ranks against — see `CONTEXT.md` ("Seeded vocabulary") and the generate-then-re-rank approach. One prompt is enough to start; add more by copying `_TEMPLATE.md`.

## Files

- `car-dependence.md` — seed sample (car use / environment), `claim` slot.
- `_TEMPLATE.md` — copy this to add a new prompt.

## How to add a prompt

1. Copy `_TEMPLATE.md` to `<topic-slug>.md`.
2. Fill in the essay question and the seed metadata (`partial_text`, `slot_rhetorical_move`, `seed_destination`).
3. Paste the init output produced for each slot you want to test.
