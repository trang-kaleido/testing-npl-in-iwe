from unittest.mock import MagicMock, patch

import httpx
import respx
from fastapi.testclient import TestClient

import main
from main import app, LANGUAGETOOL_URL

client = TestClient(app)

GRAMMAR_MATCH = {
    "matches": [
        {
            "message": "Did you mean 'went'?",
            "offset": 3,
            "length": 2,
            "replacements": [{"value": "went"}],
            "rule": {
                "id": "MORFOLOGIK_RULE_EN_US",
                "category": {"id": "GRAMMAR", "name": "Grammar"},
            },
        }
    ]
}

SPELLING_MATCH = {
    "matches": [
        {
            "message": "Possible spelling mistake found.",
            "offset": 4,
            "length": 5,
            "replacements": [{"value": "world"}],
            "rule": {
                "id": "MORFOLOGIK_RULE_EN_US",
                "category": {"id": "TYPOS", "name": "Possible Typo"},
            },
        }
    ]
}

NO_MATCHES = {"matches": []}


@respx.mock
def test_grammar_error_returns_diagnostic():
    respx.post(LANGUAGETOOL_URL).mock(
        return_value=httpx.Response(200, json=GRAMMAR_MATCH)
    )

    resp = client.post("/accuracy", json={"sentence": "He go to school yesterday."})

    assert resp.status_code == 200
    diagnostics = resp.json()
    assert len(diagnostics) == 1
    d = diagnostics[0]
    assert d["span"] == {"from": 3, "to": 5}
    assert d["category"] == "GRAMMAR"
    assert "went" in d["replacements"]
    assert d["message"] == "Did you mean 'went'?"


@respx.mock
def test_spelling_error_returns_typos_category():
    respx.post(LANGUAGETOOL_URL).mock(
        return_value=httpx.Response(200, json=SPELLING_MATCH)
    )

    resp = client.post("/accuracy", json={"sentence": "The wirld is round."})

    assert resp.status_code == 200
    diagnostics = resp.json()
    assert len(diagnostics) == 1
    assert diagnostics[0]["category"] == "TYPOS"
    assert "world" in diagnostics[0]["replacements"]


@respx.mock
def test_clean_sentence_returns_empty():
    respx.post(LANGUAGETOOL_URL).mock(
        return_value=httpx.Response(200, json=NO_MATCHES)
    )

    resp = client.post("/accuracy", json={"sentence": "He went to school yesterday."})

    assert resp.status_code == 200
    assert resp.json() == []


@respx.mock
def test_languagetool_error_returns_502():
    respx.post(LANGUAGETOOL_URL).mock(
        side_effect=httpx.ConnectError("refused")
    )

    resp = client.post("/accuracy", json={"sentence": "He go home."})

    assert resp.status_code == 502


# ── Closed-class GECToR tagger (ADR 0002) ────────────────────────────────────

def make_token(text, idx):
    t = MagicMock()
    t.text = text
    t.idx = idx
    return t


def tokenize(sentence):
    tokens = []
    idx = 0
    for word in sentence.split(" "):
        tokens.append(make_token(word, idx))
        idx += len(word) + 1
    return tokens


@respx.mock
def test_tagger_surfaces_missing_article_lt_misses():
    respx.post(LANGUAGETOOL_URL).mock(return_value=httpx.Response(200, json=NO_MATCHES))
    sentence = "He went to school"
    tokens = tokenize(sentence)  # He went to school
    tags = ["$KEEP", "$KEEP", "$KEEP", "$APPEND_the"]

    with patch.object(main, "nlp", return_value=tokens), \
         patch.object(main, "_gector_word_tags", return_value=tags):
        resp = client.post("/accuracy", json={"sentence": sentence})

    assert resp.status_code == 200
    diagnostics = resp.json()
    assert len(diagnostics) == 1
    assert diagnostics[0]["category"] == "TAGGER_GRAMMAR"
    assert diagnostics[0]["replacements"] == ["the"]


@respx.mock
def test_tagger_hit_dropped_when_overlapping_lt_match():
    lt_match = {
        "matches": [{
            "message": "Did you mean 'went'?",
            "offset": 3,
            "length": 2,
            "replacements": [{"value": "went"}],
            "rule": {"id": "X", "category": {"id": "GRAMMAR", "name": "Grammar"}},
        }]
    }
    respx.post(LANGUAGETOOL_URL).mock(return_value=httpx.Response(200, json=lt_match))
    sentence = "He go to school"
    tokens = tokenize(sentence)  # He go to school
    tags = ["$KEEP", "$TRANSFORM_VERB_VB_VBD", "$KEEP", "$KEEP"]

    with patch.object(main, "nlp", return_value=tokens), \
         patch.object(main, "process_token", return_value="went"), \
         patch.object(main, "_gector_word_tags", return_value=tags):
        resp = client.post("/accuracy", json={"sentence": sentence})

    diagnostics = resp.json()
    assert len(diagnostics) == 1
    assert diagnostics[0]["category"] == "GRAMMAR"


@respx.mock
def test_lexical_replace_tag_is_filtered_out():
    respx.post(LANGUAGETOOL_URL).mock(return_value=httpx.Response(200, json=NO_MATCHES))
    sentence = "He need book"
    tokens = tokenize(sentence)  # He need book
    tags = ["$KEEP", "$REPLACE_needed", "$KEEP"]

    with patch.object(main, "nlp", return_value=tokens), \
         patch.object(main, "_gector_word_tags", return_value=tags):
        resp = client.post("/accuracy", json={"sentence": sentence})

    assert resp.json() == []
