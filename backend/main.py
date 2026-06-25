import asyncio

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import spacy
import torch
from sentence_transformers import SentenceTransformer
import numpy as np
from gector import GECToR, load_verb_dict
from gector.predict import get_word_masks_from_word_ids, process_token
from transformers import AutoTokenizer

LANGUAGETOOL_URL = "http://localhost:8081/v2/check"
GECTOR_MODEL_ID = "gotutiyan/gector-roberta-base-5k"
VERB_DICT_PATH = "data/verb-form-vocab.txt"

nlp = spacy.load("en_core_web_sm")
sbert = SentenceTransformer("all-MiniLM-L6-v2")

gector_model = GECToR.from_pretrained(GECTOR_MODEL_ID)
gector_model.eval()
gector_tokenizer = AutoTokenizer.from_pretrained(GECTOR_MODEL_ID)
_verb_encode, _verb_decode = load_verb_dict(VERB_DICT_PATH)

# ── Candidate tables ──────────────────────────────────────────────────────────

# Case #1 — argument-missing: ROOT verb with no direct object
_VERB_OBJECTS: dict[str, list[str]] = {
    "reduce": ["emissions", "pollution", "costs", "taxes", "traffic", "congestion",
               "waste", "dependence", "reliance", "harm", "damage", "risk", "inequality", "use"],
    "increase": ["efficiency", "output", "investment", "awareness", "funding",
                 "productivity", "quality", "access", "participation"],
    "cause": ["pollution", "congestion", "emissions", "damage", "harm",
              "problems", "issues", "delays", "inequality"],
    "address": ["problem", "issue", "challenge", "concern", "inequality", "crisis", "need"],
    "improve": ["quality", "efficiency", "health", "infrastructure", "conditions", "access"],
    "protect": ["environment", "health", "rights", "wildlife", "communities", "citizens"],
    "limit": ["emissions", "use", "access", "pollution", "growth", "consumption", "dependence"],
    "promote": ["sustainability", "awareness", "health", "development", "equality", "growth"],
    "support": ["development", "growth", "sustainability", "communities", "investment", "education"],
    "prevent": ["pollution", "damage", "harm", "accidents", "crime", "inequality", "congestion"],
    "encourage": ["use", "participation", "investment", "development", "growth", "adoption"],
    "achieve": ["sustainability", "balance", "growth", "equality", "goals", "outcomes"],
    "prioritize": ["environment", "health", "sustainability", "safety", "equality", "well-being"],
    "damage": ["environment", "health", "ecosystem", "infrastructure", "communities", "well-being"],
}

# Case #2 — collocation: content word with an open set of valid partners
_WORD_COLLOCATES: dict[str, list[str]] = {
    # Adjective → noun collocates
    "significant": ["impact", "increase", "decrease", "role", "challenge", "problem"],
    "major": ["problem", "challenge", "concern", "impact", "issue"],
    "serious": ["consequences", "problem", "threat", "issue", "concern"],
    "growing": ["concern", "problem", "trend", "awareness"],
    "negative": ["impact", "effect", "consequences"],
    "positive": ["impact", "effect", "outcome"],
    "harmful": ["effects", "consequences", "impact"],
    "severe": ["consequences", "impact", "damage", "penalties"],
    "environmental": ["damage", "impact", "consequences", "benefits"],
    "economic": ["growth", "development", "impact", "consequences"],
    "social": ["consequences", "impact", "inequality", "issues"],
    # Noun → compound-noun partners
    "carbon": ["emissions", "footprint", "dioxide"],
    "air": ["pollution", "quality"],
    "traffic": ["congestion", "pollution", "management"],
    "public": ["transport", "health", "sector", "awareness"],
    "fossil": ["fuels", "fuel consumption"],
}

# Case #6 — cohesion: standard discourse-marker inventory
_COHESION_LINKERS: list[str] = [
    # Addition
    "Furthermore,",
    "Moreover,",
    "In addition,",
    # Contrast
    "However,",
    "Nevertheless,",
    "On the other hand,",
    "In contrast,",
    # Cause / effect
    "Therefore,",
    "As a result,",
    "Consequently,",
    # Illustration
    "For instance,",
    "For example,",
    # Conclusion
    "In conclusion,",
]

# Closed-class GECToR tags for /accuracy — see ADR 0002. Articles and a short
# preposition list are permitted for $APPEND_/$REPLACE_; everything else under
# those prefixes is open-vocabulary lexical generation and is dropped.
_CLOSED_CLASS_ARTICLES: set[str] = {"a", "an", "the"}
_CLOSED_CLASS_PREPOSITIONS: set[str] = {
    "in", "on", "at", "to", "of", "for", "with", "by", "from", "about",
}
_CLOSED_CLASS_WORDS: set[str] = _CLOSED_CLASS_ARTICLES | _CLOSED_CLASS_PREPOSITIONS

