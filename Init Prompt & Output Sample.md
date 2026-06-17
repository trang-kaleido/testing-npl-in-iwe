Init Prompt & Output Sample

## Prompt

```text
Core Loop Goal: Generate student-facing writing scaffolding based on:
- partial_text (Current state: null)
- slot_rhetorical_move (Current state: claim)
- seed_destination (The core argument/idea to convey)

Execute the following 7-step Chain of Thought internally to generate the final response. Do not output the step headers or internal reasoning; output only the final student-facing text exactly matching the target format.

[INTERNAL REASONING STEPS]

1. Analyze Move & Question:
   Identify the slot_rhetorical_move and the specific essay prompt question it is addressing (e.g., "What are the problems?").

2. Draft Pedagogical Guidance (Band 6 Language):
   Formulate a simple, direct explanation of what this specific sentence needs to achieve. Explain the core logic of the seed_destination using clear, foundational vocabulary. Explicitly state structural rules (e.g., "use one simple sentence", "Don't use a complex sentence here", or "Use conditional sentence").

3. Formulate Hidden Reference Sentences (Internal Only):
   Draft 2 high-level, elegant (Band 8+) candidate sentences that perfectly fulfill the seed_destination. Use these sentences as the secret blueprint/reference for steps 4, 5, and 6. Do not include these sentences in the final output.

4. Derive Question-Linked Openers:
   From the internal reference sentences, isolate the first 3 to 5 words to serve as "Openers". These openers must explicitly contain framing words that link directly to the essay paragraph's purpose/question (e.g., "One major issue is that...", "A primary problem arises when...").

5. Extract Vocabulary & Definitions:
   Identify noun phrases and verbs used in your internal reference sentences. For each, write a highly simplified, plain-English definition. For verbs, explicitly show their object collocation pattern (e.g., "obstruct [something]").

6. Abstract Syntax Templates:
   Take the internal reference sentences and replace the extracted noun phrases with clean, simple placeholders (X, Y, Z). Ensure these structures integrate seamlessly with the exact openers generated in Step 4.

7. Final Assembly:
   Assemble the final output exactly according to the template below, omitting all meta-tags, markdown headers, and internal references.


Target Output Template

JTBD - make a claim
This paragraph answers a question: [Insert Question, e.g., What are the problems?]

[Insert Step 2 Guidance: Sentence objectives and clear-language breakdown of the problem/argument]

You can start your sentence with: 

[Opener 1]...
[Opener 2]... 

Some useful vocabularies:

[Word/Phrase]: [Simple Definition]
[Verb [something]]: [Simple Definition]

Some sentence structures you can use:

[Template 1 using X, Y, Z]
[Template 2 using X, Y, Z]

**GRA Impact:** [Insert exactly one sentence explaining to the student how this specific syntax structure hits high-band criteria]
```

## Output Sample
### Context:
Question: Many people depend on their cars for everyday domestic, social, and working needs. However, unlimited use of cars causes a number of problems. What are some of these problems? What can be done to reduce the use of cars?

`partial_text` = null 
`slot_rhetorical_move` = claim 
`seed_destination`: Prioritizing unlimited Individual convenience in car use acts as a Blocking relationship against a Sustainable environment, which ultimately damages human Flourishing.

### Output (ChatGPT)
```text
JTBD - make a claim
This paragraph answers a question: What are the problems?

Your job is to introduce one main problem caused by unlimited car use. Explain that when people always choose personal convenience, it becomes harder to protect the environment. Use one simple sentence to state this problem clearly. Do not add solutions or examples yet.

You can start your sentence with:

One major problem is that...
A primary issue is that...

Some useful vocabularies:

individual convenience: personal comfort and ease for one person
sustainable environment: a natural environment that can continue to stay healthy in the future
human well-being: people's health, happiness, and quality of life
prioritize [something]: give something the highest importance
damage [something]: cause harm to something
protect [something]: keep something safe from harm

Some sentence structures you can use:

One major problem is that prioritizing X over Y damages Z.
A primary issue is that when people prioritize X, it becomes more difficult to protect Y, which harms Z.

**GRA Impact:** This structure clearly shows a cause-and-effect relationship, helping you develop ideas logically and accurately.
```
