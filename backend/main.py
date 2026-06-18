from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import spacy
from sentence_transformers import SentenceTransformer
import numpy as np

LANGUAGETOOL_URL = "http://localhost:8081/v2/check"

nlp = spacy.load("en_core_web_sm")
sbert = SentenceTransformer("all-MiniLM-L6-v2")

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


@app.post("/accuracy")
async def accuracy(req: AccuracyRequest):
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                LANGUAGETOOL_URL,
                data={"text": req.sentence, "language": "en-US"},
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
