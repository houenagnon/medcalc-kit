"""Simulating a smaller token budget on existing generations."""
import pytest

import medcalc_kit as mk
from medcalc_kit.evaluate import score_records, truncate_records


class Words:
    """Toy tokenizer: one token per whitespace-separated word."""

    def encode(self, text):
        return text.split()

    def decode(self, ids):
        return " ".join(ids)


class HFLike(Words):
    """Accepts the keyword arguments of a Hugging Face tokenizer."""

    def encode(self, text, add_special_tokens=True):
        return text.split()

    def decode(self, ids, skip_special_tokens=False):
        return " ".join(ids)


ITEMS = mk.ProbeSuite(["A", "E2E"]).build(mk.data.demo())


def record(item_id, n_words, answer):
    text = " ".join(f"w{i}" for i in range(n_words)) + " " + answer      # distinct words: not a loop
    return {"item_id": item_id, "text": text, "n_new_tokens": n_words + 2, "error": None}


@pytest.mark.parametrize("tokenizer", [Words(), HFLike()])
def test_long_answers_are_cut_and_truncated(tokenizer):
    recs = [record("demo:39:1:A", 298, '{"result": 12}'), record("demo:6:1:A", 98, '{"result": 22.857}')]
    cut = truncate_records(recs, ITEMS, {"A": 150}, tokenizer)
    long, short = cut.iloc[0], cut.iloc[1]
    assert long.n_new_tokens == 150 and len(long.text.split()) == 150 and long.truncated
    assert short.text == recs[1]["text"] and short.n_new_tokens == 100
    scores = score_records(cut, ITEMS)
    assert scores.category.tolist() == ["truncated", "well_formed"] and scores.correct.tolist() == [False, True]
    assert score_records(recs, ITEMS).correct.all()                    # the full answers were right


def test_other_probes_untouched_and_larger_budget_refused():
    recs = [record("demo:39:1:E2E", 300, '{"answer": 12}')]
    assert truncate_records(recs, ITEMS, {"A": 150}, Words()).text[0] == recs[0]["text"]
    with pytest.raises(ValueError, match="cannot be simulated"):
        truncate_records(recs, ITEMS, {"E2E": 4096}, Words())