# ── FastAPI setup ─────────────────────────────────────────────────────────────

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AccuracyRequest(BaseModel):
    sentence: str


class InitContext(BaseModel):
    seeded_vocabulary: dict[str, str]
    seed_destination: str


class StallRequest(BaseModel):
    current_sentence: str
    init_context: InitContext


# ── NLP helpers ───────────────────────────────────────────────────────────────

def _needs_object(token) -> bool:
    return not any(child.dep_ in ("dobj", "obj") for child in token.children)


def _content_lemmas(text: str) -> set[str]:
    return {t.lemma_ for t in nlp(text.lower()) if t.is_alpha and not t.is_stop}


def _generate_candidates(doc, seeded_vocabulary: dict[str, str]) -> list[str]:
    """Return candidate words covering all four stuck-state cases.

    Priority order:
      #6 cohesion        — very short sentence (sentence start / transition)
      #1 argument-missing — ROOT verb with no direct object
      #2 collocation      — last content word has known collocates
      #4 lexical retrieval — fallback: seeded vocabulary words
    """
    word_count = sum(1 for t in doc if not t.is_punct and not t.is_space)

    # Case #6: cohesion
    if word_count <= 2:
        return _COHESION_LINKERS

    # Case #1: argument-missing — ROOT verb with no dobj
    for token in doc:
        if (token.dep_ == "ROOT"
                and token.pos_ in ("VERB", "AUX")
                and token.lemma_ in _VERB_OBJECTS
                and _needs_object(token)):
            return _VERB_OBJECTS[token.lemma_]

    # Also check any verb with no dobj (not just ROOT)
    for token in reversed(list(doc)):
        if (token.pos_ == "VERB"
                and token.lemma_ in _VERB_OBJECTS
                and _needs_object(token)):
            return _VERB_OBJECTS[token.lemma_]

    # Case #2: collocation — last content word with known collocates
    for token in reversed(list(doc)):
        if (not token.is_stop
                and token.is_alpha
                and token.lemma_.lower() in _WORD_COLLOCATES):
            return _WORD_COLLOCATES[token.lemma_.lower()]

    # Case #4: lexical retrieval — propose words from seeded vocabulary
    candidates: list[str] = []
    for phrase in seeded_vocabulary:
        word = phrase.replace("[something]", "").strip().split()[0]
        if word and word not in candidates:
            candidates.append(word)
    return candidates


def _vocab_overlap_scores(candidates: list[str], seeded_vocabulary: dict[str, str]) -> list[float]:
    vocab_lemma_sets = [
        _content_lemmas(phrase.replace("[something]", "").strip()) | _content_lemmas(definition)
        for phrase, definition in seeded_vocabulary.items()
    ]
    scores = []
    for candidate in candidates:
        cand_lemmas = _content_lemmas(candidate)
        scores.append(float(sum(len(cand_lemmas & vocab) for vocab in vocab_lemma_sets)))
    return scores


def _sbert_scores(candidates: list[str], seed_destination: str) -> list[float]:
    texts = candidates + [seed_destination]
    embeddings = sbert.encode(texts, normalize_embeddings=True)
    dest_emb = embeddings[-1]
    return [float(np.dot(emb, dest_emb)) for emb in embeddings[:-1]]


def _is_closed_class_tag(tag: str) -> bool:
    if tag in ("$KEEP", "$DELETE", "$MERGE_HYPHEN", "$MERGE_SPACE"):
        return True
    if tag.startswith("$TRANSFORM_"):
        return True
    if tag.startswith("$APPEND_") or tag.startswith("$REPLACE_"):
        return tag.split("_", 1)[1] in _CLOSED_CLASS_WORDS
    return False


def _gector_word_tags(doc) -> list[str]:
    """Run the GECToR tagger once and return one tag per spaCy token.

    Word-aligned via spaCy's own tokenization (already loaded for /stall),
    so spans can be read straight off `token.idx` with no subword realignment.
    """
    words = ["$START"] + [t.text for t in doc]
    batch = gector_tokenizer(
        [words],
        return_tensors="pt",
        is_split_into_words=True,
        truncation=True,
        max_length=gector_model.config.max_length,
        add_special_tokens=not gector_model.config.is_official_model,
    )
    word_masks = torch.tensor(get_word_masks_from_word_ids(batch.word_ids, 1))
    with torch.no_grad():
        outputs = gector_model.predict(batch["input_ids"], batch["attention_mask"], word_masks)

    raw_labels = outputs.pred_labels[0]
    per_word: list[str] = []
    previous_id = None
    for j, word_id in enumerate(batch.word_ids(0)):
        if word_id is None:
            continue
        if word_id != previous_id:
            per_word.append(raw_labels[j])
        previous_id = word_id
    return per_word[1:]  # drop the synthetic $START slot


