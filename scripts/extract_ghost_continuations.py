"""Extract validated forced single-continuation prefixes for ghost text (issue #6).

Source: STREUSLE corpus (https://github.com/nert-nlp/streusle), pinned at commit
8ba61fe4f216e7967500a862554a4fff79d25f5d, file `streusle.conllu`.
License: CC BY-SA 4.0 (lexical semantic annotations) — see STREUSLE's LICENSE.txt.
The corpus is hand-annotated Yelp reviews (general conversational English, not
academic register); see docs/testing-log.md for the domain-fit tradeoff this implies.

Method:
1. Take every strong multiword expression STREUSLE tags as a compound preposition
   (MISC field `MWECat=P`), e.g. "according to", "in front of" — these are
   linguist-annotated fixed units, not just frequent n-grams.
2. Split each into (prefix, last word). A prefix only counts as a genuine forced
   continuation if, scanning *every* occurrence of that exact prefix anywhere in
   the corpus (tagged or not), 100% of occurrences are followed by the same word,
   and the prefix occurs at least twice. This rules out cases like "out of" /
   "due to", where the corpus also annotates the prefix word ("out", "due") used
   in unrelated constructions elsewhere — i.e. not actually forced.

Regenerate: python3 scripts/extract_ghost_continuations.py
(downloads the pinned STREUSLE commit's conllu file; requires network access)
"""
import re
import collections
import urllib.request

STREUSLE_COMMIT = "8ba61fe4f216e7967500a862554a4fff79d25f5d"
STREUSLE_URL = (
    f"https://raw.githubusercontent.com/nert-nlp/streusle/{STREUSLE_COMMIT}/streusle.conllu"
)
MIN_OCCURRENCES = 2


def load_sentences(conllu_text):
    sentences = []
    mwe_p = []  # (sentence_index, start_token_index, mwe_len)
    current = []
    sent_idx = -1
    tok_idx = 0
    for line in conllu_text.splitlines():
        if line.startswith("# sent_id"):
            if current:
                sentences.append(current)
            current = []
            sent_idx += 1
            tok_idx = 0
            continue
        if not line.strip() or line.startswith("#"):
            continue
        cols = line.split("\t")
        if len(cols) < 10 or "-" in cols[0] or "." in cols[0]:
            continue
        current.append(cols[1].lower())
        m = re.search(r"MWECat=P\|MWELemma=[^|]*\|MWELen=(\d+)", cols[9])
        if m:
            mwe_p.append((sent_idx, tok_idx, int(m.group(1))))
        tok_idx += 1
    if current:
        sentences.append(current)
    return sentences, mwe_p


def followers(sentences, prefix):
    plen = len(prefix)
    counts = collections.Counter()
    for sent in sentences:
        for i in range(len(sent) - plen):
            if tuple(sent[i : i + plen]) == prefix:
                counts[sent[i + plen]] += 1
    return counts


def extract(conllu_text):
    sentences, mwe_p = load_sentences(conllu_text)
    candidate_prefixes = set()
    for sidx, start, mlen in mwe_p:
        toks = sentences[sidx][start : start + mlen]
        if len(toks) == mlen:
            candidate_prefixes.add(tuple(toks[:-1]))

    results = []
    for prefix in candidate_prefixes:
        counts = followers(sentences, prefix)
        total = sum(counts.values())
        if total < MIN_OCCURRENCES:
            continue
        word, n = counts.most_common(1)[0]
        if n == total:
            results.append((" ".join(prefix), " " + word, total))
    results.sort(key=lambda r: (-r[2], r[0]))
    return results


if __name__ == "__main__":
    with urllib.request.urlopen(STREUSLE_URL) as resp:
        text = resp.read().decode("utf-8")
    for prefix, continuation, n in extract(text):
        print(f"{prefix!r} -> {continuation!r}  (n={n})")
