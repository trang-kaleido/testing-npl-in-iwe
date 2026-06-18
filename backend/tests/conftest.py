"""Module-level mocks for spaCy, sentence-transformers, and numpy.

These must be installed in sys.modules before any test file imports main,
since main.py loads the NLP models at module scope.
"""

import sys
from unittest.mock import MagicMock

# ── numpy mock (functional dot product) ──────────────────────────────────────

class _FakeArray(list):
    pass

numpy_mock = MagicMock()
numpy_mock.dot.side_effect = lambda a, b: float(sum(x * y for x, y in zip(a, b)))
numpy_mock.array.side_effect = lambda x: _FakeArray(x)
sys.modules["numpy"] = numpy_mock

# ── spaCy mock ────────────────────────────────────────────────────────────────

spacy_mock = MagicMock()
# nlp() returns an empty iterable by default; tests override via patch
spacy_mock.load.return_value = MagicMock(return_value=iter([]))
spacy_mock.tokens = MagicMock()
sys.modules["spacy"] = spacy_mock
sys.modules["spacy.tokens"] = spacy_mock.tokens

# ── sentence-transformers mock ────────────────────────────────────────────────

st_mock = MagicMock()
mock_sbert_instance = MagicMock()
# Default: each text gets a unit vector; last entry (seed_destination) also 1.0
mock_sbert_instance.encode.side_effect = (
    lambda texts, normalize_embeddings=False: [[1.0, 0.0]] * len(texts)
)
st_mock.SentenceTransformer.return_value = mock_sbert_instance
sys.modules["sentence_transformers"] = st_mock