def _tag_diagnostic(token, next_token, tag: str) -> dict | None:
    if tag == "$KEEP":
        return None

    start, end = token.idx, token.idx + len(token.text)

    if tag == "$DELETE":
        return {
            "span": {"from": start, "to": end},
            "category": "TAGGER_GRAMMAR",
            "message": f"Remove '{token.text}'.",
            "replacements": [""],
        }

    if tag in ("$MERGE_HYPHEN", "$MERGE_SPACE") and next_token is not None:
        joiner = "-" if tag == "$MERGE_HYPHEN" else ""
        merged = token.text + joiner + next_token.text
        return {
            "span": {"from": start, "to": next_token.idx + len(next_token.text)},
            "category": "TAGGER_GRAMMAR",
            "message": f"Merge into '{merged}'.",
            "replacements": [merged],
        }

    if tag.startswith("$APPEND_"):
        word = tag[len("$APPEND_"):]
        return {
            "span": {"from": end, "to": end},
            "category": "TAGGER_GRAMMAR",
            "message": f"Insert '{word}' after '{token.text}'.",
            "replacements": [word],
        }

    if tag.startswith("$REPLACE_") or tag.startswith("$TRANSFORM_"):
        corrected = process_token(token.text, tag, _verb_encode, _verb_decode)
        if not corrected or corrected == token.text:
            return None
        return {
            "span": {"from": start, "to": end},
            "category": "TAGGER_GRAMMAR",
            "message": f"Try '{corrected}' instead of '{token.text}'.",
            "replacements": [corrected],
        }

    return None


def _tagger_diagnostics(doc) -> list[dict]:
    tokens = list(doc)
    if not tokens:
        return []
    tags = _gector_word_tags(doc)
    diagnostics = []
    for i, (token, tag) in enumerate(zip(tokens, tags)):
        if not _is_closed_class_tag(tag):
            continue
        next_token = tokens[i + 1] if i + 1 < len(tokens) else None
        diagnostic = _tag_diagnostic(token, next_token, tag)
        if diagnostic is not None:
            diagnostics.append(diagnostic)
    return diagnostics


def _spans_overlap(a: dict, b: dict) -> bool:
    return a["from"] < b["to"] and b["from"] < a["to"]


def _merge_diagnostics(lt_diagnostics: list[dict], tagger_diagnostics: list[dict]) -> list[dict]:
    kept_tagger = [
        d for d in tagger_diagnostics
        if not any(_spans_overlap(d["span"], lt["span"]) for lt in lt_diagnostics)
    ]
    return lt_diagnostics + kept_tagger


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.post("/stall")
async def stall(req: StallRequest):
    doc = nlp(req.current_sentence)

    candidates = _generate_candidates(doc, req.init_context.seeded_vocabulary)
    if not candidates:
        return []

    overlap = _vocab_overlap_scores(candidates, req.init_context.seeded_vocabulary)

    if max(overlap) > 0 and len(set(overlap)) > 1:
        final_scores = overlap
    else:
        final_scores = _sbert_scores(candidates, req.init_context.seed_destination)

    ranked = sorted(zip(candidates, final_scores), key=lambda x: x[1], reverse=True)
    return [{"text": word, "score": round(score, 4)} for word, score in ranked]


async def _languagetool_diagnostics(sentence: str) -> list[dict]:
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                LANGUAGETOOL_URL,
                data={"text": sentence, "language": "en-US"},
                timeout=10.0,
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"LanguageTool unreachable: {exc}")

    matches = resp.json().get("matches", [])
    return [
        {
            "span": {
                "from": m["offset"],
                "to": m["offset"] + m["length"],
            },
            "category": m["rule"]["category"]["id"],
            "message": m["message"],
            "replacements": [r["value"] for r in m.get("replacements", [])],
        }
        for m in matches
    ]


@app.post("/accuracy")
async def accuracy(req: AccuracyRequest):
    doc = nlp(req.sentence)
    lt_diagnostics, tagger_diagnostics = await asyncio.gather(
        _languagetool_diagnostics(req.sentence),
        asyncio.to_thread(_tagger_diagnostics, doc),
    )
    return _merge_diagnostics(lt_diagnostics, tagger_diagnostics)
