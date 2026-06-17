# KALEIDO NLP Diagnostics Spike

A throwaway test harness for KALEIDO (an IELTS writing IDE). It exists to feel out whether local, deterministic NLP — instead of a per-event LLM call — can power the writer-assist events delivered inline as the student types.

## Language

### The four calls

**Init**:
The guidance produced when a new sentence slot opens — task/coherence cues, sentence openers, seeded vocabulary. Out of scope for the spike; supplied as canned content rather than generated.
_Avoid_: setup, prompt, scaffold (as a noun)

**Stall**:
A ~2-second typing pause while a sentence is unfinished, which triggers a tooltip offering word- and structure-finding help for the current sentence — likely objects/arguments, collocations, word retrieval for an empty slot, and cohesion linkers. The reactive counterpart to ghost text. It does not supply ideas or content; that is init's job.
_Avoid_: pause, idle, hesitation

**Accuracy**:
The check fired when a sentence terminator is typed, flagging grammar errors (articles, agreement, tense, prepositions) in the completed sentence.
_Avoid_: grammar check, correction, proofread

**Ghost text**:
Faint inline completion at the cursor that proactively continues what the writer is typing — fixed phrases, grammar-pattern continuations (e.g. "According" → "to"), and collocation continuations — accepted with Tab and dismissed by typing past it. Continuous and prefix-driven; its job is to pre-empt stalls before they happen.
_Avoid_: autocomplete, suggestion, Copilot

### Init outputs

**Seeded vocabulary**:
The topic-relevant words and their collocation patterns that init emits for a slot (e.g. "damage [something]"). The stall toolbox reuses this as the topic lexicon for filtering its suggestions.
_Avoid_: word bank, glossary, word list

### Text spans

**Current sentence**:
The span from the last sentence terminator to the cursor — the sentence being written right now. What stall and ghost text reason about.
_Avoid_: line, active text, current line

**Completed sentence**:
The span that closes when a sentence terminator is typed — the sentence that accuracy checks.
_Avoid_: previous sentence, last line

**Sentence slot**:
KALEIDO's one-sentence-at-a-time writing unit; opening one is what triggers init. Not modeled in the spike, which uses a free-form buffer instead.
_Avoid_: field, box, cell

### Delivery

**Inline diagnostics**:
Feedback rendered inside the text buffer at the span it applies to — cursor-anchored tooltips, diagnostic squiggles, ghost text — rather than in a separate region of the screen.
_Avoid_: out-of-band feedback, sidebar, output panel, chat
