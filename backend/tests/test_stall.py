from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from main import app, _generate_candidates, _COHESION_LINKERS, _VERB_OBJECTS, _WORD_COLLOCATES

client = TestClient(app)

CAR_DEPENDENCE_INIT = {
    "seeded_vocabulary": {
        "individual convenience": "personal comfort and ease for one person",
        "sustainable environment": "a natural environment that can continue to stay healthy in the future",
        "human well-being": "people's health, happiness, and quality of life",
        "prioritize [something]": "give something the highest importance",
        "damage [something]": "cause harm to something",
        "protect [something]": "keep something safe from harm",
    },
    "seed_destination": (
        "Prioritizing unlimited individual convenience in car use acts as a blocking relationship "
        "against a sustainable environment, which ultimately damages human flourishing."
    ),
}


# ── Token helpers ─────────────────────────────────────────────────────────────

def make_token(
    text,
    dep_="",
    pos_="NOUN",
    lemma_=None,
    is_stop=False,
    is_alpha=True,
    is_punct=False,
    is_space=False,
    children=None,
):
    t = MagicMock()
    t.text = text
    t.dep_ = dep_
    t.pos_ = pos_
    t.lemma_ = lemma_ or text.lower()
    t.is_stop = is_stop
    t.is_alpha = is_alpha
    t.is_punct = is_punct
    t.is_space = is_space
    t.children = children or []
    return t


# ── _generate_candidates unit tests ──────────────────────────────────────────

def test_generate_candidates_cohesion_on_short_sentence():
    """Sentence with ≤2 non-punct tokens → cohesion linkers."""
    doc = [make_token("In", dep_="prep", pos_="ADP", lemma_="in", is_stop=True)]
    result = _generate_candidates(doc, {})
    assert result is _COHESION_LINKERS
    assert "Furthermore," in result
    assert "However," in result
    assert "Therefore," in result


def test_generate_candidates_argument_missing():
    """ROOT verb missing dobj → verb-object candidates."""
    verb = make_token("reduce", dep_="ROOT", pos_="VERB", lemma_="reduce")
    subj = make_token("government", dep_="nsubj", pos_="NOUN")
    verb.children = [subj]  # no dobj child

    doc = [subj, verb]
    result = _generate_candidates(doc, {})
    assert result is _VERB_OBJECTS["reduce"]
    assert "emissions" in result
    assert "pollution" in result


def test_generate_candidates_collocation():
    """Last content word in known collocate table → collocate list."""
    subj = make_token("policy", dep_="nsubj", pos_="NOUN")
    verb = make_token("has", dep_="ROOT", pos_="VERB", lemma_="have")
    # "have" is NOT in _VERB_OBJECTS, so argument-missing case skips
    adj = make_token("significant", dep_="amod", pos_="ADJ", lemma_="significant")

    doc = [subj, verb, adj]
    result = _generate_candidates(doc, {})
    assert result is _WORD_COLLOCATES["significant"]
    assert "impact" in result


def test_generate_candidates_lexical_retrieval():
    """No verb-object or collocation match → seeded vocabulary fallback."""
    subj = make_token("problem", dep_="nsubj", pos_="NOUN")
    verb = make_token("affects", dep_="ROOT", pos_="VERB", lemma_="affect")
    # "affect" not in _VERB_OBJECTS or _WORD_COLLOCATES
    verb.children = [subj]

    doc = [subj, verb]
    seeded = {"individual convenience": "...", "sustainable environment": "..."}
    result = _generate_candidates(doc, seeded)
    assert "individual" in result
    assert "sustainable" in result


# ── Full endpoint tests ───────────────────────────────────────────────────────

def _make_mock_nlp(tokens):
    """Return a callable that always yields the given token list."""
    mock_doc = list(tokens)
    return MagicMock(return_value=mock_doc)


def test_stall_cohesion_case_returns_linkers():
    """Short sentence → cohesion linkers in response."""
    short_doc = [make_token("In", dep_="prep", pos_="ADP", lemma_="in", is_stop=True)]
    with patch("main.nlp", _make_mock_nlp(short_doc)):
        resp = client.post(
            "/stall",
            json={"current_sentence": "In", "init_context": CAR_DEPENDENCE_INIT},
        )
    assert resp.status_code == 200
    texts = [s["text"] for s in resp.json()]
    assert "Furthermore," in texts
    assert "However," in texts
    assert "Therefore," in texts


def test_stall_argument_missing_case_returns_verb_objects():
    """Verb with missing dobj → object candidates for that verb."""
    verb = make_token("reduce", dep_="ROOT", pos_="VERB", lemma_="reduce")
    subj = make_token("government", dep_="nsubj", pos_="NOUN")
    verb.children = [subj]

    with patch("main.nlp", _make_mock_nlp([subj, verb])):
        resp = client.post(
            "/stall",
            json={
                "current_sentence": "The government should reduce",
                "init_context": CAR_DEPENDENCE_INIT,
            },
        )
    assert resp.status_code == 200
    texts = [s["text"] for s in resp.json()]
    assert "emissions" in texts
    assert "pollution" in texts


def test_stall_collocation_case_returns_collocates():
    """Last content word has known collocates → collocate candidates."""
    adj = make_token("significant", dep_="amod", pos_="ADJ", lemma_="significant",
                     is_stop=False, is_alpha=True)
    verb = make_token("has", dep_="ROOT", pos_="VERB", lemma_="have")
    subj = make_token("policy", dep_="nsubj", pos_="NOUN")
    verb.children = [subj]

    with patch("main.nlp", _make_mock_nlp([subj, verb, adj])):
        resp = client.post(
            "/stall",
            json={
                "current_sentence": "The policy has a significant",
                "init_context": CAR_DEPENDENCE_INIT,
            },
        )
    assert resp.status_code == 200
    texts = [s["text"] for s in resp.json()]
    assert "impact" in texts


def test_stall_lexical_retrieval_case_returns_vocab_words():
    """No verb-object or collocation match → seeded-vocabulary fallback."""
    subj = make_token("problem", dep_="nsubj", pos_="NOUN")
    verb = make_token("affects", dep_="ROOT", pos_="VERB", lemma_="affect")
    verb.children = [subj]

    with patch("main.nlp", _make_mock_nlp([subj, verb])):
        resp = client.post(
            "/stall",
            json={
                "current_sentence": "The car dependence problem affects",
                "init_context": CAR_DEPENDENCE_INIT,
            },
        )
    assert resp.status_code == 200
    suggestions = resp.json()
    assert len(suggestions) > 0
    texts = [s["text"] for s in suggestions]
    assert any(t in texts for t in ("individual", "sustainable", "human", "prioritize"))


def test_stall_returns_text_and_score_keys():
    """All returned items carry 'text' and 'score' keys."""
    short_doc = [make_token("In", dep_="prep", pos_="ADP", lemma_="in", is_stop=True)]
    with patch("main.nlp", _make_mock_nlp(short_doc)):
        resp = client.post(
            "/stall",
            json={"current_sentence": "In", "init_context": CAR_DEPENDENCE_INIT},
        )
    assert resp.status_code == 200
    for item in resp.json():
        assert "text" in item
        assert "score" in item
